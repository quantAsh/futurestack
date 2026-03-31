"""
Scout Agent — Autonomous Research for Neighborhoods & Destinations.

Provides rich destination intelligence that the Concierge can call:
- Neighborhood recon (wifi, coworking, cafes, safety)
- Cost of living breakdown
- Nomad suitability scoring
- Seasonal travel intel
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.scout_agent")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.scout_agent")

from typing import Dict, Any, Optional, List
from datetime import date
from backend.services.nomad_data import DESTINATION_DATA



def get_destination_brief(
    location: str,
    travel_month: Optional[str] = None,
    budget_tier: str = "moderate",
    interests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a comprehensive destination brief for a location.
    
    This is the Scout Agent's primary tool — provides rich intel that the
    Concierge uses to make informed recommendations.
    """
    location_key = location.lower().strip()
    
    # Try to match against known destinations
    data = None
    for key, dest in DESTINATION_DATA.items():
        if key in location_key or location_key in key:
            data = dest
            break
        if dest["city"].lower() in location_key or location_key in dest["city"].lower():
            data = dest
            break
    
    if not data:
        return _generic_brief(location, travel_month, budget_tier)
    
    # Build the brief
    brief = {
        "city": data["city"],
        "country": data["country"],
        "nomad_score": data["nomad_score"],
    }
    
    # Cost of living
    col = data["cost_of_living"]
    budget_map = {
        "budget": col["total_budget_estimate"],
        "moderate": col["total_moderate_estimate"],
        "luxury": col["total_comfort_estimate"],
    }
    brief["cost_of_living"] = {
        "monthly_estimate": budget_map.get(budget_tier, col["total_moderate_estimate"]),
        "budget_tier": budget_tier,
        "breakdown": {
            "rent_1br": col["rent_1br_center"],
            "food": col["meal_midrange"] * 60,  # ~2 meals/day at mid-range
            "coworking": col["coworking_monthly"],
            "transport": col["transport_monthly"],
            "coffee": col["coffee"] * 30,
        },
        "vs_comparison": _cost_comparison(col["total_moderate_estimate"]),
    }
    
    # Weather for travel month
    if travel_month:
        month_key = travel_month[:3].lower()
        weather = data.get("weather_by_month", {}).get(month_key)
        if weather:
            brief["weather"] = {
                "month": travel_month,
                "temp_c": weather["temp_c"],
                "temp_f": round(weather["temp_c"] * 9/5 + 32),
                "rain": weather["rain"],
                "recommendation": weather["best_for"],
            }
    
    # Neighborhoods (recommend based on interests)
    neighborhoods = data.get("neighborhoods", {})
    if interests:
        # Score neighborhoods by interest match
        scored = []
        for name, hood in neighborhoods.items():
            score = sum(1 for i in interests if any(i.lower() in bf.lower() for bf in hood["best_for"]))
            scored.append((name, hood, score))
        scored.sort(key=lambda x: -x[2])
        best = scored[0] if scored else None
    else:
        best = list(neighborhoods.items())[0] if neighborhoods else None
        best = (best[0], best[1], 0) if best else None
    
    if best:
        hood = best[1]
        brief["recommended_neighborhood"] = {
            "name": best[0].replace("_", " ").title(),
            "vibe": hood["vibe"],
            "wifi_mbps": hood["wifi_avg_mbps"],
            "coworking": hood["coworking_spaces"],
            "cafe_scene": hood["cafe_scene"],
            "walkability": hood["walkability"],
            "safety": hood["safety"],
        }
    
    # All neighborhoods summary
    brief["neighborhoods"] = {
        name.replace("_", " ").title(): {
            "vibe": hood["vibe"],
            "wifi_mbps": hood["wifi_avg_mbps"],
            "safety": hood["safety"],
            "best_for": hood["best_for"],
        }
        for name, hood in neighborhoods.items()
    }
    
    # Internet
    brief["internet"] = data.get("internet", {})
    
    # Visa
    brief["visa"] = data.get("visa", {})
    
    # Highlights & watch-outs
    brief["highlights"] = data.get("highlights", [])
    brief["watch_outs"] = data.get("watch_outs", [])
    
    logger.info("scout_brief_generated", city=data["city"], nomad_score=data["nomad_score"])
    return brief


def compare_destinations(
    locations: List[str],
    budget_tier: str = "moderate",
) -> Dict[str, Any]:
    """
    Compare multiple destinations side by side.
    Used by the Concierge for "Should I go to Bali or Chiang Mai?" queries.
    """
    comparisons = []
    for loc in locations:
        brief = get_destination_brief(loc, budget_tier=budget_tier)
        comparisons.append(brief)
    
    if not comparisons:
        return {"error": "Could not find data for any of the specified locations."}
    
    return {
        "comparison": comparisons,
        "cheapest": min(comparisons, key=lambda x: x.get("cost_of_living", {}).get("monthly_estimate", float("inf"))).get("city", "Unknown"),
        "highest_nomad_score": max(comparisons, key=lambda x: x.get("nomad_score", 0)).get("city", "Unknown"),
        "best_internet": max(comparisons, key=lambda x: x.get("recommended_neighborhood", {}).get("wifi_mbps", 0)).get("city", "Unknown"),
    }


def _cost_comparison(monthly_cost: float) -> str:
    """Generate a relative cost comparison."""
    if monthly_cost < 1000:
        return "Very affordable — cheaper than 90% of nomad destinations"
    elif monthly_cost < 1500:
        return "Affordable — below average for digital nomad hubs"
    elif monthly_cost < 2000:
        return "Moderate — average for popular nomad cities"
    elif monthly_cost < 3000:
        return "Pricey — above average, but European quality of life"
    else:
        return "Expensive — premium destination, plan budget carefully"


def _generic_brief(location: str, travel_month: Optional[str], budget_tier: str) -> Dict[str, Any]:
    """Fallback for unknown destinations."""
    return {
        "city": location.title(),
        "country": "Unknown",
        "nomad_score": None,
        "data_available": False,
        "message": f"Detailed data for {location} is not yet in our database. "
                   f"We currently have rich intel for: Bali, Chiang Mai, Lisbon, Mexico City. "
                   f"Try the AI Concierge for general travel advice about {location}.",
        "tip": "Ask the concierge to search for accommodations — the OTA search works for any location.",
    }


# Singleton
scout_agent = None  # Lazy init not needed — functions are standalone
