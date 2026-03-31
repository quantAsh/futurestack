from pydantic import BaseModel, EmailStr, HttpUrl, Field, ConfigDict
from typing import List, Optional, Generic, TypeVar, Dict
from datetime import datetime

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int



# --- SUBSCRIPTION ---
class SubscriptionBase(BaseModel):
    tier: str
    status: str
    monthly_credits: int
    used_credits: int
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False

class Subscription(SubscriptionBase):
    id: str
    user_id: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# --- USER ---
class UserBase(BaseModel):
    email: Optional[EmailStr] = Field(None, example="nomad@example.com")
    name: str = Field(..., min_length=2, max_length=100, example="Alex Nomad")
    avatar: Optional[str] = Field(None, example="https://example.com/avatar.jpg")
    bio: Optional[str] = Field(None, example="Digital nomad exploring the world")
    is_host: bool = False


class UserCreate(UserBase):
    """Schema for creating a new user account."""
    password: str = Field(..., min_length=8, example="SecureP@ss123")


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar: Optional[str] = None
    bio: Optional[str] = None
    is_host: Optional[bool] = None


class User(UserBase):
    id: str
    is_admin: bool
    created_at: datetime
    subscription: Optional[Subscription] = None

    model_config = ConfigDict(from_attributes=True)


# --- LISTING ---
class ListingBase(BaseModel):
    """Base schema for co-living listings."""
    name: str = Field(..., min_length=1, max_length=200, example="Sunny Loft in Lisbon")
    description: Optional[str] = Field(None, example="A beautiful loft with ocean views, perfect for remote work.")
    property_type: Optional[str] = Field(None, example="coliving")
    city: Optional[str] = Field(None, example="Lisbon")
    country: Optional[str] = Field(None, example="Portugal")
    price_usd: Optional[float] = Field(None, ge=0, example=1200.00)
    features: List[str] = Field(default=[], example=["WiFi", "Coworking", "Kitchen"])
    images: List[str] = Field(default=[], example=["https://example.com/listing1.jpg"])


class ListingCreate(ListingBase):
    pass


class ListingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    property_type: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    price_usd: Optional[float] = Field(None, gt=0)
    features: Optional[List[str]] = None
    images: Optional[List[HttpUrl]] = None


class Listing(ListingBase):
    id: str
    owner_id: Optional[str] = None
    hub_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- BOOKING ---
class BookingBase(BaseModel):
    """Base schema for booking reservations."""
    listing_id: str = Field(..., example="listing-uuid-123")
    start_date: datetime = Field(..., example="2026-02-01T14:00:00Z")
    end_date: datetime = Field(..., example="2026-02-15T11:00:00Z")

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days


class BookingCreate(BookingBase):
    """Schema for creating a new booking. Requires listing_id and date range."""


class Booking(BookingBase):
    id: str
    user_id: str
    created_at: datetime
    status: str = "pending"

    model_config = ConfigDict(from_attributes=True)


class BookingCancellation(BaseModel):
    """Response schema for booking cancellation with refund details."""
    booking_id: str
    status: str = "cancelled"
    refund_amount: float = Field(..., description="Refund amount in USD")
    refund_percentage: int = Field(..., description="Percentage of total refunded (0, 50, or 100)")
    refund_type: str = Field(..., description="'full', 'partial', or 'none'")
    refund_id: Optional[str] = Field(None, description="Stripe Refund ID if processed")
    refund_status: str = Field(..., description="'succeeded', 'pending', 'failed', or 'skipped'")
    message: str


# --- TOKEN ---
class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    sub: str | None = None  # subject (email)
    exp: int | None = None
    jti: str | None = None  # JWT ID for revocation


# --- NEIGHBORHOOD ---
class NeighborhoodBase(BaseModel):
    name: str
    city: str
    country: str
    lat: float
    lng: float
    image: str
    cost_of_living_index: int = Field(..., ge=1, le=100)
    walkability_score: int = Field(..., ge=1, le=100)
    safety_score: int = Field(..., ge=1, le=100)
    visa_friendliness: str


class NeighborhoodCreate(NeighborhoodBase):
    pass


class Neighborhood(NeighborhoodBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


# --- HUB ---
class HubBase(BaseModel):
    name: Optional[str] = None
    mission: Optional[str] = None
    type: Optional[str] = None
    logo: Optional[str] = None
    charter: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    sustainability_score: Optional[int] = Field(50, ge=1, le=100)
    member_ids: List[str] = []
    amenity_ids: List[str] = []
    member_ids: List[str] = []
    amenity_ids: List[str] = []
    listing_ids: List[str] = []
    tags: List[str] = []


class HubCreate(HubBase):
    pass


class Hub(HubBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


# --- EXPERIENCE ---
class ExperienceBase(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    theme: Optional[str] = None
    mission: Optional[str] = None
    curator_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None
    price_usd: Optional[float] = None
    website: Optional[str] = None
    membership_link: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    price_label: Optional[str] = None
    duration_label: Optional[str] = None
    listing_ids: List[str] = []
    amenities: List[str] = []
    activities: List[str] = []


class ExperienceCreate(ExperienceBase):
    pass


class Experience(ExperienceBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


# --- COMMUNITY TASK ---
class CommunityTaskBase(BaseModel):
    title: str
    description: str
    status: str
    assignee_id: Optional[str] = None
    reward: int = Field(..., gt=0)
    xp_category: Optional[str] = None


class CommunityTaskCreate(CommunityTaskBase):
    pass


class CommunityTask(CommunityTaskBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


# --- NOTIFICATION ---
class NotificationBase(BaseModel):
    type: str  # connection, opportunity, wellbeing, alert
    title: str
    description: str
    action_type: Optional[str] = None
    action_data: Optional[str] = None


class NotificationCreate(NotificationBase):
    user_id: str


class Notification(NotificationBase):
    id: str
    user_id: str
    read: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- REVIEW ---
class ReviewBase(BaseModel):
    listing_id: str
    author_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str


class ReviewCreate(ReviewBase):
    pass


class Review(ReviewBase):
    id: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- HEALTH ---
class HealthCheck(BaseModel):
    status: str
    version: str


class DependencyCheck(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Optional[str] = None
    providers: Optional[Dict[str, bool]] = None


class ReadinessCheck(BaseModel):
    status: str
    version: str
    checks: Dict[str, DependencyCheck]


# --- MFA ---
class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MFALoginVerifyRequest(BaseModel):
    temp_token: str
    code: str = Field(..., min_length=6, max_length=6)


class MFARequiredResponse(BaseModel):
    mfa_required: bool = True
    temp_token: str
    message: str = "Two-factor authentication code required"


class MFARecoveryRequest(BaseModel):
    temp_token: str
    recovery_code: str = Field(..., min_length=10, max_length=20)


class MFAEnableResponse(BaseModel):
    status: str
    recovery_codes: List[str]
    message: str


# --- SERVICES ---
class ServiceResponse(BaseModel):
    id: str
    hub_id: str
    name: str
    description: Optional[str] = None
    price: float = 0
    category: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- EVENTS ---
class EventResponse(BaseModel):
    id: str
    hub_id: str
    name: str
    description: Optional[str] = None
    date: datetime
    location: Optional[str] = None
    capacity: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

