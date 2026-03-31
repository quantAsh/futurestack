"""
Relocation Agent — End-to-End Move Management Between Destinations.

Helps nomads plan seamless transitions between cities:
- Full relocation planning (flights, accommodation overlap, admin tasks)
- Flight cost/duration estimates between nomad hubs
- Personalized moving checklists based on destination
- Visa timeline tracking and exit planning
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.relocation_agent")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.relocation_agent")

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from backend.services.nomad_data import FLIGHT_ROUTES, SETUP_CHECKLISTS, COST_DATA as _COST_DATA_REF
from backend.services.nomad_data import FLIGHT_ROUTES, SETUP_CHECKLISTS




def plan_relocation(
    from_city: str,
    to_city: str,
    move_date: Optional[str] = None,
    budget_tier: str = "moderate",
) -> Dict[str, Any]:
    """
    Generate a comprehensive relocation plan between two nomad hubs.
    Covers flights, accommodation overlap, setup tasks, and costs.
    """
    from_key = from_city.lower().strip()
    to_key = to_city.lower().strip()

    # Get flight info
    flight = _get_flight_info(from_key, to_key)

    # Get setup checklist
    checklist = None
    for key, data in SETUP_CHECKLISTS.items():
        if key in to_key or to_key in key:
            checklist = data
            to_key = key
            break

    # Monthly cost estimates by destination (self-contained — avoids cross-import)
    _MONTHLY_COSTS = {
        "bali": {"budget": 1200, "moderate": 1800, "luxury": 2800},
        "chiang mai": {"budget": 800, "moderate": 1200, "luxury": 2000},
        "lisbon": {"budget": 1800, "moderate": 2500, "luxury": 3500},
        "mexico city": {"budget": 1200, "moderate": 1800, "luxury": 2800},
        "bangkok": {"budget": 900, "moderate": 1500, "luxury": 2700},
        "barcelona": {"budget": 2000, "moderate": 3000, "luxury": 4800},
    }
    dest_cost = None
    for key, cost_tiers in _MONTHLY_COSTS.items():
        if key in to_key or to_key in key:
            dest_cost = cost_tiers
            break

    monthly_cost = dest_cost.get(budget_tier, 1800) if dest_cost else 1800
    setup_cost = _estimate_setup_cost(to_key)

    plan = {
        "from": from_city.title(),
        "to": to_city.title(),
        "move_date": move_date or "Flexible",
        "flight": flight,
        "accommodation": {
            "tip": "Book 3-5 nights at arrival destination before finding long-term stay",
            "overlap_days": 3,
            "estimated_temp_stay": f"${flight.get('avg_cost', 150) // 3}/night for 3 nights" if flight else "$50/night for 3 nights",
        },
        "setup_checklist": checklist or _generic_checklist(to_city),
        "estimated_costs": {
            "flight": f"${flight['cost_range'][0]}-${flight['cost_range'][1]}" if flight and "cost_range" in flight else "$300-600",
            "first_month": f"${monthly_cost + setup_cost}",
            "monthly_ongoing": f"${monthly_cost}",
            "setup_costs": f"${setup_cost}",
            "setup_breakdown": {
                "sim_card": 10,
                "first_groceries": 50,
                "transport_setup": 60,
                "coworking_first_month": 100 if budget_tier != "budget" else 0,
                "misc_essentials": 80,
            },
        },
        "timeline": _build_timeline(from_city, to_city, move_date),
        "tips": [
            f"Allow 2-3 days overlap between your {from_city.title()} checkout and {to_city.title()} lease",
            "Ship heavy items via SendMyBag ($40-80) instead of checked baggage",
            "Cancel/transfer subscriptions: coworking, gym, SIM card",
            f"Update your NomadNest profile location to {to_city.title()} for community matching",
        ],
    }

    return plan


def estimate_flights(
    from_city: str,
    to_city: str,
) -> Dict[str, Any]:
    """
    Get flight cost and duration estimates between two cities.
    """
    from_key = from_city.lower().strip()
    to_key = to_city.lower().strip()

    flight = _get_flight_info(from_key, to_key)

    if flight:
        return {
            "from": from_city.title(),
            "to": to_city.title(),
            **flight,
            "booking_tips": [
                "Use Google Flights with flexible dates for best prices",
                "Set price alerts — fares drop 20-30% during flash sales",
                "Book 6-8 weeks ahead for optimal pricing",
                "Consider budget carriers for short-haul (< 5 hrs)",
            ],
        }

    return {
        "from": from_city.title(),
        "to": to_city.title(),
        "data_available": False,
        "estimated_cost": "$300-600",
        "message": f"No specific route data for {from_city} → {to_city}. Check Google Flights or Kiwi.com for current prices.",
        "booking_tips": [
            "Use Google Flights with flexible dates",
            "Check Kiwi.com for multi-city routes",
            "Consider nearby airports for cheaper fares",
        ],
    }


def moving_checklist(
    destination: str,
    from_city: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get a personalized moving/setup checklist for a destination.
    """
    dest_key = destination.lower().strip()
    checklist = None
    for key, data in SETUP_CHECKLISTS.items():
        if key in dest_key or dest_key in key:
            checklist = data
            dest_key = key
            break

    if checklist:
        total_items = sum(len(v) for v in checklist.values())
        return {
            "destination": destination.title(),
            "checklist": checklist,
            "total_items": total_items,
            "categories": list(checklist.keys()),
            "tip": "Save this checklist to your NomadNest dashboard for easy tracking.",
        }

    return {
        "destination": destination.title(),
        "checklist": _generic_checklist(destination),
        "total_items": 12,
        "data_available": False,
        "message": f"Generic checklist for {destination}. Curated checklists available for: Bali, Chiang Mai, Lisbon, Mexico City.",
    }


