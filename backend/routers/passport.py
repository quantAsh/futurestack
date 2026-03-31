"""
Passport Router - Nomad Passport and Badges.
Gamified cultural journey tracking.
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
# BADGE DEFINITIONS
# ============================================

AVAILABLE_BADGES = {
    "water_ceremony": {
        "name": "Water Ceremony",
        "description": "Participated in a sacred water ceremony",
        "icon": "💧",
        "culture": "Balinese"
    },
    "craft_apprentice": {
        "name": "Craft Apprentice",
        "description": "Learned a traditional craft from a master",
        "icon": "🎨",
        "culture": "Universal"
    },
    "earth_guardian": {
        "name": "Earth Guardian",
        "description": "Contributed to land preservation",
        "icon": "🌍",
        "culture": "Universal"
    },
    "fire_keeper": {
        "name": "Fire Keeper",
        "description": "Participated in a fire ceremony",
        "icon": "🔥",
        "culture": "Indigenous"
    },
    "story_listener": {
        "name": "Story Listener",
        "description": "Heard oral traditions from an elder",
        "icon": "📖",
        "culture": "Universal"
    },
    "community_contributor": {
        "name": "Community Contributor",
        "description": "Contributed $100+ to local communities",
        "icon": "🤝",
        "culture": "Universal"
    },
    "cultural_bridge": {
        "name": "Cultural Bridge",
        "description": "Experienced 3+ different cultures",
        "icon": "🌉",
        "culture": "Universal"
    }
}


# ============================================
# SCHEMAS
# ============================================

class PassportResponse(BaseModel):
    id: str
    user_id: str
    experiences_completed: int
    badges: List[str]
    impact_contributed_usd: float
    passport_level: str
    cultures_visited: List[str]
    regions_explored: List[str]


class BadgeInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    culture: str
    earned: bool = False


# ============================================
# ENDPOINTS
# ============================================

@router.get("/me", response_model=PassportResponse)
def get_my_passport(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Get the current user's Nomad Passport."""
    passport = db.query(models.NomadPassport).filter(
        models.NomadPassport.user_id == current_user.id
    ).first()
    
    if not passport:
        # Create new passport
        passport = models.NomadPassport(
            id=str(uuid4()),
            user_id=current_user.id,
            badges=[],
            cultures_visited=[],
            regions_explored=[]
        )
        db.add(passport)
        db.commit()
        db.refresh(passport)
    
    return passport


@router.get("/stamps")
def get_my_stamps(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Get all stamps in the user's passport."""
    passport = db.query(models.NomadPassport).filter(
        models.NomadPassport.user_id == current_user.id
    ).first()
    
    if not passport:
        return {"stamps": [], "count": 0}
    
    stamps = db.query(models.PassportStamp).filter(
        models.PassportStamp.passport_id == passport.id
    ).order_by(models.PassportStamp.earned_at.desc()).all()
    
    result = []
    for stamp in stamps:
        exp = db.query(models.CulturalExperience).filter(
            models.CulturalExperience.id == stamp.experience_id
        ).first()
        
        result.append({
            "id": stamp.id,
            "earned_at": stamp.earned_at.isoformat() if stamp.earned_at else None,
            "impact_usd": stamp.impact_usd,
            "notes": stamp.notes,
            "experience": {
                "id": exp.id,
                "title": exp.title,
                "type": exp.experience_type,
                "image_url": exp.image_url
            } if exp else None
        })
    
    return {"stamps": result, "count": len(result)}


@router.get("/badges", response_model=List[BadgeInfo])
def get_available_badges(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Get all available badges with earned status."""
    passport = db.query(models.NomadPassport).filter(
        models.NomadPassport.user_id == current_user.id
    ).first()
    
    earned_badges = passport.badges if passport and passport.badges else []
    
    result = []
    for badge_id, badge_data in AVAILABLE_BADGES.items():
        result.append(BadgeInfo(
            id=badge_id,
            name=badge_data["name"],
            description=badge_data["description"],
            icon=badge_data["icon"],
            culture=badge_data["culture"],
            earned=badge_id in earned_badges
        ))
    
    return result


@router.post("/badges/{badge_id}/claim")
def claim_badge(
    badge_id: str,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Claim a badge (with eligibility check)."""
    if badge_id not in AVAILABLE_BADGES:
        raise HTTPException(status_code=404, detail="Badge not found")
    
    passport = db.query(models.NomadPassport).filter(
        models.NomadPassport.user_id == current_user.id
    ).first()
    
    if not passport:
        raise HTTPException(status_code=400, detail="No passport found. Complete an experience first.")
    
    if passport.badges and badge_id in passport.badges:
        raise HTTPException(status_code=400, detail="Badge already claimed")
    
    # Check eligibility based on badge type
    eligible = False
    reason = "Requirements not met"
    
    if badge_id == "community_contributor":
        if passport.impact_contributed_usd >= 100:
            eligible = True
    elif badge_id == "cultural_bridge":
        if len(passport.cultures_visited or []) >= 3:
            eligible = True
    else:
        # Other badges require manual verification or experience completion
        # For now, allow claiming if user has at least 1 experience
        if passport.experiences_completed >= 1:
            eligible = True
    
    if not eligible:
        raise HTTPException(status_code=403, detail=reason)
    
    # Add badge
    current_badges = passport.badges or []
    current_badges.append(badge_id)
    passport.badges = current_badges
    
    db.commit()
    
    badge_info = AVAILABLE_BADGES[badge_id]
    return {
        "status": "claimed",
        "badge": {
            "id": badge_id,
            **badge_info
        },
        "total_badges": len(current_badges)
    }


@router.get("/leaderboard")
def get_impact_leaderboard(
    limit: int = 10,
    db: Session = Depends(get_db_dep)
):
    """Get top contributors by community impact."""
    passports = db.query(models.NomadPassport).order_by(
        models.NomadPassport.impact_contributed_usd.desc()
    ).limit(limit).all()
    
    result = []
    for i, passport in enumerate(passports):
        user = db.query(models.User).filter(
            models.User.id == passport.user_id
        ).first()
        
        result.append({
            "rank": i + 1,
            "user_name": user.name if user else "Anonymous",
            "avatar": user.avatar if user else None,
            "impact_usd": passport.impact_contributed_usd,
            "passport_level": passport.passport_level,
            "experiences_completed": passport.experiences_completed,
            "badges_count": len(passport.badges or [])
        })
    
    return {"leaderboard": result}
