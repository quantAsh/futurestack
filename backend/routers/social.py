"""
Social Matching API Router.

Connect nomads with shared interests and travel overlaps.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.social_matching import social_matching_service

router = APIRouter(prefix="/api/social", tags=["social"])


# ============================================================================
# Schemas
# ============================================================================

class ProfileUpdate(BaseModel):
    bio: Optional[str] = Field(None, max_length=500)
    profession: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    interests: Optional[List[str]] = Field(None, max_length=20)
    skills: Optional[List[str]] = Field(None, max_length=20)
    languages: Optional[List[dict]] = None  # [{"code": "en", "level": "native"}]
    work_style: str = Field(default="hybrid", pattern="^(remote|hybrid|flexible)$")
    looking_for: Optional[List[str]] = Field(None, max_length=10)
    open_to_meetups: bool = True
    open_to_coliving: bool = False
    open_to_coworking: bool = True
    travel_pace: str = Field(default="moderate", pattern="^(slow|moderate|fast)$")
    budget_level: str = Field(default="moderate", pattern="^(budget|moderate|comfortable|luxury)$")

    class Config:
        json_schema_extra = {
            "example": {
                "bio": "Full-stack dev traveling the world 🌍",
                "profession": "Software Engineer",
                "interests": ["coding", "surfing", "coffee"],
                "skills": ["python", "react", "aws"],
                "looking_for": ["coworking", "coffee", "hiking"],
                "work_style": "remote",
                "travel_pace": "slow",
            }
        }


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    bio: Optional[str]
    profession: Optional[str]
    company: Optional[str]
    interests: List[str]
    skills: List[str]
    work_style: str
    looking_for: List[str]
    open_to_meetups: bool
    open_to_coliving: bool
    open_to_coworking: bool
    travel_pace: str
    budget_level: str

    class Config:
        from_attributes = True


class TravelPlanCreate(BaseModel):
    city: str = Field(..., max_length=100)
    country: str = Field(..., max_length=100)
    country_code: Optional[str] = Field(None, max_length=3)
    start_date: datetime
    end_date: Optional[datetime] = None
    is_flexible: bool = False
    visibility: str = Field(default="connections", pattern="^(public|connections|private)$")
    notes: Optional[str] = Field(None, max_length=500)


class TravelPlanResponse(BaseModel):
    id: str
    city: str
    country: str
    start_date: datetime
    end_date: Optional[datetime]
    is_flexible: bool
    visibility: str
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True


# ============================================================================
# Profile Endpoints
# ============================================================================

@router.get("/profile", response_model=Optional[ProfileResponse])
async def get_my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get your nomad profile."""
    return social_matching_service.get_profile(db, current_user.id)


@router.post("/profile", response_model=ProfileResponse)
async def update_my_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create or update your nomad profile."""
    profile = social_matching_service.create_or_update_profile(
        db=db,
        user_id=current_user.id,
        bio=data.bio,
        profession=data.profession,
        company=data.company,
        interests=data.interests,
        skills=data.skills,
        languages=data.languages,
        work_style=data.work_style,
        looking_for=data.looking_for,
        open_to_meetups=data.open_to_meetups,
        open_to_coliving=data.open_to_coliving,
        open_to_coworking=data.open_to_coworking,
        travel_pace=data.travel_pace,
        budget_level=data.budget_level,
    )
    return profile


@router.get("/profile/{user_id}", response_model=Optional[ProfileResponse])
async def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get another user's nomad profile."""
    return social_matching_service.get_profile(db, user_id)


@router.get("/interests")
async def get_interest_suggestions(
    db: Session = Depends(get_db),
):
    """Get categorized interest suggestions for profile building."""
    return social_matching_service.get_interest_suggestions(db)


# ============================================================================
# Travel Plan Endpoints
# ============================================================================

@router.post("/travel-plans", response_model=TravelPlanResponse)
async def add_travel_plan(
    data: TravelPlanCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a travel plan for overlap matching."""
    plan = social_matching_service.add_travel_plan(
        db=db,
        user_id=current_user.id,
        city=data.city,
        country=data.country,
        country_code=data.country_code,
        start_date=data.start_date,
        end_date=data.end_date,
        is_flexible=data.is_flexible,
        visibility=data.visibility,
        notes=data.notes,
    )
    return plan


@router.get("/travel-plans", response_model=List[TravelPlanResponse])
async def get_my_travel_plans(
    include_past: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get your travel plans."""
    return social_matching_service.get_user_travel_plans(
        db, current_user.id, include_past
    )


@router.delete("/travel-plans/{plan_id}")
def delete_travel_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a travel plan."""
    plan = db.query(models.TravelPlan).filter(
        models.TravelPlan.id == plan_id,
        models.TravelPlan.user_id == current_user.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Travel plan not found")
    
    db.delete(plan)
    db.commit()
    return {"message": "Travel plan deleted"}


# ============================================================================
# Matching Endpoints
# ============================================================================

@router.get("/overlaps")
async def find_travel_overlaps(
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Find nomads with overlapping travel plans.
    
    Returns list of overlaps sorted by compatibility score.
    """
    overlaps = social_matching_service.find_travel_overlaps(
        db=db,
        user_id=current_user.id,
        city=city,
    )
    
    return {
        "overlaps": overlaps,
        "total": len(overlaps),
        "tip": "Add more travel plans to find more overlaps!" if len(overlaps) == 0 else None,
    }


@router.get("/matches")
async def find_compatible_nomads(
    min_score: int = Query(default=30, ge=0, le=100),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Find nomads compatible with you based on interests and preferences.
    
    Returns list of matches sorted by compatibility score.
    """
    # Check if user has a profile
    profile = social_matching_service.get_profile(db, current_user.id)
    if not profile:
        return {
            "matches": [],
            "total": 0,
            "tip": "Create your profile first to find compatible nomads!",
            "profile_exists": False,
        }
    
    matches = social_matching_service.find_compatible_nomads(
        db=db,
        user_id=current_user.id,
        min_score=min_score,
        limit=limit,
    )
    
    return {
        "matches": matches,
        "total": len(matches),
        "profile_exists": True,
    }


@router.get("/who-is-in/{city}")
def who_is_in_city(
    city: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Find other nomads with travel plans in a specific city.
    Useful for "who else will be in Lisbon in March?"
    """
    # Query travel plans in this city
    plans = db.query(models.TravelPlan).filter(
        models.TravelPlan.city.ilike(city),
        models.TravelPlan.user_id != current_user.id,
        models.TravelPlan.status.in_(["planned", "confirmed"]),
        models.TravelPlan.visibility.in_(["public", "connections"]),
    ).limit(50).all()
    
    nomads = []
    for plan in plans:
        user = db.query(models.User).filter(
            models.User.id == plan.user_id
        ).first()
        
        profile = social_matching_service.get_profile(db, plan.user_id)
        
        nomads.append({
            "user_id": plan.user_id,
            "name": user.name if user else "Anonymous",
            "avatar": user.avatar if user else None,
            "dates": {
                "start": plan.start_date.isoformat(),
                "end": plan.end_date.isoformat() if plan.end_date else None,
                "is_flexible": plan.is_flexible,
            },
            "profession": profile.profession if profile else None,
            "open_to_meetups": profile.open_to_meetups if profile else True,
        })
    
    return {
        "city": city,
        "nomads": nomads,
        "total": len(nomads),
    }
