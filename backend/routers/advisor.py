"""
Infrastructure AI Advisor Router — Expose AI planning tools as API endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


# --- Schemas ---

class NeedsAssessmentRequest(BaseModel):
    population: int
    vertical: str
    location: str = "rural community"
    current_situation: str = "no existing infrastructure"


class CostEstimateRequest(BaseModel):
    vertical: str
    scope: dict  # e.g. {"solar_per_kw": 500, "battery_per_kwh": 200}


class CompareRequest(BaseModel):
    solutions: list  # list of solution descriptions
    criteria: List[str] = ["price", "reliability", "scalability", "local_support"]


class ForecastRequest(BaseModel):
    vertical: str
    specifications: dict = {}
    population: int = 1000


class FundingRequest(BaseModel):
    vertical: str
    budget_usd: float
    region: str = "Africa"


# --- Endpoints ---

@router.post("/advisor/assess")
async def assess_needs(req: NeedsAssessmentRequest):
    """
    AI-powered infrastructure needs assessment.
    'Our village has 500 people, no clean water' → sizing, cost, timeline.
    """
    from backend.services.infra_advisor import assess_infrastructure_needs
    result = await assess_infrastructure_needs(req.model_dump())
    return result


@router.post("/advisor/estimate")
async def estimate_cost(req: CostEstimateRequest):
    """
    Itemized cost estimate for an infrastructure project.
    Uses FutureStack benchmark data for deterministic pricing.
    """
    from backend.services.infra_advisor import estimate_project_cost
    result = await estimate_project_cost(req.model_dump())
    return result


@router.post("/advisor/compare")
async def compare(req: CompareRequest):
    """
    AI-powered side-by-side solution comparison with scores and recommendation.
    """
    from backend.services.infra_advisor import compare_solutions
    result = await compare_solutions(req.model_dump())
    return result


@router.post("/advisor/forecast")
async def forecast(req: ForecastRequest):
    """
    Forecast project impact metrics over 1, 3, and 5 years.
    Includes ROI, payback period, and social impact score.
    """
    from backend.services.infra_advisor import forecast_impact
    result = await forecast_impact(req.model_dump())
    return result


@router.post("/advisor/funding")
async def find_funding_sources(req: FundingRequest):
    """
    Match project to funding sources: DAO treasury, micro-investments, grants, impact bonds.
    """
    from backend.services.infra_advisor import find_funding
    result = await find_funding(req.model_dump())
    return result


# --- Seed endpoint ---

@router.post("/seed")
def seed_civic_data():
    """Seed the database with demo infrastructure projects and solutions."""
    from backend.database import get_db_context
    from backend.seed_civic import seed_civic_data as do_seed

    with get_db_context() as db:
        result = do_seed(db)
    return result
