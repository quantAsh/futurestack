"""
Data Ingestion Script: CSV -> PostgreSQL
Syncs enriched_retreats.csv into the Experience table.

Run with: docker-compose exec backend python backend/scripts/ingest_csv.py
"""
import sys
import os
import csv
import re
from uuid import uuid4

# Add parent to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models
from backend.services import enrichment

# Path to the scraped data
CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "enriched_retreats.csv"
)


def parse_price(price_str: str) -> float | None:
    """Extract first numeric price from string."""
    if not price_str:
        return None
    # Find numbers with optional commas and decimals
    matches = re.findall(r"[\d,]+\.?\d*", price_str.replace(",", ""))
    for match in matches:
        try:
            price = float(match)
            if 100 < price < 50000:  # Reasonable retreat price range
                return price
        except ValueError:
            continue
    return None


def parse_amenities(amenity_str: str) -> list[str]:
    """Parse comma-separated amenities."""
    if not amenity_str:
        return []
    return [a.strip() for a in amenity_str.split(",") if a.strip()]


def get_first_image(image_str: str) -> str | None:
    """Get first valid image URL."""
    if not image_str:
        return None
    urls = [u.strip() for u in image_str.split(",")]
    for url in urls:
        if url.startswith("http") and (
            "jpg" in url or "png" in url or "webp" in url or "jpeg" in url
        ):
            return url
    return urls[0] if urls else None


def get_first_booking_link(link_str: str) -> str | None:
    """Get first booking link."""
    if not link_str:
        return None
    links = [l.strip() for l in link_str.split(",")]
    return links[0] if links else None


def ingest_csv():
    """Main ingestion function."""
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV not found at: {CSV_PATH}")
        return

    db = SessionLocal()
    ingested = 0
    skipped = 0

    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Skip if no place name
                place_name = row.get("place_name", "").strip()
                if not place_name:
                    skipped += 1
                    continue

                # Generate deterministic ID from URL
                source_url = row.get("source_url", "")
                exp_id = f"exp-{hash(source_url) % 100000}"

                # Check if already exists
                existing = (
                    db.query(models.Experience)
                    .filter(models.Experience.id == exp_id)
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.name = place_name
                    existing.theme = row.get("page_title", "")[:200]
                    existing.mission = row.get("description_long", "")[:1000]
                    existing.image = get_first_image(row.get("image_urls", ""))
                    existing.price_usd = parse_price(row.get("program_prices", ""))
                    existing.website = get_first_booking_link(
                        row.get("booking_links", "")
                    )
                    existing.amenities = parse_amenities(row.get("amenities", ""))
                else:
                    # Create new experience
                    # Create new experience
                    
                    # Enrichment
                    website = get_first_booking_link(row.get("booking_links", ""))
                    image = get_first_image(row.get("image_urls", ""))
                    is_alive = True
                    
                    # Optional: Check liveness (Can be slow, so maybe only if expensive flag set)
                    # if website:
                    #     is_alive = enrichment.check_liveness(website)
                    
                    amenities_list = parse_amenities(row.get("amenities", ""))
                    desc = row.get("description_long", "")
                    
                    tags = enrichment.generate_vibe_tags(desc, amenities_list)
                    score = enrichment.calculate_nomad_score(
                        parse_price(row.get("program_prices", "")),
                        None, # Mock internet speed for now
                        amenities_list
                    )

                    experience = models.Experience(
                        id=exp_id,
                        type="retreat",
                        name=place_name,
                        theme=row.get("page_title", "")[:200],
                        mission=desc[:1000],
                        curator_id="system",
                        start_date=None,
                        end_date=None,
                        image=image,
                        price_usd=parse_price(row.get("program_prices", "")),
                        website=website,
                        membership_link=row.get("source_url", ""),
                        city=None,
                        country=None,
                        price_label=None,
                        duration_label=None,
                        amenities=amenities_list,
                        activities=[],
                        tags=tags,
                        nomad_score=score
                    )
                    db.add(experience)

                ingested += 1

        db.commit()
        print(
            f"✅ Ingestion complete: {ingested} experiences synced, {skipped} skipped."
        )

    except Exception as e:
        print(f"❌ Error during ingestion: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Starting CSV ingestion...")
    ingest_csv()
