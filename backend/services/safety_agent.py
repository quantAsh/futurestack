"""
Safety Agent — Travel Safety, Health & Emergency Support for Nomads.

Provides the Concierge with safety tools:
- Destination safety overview with real ratings
- Emergency contacts (police, ambulance, hospitals)
- Common scam alerts and prevention tips
- Health advisories (vaccinations, water, insurance)
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.safety_agent")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.safety_agent")

from typing import Dict, Any, Optional, List
from backend.services.nomad_data import SAFETY_DATA, EMERGENCY_CONTACTS, SCAM_DATA, HEALTH_DATA






def get_safety_brief(
    city: str,
) -> Dict[str, Any]:
    """
    Get a comprehensive safety overview for a destination.
    """
    city_key = city.lower().strip()
    safety = None
    for key, data in SAFETY_DATA.items():
        if key in city_key or city_key in key:
            safety = data
            break

    if not safety:
        return {
            "city": city,
            "data_available": False,
            "message": f"No safety data for {city}. Available: Bali, Chiang Mai, Lisbon, Mexico City.",
            "generic_tips": [
                "Research the destination on travel advisory sites before going",
                "Register with your embassy for travel alerts",
                "Keep copies of passport and insurance docs in the cloud",
                "Use ride-hailing apps instead of unmarked taxis",
            ],
        }

    return safety


def emergency_contacts(
    city: str,
) -> Dict[str, Any]:
    """
    Get emergency contacts, hospitals, and embassy info for a city.
    """
    city_key = city.lower().strip()
    contacts = None
    for key, data in EMERGENCY_CONTACTS.items():
        if key in city_key or city_key in key:
            contacts = data
            break

    if not contacts:
        return {
            "city": city,
            "data_available": False,
            "message": f"No emergency data for {city}. Available: Bali, Chiang Mai, Lisbon, Mexico City.",
            "generic": {
                "police": "Check local directory",
                "ambulance": "Check local directory",
                "tip": "Save the local emergency number in your phone BEFORE you arrive.",
            },
        }

    return {
        "city": city.title(),
        **contacts,
        "tip": "Save these numbers in your phone on day 1. Screenshot this and keep offline.",
    }


def scam_alerts(
    city: str,
) -> Dict[str, Any]:
    """
    Get common scams and prevention tips for a destination.
    """
    city_key = city.lower().strip()
    scams = None
    for key, data in SCAM_DATA.items():
        if key in city_key or city_key in key:
            scams = data
            break

    if not scams:
        return {
            "city": city,
            "data_available": False,
            "message": f"No scam data for {city}. Available: Bali, Chiang Mai, Lisbon, Mexico City.",
            "universal_tips": [
                "If a deal seems too good to be true, it is",
                "Use official transport apps, never unmarked vehicles",
                "Don't give your passport to anyone except immigration officers",
                "Avoid unsolicited 'helpful' strangers at tourist sites",
            ],
        }

    high_risk = [s for s in scams["scams"] if s["risk"] == "High"]

    return {
        "city": city.title(),
        "total_scams": len(scams["scams"]),
        "high_risk_count": len(high_risk),
        "scams": scams["scams"],
        "top_alert": high_risk[0] if high_risk else None,
        "golden_rules": [
            "Never take unmarked taxis — use ride-hailing apps",
            "If someone approaches you unsolicited, be cautious",
            "Photo everything (rentals, receipts, agreements)",
            "Trust your gut — if it feels off, walk away",
        ],
    }


def health_advisories(
    city: str,
) -> Dict[str, Any]:
    """
    Get health advisories, vaccination info, and insurance tips for a destination.
    """
    city_key = city.lower().strip()
    health = None
    for key, data in HEALTH_DATA.items():
        if key in city_key or city_key in key:
            health = data
            break

    if not health:
        return {
            "city": city,
            "data_available": False,
            "message": f"No health data for {city}. Available: Bali, Chiang Mai, Lisbon, Mexico City.",
            "generic_tips": [
                "Check CDC travel health notices for your destination",
                "Get travel insurance BEFORE you leave",
                "Pack a basic first-aid kit",
                "Ask about tap water safety on arrival",
            ],
        }

    return {
        "city": city.title(),
        **health,
        "disclaimer": "This is general guidance, not medical advice. Consult a travel health clinic before your trip.",
    }
