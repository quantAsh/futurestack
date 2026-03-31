"""
Growth Router — API endpoints for the enhanced Growth Co-Pilot panel.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from backend.services.growth_metrics import (
    get_growth_snapshot,
    get_funnel_data,
    get_cohort_retention,
    get_churn_risk_users,
    get_growth_experiments,
    create_experiment,
    get_attribution_report,
    get_ab_tests,
    create_ab_test,
    calculate_significance,
)

router = APIRouter()


# ── Snapshot ──
@router.get("/snapshot")
def snapshot() -> Dict[str, Any]:
    """Real-time growth KPIs."""
    return get_growth_snapshot()


# ── Funnel ──
@router.get("/funnel")
def funnel(period: str = "30d") -> Dict[str, Any]:
    """Acquisition funnel with stage conversion rates."""
    return get_funnel_data(period)


# ── Cohort Retention ──
@router.get("/cohort")
def cohort(weeks: int = 8) -> Dict[str, Any]:
    """Weekly signup cohort retention grid."""
    return get_cohort_retention(weeks)


@router.get("/churn-risk")
def churn_risk(inactive_days: int = 14) -> List[Dict[str, Any]]:
    """Users at risk of churning."""
    return get_churn_risk_users(inactive_days)


# ── Growth Playbook ──
@router.get("/experiments")
def experiments() -> List[Dict[str, Any]]:
    """List growth playbook experiments."""
    return get_growth_experiments()


class ExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = ""

@router.post("/experiments")
def new_experiment(data: ExperimentCreate) -> Dict[str, Any]:
    """Create a new growth experiment."""
    return create_experiment(data.name, data.description or "")


@router.get("/attribution")
def attribution() -> Dict[str, Any]:
    """Get experiment attribution report."""
    return get_attribution_report()


# ── A/B Tests ──
@router.get("/ab-tests")
def ab_tests() -> List[Dict[str, Any]]:
    """List all A/B tests."""
    return get_ab_tests()


class ABTestCreate(BaseModel):
    name: str
    target_metric: str
    variants: List[Dict[str, str]]

@router.post("/ab-tests")
def new_ab_test(data: ABTestCreate) -> Dict[str, Any]:
    """Create a new A/B test."""
    if len(data.variants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 variants")
    return create_ab_test(data.name, data.target_metric, data.variants)


@router.post("/ab-tests/{test_id}/significance")
def check_significance(test_id: str) -> Dict[str, Any]:
    """Calculate statistical significance for an A/B test."""
    result = calculate_significance(test_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