def visa_timeline(
    destinations: List[Dict[str, Any]],
    nationality: str = "United States",
) -> Dict[str, Any]:
    """
    Build a visa timeline across multiple destinations.
    Input: [{"city": "Lisbon", "days": 85}, {"city": "Bali", "days": 30}, ...]
    """
    # Lightweight visa lookup (self-contained — avoids cross-import to agent_tools)
    _VISA_INFO = {
        "bali": {"visa_required": False, "allowed_stay": "30 days (VOA, extendable to 60)", "notes": "B211A for long-term"},
        "chiang mai": {"visa_required": False, "allowed_stay": "30 days (visa-exempt) or 60 days (tourist visa)", "notes": "Extendable 30 days at immigration"},
        "bangkok": {"visa_required": False, "allowed_stay": "30 days (visa-exempt)", "notes": "Same rules as Chiang Mai"},
        "lisbon": {"visa_required": False, "allowed_stay": "90 days in 180 (Schengen)", "notes": "D7 digital nomad visa available", "nomad_visa": "D7/D8 Digital Nomad Visa"},
        "barcelona": {"visa_required": False, "allowed_stay": "90 days in 180 (Schengen)", "notes": "Same Schengen zone as Portugal"},
        "mexico city": {"visa_required": False, "allowed_stay": "180 days (FMM)", "notes": "Very generous for US/CAN/EU nationals"},
    }

    timeline = []
    warnings = []
    schengen_total = 0

    schengen_cities = {"lisbon", "porto", "barcelona", "berlin", "paris", "amsterdam", "prague"}

    for dest in destinations:
        city = dest.get("city", "")
        days = dest.get("days", 30)
        city_key = city.lower().strip()

        # Look up visa info
        visa = {}
        for key, info in _VISA_INFO.items():
            if key in city_key or city_key in key:
                visa = info
                break

        # Check if days exceed allowed stay
        allowed = visa.get("allowed_stay", "")
        if "30 days" in allowed and days > 30:
            visa["warning"] = f"Stay of {days} days exceeds 30-day limit. Extension or different visa needed."
        elif "90 days" in allowed and days > 90:
            visa["warning"] = f"Stay of {days} days exceeds 90-day Schengen limit."

        # Track Schengen
        is_schengen = city_key in schengen_cities
        if is_schengen:
            schengen_total += days

        entry = {
            "city": city,
            "days": days,
            "visa_required": visa.get("visa_required", True),
            "allowed_stay": visa.get("allowed_stay", "Check embassy"),
            "notes": visa.get("notes", ""),
            "is_schengen": is_schengen,
        }

        if visa.get("warning"):
            entry["warning"] = visa["warning"]
            warnings.append(f"⚠️ {city}: {visa['warning']}")

        if visa.get("nomad_visa"):
            entry["nomad_visa_option"] = visa["nomad_visa"]

        timeline.append(entry)

    # Schengen aggregate warning
    if schengen_total > 75:
        warnings.append(
            f"🔴 Schengen alert: {schengen_total} days planned across Schengen zone. "
            f"Limit is 90 days in any 180-day period. {'ALREADY EXCEEDED!' if schengen_total > 90 else f'{90 - schengen_total} days remaining.'}"
        )

    return {
        "nationality": nationality,
        "timeline": timeline,
        "schengen_days_total": schengen_total if schengen_total > 0 else None,
        "schengen_remaining": max(0, 90 - schengen_total) if schengen_total > 0 else None,
        "warnings": warnings,
        "tip": "Always carry printed visa confirmation and proof of onward travel.",
    }


