"""
Community Agent — Social Matching & Event Orchestration for Nomad Hubs.

Provides the Concierge with community tools:
- Find travel buddies with overlapping dates/locations
- Suggest compatible nomads based on interests/skills
- Curate local events and meetups
- Get hub pulse (current stats, popular interests)

Production: uses social_matching_service for real DB queries.
Fallback: curated hub profiles when DB/user context unavailable.
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.community_agent")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.community_agent")

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from backend.services.nomad_data import LOCAL_EVENTS, HUB_PROFILES


def _get_db_session():
    """Try to get a DB session. Returns None if unavailable."""
    try:
        from backend.database import SessionLocal
        return SessionLocal()
    except Exception:
        return None


def _try_real_travel_overlaps(city: str, user_id: Optional[str] = None) -> Optional[Dict]:
    """Try to query real travel overlaps from the database."""
    if not user_id:
        return None

    db = _get_db_session()
    if not db:
        return None

    try:
        from backend.services.social_matching import social_matching_service
        overlaps = social_matching_service.find_travel_overlaps(db, user_id, city=city)

        if not overlaps:
            return None

        matches = []
        for overlap in overlaps[:10]:
            matches.append({
                "name": overlap.get("name", "Anonymous"),
                "flag": "",
                "role": "",
                "compatibility": overlap.get("compatibility", {}).get("score", 50),
                "shared_interests": overlap.get("compatibility", {}).get("breakdown", {}).get("interests", {}).get("common", []),
                "status": f"overlap: {overlap.get('overlap_days', '?')} days",
                "is_real": True,
            })

        matches.sort(key=lambda x: -x["compatibility"])
        return {
            "matches": matches,
            "total": len(overlaps),
            "source": "database",
        }
    except Exception as e:
        logger.debug("travel_overlap_db_fallback", error=str(e))
        return None
    finally:
        db.close()


def _try_real_connections(user_id: Optional[str], min_score: int = 40) -> Optional[Dict]:
    """Try to query real compatible nomads from the database."""
    if not user_id:
        return None

    db = _get_db_session()
    if not db:
        return None

    try:
        from backend.services.social_matching import social_matching_service
        matches = social_matching_service.find_compatible_nomads(db, user_id, min_score=min_score)

        if not matches:
            return None

        suggestions = []
        for match in matches[:5]:
            suggestions.append({
                "name": match.get("name", "Anonymous"),
                "flag": "",
                "role": match.get("profession", ""),
                "compatibility_score": match.get("compatibility", {}).get("score", 50),
                "shared_interests": match.get("compatibility", {}).get("breakdown", {}).get("interests", {}).get("common", []),
                "bio_preview": match.get("bio", ""),
                "reason": f"Compatibility score: {match.get('compatibility', {}).get('score', '?')}",
                "is_real": True,
            })

        return {
            "suggestions": suggestions,
            "total": len(matches),
            "source": "database",
        }
    except Exception as e:
        logger.debug("connections_db_fallback", error=str(e))
        return None
    finally:
        db.close()


def _try_live_hub_stats(city_key: str) -> Optional[Dict]:
    """Try to compute live hub stats from NomadProfile table."""
    db = _get_db_session()
    if not db:
        return None

    try:
        from sqlalchemy import func
        from backend import models

        # Count active profiles with location in this city
        count = db.query(func.count(models.NomadProfile.id)).join(
            models.NomadLocation,
            models.NomadProfile.user_id == models.NomadLocation.user_id,
        ).filter(
            models.NomadLocation.city.ilike(f"%{city_key}%"),
        ).scalar()

        if count and count > 0:
            return {"active_nomads": count, "source": "database"}
        return None
    except Exception as e:
        logger.debug("hub_stats_db_fallback", error=str(e))
        return None
    finally:
        db.close()


# --- Public API ---


def find_travel_buddies(
    city: str,
    travel_dates: Optional[str] = None,
    interests: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Find nomads with overlapping travel plans in the same city.
    Production: queries NomadProfile + TravelPlan tables via social_matching.
    Fallback: generates curated matches from hub profile data.
    """
    city_key = city.lower().strip()
    hub = None
    for key, data in HUB_PROFILES.items():
        if key in city_key or city_key in key:
            hub = data
            city_key = key
            break

    if not hub:
        return {
            "city": city,
            "data_available": False,
            "message": f"No community data for {city} yet. We have data for: Bali, Chiang Mai, Lisbon, Mexico City.",
        }

    # Try real DB query first
    real_data = _try_real_travel_overlaps(city_key, user_id)
    if real_data and real_data["matches"]:
        return {
            "city": city.title(),
            "total_nomads_here": hub["active_nomads"],
            "matches_found": len(real_data["matches"]),
            "matches": real_data["matches"],
            "source": "live",
            "tip": "Send a connection request to start chatting. We'll introduce you via the app.",
        }

    # Fallback: curated profiles from hub data
    import random
    random.seed(hash(city_key + str(interests)))

    sample_names = [
        ("Sarah K.", "🇺🇸", "Full-stack dev"),
        ("Lukas M.", "🇩🇪", "UX designer"),
        ("Yuki T.", "🇯🇵", "Product manager"),
        ("Emma L.", "🇬🇧", "Content creator"),
        ("Carlos R.", "🇲🇽", "Startup founder"),
        ("Anja V.", "🇳🇱", "Freelance writer"),
        ("Raj P.", "🇮🇳", "Data scientist"),
        ("Sophie C.", "🇫🇷", "Digital marketer"),
        ("Mike W.", "🇦🇺", "Photographer"),
        ("Nina S.", "🇸🇪", "iOS developer"),
    ]

    num_matches = random.randint(3, 7)
    matches = []
    for i in range(num_matches):
        name, flag, role = sample_names[i % len(sample_names)]
        compatibility = random.randint(55, 95)
        shared = random.sample(hub["top_interests"], min(2, len(hub["top_interests"])))
        matches.append({
            "name": f"{name}",
            "flag": flag,
            "role": role,
            "compatibility": compatibility,
            "shared_interests": shared,
            "status": random.choice(["here now", "arriving soon", "here for 2 more weeks"]),
        })

    matches.sort(key=lambda x: -x["compatibility"])

    return {
        "city": city.title(),
        "total_nomads_here": hub["active_nomads"],
        "matches_found": len(matches),
        "matches": matches,
        "source": "curated",
        "tip": "Send a connection request to start chatting. We'll introduce you via the app.",
    }


