"""
FutureStack — Civic Infrastructure Models.
Domain models for infrastructure projects, solution marketplace, RFPs, and impact tracking.
"""
from sqlalchemy import Column, String, Float, Integer, Text, Boolean, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
import enum


# ─── Infrastructure Verticals ─────────────────────────────────────────────

class InfraVertical(str, enum.Enum):
    WATER = "water"
    ENERGY = "energy"
    AI_INFRA = "ai_infrastructure"
    FOOD = "food_security"
    EDUCATION = "education"
    TRANSPORT = "transport"


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    FUNDING = "funding"
    PROCUREMENT = "procurement"
    CONSTRUCTION = "construction"
    OPERATIONAL = "operational"
    DECOMMISSIONED = "decommissioned"


# ─── Infrastructure Projects ──────────────────────────────────────────────

class InfrastructureProject(Base):
    """A community infrastructure project (solar farm, water co-op, school, etc.)."""
    __tablename__ = "infrastructure_projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    vertical = Column(String, nullable=False, index=True)  # InfraVertical value
    status = Column(String, default="planning", index=True)  # ProjectStatus value

    # Community & Location
    community_id = Column(String, ForeignKey("hubs.id"), nullable=True, index=True)
    location_name = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    region = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True, index=True)

    # Funding
    target_budget_usd = Column(Float, default=0)
    funded_usd = Column(Float, default=0)
    funding_deadline = Column(DateTime(timezone=True), nullable=True)

    # Impact
    beneficiary_count = Column(Integer, default=0)
    impact_targets = Column(JSON, default={})  # {"liters_per_day": 10000, "kwh_daily": 500}

    # Timeline
    start_date = Column(DateTime(timezone=True), nullable=True)
    estimated_completion = Column(DateTime(timezone=True), nullable=True)
    actual_completion = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    project_lead_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project_lead = relationship("User", foreign_keys=[project_lead_id], backref="led_projects")
    solutions = relationship("ProjectSolution", back_populates="project")
    rfps = relationship("CommunityRFP", back_populates="project")
    metrics = relationship("ImpactMetric", back_populates="project")


# ─── Solution Marketplace ─────────────────────────────────────────────────

class SolutionListing(Base):
    """A vendor's infrastructure product or service listed in the marketplace."""
    __tablename__ = "solution_listings"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("users.id"), index=True)
    vertical = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    solution_type = Column(String, default="product")  # product, service, consulting, training
    category = Column(String, nullable=True, index=True)  # solar_panel, water_filter, etc.

    # Pricing
    price_usd = Column(Float, nullable=True)
    price_model = Column(String, default="fixed")  # fixed, per_unit, subscription, quote_required

    # Specs
    specifications = Column(JSON, default={})  # capacity_kw, efficiency_pct, lifespan_years, etc.
    certifications = Column(JSON, default=[])  # ISO, CE, UL, etc.
    regions_available = Column(JSON, default=[])  # ["africa", "southeast_asia", ...]

    # Ratings
    impact_rating = Column(Float, nullable=True)  # 0-5 community rating
    review_count = Column(Integer, default=0)
    verified = Column(Boolean, default=False)  # FutureStack verified vendor

    # Media
    image_url = Column(String, nullable=True)
    documentation_url = Column(String, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    vendor = relationship("User", backref="solution_listings")


class ProjectSolution(Base):
    """Links a solution to a project (what's being used/deployed)."""
    __tablename__ = "project_solutions"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("infrastructure_projects.id"), index=True)
    solution_id = Column(String, ForeignKey("solution_listings.id"), index=True)
    quantity = Column(Integer, default=1)
    total_cost_usd = Column(Float, nullable=True)
    status = Column(String, default="planned")  # planned, ordered, delivered, installed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("InfrastructureProject", back_populates="solutions")
    solution = relationship("SolutionListing", backref="deployments")


# ─── Request for Proposals (RFP) ──────────────────────────────────────────

class CommunityRFP(Base):
    """A community's request for proposals on an infrastructure need."""
    __tablename__ = "community_rfps"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("infrastructure_projects.id"), index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    vertical = Column(String, nullable=False, index=True)

    # Requirements
    requirements = Column(JSON, default={})  # {"min_capacity_kw": 100, "warranty_years": 5}
    budget_min_usd = Column(Float, nullable=True)
    budget_max_usd = Column(Float, nullable=True)

    # Timeline
    submission_deadline = Column(DateTime(timezone=True), nullable=True)
    decision_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="open", index=True)  # open, evaluating, awarded, closed, cancelled

    # Creator
    created_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("InfrastructureProject", back_populates="rfps")
    proposals = relationship("VendorProposal", back_populates="rfp")
    created_by = relationship("User", backref="rfps_created")


class VendorProposal(Base):
    """A vendor's response to a community RFP."""
    __tablename__ = "vendor_proposals"

    id = Column(String, primary_key=True, index=True)
    rfp_id = Column(String, ForeignKey("community_rfps.id"), index=True)
    vendor_id = Column(String, ForeignKey("users.id"), index=True)
    solution_id = Column(String, ForeignKey("solution_listings.id"), nullable=True)

    # Proposal details
    price_usd = Column(Float, nullable=False)
    timeline_days = Column(Integer, nullable=True)
    proposal_details = Column(JSON, default={})  # warranty, support, methodology, etc.
    cover_letter = Column(Text, nullable=True)

    # Status
    status = Column(String, default="submitted", index=True)  # submitted, shortlisted, accepted, rejected
    score = Column(Float, nullable=True)  # Evaluation score 0-100

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    rfp = relationship("CommunityRFP", back_populates="proposals")
    vendor = relationship("User", backref="vendor_proposals")
    solution = relationship("SolutionListing", backref="proposals")


# ─── Impact Metrics ───────────────────────────────────────────────────────

class ImpactMetric(Base):
    """Real-time impact measurement for operational infrastructure projects."""
    __tablename__ = "impact_metrics"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("infrastructure_projects.id"), index=True)

    # Measurement
    metric_type = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)  # kwh, liters, kg, count, pct, etc.

    # Context
    period = Column(String, default="daily")  # hourly, daily, weekly, monthly, cumulative
    source = Column(String, default="manual")  # manual, iot, estimated, api
    notes = Column(Text, nullable=True)

    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("InfrastructureProject", back_populates="metrics")


# ─── Metric Type Reference ────────────────────────────────────────────────
# Water:     liters_purified, households_served, water_quality_score, distribution_km
# Energy:    kwh_generated, co2_offset_kg, uptime_pct, peak_capacity_kw
# AI:        compute_tflops, models_served, api_calls, latency_ms
# Food:      calories_produced, acres_farmed, waste_reduced_kg, meals_served
# Education: students_enrolled, completion_rate_pct, courses_offered, certifications_issued
# Transport: trips_daily, km_covered, emissions_saved_kg, passengers_served
