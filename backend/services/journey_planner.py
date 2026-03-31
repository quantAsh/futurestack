"""
Journey Planner Service - AI-powered multi-city itinerary generation.
"""
import json
import structlog
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models

logger = structlog.get_logger("nomadnest.journey_planner")


def get_available_destinations(db: Session) -> List[Dict]:
    """Get all possible destinations from hubs and listings."""
    destinations = []

    # Get hubs
    hubs = db.query(models.Hub).all()
    for hub in hubs:
        destinations.append(
            {
                "type": "hub",
                "id": hub.id,
                "name": hub.name,
                "city": hub.name.split(" - ")[-1] if " - " in hub.name else "Unknown",
                "country": "Unknown",  # Would need to be added to Hub model
                "lat": hub.lat,
                "lng": hub.lng,
                "avg_cost": 2500,  # Default estimate
            }
        )

    # Get listings grouped by city
    listings = db.query(models.Listing).all()
    cities = {}
    for listing in listings:
        key = f"{listing.city}, {listing.country}"
        if key not in cities:
            cities[key] = {
                "type": "city",
                "city": listing.city,
                "country": listing.country,
                "listings": [],
                "avg_cost": 0,
            }
        cities[key]["listings"].append(listing)
        cities[key]["avg_cost"] = sum(
            l.price_usd for l in cities[key]["listings"]
        ) / len(cities[key]["listings"])

    destinations.extend(cities.values())
    return destinations


def generate_journey_plan(
    user_id: str,
    total_duration_days: int,
    total_budget_usd: float,
    start_date: datetime,
    preferences: Optional[Dict] = None,
) -> Dict:
    """
    Generate an AI-optimized journey plan using LLM.

    Feeds available destinations, budget, and preferences into Gemini/GPT
    to produce an intelligently curated multi-city itinerary.
    Falls back to rule-based logic if LLM call fails.
    """
    db = SessionLocal()
    try:
        destinations = get_available_destinations(db)

        if not destinations:
            return {"error": "No destinations available"}

        # --- LLM-Powered Planning ---
        try:
            plan = _generate_with_llm(
                destinations, total_duration_days, total_budget_usd,
                start_date, preferences,
            )
            if plan and plan.get("legs"):
                plan["method"] = "ai"
                return plan
        except Exception as e:
            logger.warning("llm_journey_fallback", error=str(e))

        # --- Fallback: Rule-based allocation ---
        return _generate_rule_based(
            destinations, total_duration_days, total_budget_usd,
            start_date, preferences,
        )

    finally:
        db.close()


def _generate_with_llm(
    destinations: List[Dict],
    total_duration_days: int,
    total_budget_usd: float,
    start_date: datetime,
    preferences: Optional[Dict] = None,
) -> Optional[Dict]:
    """Use LLM to generate an optimized journey plan."""
    from litellm import completion
    from backend.services.ai_concierge import get_model

    model = get_model("journey planning", has_tools=False)
    if not model:
        return None

    # Prepare destination summary for the LLM (keep it compact)
    dest_summaries = []
    for d in destinations[:30]:  # Limit to avoid token overflow
        city = d.get("city", d.get("name", "Unknown"))
        country = d.get("country", "Unknown")
        cost = d.get("avg_cost", "unknown")
        dtype = d.get("type", "city")
        dest_summaries.append(f"- {city}, {country} ({dtype}, ~${cost}/mo)")

    dest_text = "\n".join(dest_summaries)
    pref_text = json.dumps(preferences) if preferences else "None specified"

    prompt = f"""You are a digital nomad travel planner. Create an optimized multi-city journey plan.

AVAILABLE DESTINATIONS:
{dest_text}

CONSTRAINTS:
- Total duration: {total_duration_days} days
- Total budget: ${total_budget_usd}
- Start date: {start_date.strftime('%Y-%m-%d')}
- Preferences: {pref_text}

RULES:
- Select 2-5 cities that fit the budget and duration
- Allocate budget proportionally to each city's cost of living
- Each stop should be at least 7 days (nomads don't hop daily)
- Provide 3 specific, local highlights per city (not generic)
- Order cities logically to minimize travel distance
- Include 1-2 travel/transit days between cities

Return ONLY valid JSON in this exact format (no markdown):
{{
  "legs": [
    {{
      "order": 1,
      "city": "City Name",
      "country": "Country",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "duration_days": 14,
      "estimated_cost_usd": 1500,
      "highlights": ["Specific thing 1", "Specific thing 2", "Specific thing 3"]
    }}
  ],
  "tips": ["Tip 1", "Tip 2", "Tip 3"]
}}"""

    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    text = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    parsed = json.loads(text)
    legs = parsed.get("legs", [])

    if not legs:
        return None

    # Calculate summary
    last_end = legs[-1]["end_date"]
    return {
        "status": "generated",
        "method": "ai",
        "summary": {
            "total_days": total_duration_days,
            "total_budget_usd": total_budget_usd,
            "num_cities": len(legs),
            "start_date": start_date.isoformat(),
            "end_date": last_end,
        },
        "legs": legs,
        "tips": parsed.get("tips", [
            "Book early for better rates",
            "Consider travel days between cities",
            "Check visa requirements for each country",
        ]),
    }


