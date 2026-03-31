"""
Social Matching Service - Connect nomads with shared interests and travel overlaps.
"""
import structlog
import json
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from uuid import uuid4

from backend import models

logger = structlog.get_logger(__name__)


# Interest categories for matching
INTEREST_CATEGORIES = {
    "tech": ["coding", "startup", "ai", "blockchain", "web3", "saas"],
    "creative": ["design", "photography", "writing", "music", "art", "video"],
    "wellness": ["yoga", "meditation", "fitness", "hiking", "surfing", "running"],
    "social": ["coffee", "networking", "coworking", "coliving", "events"],
    "food": ["cooking", "restaurants", "coffee", "wine", "vegan"],
    "adventure": ["travel", "diving", "climbing", "camping", "exploring"],
}


def _profile_to_text(profile: models.NomadProfile) -> str:
    """Convert a nomad profile into a text representation for embedding."""
    parts = []
    if profile.bio:
        parts.append(profile.bio)
    if profile.profession:
        parts.append(f"Works as {profile.profession}")
    if profile.interests:
        parts.append(f"Interests: {', '.join(profile.interests)}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")
    if profile.looking_for:
        parts.append(f"Looking for: {', '.join(profile.looking_for)}")
    if profile.travel_pace:
        parts.append(f"Travel pace: {profile.travel_pace}")
    if profile.work_style:
        parts.append(f"Work style: {profile.work_style}")
    return ". ".join(parts) if parts else ""