def suggest_connections(
    user_interests: List[str],
    user_profession: str = "",
    city: Optional[str] = None,
    min_compatibility: int = 40,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Suggest compatible nomads based on interests and profession.
    Production: queries NomadProfile via social_matching with embedding similarity.
    Fallback: scores against curated archetype profiles.
    """
    # Try real DB query first
    real_data = _try_real_connections(user_id, min_score=min_compatibility)
    if real_data and real_data["suggestions"]:
        return {
            "query": {"interests": user_interests, "profession": user_profession},
            "suggestions": real_data["suggestions"],
            "total_found": real_data["total"],
            "source": "live",
            "tip": "Tap any profile to view full details and send a connection request.",
        }

    # Fallback: curated archetype profiles
    import random
    random.seed(hash(str(user_interests) + user_profession))

    archetypes = [
        {"name": "Alex T.", "flag": "🇺🇸", "role": "Backend Engineer", "interests": ["coding", "surfing", "startup"], "bio": "Building a SaaS from Bali. Love evening surf sessions."},
        {"name": "Maria G.", "flag": "🇪🇸", "role": "UX Researcher", "interests": ["design", "yoga", "cooking"], "bio": "Remote UX lead. Passionate about wellness and Spanish cooking."},
        {"name": "Tom H.", "flag": "🇬🇧", "role": "Freelance Writer", "interests": ["writing", "coffee", "trekking"], "bio": "Travel journalist and coffee snob. Always hunting the best café."},
        {"name": "Aiko S.", "flag": "🇯🇵", "role": "Product Designer", "interests": ["design", "photography", "food"], "bio": "Designing beautiful products by day, photographing street food by night."},
        {"name": "Priya M.", "flag": "🇮🇳", "role": "Data Analyst", "interests": ["data", "yoga", "startups"], "bio": "ML engineer turned nomad. Yoga every morning, Python every afternoon."},
        {"name": "Felix N.", "flag": "🇩🇪", "role": "Indie Hacker", "interests": ["coding", "entrepreneurship", "fitness"], "bio": "Bootstrapping 3 micro-SaaS products. Gym + sauna = my therapy."},
    ]

    suggestions = []
    for person in archetypes:
        # Exact interest matches (30 pts each)
        shared = set(user_interests) & set(person["interests"])
        score = len(shared) * 30

        # Partial interest matches (10 pts each)
        for ui in user_interests:
            for pi in person["interests"]:
                if ui not in shared and pi not in shared:
                    if ui.lower() in pi.lower() or pi.lower() in ui.lower():
                        score += 10

        # Profession match bonus
        prof_match = user_profession.lower() in person["role"].lower() or any(
            w in person["role"].lower() for w in user_profession.lower().split()
        )
        if prof_match:
            score += 15

        # Small random variance
        score += random.randint(5, 20)
        score = min(score, 98)

        if score >= min_compatibility:
            suggestions.append({
                "name": person["name"],
                "flag": person["flag"],
                "role": person["role"],
                "compatibility_score": score,
                "shared_interests": list(shared),
                "bio_preview": person["bio"],
                "reason": f"{'Same profession + ' if prof_match else ''}shared interest in {', '.join(shared)}" if shared else "Complementary profile",
            })

    suggestions.sort(key=lambda x: -x["compatibility_score"])

    result = {
        "query": {"interests": user_interests, "profession": user_profession},
        "suggestions": suggestions[:5],
        "total_found": len(suggestions),
        "source": "curated",
        "tip": "Tap any profile to view full details and send a connection request.",
    }

    if len(suggestions) == 0:
        result["message"] = "No matches at this threshold. Try broadening your interests or lowering the compatibility requirement."

    return result


def curate_local_events(
    city: str,
    interests: Optional[List[str]] = None,
    event_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get curated local events and meetups for a destination.
    Filters by interests and event type if specified.
    """
    city_key = city.lower().strip()
    events = None
    for key, ev_list in LOCAL_EVENTS.items():
        if key in city_key or city_key in key:
            events = ev_list
            city_key = key
            break

    if not events:
        return {
            "city": city,
            "data_available": False,
            "message": f"No event data for {city} yet. We curate events for: Bali, Chiang Mai, Lisbon, Mexico City.",
        }

    # Filter by interests
    if interests:
        scored = []
        for event in events:
            match_count = sum(1 for i in interests if any(i.lower() in bf.lower() for bf in event["best_for"]))
            scored.append((event, match_count))
        scored.sort(key=lambda x: -x[1])
        events = [e for e, s in scored]

    # Filter by type
    if event_type:
        events = [e for e in events if event_type.lower() in e["type"].lower()]

    return {
        "city": city.title(),
        "events": events,
        "total": len(events),
        "tip": "Events update weekly. Check the NomadNest community tab for RSVPs and group chats.",
    }


def community_pulse(
    city: str,
) -> Dict[str, Any]:
    """
    Get quick community stats for a destination hub.
    Production: queries live NomadProfile aggregations.
    Fallback: curated hub profile data.
    """
    city_key = city.lower().strip()
    hub = None
    for key, data in HUB_PROFILES.items():
        if key in city_key or city_key in key:
            hub = data
            city_key = key
            break

    if not hub:
        return {
            "city": city,
            "data_available": False,
            "message": f"No community data for {city}. Available hubs: Bali, Chiang Mai, Lisbon, Mexico City.",
        }

    # Try live stats from DB
    live_stats = _try_live_hub_stats(city_key)

    return {
        "city": city.title(),
        "active_nomads": live_stats["active_nomads"] if live_stats else hub["active_nomads"],
        "avg_stay_days": hub["avg_stay_days"],
        "avg_age": hub["avg_age"],
        "nationalities": hub["nationalities_count"],
        "top_nationalities": hub["top_nationalities"],
        "top_professions": hub["top_professions"],
        "top_interests": hub["top_interests"],
        "gender_split": hub["gender_split"],
        "vibe": hub["community_vibe"],
        "source": "live" if live_stats else "curated",
        "tip": "Join the community tab to connect with nomads at this hub.",
    }
