"""
Pathways Router - Gamification contribution pathways.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/pathways", tags=["pathways"])


class PathwayOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    requirements: Optional[list] = None
    rewards: Optional[list] = None
    icon: Optional[str] = None
    is_active: bool = True
    user_progress: Optional[float] = None

    class Config:
        from_attributes = True


# Default pathways
DEFAULT_PATHWAYS = [
    {
        "id": "host",
        "name": "Host",
        "description": "Become a property host",
        "icon": "🏠",
        "requirements": ["Complete host application", "List first property", "Host 5 guests"],
        "rewards": ["Host badge", "10% commission reduction", "Priority support"],
    },
    {
        "id": "explorer",
        "name": "Explorer",
        "description": "Travel the world",
        "icon": "🌍",
        "requirements": ["Complete first booking", "Visit 3 countries", "Write 5 reviews"],
        "rewards": ["Explorer badge", "5% booking discount", "Early access"],
    },
    {
        "id": "builder",
        "name": "Builder",
        "description": "Contribute to the community",
        "icon": "🔧",
        "requirements": ["Complete 3 tasks", "Help 5 members", "Organize 1 event"],
        "rewards": ["Builder badge", "NOMAD tokens", "Community leader status"],
    },
    {
        "id": "ambassador",
        "name": "Ambassador",
        "description": "Spread the word",
        "icon": "📣",
        "requirements": ["Refer 5 users", "Share 10 posts", "Host community call"],
        "rewards": ["Ambassador badge", "Referral bonus", "Exclusive events"],
    },
]


@router.get("/", response_model=List[PathwayOut])
def list_pathways(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all contribution pathways with user progress."""
    # Get pathways from DB or use defaults
    db_pathways = db.query(models.ContributionPathway).filter(
        models.ContributionPathway.is_active == True
    ).all()

    if db_pathways:
        result = []
        for p in db_pathways:
            out = PathwayOut.model_validate(p)
            # Get user progress
            progress = db.query(models.UserPathwayProgress).filter(
                models.UserPathwayProgress.user_id == current_user.id,
                models.UserPathwayProgress.pathway_id == p.id
            ).first()
            out.user_progress = progress.progress_percent if progress else 0
            result.append(out)
        return result

    # Return defaults with mock progress
    return [PathwayOut(**p, user_progress=0) for p in DEFAULT_PATHWAYS]


@router.get("/{pathway_id}", response_model=PathwayOut)
def get_pathway(
    pathway_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get specific pathway details."""
    pathway = db.query(models.ContributionPathway).filter(
        models.ContributionPathway.id == pathway_id
    ).first()

    if pathway:
        out = PathwayOut.model_validate(pathway)
        progress = db.query(models.UserPathwayProgress).filter(
            models.UserPathwayProgress.user_id == current_user.id,
            models.UserPathwayProgress.pathway_id == pathway_id
        ).first()
        out.user_progress = progress.progress_percent if progress else 0
        return out

    # Check defaults
    for p in DEFAULT_PATHWAYS:
        if p["id"] == pathway_id:
            return PathwayOut(**p, user_progress=0)

    raise HTTPException(status_code=404, detail="Pathway not found")


@router.post("/{pathway_id}/start")
def start_pathway(
    pathway_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Start a contribution pathway."""
    existing = db.query(models.UserPathwayProgress).filter(
        models.UserPathwayProgress.user_id == current_user.id,
        models.UserPathwayProgress.pathway_id == pathway_id
    ).first()

    if existing:
        return {"status": "already_started", "progress": existing.progress_percent}

    progress = models.UserPathwayProgress(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        pathway_id=pathway_id,
        progress_percent=0,
    )
    db.add(progress)
    db.commit()

    return {"status": "started", "progress": 0}
