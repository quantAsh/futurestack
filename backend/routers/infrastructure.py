"""
Infrastructure Projects Router — CRUD, status transitions, search by vertical/region.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from backend.database import get_db
from backend.models_civic import (
    InfrastructureProject, InfraVertical, ProjectStatus,
    ImpactMetric,
)

router = APIRouter()


def get_db_dep():
    yield from get_db()


# --- Schemas ---

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    vertical: str  # water, energy, ai_infrastructure, food_security, education, transport
    community_id: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region: Optional[str] = None
    country: Optional[str] = None
    target_budget_usd: Optional[float] = 0
    beneficiary_count: Optional[int] = 0
    impact_targets: Optional[dict] = {}
    project_lead_id: Optional[str] = None


class ProjectStatusUpdate(BaseModel):
    status: str  # planning, funding, procurement, construction, operational


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_budget_usd: Optional[float] = None
    beneficiary_count: Optional[int] = None
    impact_targets: Optional[dict] = None
    estimated_completion: Optional[str] = None


# Valid status transitions
STATUS_TRANSITIONS = {
    "planning": ["funding"],
    "funding": ["procurement", "planning"],
    "procurement": ["construction", "funding"],
    "construction": ["operational", "procurement"],
    "operational": ["decommissioned"],
    "decommissioned": [],
}


# --- CRUD ---

@router.post("/projects")
def create_project(project: ProjectCreate, db: Session = Depends(get_db_dep)):
    """Create a new infrastructure project."""
    # Validate vertical
    valid_verticals = [v.value for v in InfraVertical]
    if project.vertical not in valid_verticals:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid vertical. Must be one of: {valid_verticals}",
        )

    new_project = InfrastructureProject(
        id=str(uuid4()),
        name=project.name,
        description=project.description,
        vertical=project.vertical,
        community_id=project.community_id,
        location_name=project.location_name,
        latitude=project.latitude,
        longitude=project.longitude,
        region=project.region,
        country=project.country,
        target_budget_usd=project.target_budget_usd,
        beneficiary_count=project.beneficiary_count,
        impact_targets=project.impact_targets,
        project_lead_id=project.project_lead_id,
        status="planning",
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return {
        "id": new_project.id,
        "name": new_project.name,
        "vertical": new_project.vertical,
        "status": new_project.status,
        "message": f"Project '{new_project.name}' created in {new_project.vertical} vertical.",
    }


@router.get("/projects")
def list_projects(
    vertical: Optional[str] = None,
    status: Optional[str] = None,
    region: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db_dep),
):
    """List infrastructure projects with optional filters."""
    query = db.query(InfrastructureProject)

    if vertical:
        query = query.filter(InfrastructureProject.vertical == vertical)
    if status:
        query = query.filter(InfrastructureProject.status == status)
    if region:
        query = query.filter(InfrastructureProject.region.ilike(f"%{region}%"))
    if country:
        query = query.filter(InfrastructureProject.country.ilike(f"%{country}%"))

    total = query.count()
    projects = query.order_by(InfrastructureProject.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "vertical": p.vertical,
                "status": p.status,
                "location": p.location_name,
                "country": p.country,
                "target_budget_usd": p.target_budget_usd,
                "funded_usd": p.funded_usd,
                "funding_pct": round((p.funded_usd / p.target_budget_usd * 100), 1) if p.target_budget_usd else 0,
                "beneficiary_count": p.beneficiary_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ],
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db_dep)):
    """Get detailed project info including impact metrics."""
    project = db.query(InfrastructureProject).filter(InfrastructureProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get latest metrics
    metrics = (
        db.query(ImpactMetric)
        .filter(ImpactMetric.project_id == project_id)
        .order_by(ImpactMetric.recorded_at.desc())
        .limit(20)
        .all()
    )

    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "vertical": project.vertical,
        "status": project.status,
        "location": {
            "name": project.location_name,
            "lat": project.latitude,
            "lng": project.longitude,
            "region": project.region,
            "country": project.country,
        },
        "funding": {
            "target_usd": project.target_budget_usd,
            "funded_usd": project.funded_usd,
            "pct": round((project.funded_usd / project.target_budget_usd * 100), 1) if project.target_budget_usd else 0,
            "deadline": project.funding_deadline.isoformat() if project.funding_deadline else None,
        },
        "impact": {
            "beneficiary_count": project.beneficiary_count,
            "targets": project.impact_targets,
        },
        "timeline": {
            "start": project.start_date.isoformat() if project.start_date else None,
            "estimated_completion": project.estimated_completion.isoformat() if project.estimated_completion else None,
            "actual_completion": project.actual_completion.isoformat() if project.actual_completion else None,
        },
        "latest_metrics": [
            {
                "type": m.metric_type,
                "value": m.value,
                "unit": m.unit,
                "period": m.period,
                "source": m.source,
                "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
            }
            for m in metrics
        ],
        "project_lead_id": project.project_lead_id,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


@router.put("/projects/{project_id}")
def update_project(project_id: str, update: ProjectUpdate, db: Session = Depends(get_db_dep)):
    """Update project details."""
    project = db.query(InfrastructureProject).filter(InfrastructureProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if update.name is not None:
        project.name = update.name
    if update.description is not None:
        project.description = update.description
    if update.target_budget_usd is not None:
        project.target_budget_usd = update.target_budget_usd
    if update.beneficiary_count is not None:
        project.beneficiary_count = update.beneficiary_count
    if update.impact_targets is not None:
        project.impact_targets = update.impact_targets
    if update.estimated_completion is not None:
        project.estimated_completion = datetime.fromisoformat(update.estimated_completion)

    db.commit()
    return {"status": "updated", "project_id": project_id}


@router.post("/projects/{project_id}/transition")
def transition_project_status(
    project_id: str,
    update: ProjectStatusUpdate,
    db: Session = Depends(get_db_dep),
):
    """Transition a project to the next status (with validation)."""
    project = db.query(InfrastructureProject).filter(InfrastructureProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    allowed = STATUS_TRANSITIONS.get(project.status, [])
    if update.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{project.status}' to '{update.status}'. Allowed: {allowed}",
        )

    old_status = project.status
    project.status = update.status

    # Auto-set dates on key transitions
    if update.status == "construction" and not project.start_date:
        project.start_date = datetime.utcnow()
    if update.status == "operational":
        project.actual_completion = datetime.utcnow()

    db.commit()

    return {
        "status": "transitioned",
        "project_id": project_id,
        "from": old_status,
        "to": update.status,
    }


# --- Vertical Summary ---

@router.get("/verticals/summary")
def get_vertical_summary(db: Session = Depends(get_db_dep)):
    """Get aggregate stats per vertical."""
    from sqlalchemy import func

    verticals = [v.value for v in InfraVertical]
    summary = []

    for v in verticals:
        projects = db.query(InfrastructureProject).filter(InfrastructureProject.vertical == v).all()
        total_funded = sum(p.funded_usd or 0 for p in projects)
        total_budget = sum(p.target_budget_usd or 0 for p in projects)
        total_beneficiaries = sum(p.beneficiary_count or 0 for p in projects)
        operational = sum(1 for p in projects if p.status == "operational")

        summary.append({
            "vertical": v,
            "total_projects": len(projects),
            "operational": operational,
            "total_budget_usd": round(total_budget, 2),
            "total_funded_usd": round(total_funded, 2),
            "total_beneficiaries": total_beneficiaries,
        })

    return summary