def _get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding for text, with Redis caching."""
    try:
        import redis as sync_redis
        from backend.config import settings

        # Cache key based on content hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        cache_key = f"embedding:{text_hash}"

        # Try cache first
        try:
            r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # Generate embedding via litellm
        from litellm import embedding
        response = embedding(model="text-embedding-3-small", input=[text])
        vec = response.data[0]["embedding"]

        # Cache for 24 hours
        try:
            r.setex(cache_key, 86400, json.dumps(vec))
        except Exception:
            pass

        return vec
    except Exception as e:
        logger.debug("embedding_unavailable", error=str(e))
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rule_based_score(
    profile1: models.NomadProfile,
    profile2: models.NomadProfile,
) -> Dict[str, Any]:
    """Rule-based compatibility scoring (0-100)."""
    score = 0
    breakdown = {}

    # Interest overlap (0-40 points)
    interests1 = set(profile1.interests or [])
    interests2 = set(profile2.interests or [])
    if interests1 and interests2:
        common_interests = interests1 & interests2
        interest_score = min(40, len(common_interests) * 10)
        score += interest_score
        breakdown["interests"] = {
            "score": interest_score,
            "common": list(common_interests),
        }

    # Skills overlap (0-20 points)
    skills1 = set(profile1.skills or [])
    skills2 = set(profile2.skills or [])
    if skills1 and skills2:
        common_skills = skills1 & skills2
        skill_score = min(20, len(common_skills) * 5)
        score += skill_score
        breakdown["skills"] = {
            "score": skill_score,
            "common": list(common_skills),
        }

    # Looking for match (0-20 points)
    looking1 = set(profile1.looking_for or [])
    looking2 = set(profile2.looking_for or [])
    if looking1 and looking2:
        common_looking = looking1 & looking2
        looking_score = min(20, len(common_looking) * 10)
        score += looking_score
        breakdown["looking_for"] = {
            "score": looking_score,
            "common": list(common_looking),
        }

    # Travel pace match (0-10 points)
    if profile1.travel_pace == profile2.travel_pace:
        score += 10
        breakdown["travel_pace"] = {"score": 10, "match": True}

    # Budget level match (0-10 points)
    if profile1.budget_level == profile2.budget_level:
        score += 10
        breakdown["budget_level"] = {"score": 10, "match": True}

    return {
        "score": min(100, score),
        "breakdown": breakdown,
        "method": "rule_based",
    }


def calculate_compatibility_score(
    profile1: models.NomadProfile,
    profile2: models.NomadProfile,
) -> Dict[str, Any]:
    """
    Calculate compatibility score between two nomad profiles.
    Uses embedding-based semantic similarity when available,
    blended with rule-based scoring. Falls back to pure rule-based.
    Returns score (0-100), breakdown, and method used.
    """
    rule_result = _rule_based_score(profile1, profile2)

    # Try semantic matching for richer comparison
    text1 = _profile_to_text(profile1)
    text2 = _profile_to_text(profile2)

    if len(text1) > 20 and len(text2) > 20:
        emb1 = _get_embedding(text1)
        emb2 = _get_embedding(text2)

        if emb1 and emb2:
            similarity = _cosine_similarity(emb1, emb2)
            semantic_score = int(similarity * 100)

            # Blend: 60% semantic + 40% rule-based
            blended = int(semantic_score * 0.6 + rule_result["score"] * 0.4)

            return {
                "score": min(100, blended),
                "breakdown": {
                    **rule_result["breakdown"],
                    "semantic": {
                        "score": semantic_score,
                        "cosine_similarity": round(similarity, 3),
                    },
                },
                "method": "hybrid",
            }

    return rule_result


class SocialMatchingService:
    """
    Service for nomad social matching.
    
    Features:
    - Profile management with interests
    - Travel plan sharing
    - Find nomads with overlapping travel
    - Compatibility scoring
    """
    
    # Profile Management
    def create_or_update_profile(
        self,
        db: Session,
        user_id: str,
        bio: Optional[str] = None,
        profession: Optional[str] = None,
        company: Optional[str] = None,
        interests: Optional[List[str]] = None,
        skills: Optional[List[str]] = None,
        languages: Optional[List[dict]] = None,
        work_style: str = "hybrid",
        looking_for: Optional[List[str]] = None,
        open_to_meetups: bool = True,
        open_to_coliving: bool = False,
        open_to_coworking: bool = True,
        travel_pace: str = "moderate",
        budget_level: str = "moderate",
    ) -> models.NomadProfile:
        """Create or update a nomad profile."""
        profile = db.query(models.NomadProfile).filter(
            models.NomadProfile.user_id == user_id
        ).first()
        
        if profile:
            # Update existing
            if bio is not None:
                profile.bio = bio
            if profession is not None:
                profile.profession = profession
            if company is not None:
                profile.company = company
            if interests is not None:
                profile.interests = interests
            if skills is not None:
                profile.skills = skills
            if languages is not None:
                profile.languages = languages
            profile.work_style = work_style
            if looking_for is not None:
                profile.looking_for = looking_for
            profile.open_to_meetups = open_to_meetups
            profile.open_to_coliving = open_to_coliving
            profile.open_to_coworking = open_to_coworking
            profile.travel_pace = travel_pace
            profile.budget_level = budget_level
            profile.updated_at = datetime.utcnow()
        else:
            # Create new
            profile = models.NomadProfile(
                id=str(uuid4()),
                user_id=user_id,
                bio=bio,
                profession=profession,
                company=company,
                interests=interests or [],
                skills=skills or [],
                languages=languages or [],
                work_style=work_style,
                looking_for=looking_for or [],
                open_to_meetups=open_to_meetups,
                open_to_coliving=open_to_coliving,
                open_to_coworking=open_to_coworking,
                travel_pace=travel_pace,
                budget_level=budget_level,
            )
            db.add(profile)
        
        db.commit()
        db.refresh(profile)
        return profile
    
    def get_profile(
        self,
        db: Session,
        user_id: str,
    ) -> Optional[models.NomadProfile]:
        """Get a nomad profile by user ID."""
        return db.query(models.NomadProfile).filter(
            models.NomadProfile.user_id == user_id
        ).first()
    
    # Travel Plans
    def add_travel_plan(
        self,
        db: Session,
        user_id: str,
        city: str,
        country: str,
        country_code: Optional[str],
        start_date: datetime,
        end_date: Optional[datetime] = None,
        is_flexible: bool = False,
        visibility: str = "connections",
        notes: Optional[str] = None,
    ) -> models.TravelPlan:
        """Add a travel plan."""
        plan = models.TravelPlan(
            id=str(uuid4()),
            user_id=user_id,
            city=city,
            country=country,
            country_code=country_code,
            start_date=start_date,
            end_date=end_date,
            is_flexible=is_flexible,
            visibility=visibility,
            notes=notes,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        
        logger.info("travel_plan_added", user_id=user_id, city=city)
        return plan
    
    def get_user_travel_plans(
        self,
        db: Session,
        user_id: str,
        include_past: bool = False,
    ) -> List[models.TravelPlan]:
        """Get user's travel plans."""
        query = db.query(models.TravelPlan).filter(
            models.TravelPlan.user_id == user_id,
            models.TravelPlan.status.in_(["planned", "confirmed"]),
        )
        
        if not include_past:
            query = query.filter(
                or_(
                    models.TravelPlan.end_date >= datetime.utcnow(),
                    models.TravelPlan.end_date == None,
                )
            )
        
        return query.order_by(models.TravelPlan.start_date).all()
    
    # Overlap Detection
    def find_travel_overlaps(
        self,
        db: Session,
        user_id: str,
        city: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find other nomads with overlapping travel plans.
        Returns list of overlaps with compatibility scores.
        """
        # Get user's connections for visibility
        connections = db.query(models.NomadConnection).filter(
            and_(
                or_(
                    models.NomadConnection.user_id == user_id,
                    models.NomadConnection.connected_user_id == user_id,
                ),
                models.NomadConnection.status == "accepted",
            )
        ).all()
        
        connected_ids = {
            conn.connected_user_id if conn.user_id == user_id else conn.user_id
            for conn in connections
        }
        
        # Get user's upcoming plans
        my_plans = self.get_user_travel_plans(db, user_id)
        if not my_plans:
            return []
        
        overlaps = []
        
        for my_plan in my_plans:
            # Find overlapping plans from others
            query = db.query(models.TravelPlan).filter(
                models.TravelPlan.user_id != user_id,
                models.TravelPlan.city.ilike(my_plan.city),
                models.TravelPlan.status.in_(["planned", "confirmed"]),
            )
            
            # Date overlap logic
            if my_plan.end_date:
                query = query.filter(
                    models.TravelPlan.start_date <= my_plan.end_date,
                    or_(
                        models.TravelPlan.end_date >= my_plan.start_date,
                        models.TravelPlan.end_date == None,
                    )
                )
            else:
                query = query.filter(
                    or_(
                        models.TravelPlan.end_date >= my_plan.start_date,
                        models.TravelPlan.end_date == None,
                    )
                )
            
            other_plans = query.all()
            
            for other_plan in other_plans:
                # Check visibility
                if other_plan.visibility == "private":
                    continue
                elif other_plan.visibility == "connections" and other_plan.user_id not in connected_ids:
                    continue
                
                # Get other user and profile
                other_user = db.query(models.User).filter(
                    models.User.id == other_plan.user_id
                ).first()
                
                my_profile = self.get_profile(db, user_id)
                other_profile = self.get_profile(db, other_plan.user_id)
                
                # Calculate compatibility
                compatibility = {"score": 50, "breakdown": {}}  # Default
                if my_profile and other_profile:
                    compatibility = calculate_compatibility_score(my_profile, other_profile)
                
                # Calculate overlap days
                overlap_start = max(my_plan.start_date, other_plan.start_date)
                overlap_end = min(
                    my_plan.end_date or (my_plan.start_date + timedelta(days=365)),
                    other_plan.end_date or (other_plan.start_date + timedelta(days=365)),
                )
                overlap_days = max(0, (overlap_end - overlap_start).days)
                
                overlaps.append({
                    "user_id": other_plan.user_id,
                    "name": other_user.name if other_user else "Anonymous",
                    "avatar": other_user.avatar if other_user else None,
                    "city": my_plan.city,
                    "country": my_plan.country,
                    "their_dates": {
                        "start": other_plan.start_date.isoformat(),
                        "end": other_plan.end_date.isoformat() if other_plan.end_date else None,
                        "is_flexible": other_plan.is_flexible,
                    },
                    "overlap_days": overlap_days,
                    "compatibility": compatibility,
                    "is_connection": other_plan.user_id in connected_ids,
                    "open_to_meetups": other_profile.open_to_meetups if other_profile else True,
                })
        
        # Sort by compatibility score
        overlaps.sort(key=lambda x: x["compatibility"]["score"], reverse=True)
        
        return overlaps
    
    def find_compatible_nomads(
        self,
        db: Session,
        user_id: str,
        min_score: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find nomads compatible with the user based on profile.
        """
        my_profile = self.get_profile(db, user_id)
        if not my_profile:
            return []
        
        # Get all profiles except user's
        profiles = db.query(models.NomadProfile).filter(
            models.NomadProfile.user_id != user_id,
            models.NomadProfile.open_to_meetups == True,
        ).limit(100).all()
        
        matches = []
        for profile in profiles:
            compatibility = calculate_compatibility_score(my_profile, profile)
            
            if compatibility["score"] >= min_score:
                user = db.query(models.User).filter(
                    models.User.id == profile.user_id
                ).first()
                
                # Get their location if available
                location = db.query(models.NomadLocation).filter(
                    models.NomadLocation.user_id == profile.user_id,
                    models.NomadLocation.ghost_mode == False,
                ).first()
                
                matches.append({
                    "user_id": profile.user_id,
                    "name": user.name if user else "Anonymous",
                    "avatar": user.avatar if user else None,
                    "bio": profile.bio,
                    "profession": profile.profession,
                    "interests": profile.interests[:5] if profile.interests else [],
                    "location": {
                        "city": location.city if location else None,
                        "country": location.country if location else None,
                    } if location else None,
                    "compatibility": compatibility,
                    "open_to": {
                        "meetups": profile.open_to_meetups,
                        "coliving": profile.open_to_coliving,
                        "coworking": profile.open_to_coworking,
                    },
                })
        
        # Sort by score
        matches.sort(key=lambda x: x["compatibility"]["score"], reverse=True)
        
        return matches[:limit]
    
    def get_interest_suggestions(
        self,
        db: Session,
    ) -> Dict[str, List[str]]:
        """Get categorized interest suggestions."""
        return INTEREST_CATEGORIES


# Singleton
social_matching_service = SocialMatchingService()