# --- Helper Functions ---

def _get_flight_info(from_key: str, to_key: str) -> Optional[Dict]:
    """Look up flight info in both directions."""
    # Try direct match
    for (f, t), info in FLIGHT_ROUTES.items():
        if (f in from_key or from_key in f) and (t in to_key or to_key in t):
            return {**info, "avg_cost": sum(info["cost_range"]) // 2}
        if (f in to_key or to_key in f) and (t in from_key or from_key in t):
            return {**info, "avg_cost": sum(info["cost_range"]) // 2}
    return None


def _estimate_setup_cost(dest_key: str) -> int:
    """Estimate one-time setup costs for a destination."""
    costs = {
        "bali": 200, "chiang mai": 150, "lisbon": 300,
        "mexico city": 200, "bangkok": 180, "barcelona": 350,
    }
    return costs.get(dest_key, 250)


def _build_timeline(from_city: str, to_city: str, move_date: Optional[str]) -> List[Dict]:
    """Build a move timeline."""
    return [
        {"phase": "📋 Pre-move", "when": "2-4 weeks before", "tasks": ["Book flights", "Arrange first accommodation", "Start visa process"]},
        {"phase": "📦 Pack & cancel", "when": "1 week before", "tasks": ["Cancel coworking/gym", "Pack essentials", "Return scooter/keys"]},
        {"phase": "✈️ Travel day", "when": move_date or "Move day", "tasks": [f"Fly {from_city.title()} → {to_city.title()}", "Arrive and check in"]},
        {"phase": "🏠 Setup", "when": "First 48 hours", "tasks": ["Get SIM card", "Withdraw local currency", "Scout neighborhood"]},
        {"phase": "⚡ Settle", "when": "First week", "tasks": ["Find coworking", "Set up payments", "Join community"]},
    ]


def _generic_checklist(destination: str) -> Dict[str, List[str]]:
    """Generic checklist for unknown destinations."""
    return {
        "before_arrival": [
            "Check visa requirements for your nationality",
            "Book first 3-5 nights of accommodation",
            "Download ride-hailing apps for the region",
            "Get travel insurance (SafetyWing or World Nomads)",
        ],
        "first_48_hours": [
            "Buy local SIM card at the airport",
            "Withdraw local currency from ATM",
            "Orient yourself — walk the main neighborhoods",
        ],
        "first_week": [
            "Find coworking spaces — try day passes",
            "Set up local payment methods",
            "Join local digital nomad community groups",
        ],
    }
