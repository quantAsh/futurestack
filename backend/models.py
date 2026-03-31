from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Float,
    Text,
    Date,
    DateTime,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from backend.database import Base
import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)  # UUID
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)  # For local auth
    name = Column(String)
    avatar = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    is_host = Column(Boolean, default=False)
    wallet_address = Column(String, nullable=True)  # Phase 9: Web3
    reputation_score = Column(Integer, default=0)  # Phase 9: Trust Graph
    is_verified_on_chain = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    # MFA fields
    mfa_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_recovery_codes = Column(JSON, nullable=True)  # Hashed recovery codes

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_wallet_address", "wallet_address"),
        Index("idx_user_created_at", "created_at"),
    )

    listings = relationship("Listing", back_populates="owner")
    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="author_user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, index=True)  # JWT JTI
    user_id = Column(String, ForeignKey("users.id"), index=True)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="refresh_tokens")


class UserSession(Base):
    """Persistent session tracking (SQLite fallback when Redis is unavailable)."""
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, index=True)  # Same as refresh token JTI
    user_id = Column(String, ForeignKey("users.id"), index=True)
    device_info = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="sessions")

    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
    )


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True, index=True)
    owner_id = Column(String, ForeignKey("users.id"))
    name = Column(String, index=True)
    description = Column(Text)
    property_type = Column(String)
    city = Column(String, index=True)
    country = Column(String, index=True)
    price_usd = Column(Float)
    features = Column(JSON)
    images = Column(JSON)
    guest_capacity = Column(Integer)
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    virtual_tour_url = Column(String, nullable=True)  # Phase 9: AR/VR
    ar_model_url = Column(String, nullable=True)  # Phase 9: AR
    hub_id = Column(String, nullable=True)  # Linked to Hub
    
    # Enrichment fields (populated by scraper)
    booking_url = Column(String, nullable=True)  # External booking link
    scraped_amenities = Column(JSON, nullable=True)  # Wifi, Pool, Spa, etc.
    price_range = Column(String, nullable=True)  # "From $2,500/week"
    program_names = Column(JSON, nullable=True)  # Retreat programs
    upcoming_dates = Column(JSON, nullable=True)  # Available dates
    social_links = Column(JSON, nullable=True)  # {Instagram: url, Facebook: url}
    last_enriched_at = Column(DateTime(timezone=True), nullable=True)
    
    # Cultural Experience fields (Quantum Temple inspired)
    culture_keeper_id = Column(String, ForeignKey("culture_keepers.id"), nullable=True)
    community_impact_percent = Column(Float, default=0.1)  # % of booking to community
    cultural_tags = Column(JSON, nullable=True)  # ["balinese", "water_heritage", ...]

    __table_args__ = (
        Index("idx_listing_location", "city", "country"),
        Index("idx_listing_owner", "owner_id"),
        Index("idx_listing_price", "price_usd"),
        # Note: GIN index on JSON features removed due to PostgreSQL compatibility 
    )

    owner = relationship("User", back_populates="listings")
    bookings = relationship("Booking", back_populates="listing")
    reviews = relationship("Review", back_populates="listing")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, index=True)
    listing_id = Column(String, ForeignKey("listings.id"))
    user_id = Column(String, ForeignKey("users.id"))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    total_price_usd = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_booking_user_dates", "user_id", "start_date", "end_date"),
        Index("idx_booking_listing_dates", "listing_id", "start_date", "end_date"),
        Index("idx_booking_created_at", "created_at"),
    )

    listing = relationship("Listing", back_populates="bookings")
    user = relationship("User", back_populates="bookings")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, index=True)
    listing_id = Column(String, ForeignKey("listings.id"))
    author_id = Column(String, ForeignKey("users.id"))
    rating = Column(Integer)
    comment = Column(Text)

    listing = relationship("Listing", back_populates="reviews")
    author_user = relationship("User", back_populates="reviews")


class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    city = Column(String)
    country = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    image = Column(String)
    cost_of_living_index = Column(Integer)
    walkability_score = Column(Integer)
    safety_score = Column(Integer)
    visa_friendliness = Column(String)


class Hub(Base):
    __tablename__ = "hubs"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    mission = Column(Text)
    type = Column(String)  # HubType
    logo = Column(String)
    charter = Column(Text)
    lat = Column(Float)
    lng = Column(Float)
    sustainability_score = Column(Integer, default=50)

    # Simple arrays for brevity in this MVP, could be related tables
    member_ids = Column(JSON, default=[])
    listing_ids = Column(JSON, default=[])
    amenity_ids = Column(JSON, default=[])
    tags = Column(JSON, default=[])


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(String, primary_key=True, index=True)
    type = Column(String)  # Residency or Retreat
    name = Column(String)
    theme = Column(String)
    mission = Column(Text)
    curator_id = Column(String)
    start_date = Column(String)  # Storing as ISO string for simplicity or DateTime
    end_date = Column(String)
    image = Column(String)
    price_usd = Column(Float, nullable=True)
    website = Column(String, nullable=True)
    membership_link = Column(String, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    price_label = Column(String, nullable=True)
    duration_label = Column(String, nullable=True)

    listing_ids = Column(JSON, default=[])
    amenities = Column(JSON, default=[])
    activities = Column(JSON, default=[])
    
    # Creator economy fields
    host_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    revenue_share_rate = Column(Float, default=0.85)  # Host keeps 85%, platform takes 15%
    max_guests = Column(Integer, nullable=True)
    
    # Enrichment fields
    tags = Column(JSON, default=[])
    nomad_score = Column(Integer, default=50)

    host = relationship("User", foreign_keys=[host_id], backref="hosted_experiences")


class CommunityTask(Base):
    __tablename__ = "community_tasks"

    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    status = Column(String)  # To Do, In Progress, Done
    assignee_id = Column(String, nullable=True)
    reward = Column(Integer)
    xp_category = Column(String, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    type = Column(String)  # connection, opportunity, wellbeing, alert
    title = Column(String)
    description = Column(Text)
    read = Column(Boolean, default=False)
    action_type = Column(String, nullable=True)  # book_resource, view_profile, etc.
    action_data = Column(Text, nullable=True)  # JSON string for action details
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="notifications")


# --- PHASE 7 MODELS ---


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True)
    tier = Column(String)  # free, pro, unlimited
    status = Column(String, default="active")  # active, cancelled, expired
    monthly_credits = Column(Integer, default=0)  # nights per month
    used_credits = Column(Integer, default=0)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Stripe integration (Phase 14)
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)

    user = relationship("User", backref=backref("subscription", uselist=False))


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    name = Column(String, index=True)
    category = Column(String)  # design, development, marketing, etc.
    description = Column(Text, nullable=True)
    rate_usd = Column(Float, nullable=True)  # hourly rate, null = free
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="skills")


