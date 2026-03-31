"""
Culture Router - Culture Keepers and Cultural Experiences.
Inspired by Quantum Temple's regenerative travel model.
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


# ============================================
# SCHEMAS
# ============================================

class CultureKeeperCreate(BaseModel):
    name: str
    bio: Optional[str] = None
    culture: Optional[str] = None
    region: Optional[str] = None
    traditions: Optional[List[str]] = None
    photo_url: Optional[str] = None


class CultureKeeperResponse(BaseModel):
    id: str
    user_id: str
    name: str
    bio: Optional[str]
    culture: Optional[str]
    region: Optional[str]
    traditions: Optional[List[str]]
    photo_url: Optional[str]
    verified: bool
    impact_total_usd: float


class CulturalExperienceCreate(BaseModel):
    listing_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    experience_type: str = "tradition"
    duration_hours: float = 2.0
    max_participants: int = 10
    price_usd: float = 0.0
    community_impact_percent: float = 0.4
    image_url: Optional[str] = None


class CulturalExperienceResponse(BaseModel):
    id: str
    keeper_id: str
    listing_id: Optional[str]
    title: str
    description: Optional[str]
    experience_type: str
    duration_hours: float
    max_participants: int
    price_usd: float
    community_impact_percent: float
    image_url: Optional[str]
    is_active: bool


# ============================================
# CULTURE KEEPERS ENDPOINTS
# ============================================

@router.get("/keepers", response_model=List[CultureKeeperResponse])
def list_culture_keepers(
    verified_only: bool = False,
    culture: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_dep)
):
    """List all Culture Keepers."""
    query = db.query(models.CultureKeeper)
    
    if verified_only:
        query = query.filter(models.CultureKeeper.verified == True)
    
    if culture:
        query = query.filter(models.CultureKeeper.culture.ilike(f"%{culture}%"))
    
    keepers = query.offset(skip).limit(limit).all()
    return keepers


@router.get("/keepers/{keeper_id}")
def get_culture_keeper(keeper_id: str, db: Session = Depends(get_db_dep)):
    """Get a Culture Keeper's profile with their experiences."""
    keeper = db.query(models.CultureKeeper).filter(
        models.CultureKeeper.id == keeper_id
    ).first()
    
    if not keeper:
        raise HTTPException(status_code=404, detail="Culture Keeper not found")
    
    experiences = db.query(models.CulturalExperience).filter(
        models.CulturalExperience.keeper_id == keeper_id,
        models.CulturalExperience.is_active == True
    ).all()
    
    return {
        "id": keeper.id,
        "name": keeper.name,
        "bio": keeper.bio,
        "culture": keeper.culture,
        "region": keeper.region,
        "traditions": keeper.traditions,
        "photo_url": keeper.photo_url,
        "verified": keeper.verified,
        "impact_total_usd": keeper.impact_total_usd,
        "experiences": [
            {
                "id": exp.id,
                "title": exp.title,
                "experience_type": exp.experience_type,
                "duration_hours": exp.duration_hours,
                "price_usd": exp.price_usd,
                "image_url": exp.image_url
            }
            for exp in experiences
        ]
    }


