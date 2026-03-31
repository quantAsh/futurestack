from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import date
from pydantic import BaseModel


class OTASearchResult(BaseModel):
    id: str  # Unique ID within the provider
    provider_id: str
    name: str
    url: str
    price_per_night: float
    total_price: float
    currency: str = "USD"
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    location: str
    image_url: Optional[str] = None
    amenities: List[str] = []

    # Metadata for determining if it's the "same" listing
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class OTABookingResult(BaseModel):
    booking_id: str
    status: str  # "confirmed", "pending", "failed"
    confirmation_code: Optional[str] = None
    redirect_url: Optional[str] = None
    error_message: Optional[str] = None


class BaseOTAProvider(ABC):
    """
    Abstract base class for all OTA providers (Booking.com, Airbnb, Native, etc.)
    """

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        self.provider_id = provider_id
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Friendly name of the provider"""
        pass

    @property
    @abstractmethod
    def type(self) -> str:
        """Type of provider: 'api', 'scraper', 'affiliate', 'native'"""
        pass

    @property
    def commission_rate(self) -> float:
        """Commission rate (0.0 to 1.0)"""
        return self.config.get("commission_rate", 0.0)

    @abstractmethod
    async def search(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int = 1,
        currency: str = "USD",
    ) -> List[OTASearchResult]:
        """
        Search for accommodations.
        Should return a list of standardized results.
        """
        pass

    @abstractmethod
    async def get_details(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for a specific listing.
        """
        pass

    @abstractmethod
    async def check_availability(
        self, listing_id: str, check_in: date, check_out: date
    ) -> bool:
        """
        Check if a listing is available for the given dates.
        """
        pass

    async def create_booking(
        self,
        listing_id: str,
        user_details: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> OTABookingResult:
        """
        Create a booking.
        For affiliate/scraper providers, this might just return a redirect URL.
        """
        # Default implementation for manual/affiliate links
        details = await self.get_details(listing_id)
        if not details:
            return OTABookingResult(
                booking_id="", status="failed", error_message="Listing not found"
            )

        return OTABookingResult(
            booking_id="", status="redirect", redirect_url=details.get("url")
        )