class SkillRequest(Base):
    __tablename__ = "skill_requests"

    id = Column(String, primary_key=True, index=True)
    requester_id = Column(String, ForeignKey("users.id"), index=True)
    skill_name = Column(String)
    hub_id = Column(String, nullable=True)
    description = Column(Text)
    budget_usd = Column(Float, nullable=True)
    status = Column(String, default="open")  # open, matched, completed, cancelled
    matched_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requester = relationship(
        "User", foreign_keys=[requester_id], backref="skill_requests"
    )


class Journey(Base):
    __tablename__ = "journeys"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    name = Column(String)
    status = Column(String, default="draft")  # draft, planned, booked, completed
    total_budget_usd = Column(Float, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    preferences = Column(Text, nullable=True)  # JSON constraints
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="journeys")
    legs = relationship(
        "JourneyLeg", back_populates="journey", order_by="JourneyLeg.order"
    )


class JourneyLeg(Base):
    __tablename__ = "journey_legs"

    id = Column(String, primary_key=True, index=True)
    journey_id = Column(String, ForeignKey("journeys.id"), index=True)
    hub_id = Column(String, ForeignKey("hubs.id"), nullable=True)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=True)
    city = Column(String)
    country = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    order = Column(Integer)  # sequence in journey
    estimated_cost_usd = Column(Float, nullable=True)
    booking_id = Column(String, nullable=True)  # linked booking when booked

    journey = relationship("Journey", back_populates="legs")


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(String, primary_key=True, index=True)
    listing_id = Column(String, ForeignKey("listings.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    original_price = Column(Float)
    offered_price = Column(Float)
    counter_price = Column(Float, nullable=True)
    status = Column(String, default="pending")  # pending, accepted, rejected, countered
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", backref="negotiations")
    user = relationship("User", backref="negotiations")


# --- PHASE 8 MODELS ---


class SpendingRecord(Base):
    __tablename__ = "spending_records"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    category = Column(
        String
    )  # accommodation, food, transport, coworking, entertainment
    amount_usd = Column(Float)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    date = Column(DateTime, index=True)
    notes = Column(Text, nullable=True)
    booking_id = Column(String, nullable=True)  # Link to booking if applicable
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="spending_records")


class ExperienceBooking(Base):
    __tablename__ = "experience_bookings"

    id = Column(String, primary_key=True, index=True)
    experience_id = Column(String, ForeignKey("experiences.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    booking_date = Column(DateTime)
    num_guests = Column(Integer, default=1)
    total_price_usd = Column(Float)
    status = Column(
        String, default="pending"
    )  # pending, confirmed, completed, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    experience = relationship("Experience", backref="bookings")
    user = relationship("User", backref="experience_bookings")


class HostEarnings(Base):
    __tablename__ = "host_earnings"

    id = Column(String, primary_key=True, index=True)
    host_id = Column(String, ForeignKey("users.id"), index=True)
    source_type = Column(String)  # listing, experience
    source_id = Column(String)  # listing_id or experience_id
    gross_amount_usd = Column(Float)
    platform_fee_usd = Column(Float)  # 15% platform fee
    net_amount_usd = Column(Float)
    status = Column(String, default="pending")  # pending, paid
    payout_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    host = relationship("User", backref="earnings")


# --- PHASE 9 MODELS ---


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(String, primary_key=True, index=True)
    author_id = Column(String, ForeignKey("users.id"), index=True)
    title = Column(String)
    description = Column(Text)
    status = Column(String, default="active")  # active, passed, rejected, executed
    yes_votes = Column(Float, default=0)
    no_votes = Column(Float, default=0)
    end_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    author = relationship("User", backref="proposals")
    votes = relationship("Vote", back_populates="proposal")


class Vote(Base):
    __tablename__ = "votes"

    id = Column(String, primary_key=True, index=True)
    proposal_id = Column(String, ForeignKey("proposals.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    vote_type = Column(String)  # yes, no
    weight = Column(Float, default=1.0)  # Based on reputation
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    proposal = relationship("Proposal", back_populates="votes")
    user = relationship("User", backref="votes")


# --- AGENT PERSISTENCE ---


class AgentJob(Base):
    __tablename__ = "agent_jobs"

    id = Column(String, primary_key=True, index=True)  # UUID
    type = Column(String)  # negotiate, availability, etc.
    url = Column(String)
    goal = Column(Text)
    status = Column(String, default="queued")  # queued, running, completed, failed
    result = Column(Text, nullable=True)  # JSON string
    error = Column(Text, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", backref="agent_jobs")


class AgentMemoryRecord(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    domain = Column(String, index=True)
    key = Column(String, index=True)
    value = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HubInvestment(Base):
    __tablename__ = "hub_investments"

    id = Column(String, primary_key=True, index=True)  # UUID
    hub_id = Column(String, ForeignKey("hubs.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    shares = Column(Float)
    amount_usd = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hub = relationship("Hub", backref="investments")
    user = relationship("User", backref="investments")


class TokenStake(Base):
    """NEST token staking for governance weight and profit sharing."""
    __tablename__ = "token_stakes"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    amount = Column(Float, nullable=False)  # NEST tokens staked
    staked_at = Column(DateTime(timezone=True), server_default=func.now())
    unstaked_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    user = relationship("User", backref="stakes")


class TreasuryAllocation(Base):
    """Track where treasury funds are allocated — profit sharing, grants, buybacks."""
    __tablename__ = "treasury_allocations"

    id = Column(String, primary_key=True, index=True)
    allocation_type = Column(String, nullable=False)  # profit_share, grant, buyback, operational
    amount_usd = Column(Float, nullable=False)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=True)  # For profit_share
    proposal_id = Column(String, ForeignKey("proposals.id"), nullable=True)  # Linked governance vote
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    recipient = relationship("User", backref="treasury_receipts")
    proposal = relationship("Proposal", backref="allocations")


class HubFinancials(Base):
    """Real-time financial data for hub investment opportunities."""
    __tablename__ = "hub_financials"

    id = Column(String, primary_key=True, index=True)
    hub_id = Column(String, ForeignKey("hubs.id"), unique=True, index=True)
    total_valuation_usd = Column(Float, default=1000000)
    total_shares = Column(Float, default=1000)  # Total shares issued
    available_shares = Column(Float, default=500)  # Shares available for purchase
    annual_yield_pct = Column(Float, default=10.0)  # Estimated annual yield
    last_appraisal = Column(DateTime(timezone=True), server_default=func.now())
    investor_discount_pct = Column(Float, default=5.0)  # Booking discount for investors

    hub = relationship("Hub", backref="financials", uselist=False)


class BuybackOrder(Base):
    """DAO-managed buyback pool for investment exit liquidity."""
    __tablename__ = "buyback_orders"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    hub_id = Column(String, ForeignKey("hubs.id"), index=True)
    shares = Column(Float, nullable=False)
    price_per_share_usd = Column(Float, nullable=False)
    total_usd = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, completed, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="buyback_orders")
    hub = relationship("Hub", backref="buyback_orders")


class AgentStep(Base):
    """Detailed log of each step taken by an AI agent."""

    __tablename__ = "agent_steps"

    id = Column(String, primary_key=True, index=True)  # UUID
    job_id = Column(String, ForeignKey("agent_jobs.id"), index=True)
    step_index = Column(Integer)
    action = Column(String)  # click, fill, wait, etc.
    selector = Column(String, nullable=True)
    value = Column(String, nullable=True)
    reasoning = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("AgentJob", backref="steps")


# --- OTA INTEGRATION ---


class OTAProvider(Base):
    """External travel platform providers"""

    __tablename__ = "ota_providers"

    id = Column(String, primary_key=True)  # e.g., "booking_com", "airbnb"
    name = Column(String)  # "Booking.com", "Airbnb", etc.
    type = Column(String)  # "api", "scraper", "affiliate"
    api_endpoint = Column(String, nullable=True)
    commission_rate = Column(Float, default=0.0)  # e.g., 0.15 for 15%
    is_active = Column(Boolean, default=True)
    credentials_encrypted = Column(Text, nullable=True)  # Encrypted API keys

    listings = relationship("ExternalListing", backref="provider")


class ExternalListing(Base):
    """Listings from external OTA providers"""

    __tablename__ = "external_listings"

    id = Column(String, primary_key=True)  # UUID
    provider_id = Column(String, ForeignKey("ota_providers.id"))
    external_id = Column(String)  # Provider's listing ID
    name = Column(String)
    url = Column(String)
    price_per_night = Column(Float)
    currency = Column(String, default="USD")
    location = Column(String)
    rating = Column(Float, nullable=True)
    amenities = Column(JSON, default=[])
    last_synced = Column(DateTime, default=func.now())

    # Cached data
    availability_cache = Column(JSON, nullable=True)
    pricing_cache = Column(JSON, nullable=True)
    images = Column(JSON, default=[])


class OTABooking(Base):
    """Track bookings made through external providers"""

    __tablename__ = "ota_bookings"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id"))
    external_listing_id = Column(String, ForeignKey("external_listings.id"))
    provider_id = Column(String, ForeignKey("ota_providers.id"))

    # Booking details
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    total_price = Column(Float)
    currency = Column(String, default="USD")
    commission_earned = Column(Float, default=0.0)

    # Tracking
    booking_status = Column(
        String, default="pending"
    )  # "pending", "confirmed", "cancelled", "completed"
    external_booking_ref = Column(String, nullable=True)
    payment_status = Column(String, default="pending")  # "pending", "paid", "refunded"

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", backref="ota_bookings")
    listing = relationship("ExternalListing", backref="bookings")
    provider = relationship("OTAProvider")


class AIMetric(Base):
    """Track detailed AI usage and costs"""

    __tablename__ = "ai_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    model = Column(String, index=True)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    duration_ms = Column(Float)
    estimated_cost_usd = Column(Float)
    session_id = Column(String, index=True, nullable=True)
    user_id = Column(String, nullable=True)
    metric_type = Column(String, default="completion")  # completion, error
    error_message = Column(Text, nullable=True)


class AICacheEntry(Base):
    """SQLite-backed AI response cache (fallback when Redis unavailable)."""
    __tablename__ = "ai_cache_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    query_hash = Column(String(16), unique=True, index=True, nullable=False)
    query_preview = Column(String(100), nullable=True)  # First 100 chars for debugging
    response_json = Column(Text, nullable=False)  # JSON-serialized response
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)


# --- PHASE 13 MODELS: Messaging & Applications ---

class ChatThread(Base):
    """A conversation thread between users, optionally linked to a listing."""

    __tablename__ = "chat_threads"

    id = Column(String, primary_key=True, index=True)
    participant_ids = Column(JSON, nullable=False)  # [user_id_1, user_id_2]
    listing_id = Column(String, ForeignKey("listings.id"), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", backref="chat_threads")
    messages = relationship("ChatMessage", back_populates="thread", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """A single message within a chat thread."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, index=True)
    thread_id = Column(String, ForeignKey("chat_threads.id"), index=True, nullable=False)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("ChatThread", back_populates="messages")
    sender = relationship("User", backref="sent_messages")


class HostApplication(Base):
    """Application submitted by a user to become a host or join a hub."""

    __tablename__ = "host_applications"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    hub_id = Column(String, ForeignKey("hubs.id"), nullable=True)
    status = Column(String, default="pending", index=True)  # pending, approved, rejected
    answers = Column(JSON, nullable=True)  # Application form answers
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    applicant = relationship("User", foreign_keys=[user_id], backref="host_applications")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    hub = relationship("Hub", backref="applications")


# --- PHASE 14 MODELS: Push Notifications ---

class PushSubscription(Base):
    """Web Push notification subscription for a user's device."""

    __tablename__ = "push_subscriptions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    endpoint = Column(String, unique=True, nullable=False)
    p256dh_key = Column(String, nullable=False)
    auth_key = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="push_subscriptions")


class NotificationPreferences(Base):
    """User preferences for notification types and delivery."""

    __tablename__ = "notification_preferences"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    
    # Notification type toggles (opt-out)
    email_marketing = Column(Boolean, default=True)
    email_transactional = Column(Boolean, default=True)  # Booking confirmations, etc.
    email_digest = Column(Boolean, default=False)  # Daily/weekly summary
    
    push_bookings = Column(Boolean, default=True)
    push_messages = Column(Boolean, default=True)
    push_community = Column(Boolean, default=True)  # Hub events, member updates
    push_ai_insights = Column(Boolean, default=True)  # AI-generated recommendations
    
    # Digest settings
    digest_frequency = Column(String, default="weekly")  # daily, weekly, never
    digest_day = Column(Integer, default=1)  # 0=Sunday, 1=Monday, etc.
    digest_hour = Column(Integer, default=9)  # Hour in UTC
    
    # Quiet hours (no push notifications)
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(Integer, default=22)  # 10 PM
    quiet_hours_end = Column(Integer, default=8)  # 8 AM
    timezone = Column(String, default="UTC")
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", backref="notification_preferences")


# --- SERVICE AND EVENTS MODELS ---

class Service(Base):
    """A service offered by a hub."""

    __tablename__ = "services"

    id = Column(String, primary_key=True, index=True)
    hub_id = Column(String, ForeignKey("hubs.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, default=0)
    category = Column(String, nullable=True)  # transport, workspace, amenity, food
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hub = relationship("Hub", backref="services")

class CommunityEvent(Base):
    """A community event at a hub."""

    __tablename__ = "community_events"

    id = Column(String, primary_key=True, index=True)
    hub_id = Column(String, ForeignKey("hubs.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    date = Column(DateTime(timezone=True), nullable=False)
    location = Column(String, nullable=True)
    capacity = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hub = relationship("Hub", backref="events")


class EscalationRequest(Base):
    """
    Tracks conversations that require human intervention.
    Created when AI concierge escalates complex/sensitive issues.
    """

    __tablename__ = "escalation_requests"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    session_id = Column(String, index=True, nullable=False)  # AI conversation session
    query = Column(Text, nullable=False)  # Original user query
    ai_context = Column(JSON, nullable=True)  # Conversation history for context
    reason = Column(String, nullable=False)  # Why escalated (from AI)
    priority = Column(String, default="medium")  # low, medium, high
    status = Column(String, default="pending")  # pending, assigned, resolved, expired
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True)  # Admin user
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id], backref="escalation_requests")
    assignee = relationship("User", foreign_keys=[assigned_to])

    __table_args__ = (
        Index("idx_escalation_status", "status"),
        Index("idx_escalation_priority", "priority"),
        Index("idx_escalation_created", "created_at"),
    )


class Network(Base):
    """
    Co-living network/partnership for cross-hub memberships.
    """

    __tablename__ = "networks"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    hub_ids = Column(JSON, default=[])  # Partner hubs in this network
    member_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NetworkMembership(Base):
    """
    User membership in a co-living network.
    """

    __tablename__ = "network_memberships"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    network_id = Column(String, ForeignKey("networks.id"), index=True, nullable=False)
    status = Column(String, default="active")  # active, expired, cancelled
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="network_memberships")
    network = relationship("Network", backref="members")


class MembershipTier(Base):
    """
    Subscription tier definition.
    """

    __tablename__ = "membership_tiers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Free, Explorer, Nomad, Elite
    price_monthly = Column(Float, default=0)
    price_yearly = Column(Float, nullable=True)
    stripe_price_id = Column(String, nullable=True)  # Stripe Price ID
    features = Column(JSON, default=[])
    max_bookings_per_month = Column(Integer, nullable=True)
    discount_percent = Column(Float, default=0)
    priority_support = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WalletTransaction(Base):
    """
    Web3 wallet transaction history.
    Tracks payments, rewards, and staking.
    """

    __tablename__ = "wallet_transactions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    tx_hash = Column(String, nullable=True)  # Blockchain transaction hash
    type = Column(String, nullable=False)  # payment, reward, stake, unstake, refund
    amount = Column(Float, nullable=False)
    currency = Column(String, default="ETH")  # ETH, USDC, NOMAD
    status = Column(String, default="pending")  # pending, confirmed, failed
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="wallet_transactions")
    booking = relationship("Booking", backref="wallet_transactions")

    __table_args__ = (
        Index("idx_wallet_user_id", "user_id"),
        Index("idx_wallet_created", "created_at"),
    )


class AIUsage(Base):
    """
    Per-request AI usage tracking for cost metering.
    """

    __tablename__ = "ai_usage"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)
    model = Column(String, nullable=False)  # gemini-2.0-flash, gpt-4o, etc.
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0)  # Estimated cost
    duration_ms = Column(Float, nullable=True)
    tool_calls = Column(Integer, default=0)
    cached = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="ai_usage")

    __table_args__ = (
        Index("idx_ai_usage_user_id", "user_id"),
        Index("idx_ai_usage_created", "created_at"),
    )


class SoulBoundToken(Base):
    """Achievement badges awarded to users."""

    __tablename__ = "soul_bound_tokens"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    category = Column(String, default="achievement")
    metadata_ = Column(JSON, nullable=True)
    awarded_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="soul_bound_tokens")


class ContributionPathway(Base):
    """Gamification pathways for user progression."""

    __tablename__ = "contribution_pathways"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=True)
    rewards = Column(JSON, nullable=True)
    icon = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class UserPathwayProgress(Base):
    """User's progress in a pathway."""

    __tablename__ = "user_pathway_progress"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    pathway_id = Column(String, ForeignKey("contribution_pathways.id"), index=True)
    progress_percent = Column(Float, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="pathway_progress")
    pathway = relationship("ContributionPathway", backref="user_progress")


class WaitlistEntry(Base):
    """Waitlist for launches."""

    __tablename__ = "waitlist_entries"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    waitlist_type = Column(String, nullable=False)
    position = Column(Integer, nullable=True)
    invited = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="waitlist_entries")


