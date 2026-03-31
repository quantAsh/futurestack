"""
Hub Intelligence Router - Real-time hub insights.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.services import hub_intelligence
from backend.middleware.auth import get_current_user

router = APIRouter()


def get_db_dep():
    yield from get_db()


@router.get("/{hub_id}/intel")
def get_intel(
    hub_id: str, 
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Get real-time hub intelligence."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    return hub_intelligence.get_hub_intelligence(hub_id)


@router.get("/{hub_id}/residents")
def get_residents(hub_id: str, db: Session = Depends(get_db_dep)):
    """Get current hub residents."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    residents = hub_intelligence.get_hub_residents(hub_id, db)
    return {"hub_id": hub_id, "count": len(residents), "residents": residents}


@router.get("/{hub_id}/suggest-events")
def suggest_events(hub_id: str, db: Session = Depends(get_db_dep)):
    """Get AI event suggestions for a hub."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    residents = hub_intelligence.get_hub_residents(hub_id, db)
    events = hub_intelligence.suggest_events(residents, hub.name)

    return {
        "hub_id": hub_id,
        "hub_name": hub.name,
        "resident_count": len(residents),
        "suggested_events": events,
    }


@router.get("/{hub_id}/mood")
def get_mood(hub_id: str, db: Session = Depends(get_db_dep)):
    """Get current hub mood/energy."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    residents = hub_intelligence.get_hub_residents(hub_id, db)
    mood = hub_intelligence.analyze_hub_mood(residents)

    return {"hub_id": hub_id, "hub_name": hub.name, **mood}
