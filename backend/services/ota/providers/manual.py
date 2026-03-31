from typing import List, Optional, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.services.ota.providers.base import (
    BaseOTAProvider,
    OTASearchResult,
    OTABookingResult,
)
from backend import models


class ManualProvider(BaseOTAProvider):
    """
    Provider for manually curated listings (e.g., from retreats.csv).
    These usually have direct booking links.
    """

    def __init__(self, provider_id: str, config: Dict[str, Any], db: Session):
        super().__init__(provider_id, config)
        self.db = db

    @property
    def name(self) -> str:
        return "Partner Sites"

    @property
    def type(self) -> str:
        return "affiliate"

    async def search(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int = 1,
        currency: str = "USD",
    ) -> List[OTASearchResult]:
        """
        Search external listings that we've imported manually.
        """
        # Search ExternalListing table where provider_id matches this provider
        query = self.db.query(models.ExternalListing).filter(
            models.ExternalListing.provider_id == self.provider_id,
            models.ExternalListing.location.ilike(f"%{location}%"),
        )

        listings = query.all()

        results = []
        for l in listings:
            # Calculate total estimate
            days = (check_out - check_in).days
            total_price = l.price_per_night * days

            results.append(
                OTASearchResult(
                    id=l.id,
                    provider_id=self.provider_id,
                    name=l.name,
                    url=l.url,  # Direct external link
                    price_per_night=l.price_per_night,
                    total_price=round(total_price, 2),
                    currency=l.currency,
                    rating=l.rating,
                    location=l.location,
                    image_url=l.images[0] if l.images else None,
                    amenities=l.amenities or [],
                )
            )

        return results

    async def get_details(self, listing_id: str) -> Optional[Dict[str, Any]]:
        l = (
            self.db.query(models.ExternalListing)
            .filter(models.ExternalListing.id == listing_id)
            .first()
        )
        if not l:
            return None
        return {
            "id": l.id,
            "name": l.name,
            "url": l.url,
            "amenities": l.amenities,
            "images": l.images,
        }

    async def check_availability(
        self, listing_id: str, check_in: date, check_out: date
    ) -> bool:
        # We can't easily check availability for strict manual links without a scraper
        # So we assume available for now, or use a cached availability field if we scraped it
        return True

    async def create_booking(
        self,
        listing_id: str,
        user_details: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> OTABookingResult:
        details = await self.get_details(listing_id)
        if not details:
            return OTABookingResult(
                booking_id="", status="failed", error_message="Listing not found"
            )

        # Return redirect URL for the user to book directly
        return OTABookingResult(
            booking_id="", status="redirect", redirect_url=details.get("url")
        )