class Campaign(Base):
    """Marketing campaigns."""

    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    campaign_type = Column(String, default="referral")
    code = Column(String, unique=True, nullable=True)
    discount_percent = Column(Float, default=0)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Immutable audit log for admin actions."""

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    actor_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    actor_email = Column(String, nullable=True)  # Denormalized for quick lookups
    actor_ip = Column(String, nullable=True)  # IP address of the actor
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    before_state = Column(JSON, nullable=True)  # State before change
    after_state = Column(JSON, nullable=True)  # State after change
    changes = Column(JSON, nullable=True)  # Calculated diff
    extra_data = Column(JSON, nullable=True)  # Additional metadata
    ip_address = Column(String, nullable=True)  # Deprecated, use actor_ip
    success = Column(String, nullable=True)  # "true" or "false"
    error_message = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    actor = relationship("User", backref="audit_logs")


# ============================================
# CULTURAL EXPERIENCES & NOMAD PASSPORT
# Quantum Temple Inspired - Regenerative Travel
# ============================================

class CultureKeeper(Base):
    """A verified local host who preserves cultural traditions."""
    __tablename__ = "culture_keepers"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String, nullable=False)
    bio = Column(Text, nullable=True)
    culture = Column(String, nullable=True)  # e.g., "Balinese", "Maori"
    region = Column(String, nullable=True)  # e.g., "Ubud, Bali"
    traditions = Column(JSON, nullable=True)  # ["water ceremonies", "wood carving"]
    photo_url = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    impact_total_usd = Column(Float, default=0.0)  # Total USD contributed to community
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="culture_keeper_profile")
    experiences = relationship("CulturalExperience", back_populates="keeper")


class CulturalExperience(Base):
    """A cultural experience offered by a Culture Keeper."""
    __tablename__ = "cultural_experiences"

    id = Column(String, primary_key=True, index=True)
    keeper_id = Column(String, ForeignKey("culture_keepers.id"), nullable=False)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=True)  # Optional tie to a listing
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    experience_type = Column(String, default="tradition")  # ceremony, workshop, tradition, craft
    duration_hours = Column(Float, default=2.0)
    max_participants = Column(Integer, default=10)
    price_usd = Column(Float, default=0.0)  # 0 = included in stay
    community_impact_percent = Column(Float, default=0.4)  # 40% to community
    
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    keeper = relationship("CultureKeeper", back_populates="experiences")
    listing = relationship("Listing", backref="cultural_experiences")


class NomadPassport(Base):
    """Tracks a user's cultural journey and achievements."""
    __tablename__ = "nomad_passports"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    
    experiences_completed = Column(Integer, default=0)
    badges = Column(JSON, default=list)  # ["water_ceremony", "craft_apprentice", ...]
    impact_contributed_usd = Column(Float, default=0.0)  # Total USD user has contributed
    passport_level = Column(String, default="explorer")  # explorer, pilgrim, guardian
    
    # Stamp tracking
    cultures_visited = Column(JSON, default=list)  # ["Balinese", "Maori", ...]
    regions_explored = Column(JSON, default=list)  # ["Bali", "New Zealand", ...]
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="nomad_passport")


