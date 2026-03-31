"""
Skills Marketplace Router - Peer-to-peer skill exchange.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter()


def get_db_dep():
    yield from get_db()


# Skill categories
SKILL_CATEGORIES = [
    "development",
    "design",
    "marketing",
    "writing",
    "photography",
    "video",
    "music",
    "language",
    "fitness",
    "cooking",
    "business",
    "other",
]


class SkillCreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    rate_usd: Optional[float] = None  # null = free


class SkillResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    name: str
    category: str
    description: Optional[str]
    rate_usd: Optional[float]
    is_available: bool


class SkillRequestCreate(BaseModel):
    skill_name: str
    description: str
    hub_id: Optional[str] = None
    budget_usd: Optional[float] = None


@router.get("/categories")
def get_categories():
    """Get available skill categories."""
    return SKILL_CATEGORIES


@router.get("/", response_model=List[SkillResponse])
def get_skills(
    category: Optional[str] = None,
    hub_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_dep),
):
    """Browse available skills."""
    query = db.query(models.Skill).filter(models.Skill.is_available == True)

    if category:
        query = query.filter(models.Skill.category == category)

    skills = query.offset(skip).limit(limit).all()

    # Enrich with user names
    result = []
    for skill in skills:
        user = db.query(models.User).filter(models.User.id == skill.user_id).first()
        result.append(
            {
                "id": skill.id,
                "user_id": skill.user_id,
                "user_name": user.name if user else None,
                "name": skill.name,
                "category": skill.category,
                "description": skill.description,
                "rate_usd": skill.rate_usd,
                "is_available": skill.is_available,
            }
        )

    return result


@router.post("/", response_model=SkillResponse)
def add_skill(
    skill: SkillCreate, 
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Add a skill to your profile."""
    if skill.category not in SKILL_CATEGORIES:
        raise HTTPException(
            status_code=400, detail=f"Invalid category. Choose from: {SKILL_CATEGORIES}"
        )

    db_skill = models.Skill(
        id=str(uuid4()),
        user_id=current_user.id,
        name=skill.name,
        category=skill.category,
        description=skill.description,
        rate_usd=skill.rate_usd,
        is_available=True,
    )
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)

    return db_skill


@router.get("/user/{user_id}")
def get_user_skills(user_id: str, db: Session = Depends(get_db_dep)):
    """Get all skills for a user."""
    skills = db.query(models.Skill).filter(models.Skill.user_id == user_id).all()
    return skills


@router.post("/request")
def create_skill_request(
    request: SkillRequestCreate, db: Session = Depends(get_db_dep)
):
    """Request help with a skill."""
    db_request = models.SkillRequest(
        id=str(uuid4()),
        requester_id=request.requester_id,
        skill_name=request.skill_name,
        description=request.description,
        hub_id=request.hub_id,
        budget_usd=request.budget_usd,
        status="open",
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    return {
        "id": db_request.id,
        "status": "open",
        "message": "Request created. Matching in progress.",
    }


@router.get("/requests/open")
def get_open_requests(
    hub_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db_dep),
):
    """Get open skill requests."""
    query = db.query(models.SkillRequest).filter(models.SkillRequest.status == "open")

    if hub_id:
        query = query.filter(models.SkillRequest.hub_id == hub_id)

    return (
        query.order_by(models.SkillRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/match/{request_id}")
def match_skill_request(request_id: str, db: Session = Depends(get_db_dep)):
    """AI-match a skill request with available providers."""
    request = (
        db.query(models.SkillRequest)
        .filter(models.SkillRequest.id == request_id)
        .first()
    )

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Find matching skills
    matches = (
        db.query(models.Skill)
        .filter(models.Skill.name.ilike(f"%{request.skill_name}%"))
        .filter(models.Skill.is_available == True)
        .filter(models.Skill.user_id != request.requester_id)
        .limit(5)
        .all()
    )

    result = []
    for skill in matches:
        user = db.query(models.User).filter(models.User.id == skill.user_id).first()

        # Calculate match score (simple for now)
        score = 100
        if request.budget_usd and skill.rate_usd:
            if skill.rate_usd <= request.budget_usd:
                score += 20
            else:
                score -= 20

        result.append(
            {
                "skill_id": skill.id,
                "user_id": skill.user_id,
                "user_name": user.name if user else "Unknown",
                "skill_name": skill.name,
                "rate_usd": skill.rate_usd,
                "match_score": score,
            }
        )

    # Sort by score
    result.sort(key=lambda x: x["match_score"], reverse=True)

    return {"request_id": request_id, "matches": result, "count": len(result)}


@router.post("/requests/{request_id}/accept")
def accept_request(
    request_id: str, provider_id: str, db: Session = Depends(get_db_dep)
):
    """Accept a skill request as provider."""
    request = (
        db.query(models.SkillRequest)
        .filter(models.SkillRequest.id == request_id)
        .first()
    )

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "open":
        raise HTTPException(status_code=400, detail="Request is no longer open")

    request.matched_user_id = provider_id
    request.status = "matched"
    db.commit()

    return {"status": "matched", "request_id": request_id, "provider_id": provider_id}
