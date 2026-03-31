"""
OTA Provider that uses the Rust ota_search binary for fast,
multi-provider accommodation scraping (Booking.com, Hostelworld, Airbnb).
Falls back to Playwright if the Rust binary isn't built.
"""
from typing import List, Dict, Any, Optional
from datetime import date
from pathlib import Path
import asyncio
import json
import re
import structlog

from backend.services.ota.providers.base import BaseOTAProvider, OTASearchResult

logger = structlog.get_logger(__name__)

# Path to the Rust binary (release build)
RUST_BINARY = Path(__file__).resolve().parents[4] / "rust-crawler" / "target" / "release" / "ota_search"


def _parse_price(text: str) -> Optional[float]:
    """Extract numeric price from text like 'US$142' or '$1,200'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,]", "", text)
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


class BrowserProvider(BaseOTAProvider):
    """
    Multi-provider OTA search (Booking.com + Hostelworld + Airbnb).
    Strategy:
      1. Try Rust binary (ota_search) — fast, multi-provider, no browser needed
      2. Fall back to Playwright headless browser scraping
    """

    @property
    def name(self) -> str:
        return "Booking.com"

    @property
    def type(self) -> str:
        return "scraper"

    async def _search_rust(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int,
        currency: str,
    ) -> Optional[List[OTASearchResult]]:
        """Try to use the Rust ota_search binary (multi-provider)."""
        if not RUST_BINARY.exists():
            logger.debug("rust_binary_not_found", path=str(RUST_BINARY))
            return None

        cmd = [
            str(RUST_BINARY),
            "--location", location,
            "--checkin", check_in.isoformat(),
            "--checkout", check_out.isoformat(),
            "--guests", str(guests),
            "--currency", currency,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)

            if proc.returncode != 0:
                logger.warning("rust_scrape_failed", stderr=stderr.decode()[:200])
                return None

            raw = json.loads(stdout.decode())
            # ota_search returns SearchResults { listings: [...], ranked: [...], ... }
            listings = raw.get("listings", raw) if isinstance(raw, dict) else raw
            results = []
            for item in listings:
                loc = item.get("location", {})
                loc_str = loc.get("address", location) if isinstance(loc, dict) else str(loc)
                results.append(OTASearchResult(
                    id=item["id"],
                    provider_id=self.provider_id,
                    name=item["name"],
                    url=item.get("url", ""),
                    price_per_night=item.get("price_per_night"),
                    total_price=item.get("total_price"),
                    currency=item.get("currency", "USD"),
                    location=loc_str,
                    image_url=item.get("image_url", ""),
                    rating=item.get("rating"),
                    reviews_count=item.get("reviews_count", 0),
                ))

            logger.info("rust_scrape_success", location=location, count=len(results))
            return results

        except asyncio.TimeoutError:
            logger.warning("rust_scrape_timeout", location=location)
            return None
        except Exception as e:
            logger.warning("rust_scrape_error", error=str(e))
            return None

    async def _search_playwright(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int,
        currency: str,
    ) -> List[OTASearchResult]:
        """Fallback: use Playwright headless browser."""
        results = []
        days = (check_out - check_in).days or 1

        url = (
            f"https://www.booking.com/searchresults.html"
            f"?ss={location}"
            f"&checkin={check_in.isoformat()}"
            f"&checkout={check_out.isoformat()}"
            f"&group_adults={guests}"
            f"&no_rooms=1&selected_currency=USD"
        )

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1440, "height": 900},
                    locale="en-US",
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                # Dismiss cookie banner
                try:
                    accept_btn = page.locator("button#onetrust-accept-btn-handler")
                    if await accept_btn.is_visible(timeout=3000):
                        await accept_btn.click()
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

                try:
                    await page.wait_for_selector('[data-testid="property-card"]', timeout=10000)
                except Exception:
                    pass

                raw_results = await page.evaluate("""
                    () => {
                        const cards = document.querySelectorAll('[data-testid="property-card"]');
                        return Array.from(cards).slice(0, 8).map((card, idx) => {
                            const nameEl = card.querySelector('[data-testid="title"]');
                            const priceEl = card.querySelector('[data-testid="price-and-discounted-price"]')
                                         || card.querySelector('.prco-valign-middle-helper');
                            const ratingEl = card.querySelector('[data-testid="review-score"] > div:first-child');
                            const imgEl = card.querySelector('img[data-testid="image"]') || card.querySelector('img');
                            const addrEl = card.querySelector('[data-testid="address"]');
                            const linkEl = card.querySelector('a[data-testid="title-link"]') || card.querySelector('a');
                            return {
                                name: nameEl ? nameEl.textContent.trim() : '',
                                priceText: priceEl ? priceEl.textContent.trim() : '',
                                rating: ratingEl ? ratingEl.textContent.trim() : '',
                                image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : '',
                                address: addrEl ? addrEl.textContent.trim() : '',
                                link: linkEl ? linkEl.href : '',
                                idx
                            };
                        });
                    }
                """)

                for item in raw_results:
                    if not item.get("name"):
                        continue
                    price = _parse_price(item.get("priceText", ""))
                    rating_val = None
                    try:
                        m = re.search(r"[\d.]+", item.get("rating", "") or "")
                        if m:
                            rating_val = float(m.group())
                    except (ValueError, AttributeError):
                        pass

                    results.append(OTASearchResult(
                        id=f"booking-{item['idx']}",
                        provider_id=self.provider_id,
                        name=item["name"],
                        url=item.get("link", url),
                        price_per_night=round(price / days, 2) if price else None,
                        total_price=price,
                        currency="USD",
                        location=item.get("address", location),
                        image_url=item.get("image", ""),
                        rating=rating_val,
                        reviews_count=0,
                    ))

                await browser.close()

        except ImportError:
            logger.warning("playwright_not_installed")
        except Exception as e:
            logger.error("playwright_search_failed", error=str(e))

        return results

    async def search(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int = 1,
        currency: str = "USD",
    ) -> List[OTASearchResult]:
        """
        Search Booking.com — try Rust binary first, fall back to Playwright.
        """
        logger.info("booking_search_start", location=location)

        # Strategy 1: Rust binary (fast, no browser)
        rust_results = await self._search_rust(location, check_in, check_out, guests, currency)
        if rust_results is not None:
            return rust_results

        # Strategy 2: Playwright headless browser (slower, more reliable)
        logger.info("booking_falling_back_to_playwright", location=location)
        return await self._search_playwright(location, check_in, check_out, guests, currency)

    async def get_details(self, listing_id: str) -> Optional[Dict[str, Any]]:
        return {"provider": "Booking.com", "note": "Visit Booking.com for full details"}

    async def check_availability(
        self, listing_id: str, check_in: date, check_out: date
    ) -> bool:
        return True