class PassportStamp(Base):
    """Individual stamp in a Nomad Passport for completed experiences."""
    __tablename__ = "passport_stamps"

    id = Column(String, primary_key=True, index=True)
    passport_id = Column(String, ForeignKey("nomad_passports.id"), nullable=False)
    experience_id = Column(String, ForeignKey("cultural_experiences.id"), nullable=False)
    
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    impact_usd = Column(Float, default=0.0)  # USD contributed via this experience
    notes = Column(Text, nullable=True)  # Personal reflection/memory

    passport = relationship("NomadPassport", backref="stamps")
    experience = relationship("CulturalExperience", backref="stamps")


# ============================================
# AI USAGE METRICS
# Cost tracking and token metering
# ============================================

class AIUsageMetrics(Base):
    """Tracks AI API usage for cost analysis and quotas."""
    __tablename__ = "ai_usage_metrics"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    # Request metadata
    endpoint = Column(String, nullable=False)  # e.g., "concierge", "negotiations"
    model = Column(String, nullable=True)  # e.g., "gpt-4o", "gemini-pro"
    provider = Column(String, nullable=True)  # "openai", "google", "anthropic"
    
    # Token counts
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Cost tracking (in USD cents for precision)
    cost_cents = Column(Integer, default=0)
    
    # Timing
    latency_ms = Column(Integer, nullable=True)
    
    # Request details
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_ai_metrics_user", "user_id"),
        Index("idx_ai_metrics_endpoint", "endpoint"),
        Index("idx_ai_metrics_created", "created_at"),
    )

    user = relationship("User", backref="ai_usage_metrics")


