"""
Hub Intelligence Service - Real-time hub insights and event suggestions.
"""
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models


def get_hub_residents(hub_id: str, db: Session) -> List[Dict]:
    """Get current residents at a hub based on bookings."""
    now = datetime.now()

    # Get hub's listings
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        return []

    # Get listings in this hub
    listings = db.query(models.Listing).filter(models.Listing.hub_id == hub_id).all()
    listing_ids = [l.id for l in listings]

    if not listing_ids:
        return []

    # Get active bookings
    bookings = (
        db.query(models.Booking)
        .filter(models.Booking.listing_id.in_(listing_ids))
        .filter(models.Booking.start_date <= now)
        .filter(models.Booking.end_date >= now)
        .all()
    )

    residents = []
    for b in bookings:
        user = db.query(models.User).filter(models.User.id == b.user_id).first()
        if user:
            # Get user's skills
            skills = (
                db.query(models.Skill).filter(models.Skill.user_id == user.id).all()
            )

            residents.append(
                {
                    "user_id": user.id,
                    "name": user.name,
                    "bio": user.bio,
                    "skills": [s.name for s in skills],
                    "is_host": user.is_host,
                    "checkout_date": b.end_date.isoformat() if b.end_date else None,
                }
            )

    return residents


def analyze_hub_mood(residents: List[Dict]) -> Dict:
    """Analyze hub mood based on current residents."""
    if not residents:
        return {"mood": "quiet", "energy": "low", "message": "Hub is currently quiet"}

    count = len(residents)
    skill_count = sum(len(r.get("skills", [])) for r in residents)

    if count >= 10:
        mood = "buzzing"
        energy = "high"
    elif count >= 5:
        mood = "social"
        energy = "medium"
    else:
        mood = "cozy"
        energy = "low"

    # Check for skill clusters
    all_skills = []
    for r in residents:
        all_skills.extend(r.get("skills", []))

    skill_summary = {}
    for s in all_skills:
        s_lower = s.lower()
        for cat in ["development", "design", "marketing", "writing"]:
            if cat in s_lower:
                skill_summary[cat] = skill_summary.get(cat, 0) + 1

    dominant_skill = (
        max(skill_summary.items(), key=lambda x: x[1])[0] if skill_summary else None
    )

    return {
        "mood": mood,
        "energy": energy,
        "resident_count": count,
        "skill_diversity": len(skill_summary),
        "dominant_skill": dominant_skill,
        "message": f"Hub is {mood} with {count} residents. {'Strong ' + dominant_skill + ' presence!' if dominant_skill else ''}",
    }


def suggest_events(residents: List[Dict], hub_name: str) -> List[Dict]:
    """Generate AI event suggestions based on residents."""
    if len(residents) < 2:
        return [
            {
                "title": "Welcome Coffee",
                "description": "Casual meet and greet for new arrivals",
                "suggested_time": "Tomorrow 10:00 AM",
                "min_attendees": 2,
            }
        ]

    suggestions = []

    # Check for skill clusters
    skills = []
    for r in residents:
        skills.extend(r.get("skills", []))

    # Developer event
    dev_count = sum(
        1
        for s in skills
        if any(t in s.lower() for t in ["dev", "code", "programming", "software"])
    )
    if dev_count >= 2:
        suggestions.append(
            {
                "title": "Code & Coffee",
                "description": f"Pair programming and tech discussions with {dev_count} developers",
                "suggested_time": "This week, morning",
                "type": "professional",
            }
        )

    # Creative event
    creative_count = sum(
        1
        for s in skills
        if any(t in s.lower() for t in ["design", "photo", "video", "art"])
    )
    if creative_count >= 2:
        suggestions.append(
            {
                "title": "Creative Showcase",
                "description": "Share your portfolio and get feedback from fellow creatives",
                "suggested_time": "This weekend, afternoon",
                "type": "creative",
            }
        )

    # Default social events
    suggestions.append(
        {
            "title": "Community Dinner",
            "description": f"Potluck dinner for all {len(residents)} residents",
            "suggested_time": "Friday 7:00 PM",
            "type": "social",
        }
    )

    if len(residents) >= 5:
        suggestions.append(
            {
                "title": "Skill Swap",
                "description": "15-minute micro-lessons where everyone teaches something",
                "suggested_time": "Saturday 3:00 PM",
                "type": "learning",
            }
        )

    return suggestions


def get_hub_intelligence(hub_id: str) -> Dict:
    """Get complete hub intelligence report."""
    db = SessionLocal()
    try:
        hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
        if not hub:
            return {"error": "Hub not found"}

        # Get all hub listings for capacity
        listings = (
            db.query(models.Listing).filter(models.Listing.hub_id == hub_id).all()
        )
        total_capacity = sum(l.guest_capacity or 1 for l in listings)

        residents = get_hub_residents(hub_id, db)
        mood = analyze_hub_mood(residents)
        events = suggest_events(residents, hub.name)

        occupancy = len(residents) / total_capacity if total_capacity > 0 else 0

        return {
            "hub_id": hub_id,
            "hub_name": hub.name,
            "timestamp": datetime.now().isoformat(),
            "occupancy": {
                "current": len(residents),
                "capacity": total_capacity,
                "rate": round(occupancy * 100, 1),
            },
            "mood": mood,
            "residents": residents,
            "suggested_events": events,
        }

    finally:
        db.close()