@router.post("/keepers", response_model=CultureKeeperResponse)
def become_culture_keeper(
    data: CultureKeeperCreate,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Register as a Culture Keeper (requires host status)."""
    # Check if user already is a keeper
    existing = db.query(models.CultureKeeper).filter(
        models.CultureKeeper.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="You are already a Culture Keeper")
    
    keeper = models.CultureKeeper(
        id=str(uuid4()),
        user_id=current_user.id,
        name=data.name,
        bio=data.bio,
        culture=data.culture,
        region=data.region,
        traditions=data.traditions,
        photo_url=data.photo_url,
        verified=False  # Requires admin verification
    )
    
    db.add(keeper)
    db.commit()
    db.refresh(keeper)
    
    return keeper


# ============================================
# CULTURAL EXPERIENCES ENDPOINTS
# ============================================

@router.get("/experiences", response_model=List[CulturalExperienceResponse])
def list_experiences(
    experience_type: Optional[str] = None,
    keeper_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_dep)
):
    """Browse cultural experiences."""
    query = db.query(models.CulturalExperience).filter(
        models.CulturalExperience.is_active == True
    )
    
    if experience_type:
        query = query.filter(models.CulturalExperience.experience_type == experience_type)
    
    if keeper_id:
        query = query.filter(models.CulturalExperience.keeper_id == keeper_id)
    
    return query.offset(skip).limit(limit).all()


@router.get("/experiences/{experience_id}")
def get_experience(experience_id: str, db: Session = Depends(get_db_dep)):
    """Get a cultural experience with keeper info."""
    exp = db.query(models.CulturalExperience).filter(
        models.CulturalExperience.id == experience_id
    ).first()
    
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    
    keeper = db.query(models.CultureKeeper).filter(
        models.CultureKeeper.id == exp.keeper_id
    ).first()
    
    return {
        **{c.name: getattr(exp, c.name) for c in exp.__table__.columns},
        "keeper": {
            "id": keeper.id,
            "name": keeper.name,
            "culture": keeper.culture,
            "photo_url": keeper.photo_url,
            "verified": keeper.verified
        } if keeper else None
    }


@router.post("/experiences", response_model=CulturalExperienceResponse)
def create_experience(
    data: CulturalExperienceCreate,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Create a cultural experience (must be a Culture Keeper)."""
    keeper = db.query(models.CultureKeeper).filter(
        models.CultureKeeper.user_id == current_user.id
    ).first()
    
    if not keeper:
        raise HTTPException(
            status_code=403, 
            detail="You must be a Culture Keeper to create experiences"
        )
    
    experience = models.CulturalExperience(
        id=str(uuid4()),
        keeper_id=keeper.id,
        listing_id=data.listing_id,
        title=data.title,
        description=data.description,
        experience_type=data.experience_type,
        duration_hours=data.duration_hours,
        max_participants=data.max_participants,
        price_usd=data.price_usd,
        community_impact_percent=data.community_impact_percent,
        image_url=data.image_url,
        is_active=True
    )
    
    db.add(experience)
    db.commit()
    db.refresh(experience)
    
    return experience


@router.post("/experiences/{experience_id}/join")
def join_experience(
    experience_id: str,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Join a cultural experience and earn a passport stamp."""
    exp = db.query(models.CulturalExperience).filter(
        models.CulturalExperience.id == experience_id
    ).first()
    
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    
    # Get or create passport
    passport = db.query(models.NomadPassport).filter(
        models.NomadPassport.user_id == current_user.id
    ).first()
    
    if not passport:
        passport = models.NomadPassport(
            id=str(uuid4()),
            user_id=current_user.id
        )
        db.add(passport)
        db.commit()
        db.refresh(passport)
    
    # Calculate impact
    impact = exp.price_usd * exp.community_impact_percent
    
    # Create stamp
    stamp = models.PassportStamp(
        id=str(uuid4()),
        passport_id=passport.id,
        experience_id=experience_id,
        impact_usd=impact
    )
    db.add(stamp)
    
    # Update passport stats
    passport.experiences_completed += 1
    passport.impact_contributed_usd += impact
    
    # Update keeper impact
    keeper = db.query(models.CultureKeeper).filter(
        models.CultureKeeper.id == exp.keeper_id
    ).first()
    if keeper:
        keeper.impact_total_usd += impact
    
    # Update passport level
    if passport.experiences_completed >= 10:
        passport.passport_level = "guardian"
    elif passport.experiences_completed >= 4:
        passport.passport_level = "pilgrim"
    
    db.commit()
    
    return {
        "status": "joined",
        "experience_id": experience_id,
        "stamp_id": stamp.id,
        "impact_usd": impact,
        "passport_level": passport.passport_level,
        "total_experiences": passport.experiences_completed
    }