# ============================================
# CO-LIVING NETWORKS & PARTNERSHIPS
# ============================================

class CoLivingNetwork(Base):
    """A network of co-living spaces and partnerships."""
    __tablename__ = "coliving_networks"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    partnership_type = Column(String, default="affiliate")  # affiliate, partner, premium
    regions = Column(JSON, nullable=True)  # ["Europe", "Southeast Asia", ...]
    benefits = Column(JSON, nullable=True)  # ["10% discount", "Priority booking", ...]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Use backref instead of relationship to avoid conflict with existing NetworkMembership
    # For now, query memberships separately via coliving_network_id if needed


# ============================================
# EVENTS & SERVICES (NEW)
# ============================================

class Event(Base):
    """Local events that affect pricing (festivals, conferences, holidays)."""
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String, default="conference")  # conference, festival, meetup, holiday
    location = Column(String, nullable=False, index=True)
    start_date = Column(DateTime(timezone=True), nullable=False, index=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    price_impact_percent = Column(Float, default=0.0)  # How much it affects local pricing
    tags = Column(JSON, default=[])
    source_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_event_location", "location"),
        Index("idx_event_dates", "start_date", "end_date"),
    )


class MarketplaceService(Base):
    """Marketplace services offered by community members (freelance/consulting)."""
    __tablename__ = "marketplace_services"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, default="consulting")  # consulting, design, development, local, wellness
    price_usd = Column(Float, nullable=False)
    price_type = Column(String, default="hourly")  # hourly, fixed, negotiable
    availability = Column(String, nullable=True)
    location = Column(String, nullable=True)
    remote = Column(Boolean, default=True)
    tags = Column(JSON, default=[])
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="marketplace_services")

    __table_args__ = (
        Index("idx_marketplace_service_user", "user_id"),
        Index("idx_marketplace_service_category", "category"),
    )


# Note: Campaign model already exists at line 914 with:
# - campaign_type, code, discount_percent, is_active, usage_count
# To add launch/budget/target tracking, enhance that existing model


# ============================================================================
# WOW Features: Quick Wins
# ============================================================================


