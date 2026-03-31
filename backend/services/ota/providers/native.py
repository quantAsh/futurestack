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


class NativeProvider(BaseOTAProvider):
    """
    Provider for native NomadNest listings.
    """

    def __init__(self, provider_id: str, config: Dict[str, Any], db: Session):
        super().__init__(provider_id, config)
        self.db = db

    @property
    def name(self) -> str:
        return "NomadNest"

    @property
    def type(self) -> str:
        return "native"

    async def search(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int = 1,
        currency: str = "USD",
    ) -> List[OTASearchResult]:
        """
        Search internal Listing database.
        """
        # Split multi-word queries into individual terms for broader matching
        # e.g., "Bali wellness" -> match "Bali" OR "wellness"
        terms = [t.strip() for t in location.split() if t.strip()]

        if terms:
            term_filters = []
            for term in terms:
                term_filters.append(
                    or_(
                        models.Listing.city.ilike(f"%{term}%"),
                        models.Listing.country.ilike(f"%{term}%"),
                        models.Listing.name.ilike(f"%{term}%"),
                        models.Listing.description.ilike(f"%{term}%"),
                    )
                )
            query = self.db.query(models.Listing).filter(or_(*term_filters))
        else:
            query = self.db.query(models.Listing)

        listings = query.limit(20).all()

        # Fallback: if no location match, show featured listings
        if not listings:
            listings = self.db.query(models.Listing).limit(10).all()

        results = []
        for l in listings:
            # Basic price calculation (price per month / 30 * nights) or just per night if we had it
            # Listing model has price_usd (monthly usually for nomadnest).
            price_per_night = (l.price_usd or 1000) / 30.0
            days = (check_out - check_in).days
            total_price = price_per_night * days

            results.append(
                OTASearchResult(
                    id=l.id,
                    provider_id=self.provider_id,
                    name=l.name or "Unknown Listing",
                    url=f"/listings/{l.id}",
                    price_per_night=round(price_per_night, 2),
                    total_price=round(total_price, 2),
                    currency=currency,
                    rating=None,
                    reviews_count=0,
                    location=f"{l.city}, {l.country}",
                    image_url=l.images[0] if l.images else None,
                    amenities=l.features or [],
                    latitude=None,
                    longitude=None,
                )
            )

        return results

    async def get_details(self, listing_id: str) -> Optional[Dict[str, Any]]:
        l = (
            self.db.query(models.Listing)
            .filter(models.Listing.id == listing_id)
            .first()
        )
        if not l:
            return None
        return {
            "id": l.id,
            "name": l.name,
            "description": l.description,
            "amenities": l.features or [],
            "images": l.images or [],
            "url": f"/listings/{l.id}",
        }

    async def check_availability(
        self, listing_id: str, check_in: date, check_out: date
    ) -> bool:
        # Check for overlapping bookings in Booking table
        # This requires the existing Booking model
        overlapping = (
            self.db.query(models.Booking)
            .filter(
                models.Booking.listing_id == listing_id,
                models.Booking.end_date >= check_in,
                models.Booking.start_date <= check_out,
            )
            .count()
        )
        return overlapping == 0

    async def create_booking(
        self,
        listing_id: str,
        user_details: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> OTABookingResult:
        # For native bookings, we might redirect to the internal booking flow
        # or create it directly. For OTA interface uniformity, let's say we return success
        # and let the calling service handle the actual DB insertion via existing services.

        # In a real OTA, this would call the internal BookingService.
        return OTABookingResult(
            booking_id="native_pending",
            status="pending",
            redirect_url=f"/bookings/checkout?listing_id={listing_id}&start={start_date}&end={end_date}",
        )
