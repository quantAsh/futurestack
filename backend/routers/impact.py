"""
Impact Metrics Router — record, query, and dashboard community infrastructure impact.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from backend.database import get_db
from backend.models_civic import ImpactMetric, InfrastructureProject, InfraVertical

router = APIRouter()


def get_db_dep():
    yield from get_db()


# --- Vertical-specific metric types ---
VERTICAL_METRICS = {
    "water": {
        "liters_purified": "liters",
        "households_served": "count",
        "water_quality_score": "score",
        "distribution_km": "km",
    },
    "energy": {
        "kwh_generated": "kwh",
        "co2_offset_kg": "kg",
        "uptime_pct": "pct",
        "peak_capacity_kw": "kw",
    },
    "ai_infrastructure": {
        "compute_tflops": "tflops",
        "models_served": "count",
        "api_calls": "count",
        "latency_ms": "ms",
    },
    "food_security": {
        "calories_produced": "kcal",
        "acres_farmed": "acres",
        "waste_reduced_kg": "kg",
        "meals_served": "count",
    },
    "education": {
        "students_enrolled": "count",
        "completion_rate_pct": "pct",
        "courses_offered": "count",
        "certifications_issued": "count",
    },
    "transport": {
        "trips_daily": "count",
        "km_covered": "km",
        "emissions_saved_kg": "kg",
        "passengers_served": "count",
    },
}


# --- Schemas ---

class MetricRecord(BaseModel):
    project_id: str
    metric_type: str
    value: float
    unit: Optional[str] = None
    period: str = "daily"  # hourly, daily, weekly, monthly, cumulative
    source: str = "manual"  # manual, iot, estimated, api
    notes: Optional[str] = None


class MetricBatchRecord(BaseModel):
    project_id: str
    metrics: List[dict]  # [{"metric_type": "kwh_generated", "value": 450}]
    period: str = "daily"
    source: str = "manual"


# --- Record Metrics ---

@router.post("/metrics")
def record_metric(metric: MetricRecord, db: Session = Depends(get_db_dep)):
    """Record a single impact metric for a project."""
    project = db.query(InfrastructureProject).filter(InfrastructureProject.id == metric.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Auto-resolve unit from vertical config
    unit = metric.unit
    if not unit:
        vertical_metrics = VERTICAL_METRICS.get(project.vertical, {})
        unit = vertical_metrics.get(metric.metric_type, "unit")

    record = ImpactMetric(
        id=str(uuid4()),
        project_id=metric.project_id,
        metric_type=metric.metric_type,
        value=metric.value,
        unit=unit,
        period=metric.period,
        source=metric.source,
        notes=metric.notes,
    )
    db.add(record)
    db.commit()

    return {
        "id": record.id,
        "metric_type": metric.metric_type,
        "value": metric.value,
        "unit": unit,
        "status": "recorded",
    }


@router.post("/metrics/batch")
def record_metrics_batch(batch: MetricBatchRecord, db: Session = Depends(get_db_dep)):
    """Record multiple metrics for a project at once."""
    project = db.query(InfrastructureProject).filter(InfrastructureProject.id == batch.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    vertical_metrics = VERTICAL_METRICS.get(project.vertical, {})
    recorded = []

    for m in batch.metrics:
        mt = m.get("metric_type")
        val = m.get("value", 0)
        unit = m.get("unit") or vertical_metrics.get(mt, "unit")

        record = ImpactMetric(
            id=str(uuid4()),
            project_id=batch.project_id,
            metric_type=mt,
            value=val,
            unit=unit,
            period=batch.period,
            source=batch.source,
        )
        db.add(record)
        recorded.append({"metric_type": mt, "value": val, "unit": unit})

    db.commit()
    return {"recorded": len(recorded), "metrics": recorded}


# --- Query Metrics ---

@router.get("/metrics/{project_id}")
def get_project_metrics(
    project_id: str,
    metric_type: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db_dep),
):
    """Get metrics for a project."""
    query = db.query(ImpactMetric).filter(ImpactMetric.project_id == project_id)

    if metric_type:
        query = query.filter(ImpactMetric.metric_type == metric_type)
    if period:
        query = query.filter(ImpactMetric.period == period)

    metrics = query.order_by(ImpactMetric.recorded_at.desc()).limit(limit).all()

    return [
        {
            "id": m.id,
            "metric_type": m.metric_type,
            "value": m.value,
            "unit": m.unit,
            "period": m.period,
            "source": m.source,
            "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
        }
        for m in metrics
    ]


# --- Impact Dashboard ---

@router.get("/impact/dashboard")
def impact_dashboard(vertical: Optional[str] = None, db: Session = Depends(get_db_dep)):
    """
    Aggregate impact dashboard across all projects.
    Shows cumulative metrics per vertical.
    """
    query = db.query(InfrastructureProject).filter(InfrastructureProject.status == "operational")
    if vertical:
        query = query.filter(InfrastructureProject.vertical == vertical)

    projects = query.all()
    project_ids = [p.id for p in projects]

    if not project_ids:
        return {"verticals": {}, "total_projects": 0, "total_beneficiaries": 0}

    # Aggregate metrics by type
    aggregates = (
        db.query(
            ImpactMetric.metric_type,
            func.sum(ImpactMetric.value).label("total"),
            func.avg(ImpactMetric.value).label("avg"),
            func.max(ImpactMetric.value).label("peak"),
            func.count(ImpactMetric.id).label("readings"),
        )
        .filter(ImpactMetric.project_id.in_(project_ids))
        .group_by(ImpactMetric.metric_type)
        .all()
    )

    return {
        "total_projects": len(projects),
        "total_beneficiaries": sum(p.beneficiary_count or 0 for p in projects),
        "total_funded_usd": round(sum(p.funded_usd or 0 for p in projects), 2),
        "metrics": {
            a.metric_type: {
                "total": round(a.total, 2),
                "average": round(a.avg, 2),
                "peak": round(a.peak, 2),
                "readings": a.readings,
            }
            for a in aggregates
        },
    }


# --- Metric Types Reference ---

@router.get("/impact/metric-types")
def get_metric_types():
    """Get available metric types per vertical."""
    return VERTICAL_METRICS