class CityLivingCost(Base):
    """Cost of living data for cities - used for comparison calculator."""
    __tablename__ = "city_living_costs"

    id = Column(String, primary_key=True, index=True)
    city = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False, index=True)
    country_code = Column(String(3), nullable=True)
    
    # Monthly costs in USD
    rent_studio = Column(Float, nullable=True)  # Studio apartment
    rent_1br = Column(Float, nullable=True)  # 1-bedroom apartment
    coworking = Column(Float, nullable=True)  # Coworking space
    meal_cheap = Column(Float, nullable=True)  # Cheap meal
    meal_mid = Column(Float, nullable=True)  # Mid-range restaurant
    coffee = Column(Float, nullable=True)
    groceries = Column(Float, nullable=True)  # Monthly groceries
    transport = Column(Float, nullable=True)  # Monthly transport
    utilities = Column(Float, nullable=True)  # Monthly utilities
    internet = Column(Float, nullable=True)  # Dedicated internet
    gym = Column(Float, nullable=True)  # Gym membership
    
    # Quality scores (1-10)
    wifi_quality = Column(Float, nullable=True)
    safety_score = Column(Float, nullable=True)
    weather_score = Column(Float, nullable=True)
    nightlife_score = Column(Float, nullable=True)
    outdoor_score = Column(Float, nullable=True)
    english_level = Column(Float, nullable=True)
    
    # Nomad-specific
    nomad_score = Column(Float, nullable=True)  # Overall nomad-friendliness
    visa_type = Column(String, nullable=True)  # tourist, dnv, schengen
    visa_duration_days = Column(Integer, nullable=True)
    timezone = Column(String, nullable=True)
    
    # Metadata
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String, default="manual")  # manual, numbeo, nomadlist

    __table_args__ = (
        Index("idx_city_cost_city", "city"),
        Index("idx_city_cost_country", "country"),
    )



# ============================================================================
# WOW Features: Phase 2 - Live Nomad Map
# ============================================================================

class NomadLocation(Base):
    """Track nomad locations for the live map feature."""
    __tablename__ = "nomad_locations"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True, unique=True)
    
    # Location data
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    city = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True, index=True)
    country_code = Column(String(3), nullable=True)
    
    # Privacy controls
    visibility = Column(String, default="connections")  # public, connections, private
    blur_radius_km = Column(Float, default=5.0)  # Blur precise location
    ghost_mode = Column(Boolean, default=False)  # Hide completely
    show_city_only = Column(Boolean, default=True)  # Only show city, not exact location
    
    # Status
    status = Column(String, nullable=True)  # "Working from cafe", "Exploring", etc.
    available_for_meetup = Column(Boolean, default=False)
    
    # Travel info
    arrival_date = Column(DateTime(timezone=True), nullable=True)
    planned_departure = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref=backref("location", uselist=False))

    __table_args__ = (
        Index("idx_nomad_location_user", "user_id"),
        Index("idx_nomad_location_city", "city"),
        Index("idx_nomad_location_coords", "latitude", "longitude"),
        Index("idx_nomad_location_visibility", "visibility"),
    )


class NomadConnection(Base):
    """Track connections between nomads for visibility controls."""
    __tablename__ = "nomad_connections"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    connected_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="pending")  # pending, accepted, blocked
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], backref="connections_sent")
    connected_user = relationship("User", foreign_keys=[connected_user_id], backref="connections_received")

    __table_args__ = (
        Index("idx_connection_user", "user_id"),
        Index("idx_connection_connected", "connected_user_id"),
    )


# ============================================================================
# WOW Features: Phase 2 - Visa Wizard
# ============================================================================

class VisaRequirement(Base):
    """Visa requirements between passport countries and destinations."""
    __tablename__ = "visa_requirements"

    id = Column(String, primary_key=True, index=True)
    
    # Passport holder's country
    passport_country = Column(String, nullable=False, index=True)
    passport_country_code = Column(String(3), nullable=False, index=True)
    
    # Destination country
    destination_country = Column(String, nullable=False, index=True)
    destination_country_code = Column(String(3), nullable=False, index=True)
    
    # Visa type and duration
    visa_type = Column(String, nullable=False)  # visa_free, visa_on_arrival, e_visa, visa_required
    duration_days = Column(Integer, nullable=True)  # Max stay without visa
    
    # Digital nomad visa info
    dnv_available = Column(Boolean, default=False)  # Digital Nomad Visa available
    dnv_duration_months = Column(Integer, nullable=True)
    dnv_min_income_usd = Column(Float, nullable=True)  # Monthly income requirement
    dnv_cost_usd = Column(Float, nullable=True)  # Visa cost
    
    # Zone info
    is_schengen = Column(Boolean, default=False)
    is_eu = Column(Boolean, default=False)
    
    # Additional info
    notes = Column(Text, nullable=True)
    application_url = Column(String, nullable=True)
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_visa_passport", "passport_country_code"),
        Index("idx_visa_destination", "destination_country_code"),
        Index("idx_visa_type", "visa_type"),
    )


class SchengenStay(Base):
    """Track user's Schengen zone stays for 90/180 day rule."""
    __tablename__ = "schengen_stays"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Stay details
    country_code = Column(String(3), nullable=False)
    entry_date = Column(DateTime(timezone=True), nullable=False)
    exit_date = Column(DateTime(timezone=True), nullable=True)  # Null if still there
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="schengen_stays")

    __table_args__ = (
        Index("idx_schengen_user", "user_id"),
        Index("idx_schengen_dates", "entry_date", "exit_date"),
    )


# ============================================================================
# WOW Features: Phase 2 - Social Matching
# ============================================================================

class NomadProfile(Base):
    """Extended nomad profile for social matching."""
    __tablename__ = "nomad_profiles"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Basic info
    bio = Column(Text, nullable=True)
    profession = Column(String, nullable=True)
    company = Column(String, nullable=True)
    
    # Interests (stored as JSON array)
    interests = Column(JSON, default=[])  # ["coding", "surfing", "coffee"]
    skills = Column(JSON, default=[])  # ["python", "design", "marketing"]
    languages = Column(JSON, default=[])  # [{"code": "en", "level": "native"}]
    
    # Work style
    work_style = Column(String, default="hybrid")  # remote, hybrid, flexible
    timezone_preference = Column(String, nullable=True)  # GMT+1, PST, etc.
    work_hours = Column(String, nullable=True)  # "9am-5pm EST"
    
    # Social preferences
    looking_for = Column(JSON, default=[])  # ["coworking", "coffee", "hiking", "coliving"]
    open_to_meetups = Column(Boolean, default=True)
    open_to_coliving = Column(Boolean, default=False)
    open_to_coworking = Column(Boolean, default=True)
    
    # Travel style
    travel_pace = Column(String, default="moderate")  # slow, moderate, fast
    budget_level = Column(String, default="moderate")  # budget, moderate, comfortable, luxury
    
    # Timestamps
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref=backref("nomad_profile", uselist=False))

    __table_args__ = (
        Index("idx_nomad_profile_user", "user_id"),
    )