def _generate_rule_based(
    destinations: List[Dict],
    total_duration_days: int,
    total_budget_usd: float,
    start_date: datetime,
    preferences: Optional[Dict] = None,
) -> Dict:
    """Fallback rule-based journey generation."""
    num_legs = min(len(destinations), max(2, total_duration_days // 14))
    days_per_leg = total_duration_days // num_legs
    budget_per_leg = total_budget_usd / num_legs

    selected = destinations[:num_legs]

    legs = []
    current_date = start_date
    for i, dest in enumerate(selected):
        leg_end = current_date + timedelta(days=days_per_leg)

        legs.append(
            {
                "order": i + 1,
                "city": dest.get("city", dest.get("name", "Unknown")),
                "country": dest.get("country", "Unknown"),
                "hub_id": dest.get("id") if dest.get("type") == "hub" else None,
                "start_date": current_date.isoformat(),
                "end_date": leg_end.isoformat(),
                "duration_days": days_per_leg,
                "estimated_cost_usd": budget_per_leg,
                "highlights": [
                    "Coworking space included",
                    "Community events",
                    "Local experiences",
                ],
            }
        )
        current_date = leg_end

    return {
        "status": "generated",
        "method": "rule_based",
        "summary": {
            "total_days": total_duration_days,
            "total_budget_usd": total_budget_usd,
            "num_cities": len(legs),
            "start_date": start_date.isoformat(),
            "end_date": current_date.isoformat(),
        },
        "legs": legs,
        "tips": [
            "Book early for better rates",
            "Consider travel days between cities",
            "Check visa requirements for each country",
        ],
    }


def create_journey_from_plan(user_id: str, plan: Dict, name: str = "My Journey") -> str:
    """Save a generated journey plan to the database."""
    db = SessionLocal()
    try:
        journey = models.Journey(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            status="planned",
            total_budget_usd=plan["summary"]["total_budget_usd"],
            start_date=datetime.fromisoformat(plan["summary"]["start_date"]),
            end_date=datetime.fromisoformat(plan["summary"]["end_date"]),
            preferences=json.dumps(plan.get("preferences", {})),
        )
        db.add(journey)

        # Add legs
        for leg_data in plan["legs"]:
            leg = models.JourneyLeg(
                id=str(uuid4()),
                journey_id=journey.id,
                hub_id=leg_data.get("hub_id"),
                city=leg_data["city"],
                country=leg_data["country"],
                start_date=datetime.fromisoformat(leg_data["start_date"]),
                end_date=datetime.fromisoformat(leg_data["end_date"]),
                order=leg_data["order"],
                estimated_cost_usd=leg_data["estimated_cost_usd"],
            )
            db.add(leg)

        db.commit()
        return journey.id

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