class TravelPlan(Base):
    """User's upcoming travel plans for overlap detection."""
    __tablename__ = "travel_plans"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Location
    city = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False)
    country_code = Column(String(3), nullable=True)
    
    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)  # Null = flexible
    is_flexible = Column(Boolean, default=False)
    
    # Visibility
    visibility = Column(String, default="connections")  # public, connections, private
    
    # Status
    status = Column(String, default="planned")  # planned, confirmed, completed, cancelled
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="travel_plans")

    __table_args__ = (
        Index("idx_travel_plan_user", "user_id"),
        Index("idx_travel_plan_city", "city"),
        Index("idx_travel_plan_dates", "start_date", "end_date"),
    )


# ============================================================================
# WOW Features: Phase 3 - AI Trip Planner
# ============================================================================

class TripItinerary(Base):
    """AI-generated multi-city trip itinerary."""
    __tablename__ = "trip_itineraries"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Trip details
    name = Column(String, nullable=False)  # "European Summer 2026"
    description = Column(Text, nullable=True)
    
    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    total_days = Column(Integer, nullable=False)
    
    # Budget
    budget_usd = Column(Float, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    
    # Passport for visa calculation
    passport_country_code = Column(String(3), nullable=True)
    
    # Preferences (JSON)
    preferences = Column(JSON, default={})  # pace, focus, accommodation_type, etc.
    
    # Status
    status = Column(String, default="draft")  # draft, planned, booked, completed
    
    # AI metadata
    ai_suggestions = Column(JSON, default=[])  # AI-generated tips
    optimization_score = Column(Float, nullable=True)  # Route efficiency 0-100
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="trip_itineraries")
    stops = relationship("TripStop", back_populates="itinerary", order_by="TripStop.order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_trip_user", "user_id"),
        Index("idx_trip_dates", "start_date", "end_date"),
    )


class TripStop(Base):
    """Individual stop in a trip itinerary."""
    __tablename__ = "trip_stops"

    id = Column(String, primary_key=True, index=True)
    itinerary_id = Column(String, ForeignKey("trip_itineraries.id"), nullable=False, index=True)
    
    # Order in trip
    order = Column(Integer, nullable=False)
    
    # Location
    city = Column(String, nullable=False)
    country = Column(String, nullable=False)
    country_code = Column(String(3), nullable=True)
    
    # Dates
    arrival_date = Column(DateTime(timezone=True), nullable=False)
    departure_date = Column(DateTime(timezone=True), nullable=False)
    nights = Column(Integer, nullable=False)
    
    # Accommodation (optional link to listing)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=True)
    accommodation_cost = Column(Float, nullable=True)
    
    # Transport
    transport_from_previous = Column(String, nullable=True)  # flight, train, bus, car
    transport_cost = Column(Float, nullable=True)
    transport_duration_hours = Column(Float, nullable=True)
    
    # Living costs (estimated)
    daily_living_cost = Column(Float, nullable=True)
    
    # Visa info
    visa_required = Column(Boolean, default=False)
    visa_type = Column(String, nullable=True)  # visa_free, visa_on_arrival, etc.
    
    # Notes and activities
    notes = Column(Text, nullable=True)
    activities = Column(JSON, default=[])  # ["visit museum", "try local food"]
    
    # Weather/climate
    avg_temp_celsius = Column(Float, nullable=True)
    weather_note = Column(String, nullable=True)  # "rainy season"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    itinerary = relationship("TripItinerary", back_populates="stops")
    listing = relationship("Listing", backref="trip_stops")

    __table_args__ = (
        Index("idx_stop_itinerary", "itinerary_id"),
    )


# ============================================================================
# WOW Features: Phase 3 - Virtual Co-Working
# ============================================================================

class CoWorkingRoom(Base):
    """Virtual co-working room for focused work sessions."""
    __tablename__ = "coworking_rooms"

    id = Column(String, primary_key=True, index=True)
    
    # Room details
    name = Column(String, nullable=False)  # "Deep Work Den", "Chill Cafe Vibes"
    description = Column(Text, nullable=True)
    theme = Column(String, default="focus")  # focus, creative, social, quiet
    
    # Host
    host_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Capacity
    max_participants = Column(Integer, default=10)
    
    # Video integration
    video_provider = Column(String, default="daily")  # daily, jitsi, whereby
    video_room_url = Column(String, nullable=True)
    video_room_id = Column(String, nullable=True)
    
    # Pomodoro settings
    pomodoro_enabled = Column(Boolean, default=True)
    work_minutes = Column(Integer, default=25)
    break_minutes = Column(Integer, default=5)
    long_break_minutes = Column(Integer, default=15)
    sessions_before_long_break = Column(Integer, default=4)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=True)
    current_session_start = Column(DateTime(timezone=True), nullable=True)
    current_pomodoro_cycle = Column(Integer, default=0)
    current_pomodoro_state = Column(String, default="idle")  # idle, work, break, long_break
    
    # Schedule (for recurring rooms)
    schedule = Column(JSON, nullable=True)  # {"days": ["mon", "wed"], "start_time": "09:00", "timezone": "UTC"}
    
    # Music/ambience
    ambient_sound = Column(String, nullable=True)  # "cafe", "rain", "lofi", "nature"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    host = relationship("User", backref="hosted_coworking_rooms")

    __table_args__ = (
        Index("idx_cowork_host", "host_id"),
        Index("idx_cowork_active", "is_active", "is_public"),
    )


class CoWorkingSession(Base):
    """User participation in a co-working room."""
    __tablename__ = "coworking_sessions"

    id = Column(String, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("coworking_rooms.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Session timing
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)
    
    # Pomodoro tracking
    pomodoros_completed = Column(Integer, default=0)
    total_focus_minutes = Column(Integer, default=0)
    
    # User status
    status = Column(String, default="active")  # active, away, do_not_disturb
    current_task = Column(String, nullable=True)  # "Working on API docs"
    
    # Mic/camera
    mic_enabled = Column(Boolean, default=False)
    camera_enabled = Column(Boolean, default=False)

    room = relationship("CoWorkingRoom", backref="sessions")
    user = relationship("User", backref="coworking_sessions")

    __table_args__ = (
        Index("idx_session_room", "room_id"),
        Index("idx_session_user", "user_id"),
    )


# ============================================================================
# WOW Features: Phase 3 - "Do It For Me" Autonomous Booking
# ============================================================================

class AutonomousBookingRequest(Base):
    """User request for autonomous end-to-end booking."""
    __tablename__ = "autonomous_booking_requests"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Request details
    request_type = Column(String, nullable=False)  # accommodation, flight, full_trip
    
    # Preferences (JSON)
    preferences = Column(JSON, nullable=False)  # Destination, dates, budget, requirements
    # Example: {
    #   "destination": "Lisbon",
    #   "check_in": "2026-03-01",
    #   "check_out": "2026-03-15",
    #   "budget_usd": 1500,
    #   "requirements": ["wifi", "kitchen", "quiet area"],
    #   "flexibility": "2_days",
    #   "payment_authorized": true
    # }
    
    # Budget
    max_budget_usd = Column(Float, nullable=False)
    authorized_payment_usd = Column(Float, nullable=True)  # Pre-authorized amount
    
    # Status
    status = Column(String, default="pending")  # pending, searching, negotiating, awaiting_approval, booking, completed, failed, cancelled
    current_step = Column(String, nullable=True)  # Human-readable current action
    progress_percent = Column(Integer, default=0)  # 0-100
    
    # Results
    found_options = Column(JSON, default=[])  # List of options found
    selected_option = Column(JSON, nullable=True)  # The option being booked
    booking_confirmation = Column(JSON, nullable=True)  # Final booking details
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    user = relationship("User", backref="autonomous_bookings")

    __table_args__ = (
        Index("idx_auto_booking_user", "user_id"),
        Index("idx_auto_booking_status", "status"),
    )


class AutonomousBookingStep(Base):
    """Individual step in an autonomous booking process."""
    __tablename__ = "autonomous_booking_steps"

    id = Column(String, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("autonomous_booking_requests.id"), nullable=False, index=True)
    
    # Step details
    step_number = Column(Integer, nullable=False)
    action = Column(String, nullable=False)  # search_listings, check_availability, compare_prices, negotiate, book
    description = Column(String, nullable=False)  # Human-readable description
    
    # Status
    status = Column(String, default="pending")  # pending, running, completed, failed, skipped
    
    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Error
    error_message = Column(Text, nullable=True)

    request = relationship("AutonomousBookingRequest", backref="steps")

    __table_args__ = (
        Index("idx_step_request", "request_id"),
    )


# ============================================================================
# WOW Features: Price Drop Alerts
# ============================================================================

class PriceAlert(Base):
    """User-created price alert for a listing or search."""
    __tablename__ = "price_alerts"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Alert type
    alert_type = Column(String, nullable=False)  # listing, search, city
    
    # Target (one of these will be set)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=True, index=True)
    search_criteria = Column(JSON, nullable=True)  # For search-based alerts
    city = Column(String, nullable=True)  # For city-wide alerts
    
    # Price threshold
    target_price = Column(Float, nullable=True)  # Alert if below this
    drop_percent = Column(Float, nullable=True)  # Alert if drops by this %
    original_price = Column(Float, nullable=True)  # Price when alert was created
    
    # Alert settings
    is_active = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=True)
    notify_push = Column(Boolean, default=True)
    
    # Check-in/out preferences
    check_in_date = Column(Date, nullable=True)
    check_out_date = Column(Date, nullable=True)
    
    # Alert history
    last_checked = Column(DateTime(timezone=True), nullable=True)
    last_notified = Column(DateTime(timezone=True), nullable=True)
    times_triggered = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="price_alerts")
    listing = relationship("Listing", backref="price_alerts")

    __table_args__ = (
        Index("idx_price_alert_user", "user_id"),
        Index("idx_price_alert_listing", "listing_id"),
        Index("idx_price_alert_active", "is_active"),
    )


class PriceHistory(Base):
    """Historical price data for listings."""
    __tablename__ = "price_history"

    id = Column(String, primary_key=True, index=True)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=False, index=True)
    
    # Price data
    price = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    price_type = Column(String, default="nightly")  # nightly, weekly, monthly
    
    # Optional date range (for availability-based pricing)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", backref="price_history")

    __table_args__ = (
        Index("idx_price_history_listing", "listing_id"),
        Index("idx_price_history_date", "recorded_at"),
    )


# ============================================================================
# WOW Features: Host Video Tours
# ============================================================================

class VideoTour(Base):
    """Video tour of a listing."""
    __tablename__ = "video_tours"

    id = Column(String, primary_key=True, index=True)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=False, index=True)
    host_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Video details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tour_type = Column(String, default="recorded")  # recorded, live, scheduled
    
    # Media
    video_url = Column(String, nullable=True)  # For recorded tours
    thumbnail_url = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Live/scheduled tour
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    meeting_url = Column(String, nullable=True)  # Zoom/Meet link
    max_attendees = Column(Integer, default=10)
    
    # AI summary
    ai_summary = Column(Text, nullable=True)
    ai_highlights = Column(JSON, nullable=True)  # ["Great natural light", "Modern kitchen"]
    
    # Status
    status = Column(String, default="processing")  # processing, ready, live, completed
    views_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", backref="video_tours")
    host = relationship("User", backref="hosted_video_tours")

    __table_args__ = (
        Index("idx_video_tour_listing", "listing_id"),
        Index("idx_video_tour_host", "host_id"),
    )


class TourRegistration(Base):
    """User registration for a live video tour."""
    __tablename__ = "tour_registrations"

    id = Column(String, primary_key=True, index=True)
    tour_id = Column(String, ForeignKey("video_tours.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    attended = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)

    tour = relationship("VideoTour", backref="registrations")
    user = relationship("User", backref="tour_registrations")

    __table_args__ = (
        Index("idx_tour_reg_tour", "tour_id"),
        Index("idx_tour_reg_user", "user_id"),
    )









