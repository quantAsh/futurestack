"""
Agent Tools for the Agentic Concierge.
These are functions the LLM can call to take actions on behalf of the user.
"""
from uuid import uuid4
from datetime import datetime
from typing import Optional, List, Dict, Any


def _get_db():
    """Lazy import of database dependencies — avoids cascading import at module level."""
    from backend.database import SessionLocal
    from backend import models
    return SessionLocal, models


def _get_concierge_tools():
    """Lazy import of concierge booking tools."""
    from backend.services.concierge_tools import (
        initiate_booking,
        get_booking_status,
        get_booking_url,
        search_bookable_listings,
    )
    return initiate_booking, get_booking_status, get_booking_url, search_bookable_listings


# --- TOOL DEFINITIONS (for LLM function calling) ---
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "initiate_booking",
            "description": "Start an automated booking process for a listing. The AI agent will navigate to the booking site and attempt to complete the reservation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_id": {
                        "type": "string",
                        "description": "The ID of the listing to book"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests",
                        "default": 2
                    }
                },
                "required": ["listing_id", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_booking_status",
            "description": "Check the status of an in-progress booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job ID returned when booking was initiated"
                    }
                },
                "required": ["job_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": "Search for available listings/accommodations. Use this when user asks about places to stay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City to search in (e.g., 'Lisbon', 'Scottsdale')",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price in USD per month",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": "Create a booking for a listing. Use this when user wants to book accommodation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_id": {
                        "type": "string",
                        "description": "ID of the listing to book",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID of the user making the booking",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format",
                    },
                },
                "required": ["listing_id", "user_id", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_members",
            "description": "Find community members with specific skills or at a hub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hub_id": {"type": "string", "description": "Filter by hub ID"},
                    "skill": {
                        "type": "string",
                        "description": "Skill to search for (e.g., 'python', 'design')",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hubs",
            "description": "Get a list of all available community hubs/co-living spaces.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_all_platforms",
            "description": "Search accommodations across Airbnb, Booking.com, and Hostelworld in real-time. Returns scored and ranked results filtered for digital nomad relevance (co-living, remote work, long-stay, budget). Use this when the user wants to find or compare accommodation options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Destination city or region (e.g. 'Bali', 'Lisbon', 'Chiang Mai')",
                    },
                    "check_in": {
                        "type": "string",
                        "format": "date",
                        "description": "Check-in date in YYYY-MM-DD format",
                    },
                    "check_out": {
                        "type": "string",
                        "format": "date",
                        "description": "Check-out date in YYYY-MM-DD format",
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests (default 1)",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price per night in USD",
                    },
                },
                "required": ["location", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "destination_brief",
            "description": "Get a comprehensive destination intelligence brief for a city. Includes neighborhood-level wifi speeds, coworking spaces, cafe scene, safety scores, cost of living breakdown, visa info, and weather by month. Use this BEFORE or alongside accommodation search to give users rich context about a destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or destination (e.g. 'Bali', 'Chiang Mai', 'Lisbon', 'Mexico City')",
                    },
                    "travel_month": {
                        "type": "string",
                        "description": "Month of travel (e.g. 'April', 'December')",
                    },
                    "budget_tier": {
                        "type": "string",
                        "enum": ["budget", "moderate", "luxury"],
                        "description": "Budget level (default: moderate)",
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "User interests to match neighborhoods (e.g. ['surfing', 'yoga', 'nightlife'])",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_destinations",
            "description": "Compare multiple destinations side by side on cost of living, nomad score, internet speed, visa requirements, and weather. Use this when users ask 'Should I go to X or Y?' or 'Compare these cities for remote work.'",
            "parameters": {
                "type": "object",
                "properties": {
                    "locations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 2-4 cities to compare (e.g. ['Bali', 'Chiang Mai', 'Lisbon'])",
                    },
                    "budget_tier": {
                        "type": "string",
                        "enum": ["budget", "moderate", "luxury"],
                        "description": "Budget level for cost comparison",
                    },
                },
                "required": ["locations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Transfer conversation to human support for complex issues like disputes, high-value bookings, refunds, or technical problems the AI cannot resolve.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why escalation is needed (brief explanation)",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Urgency level of the issue",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_trip",
            "description": "Plan a multi-destination trip with cost estimates, visa checks, weather, and neighborhood recommendations for each leg. Use this when users say things like 'Plan my Q2 in Asia' or 'I want to visit Bali then Chiang Mai then Lisbon.'",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of destinations (e.g. ['Bali', 'Chiang Mai', 'Lisbon'])",
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Trip start date (YYYY-MM-DD). Defaults to 2 weeks from now.",
                    },
                    "duration_days": {
                        "type": "integer",
                        "description": "Total trip duration in days (default 30). Divided equally across destinations.",
                    },
                    "budget_tier": {
                        "type": "string",
                        "enum": ["budget", "moderate", "luxury"],
                        "description": "Budget level for cost estimates",
                    },
                    "nationality": {
                        "type": "string",
                        "description": "Passport nationality for visa checks (default: United States)",
                    },
                },
                "required": ["destinations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather information for a destination. Use this for trip planning and packing advice.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or destination (e.g., 'Lisbon, Portugal')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check weather for (YYYY-MM-DD). Defaults to today.",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_visa_requirements",
            "description": "Get visa and entry requirements for a destination based on passport nationality. Essential for digital nomad travel planning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination country (e.g., 'Portugal')",
                    },
                    "nationality": {
                        "type": "string",
                        "description": "Passport country (e.g., 'United States')",
                    },
                    "stay_duration": {
                        "type": "integer",
                        "description": "Planned stay in days",
                    },
                },
                "required": ["destination", "nationality"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_itinerary",
            "description": "Generate a personalized travel itinerary suggestion based on preferences, dates, and budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of destinations to include (e.g., ['Lisbon', 'Barcelona'])",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Trip start date (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Trip end date (YYYY-MM-DD)",
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Interests/preferences (e.g., ['coworking', 'surfing', 'nightlife'])",
                    },
                    "budget": {
                        "type": "string",
                        "enum": ["budget", "moderate", "luxury"],
                        "description": "Budget tier",
                    },
                },
                "required": ["destinations", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_preference",
            "description": "Save a user preference or important fact to long-term memory. Use this when the user explicitly tells you something to remember (e.g., 'I am vegan', 'I hate flying', 'My budget is $2k').",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference": {
                        "type": "string",
                        "description": "The fact or preference to remember",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["food", "travel", "accommodation", "budget", "general"],
                        "description": "Category of the preference",
                    },
                },
                "required": ["preference"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_search_watch",
            "description": "Create a proactive 'Sniper' watch for listings. The agent will monitor for new listings matching criteria and notify the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or destination to watch",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum monthly price",
                    },
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required amenities (e.g. ['wifi', 'pool'])",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_listings",
            "description": "Generate a side-by-side comparison of specific listings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of listing IDs to compare",
                    },
                },
                "required": ["listing_ids"],
            },
        },
    },
    # --- Host Copilot Tools ---
    {
        "type": "function",
        "function": {
            "name": "generate_auto_replies",
            "description": "Generate smart auto-reply drafts for common guest questions (wifi, check-in, extension, coworking, laundry, transport, kitchen). Use when a host asks for help with guest communication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_name": {
                        "type": "string",
                        "description": "Name of the listing",
                    },
                    "listing_city": {
                        "type": "string",
                        "description": "City where the listing is located",
                    },
                },
                "required": ["listing_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_smart_pricing",
            "description": "Get AI-powered pricing recommendations based on market data, seasonality, and occupancy. Tells the host if they're overpriced, underpriced, and suggests tactical adjustments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_name": {"type": "string", "description": "Name of the listing"},
                    "current_price": {"type": "number", "description": "Current monthly or nightly price in USD"},
                    "city": {"type": "string", "description": "City where the listing is"},
                    "occupancy_rate": {"type": "number", "description": "Current occupancy rate 0-1 (e.g. 0.7 = 70%)"},
                    "upcoming_vacancy_days": {"type": "integer", "description": "Number of upcoming unbooked days"},
                },
                "required": ["listing_name", "current_price", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_listing",
            "description": "Analyze a listing and suggest optimizations to increase bookings. Checks photos, amenities, description, title, and nomad-friendliness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_name": {"type": "string", "description": "Name of the listing"},
                    "description": {"type": "string", "description": "Current listing description text"},
                    "photos_count": {"type": "integer", "description": "Number of photos in the listing"},
                    "city": {"type": "string", "description": "City where the listing is"},
                },
                "required": ["listing_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_review_response",
            "description": "Draft a professional, personalized response to a guest review. Adjusts tone based on rating (grateful for positive, solution-oriented for negative).",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_name": {"type": "string"},
                    "rating": {"type": "integer", "description": "Guest rating 1-5"},
                    "review_text": {"type": "string", "description": "The guest's review text"},
                    "listing_name": {"type": "string"},
                },
                "required": ["guest_name", "rating", "review_text", "listing_name"],
            },
        },
    },
    # --- Booking Pipeline Tools (merged from concierge_tools) ---
    {
        "type": "function",
        "function": {
            "name": "get_booking_url",
            "description": "Get the external booking URL and availability info for a listing. Returns the direct booking link, price range, upcoming dates, and amenities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_id": {
                        "type": "string",
                        "description": "The ID of the listing to get booking info for",
                    },
                },
                "required": ["listing_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_bookable_listings",
            "description": "Search for listings that have online booking URLs available. Returns only bookable listings with direct links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City, country, or location to search in",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search for (e.g., 'wellness', 'yoga')",
                    },
                },
            },
        },
    },
    # --- Community Agent Tools ---
    {
        "type": "function",
        "function": {
            "name": "find_travel_buddies",
            "description": "Find other digital nomads who are in (or heading to) the same city at the same time. Returns compatibility scores and shared interests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to find nomads in"},
                    "travel_dates": {"type": "string", "description": "Optional date range (e.g., 'April 1-30')"},
                    "interests": {"type": "array", "items": {"type": "string"}, "description": "Optional interests to match on"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_connections",
            "description": "Suggest compatible nomads based on interests, profession, and compatibility scoring. Great for finding collaborators or friends.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_interests": {"type": "array", "items": {"type": "string"}, "description": "User's interests"},
                    "user_profession": {"type": "string", "description": "User's profession or role"},
                    "city": {"type": "string", "description": "Optional city filter"},
                    "min_compatibility": {"type": "integer", "description": "Minimum compatibility score (0-100)"},
                },
                "required": ["user_interests"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "curate_local_events",
            "description": "Get curated events, meetups, and activities happening at a destination. Filtered by interests and event type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to get events for"},
                    "interests": {"type": "array", "items": {"type": "string"}, "description": "Interests to filter events"},
                    "event_type": {"type": "string", "description": "Event type filter (networking, cultural, fitness, wellness)"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "community_pulse",
            "description": "Get community stats for a nomad hub — number of active nomads, top professions, interests, demographics, and vibe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to get community pulse for"},
                },
                "required": ["city"],
            },
        },
    },
    # --- Finance Agent Tools ---
    {
        "type": "function",
        "function": {
            "name": "estimate_trip_budget",
            "description": "Estimate the total budget for a multi-city trip with per-city and per-category breakdown (rent, food, coworking, transport, etc). Includes inter-city transport costs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinations": {"type": "array", "items": {"type": "string"}, "description": "List of cities"},
                    "days_per_destination": {"type": "array", "items": {"type": "integer"}, "description": "Days at each destination"},
                    "total_days": {"type": "integer", "description": "Total trip duration in days"},
                    "budget_tier": {"type": "string", "enum": ["budget", "moderate", "luxury"], "description": "Budget tier"},
                },
                "required": ["destinations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_cost_of_living",
            "description": "Side-by-side cost of living comparison for multiple nomad cities, with monthly totals, daily rates, and per-category breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cities": {"type": "array", "items": {"type": "string"}, "description": "Cities to compare"},
                    "budget_tier": {"type": "string", "enum": ["budget", "moderate", "luxury"], "description": "Budget tier"},
                },
                "required": ["cities"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_currency_tips",
            "description": "Practical tips for handling money in a destination — best payment methods, ATM advice, tipping culture, payment apps, and common pitfalls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country_or_currency": {"type": "string", "description": "Country name, city name, or currency code (e.g., 'Thailand', 'Bali', 'THB')"},
                },
                "required": ["country_or_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tax_residency_check",
            "description": "Check if your stays in various countries would trigger tax residency (typically 183 days). Returns alerts, warnings, and safe statuses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "countries_and_days": {
                        "type": "object",
                        "description": "Object mapping country names to number of days stayed, e.g. {'Portugal': 95, 'Thailand': 45}",
                    },
                },
                "required": ["countries_and_days"],
            },
        },
    },
    # --- Relocation Agent Tools ---
    {
        "type": "function",
        "function": {
            "name": "plan_relocation",
            "description": "Generate a comprehensive relocation plan between two cities — flights, costs, setup checklist, and timeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_city": {"type": "string", "description": "City you're moving from"},
                    "to_city": {"type": "string", "description": "City you're moving to"},
                    "move_date": {"type": "string", "description": "Target move date"},
                    "budget_tier": {"type": "string", "enum": ["budget", "moderate", "luxury"]},
                },
                "required": ["from_city", "to_city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_flights",
            "description": "Get flight cost and duration estimates between two nomad cities, with airline recommendations and booking tips.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_city": {"type": "string", "description": "Departure city"},
                    "to_city": {"type": "string", "description": "Arrival city"},
                },
                "required": ["from_city", "to_city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "moving_checklist",
            "description": "Get a personalized setup checklist for a destination — what to do before arrival, first 48 hours, first week, and ongoing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City you're moving to"},
                    "from_city": {"type": "string", "description": "City you're moving from (optional)"},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visa_timeline",
            "description": "Build a visa timeline for multi-destination travel. Tracks Schengen days across EU countries and warns about limits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "days": {"type": "integer"},
                            },
                        },
                        "description": "List of destinations with planned days",
                    },
                    "nationality": {"type": "string", "description": "User's nationality/passport country"},
                },
                "required": ["destinations"],
            },
        },
    },
    # --- Safety Agent Tools ---
    {
        "type": "function",
        "function": {
            "name": "get_safety_brief",
            "description": "Get an overall safety brief for a destination — ratings for crime, traffic, disasters, plus areas to avoid and safe neighborhoods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to get safety info for"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "emergency_contacts",
            "description": "Get local emergency numbers (police, ambulance), recommended hospitals, and embassy contacts for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to get emergency contacts for"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scam_alerts",
            "description": "Get common scams and how to avoid them at a destination. Includes risk level and prevention tips.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to get scam alerts for"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "health_advisories",
            "description": "Get health advisories — vaccinations, water safety, mosquito risks, insurance recommendations, and pharmacy info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City to get health info for"},
                },
                "required": ["city"],
            },
        },
    },
]
# --- TOOL IMPLEMENTATIONS ---


def search_listings(
    city: Optional[str] = None, max_price: Optional[float] = None
) -> List[dict]:
    """Search listings with optional filters."""
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        query = db.query(models.Listing)
        if city:
            query = query.filter(models.Listing.city.ilike(f"%{city}%"))
        if max_price:
            query = query.filter(models.Listing.price_usd <= max_price)

        results = query.limit(5).all()
        return [
            {
                "id": l.id,
                "name": l.name,
                "city": l.city,
                "country": l.country,
                "price_usd": l.price_usd,
                "property_type": l.property_type,
            }
            for l in results
        ]
    finally:
        db.close()


def create_booking(
    listing_id: str, user_id: str, start_date: str, end_date: str
) -> dict:
    """Create a new booking."""
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        # Verify listing exists
        listing = (
            db.query(models.Listing).filter(models.Listing.id == listing_id).first()
        )
        if not listing:
            return {"success": False, "error": f"Listing {listing_id} not found"}

        # Create booking
        booking = models.Booking(
            id=str(uuid4()),
            listing_id=listing_id,
            user_id=user_id,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
        )
        db.add(booking)
        db.commit()

        return {
            "success": True,
            "booking_id": booking.id,
            "listing_name": listing.name,
            "dates": f"{start_date} to {end_date}",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def find_members(
    hub_id: Optional[str] = None, skill: Optional[str] = None
) -> List[dict]:
    """Find community members."""
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        query = db.query(models.User)
        results = query.limit(10).all()

        members = [
            {"id": u.id, "name": u.name, "bio": u.bio or "No bio", "is_host": u.is_host}
            for u in results
        ]

        # Filter by skill in bio if specified (simple text search)
        if skill:
            members = [
                m for m in members if skill.lower() in (m.get("bio", "").lower())
            ]

        return members[:5]
    finally:
        db.close()


def get_hubs() -> List[dict]:
    """Get all hubs."""
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        hubs = db.query(models.Hub).all()
        return [
            {"id": h.id, "name": h.name, "type": h.type, "mission": h.mission}
            for h in hubs
        ]
    finally:
        db.close()


def search_all_platforms(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    max_price: Optional[float] = None,
) -> dict:
    """
    Execute multi-provider OTA search via Rust pipeline.
    
    Calls the nomadnest-crawler binary which scrapes Airbnb, Booking.com,
    and Hostelworld, applies niche filtering for digital nomad relevance,
    scores results across 5 dimensions, and returns ranked results as JSON.
    """
    import subprocess
    import os

    # Find the Rust binary
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    binary_paths = [
        os.path.join(project_root, "rust-crawler", "target", "release", "nomadnest-crawler"),
        os.path.join(project_root, "rust-crawler", "target", "debug", "nomadnest-crawler"),
    ]
    
    binary = None
    for path in binary_paths:
        if os.path.isfile(path):
            binary = path
            break
    
    if not binary:
        # Fallback to DB search if binary not available
        return _fallback_db_search(location, max_price)

    try:
        cmd = [
            binary,
            "--location", location,
            "--checkin", check_in,
            "--checkout", check_out,
            "--guests", str(guests),
            "--currency", "USD",
            "--json",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return {"error": f"OTA search failed: {result.stderr[:200]}"}

        # Parse JSON from stdout (skip log lines on stderr)
        import json as _json
        data = _json.loads(result.stdout)

        ranked = data.get("ranked", [])
        
        # Apply max_price filter if specified
        if max_price:
            ranked = [
                r for r in ranked
                if r.get("listing", {}).get("price_per_night") is not None
                and r["listing"]["price_per_night"] <= max_price
            ]

        # Format for LLM context — concise summaries the AI can reason about
        top_results = []
        for r in ranked[:10]:
            listing = r.get("listing", {})
            loc = listing.get("location", {})
            prop = listing.get("property", {})
            
            top_results.append({
                "rank": r.get("rank"),
                "name": listing.get("name", "Unknown"),
                "location": loc.get("address", location),
                "price_per_night": listing.get("price_per_night"),
                "total_price": listing.get("total_price"),
                "currency": listing.get("currency", "USD"),
                "rating": listing.get("rating"),
                "reviews": listing.get("reviews_count", 0),
                "property_type": prop.get("property_type", "unknown"),
                "amenities": prop.get("amenities", []),
                "nomad_friendly": prop.get("nomad_friendly", False),
                "url": listing.get("url", ""),
                "image_url": listing.get("image_url", ""),
                "source": listing.get("source", ""),
                "overall_score": r.get("overall_score", 0),
                "value_score": r.get("value_score", 0),
                "amenity_score": r.get("amenity_score", 0),
                "review_score": r.get("review_score", 0),
            })

        providers_succeeded = data.get("providers_succeeded", [])
        providers_queried = data.get("providers_queried", [])

        return {
            "summary": f"Found {data.get('total_found', 0)} stays from {', '.join(providers_succeeded) or 'no providers'}",
            "total_found": data.get("total_found", 0),
            "providers_searched": providers_queried,
            "providers_succeeded": providers_succeeded,
            "top_deals": top_results,
            "search_params": {
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
            },
        }

    except subprocess.TimeoutExpired:
        return {"error": "OTA search timed out (30s). Try a more specific location."}
    except Exception as e:
        return {"error": f"OTA search error: {str(e)}"}


def _fallback_db_search(location: str, max_price: Optional[float] = None) -> dict:
    """Fallback to database search when Rust binary is not available."""
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        query = db.query(models.Listing)
        if location:
            query = query.filter(
                (models.Listing.city.ilike(f"%{location}%")) |
                (models.Listing.country.ilike(f"%{location}%"))
            )
        if max_price:
            query = query.filter(models.Listing.price_usd <= max_price)

        listings = query.limit(10).all()
        return {
            "summary": f"Found {len(listings)} listings in database (OTA binary not available)",
            "total_found": len(listings),
            "providers_searched": ["NomadNest DB"],
            "providers_succeeded": ["NomadNest DB"] if listings else [],
            "top_deals": [
                {
                    "name": l.name,
                    "location": f"{l.city}, {l.country}",
                    "price_per_night": l.price_usd / 30 if l.price_usd else None,
                    "property_type": l.property_type,
                    "url": l.booking_url or "",
                    "source": "NomadNest",
                }
                for l in listings
            ],
        }
    finally:
        db.close()


def escalate_to_human(
    reason: str,
    priority: str = "medium",
    user_id: str = None,
    session_id: str = None,
    query: str = None,
    ai_context: dict = None
) -> dict:
    """Create an escalation request for human support and notify via WebSocket."""
    from backend.routers.escalations import create_escalation_request
    import asyncio
    
    if not user_id or not session_id:
        return {
            "success": True,
            "message": "I'm connecting you with a human specialist who can help with this.",
            "escalated": True,
            "reason": reason,
            "priority": priority
        }
    
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        # Create escalation record
        try:
            loop = asyncio.new_event_loop()
            escalation = loop.run_until_complete(
                create_escalation_request(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    query=query or "User request requiring human assistance",
                    reason=reason,
                    priority=priority,
                    ai_context=ai_context
                )
            )
            
            # Emit WebSocket notification to user + admins
            try:
                from backend.socket_server import emit_escalation_update, emit_escalation_to_admins
                escalation_data = {
                    "escalation_id": escalation.id,
                    "type": "escalation_created",
                    "reason": reason,
                    "priority": priority,
                    "status": "pending",
                    "query_preview": (query or "")[:100],
                }
                # Notify user
                loop.run_until_complete(
                    emit_escalation_update(user_id, escalation_data)
                )
                # Notify all admins
                loop.run_until_complete(
                    emit_escalation_to_admins(escalation_data)
                )
            except Exception as ws_err:
                # WebSocket notification is non-critical
                pass
            
            loop.close()
            return {
                "success": True,
                "escalation_id": escalation.id,
                "message": "I've connected you with our support team. A specialist will review your request shortly.",
                "escalated": True,
                "priority": priority
            }
        except Exception as e:
            return {
                "success": True,
                "message": "I'm connecting you with a human specialist who can help with this.",
                "escalated": True,
                "reason": reason,
                "priority": priority,
                "note": "Escalation logged for follow-up"
            }
    finally:
        db.close()


# Weather cache: {location_key: (timestamp, data)}
_weather_cache: dict = {}
_WEATHER_CACHE_TTL = 3600  # 1 hour

# Curated fallback weather (when API unavailable)
_WEATHER_FALLBACK = {
    "lisbon": {"temp": 22, "condition": "Sunny", "humidity": 65, "uv": 6},
    "bali": {"temp": 28, "condition": "Partly Cloudy", "humidity": 80, "uv": 8},
    "mexico city": {"temp": 24, "condition": "Clear", "humidity": 45, "uv": 7},
    "barcelona": {"temp": 20, "condition": "Sunny", "humidity": 60, "uv": 5},
    "chiang mai": {"temp": 30, "condition": "Hot", "humidity": 70, "uv": 9},
    "porto": {"temp": 18, "condition": "Partly Cloudy", "humidity": 70, "uv": 4},
    "medellin": {"temp": 22, "condition": "Pleasant", "humidity": 75, "uv": 6},
    "cape town": {"temp": 25, "condition": "Sunny", "humidity": 55, "uv": 8},
    "bangkok": {"temp": 32, "condition": "Hot", "humidity": 75, "uv": 9},
    "berlin": {"temp": 15, "condition": "Cloudy", "humidity": 70, "uv": 3},
}


def _fetch_openweather(location: str) -> Optional[dict]:
    """Call OpenWeatherMap API. Returns None on failure."""
    import os
    import time

    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        return None

    # Check cache
    cache_key = location.lower().strip()
    if cache_key in _weather_cache:
        ts, cached = _weather_cache[cache_key]
        if time.time() - ts < _WEATHER_CACHE_TTL:
            return cached

    try:
        import httpx
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = httpx.get(url, params={
            "q": location,
            "appid": api_key,
            "units": "metric",
        }, timeout=5.0)

        if resp.status_code != 200:
            return None

        data = resp.json()
        result = {
            "temp": round(data["main"]["temp"]),
            "condition": data["weather"][0]["main"] if data.get("weather") else "Unknown",
            "humidity": data["main"].get("humidity", 0),
            "uv": 5,  # OpenWeather free tier doesn't include UV; default
        }

        # Cache it
        _weather_cache[cache_key] = (time.time(), result)
        return result
    except Exception:
        return None


def get_weather(location: str, date: Optional[str] = None) -> dict:
    """
    Get weather information for a destination.
    Primary: OpenWeatherMap API (live, any city worldwide).
    Fallback: curated data for popular nomad hubs.
    """
    from datetime import date as d

    location_lower = location.lower().split(",")[0].strip()

    # Try live API first
    api_data = _fetch_openweather(location)
    if api_data:
        return {
            "location": location,
            "date": date or str(d.today()),
            "temperature_c": api_data["temp"],
            "temperature_f": round(api_data["temp"] * 9/5 + 32),
            "condition": api_data["condition"],
            "humidity": api_data["humidity"],
            "uv_index": api_data["uv"],
            "packing_tips": _get_packing_tips(api_data["temp"], api_data["condition"]),
            "source": "live",
        }

    # Fallback: curated data
    if location_lower in _WEATHER_FALLBACK:
        data = _WEATHER_FALLBACK[location_lower]
        return {
            "location": location,
            "date": date or str(d.today()),
            "temperature_c": data["temp"],
            "temperature_f": round(data["temp"] * 9/5 + 32),
            "condition": data["condition"],
            "humidity": data["humidity"],
            "uv_index": data["uv"],
            "packing_tips": _get_packing_tips(data["temp"], data["condition"]),
            "source": "curated",
        }

    # Unknown location, no API
    return {
        "location": location,
        "date": date or str(d.today()),
        "temperature_c": 23,
        "temperature_f": 73,
        "condition": "Mild",
        "humidity": 60,
        "uv_index": 5,
        "packing_tips": ["Light layers", "Sunglasses", "Umbrella"],
        "source": "default",
        "note": "Set OPENWEATHER_API_KEY for live weather data",
    }


def _get_packing_tips(temp: int, condition: str) -> List[str]:
    """Generate packing tips based on weather."""
    tips = []
    if temp > 25:
        tips.extend(["Light, breathable clothing", "Sunscreen SPF 50"])
    elif temp > 15:
        tips.extend(["Light layers", "Light jacket for evenings"])
    else:
        tips.extend(["Warm layers", "Jacket or coat"])
    
    if "rain" in condition.lower() or "cloud" in condition.lower():
        tips.append("Rain jacket or umbrella")
    if "sun" in condition.lower():
        tips.extend(["Sunglasses", "Hat"])
    
    return tips


def get_visa_requirements(
    destination: str,
    nationality: str,
    stay_duration: Optional[int] = None
) -> dict:
    """
    Get visa requirements for a destination.
    Covers US, EU, UK, Canadian, Australian nationalities.
    Advisory only — always verify with the destination's embassy.
    """
    # Schengen zone countries
    schengen_countries = [
        "portugal", "spain", "france", "germany", "italy", "netherlands",
        "belgium", "greece", "austria", "czech republic", "poland",
        "croatia", "sweden", "norway", "denmark", "finland", "hungary",
        "slovakia", "slovenia", "estonia", "latvia", "lithuania",
        "luxembourg", "malta", "iceland", "switzerland", "liechtenstein",
    ]

    # Nationalities that get Schengen visa-free (90/180)
    schengen_visa_free = [
        "united states", "american", "canadian", "canada",
        "british", "united kingdom", "uk",
        "australian", "australia",
    ]

    # Visa-free access by nationality group
    visa_free = {
        # US citizens
        "us": {
            "mexico": {"days": 180, "notes": "Tourist permit (FMM) on arrival"},
            "thailand": {"days": 30, "notes": "Visa-exempt, extendable 30 days at immigration"},
            "indonesia": {"days": 30, "notes": "Visa on arrival ($35), extendable 30 days"},
            "japan": {"days": 90, "notes": "Visa-exempt"},
            "south korea": {"days": 90, "notes": "K-ETA required ($10)"},
            "uk": {"days": 180, "notes": "Standard visitor visa-free"},
            "colombia": {"days": 90, "notes": "Tourist stamp on arrival, extendable"},
            "brazil": {"days": 90, "notes": "Tourist visa-free since 2024"},
        },
        # EU citizens (non-Schengen destinations)
        "eu": {
            "mexico": {"days": 180, "notes": "Tourist permit on arrival"},
            "thailand": {"days": 30, "notes": "Visa-exempt, extendable"},
            "indonesia": {"days": 30, "notes": "Visa on arrival, extendable"},
            "japan": {"days": 90, "notes": "Visa-exempt"},
            "south korea": {"days": 90, "notes": "Visa-exempt"},
            "uk": {"days": 180, "notes": "Visa-free for EU citizens"},
            "colombia": {"days": 90, "notes": "Tourist stamp on arrival"},
            "brazil": {"days": 90, "notes": "Visa-exempt"},
        },
        # UK citizens
        "uk": {
            "mexico": {"days": 180, "notes": "Tourist permit on arrival"},
            "thailand": {"days": 30, "notes": "Visa-exempt, extendable"},
            "indonesia": {"days": 30, "notes": "Visa on arrival, extendable"},
            "japan": {"days": 90, "notes": "Visa-exempt"},
            "south korea": {"days": 90, "notes": "Visa-exempt"},
            "colombia": {"days": 90, "notes": "Tourist stamp on arrival"},
            "brazil": {"days": 90, "notes": "Visa-exempt"},
        },
        # Canadian citizens
        "ca": {
            "mexico": {"days": 180, "notes": "Tourist permit on arrival"},
            "thailand": {"days": 30, "notes": "Visa-exempt, extendable"},
            "indonesia": {"days": 30, "notes": "Visa on arrival, extendable"},
            "japan": {"days": 90, "notes": "Visa-exempt (6 months)"},
            "south korea": {"days": 90, "notes": "Visa-exempt"},
            "uk": {"days": 180, "notes": "Visa-free"},
            "colombia": {"days": 90, "notes": "Tourist stamp on arrival"},
        },
        # Australian citizens
        "au": {
            "mexico": {"days": 180, "notes": "Tourist permit on arrival"},
            "thailand": {"days": 30, "notes": "Visa-exempt, extendable"},
            "indonesia": {"days": 30, "notes": "Visa on arrival, extendable"},
            "japan": {"days": 90, "notes": "Visa-exempt"},
            "south korea": {"days": 90, "notes": "Visa-exempt"},
            "uk": {"days": 180, "notes": "Visa-free"},
            "colombia": {"days": 90, "notes": "Tourist stamp on arrival"},
        },
    }

    # Digital nomad visas (nationality-independent)
    nomad_visas = {
        "portugal": {"name": "D7 Visa / D8 Digital Nomad", "duration": "1 year (renewable)", "min_income": 760},
        "spain": {"name": "Digital Nomad Visa", "duration": "1 year (renewable to 3)", "min_income": 2334},
        "croatia": {"name": "Digital Nomad Visa", "duration": "1 year", "min_income": 2232},
        "germany": {"name": "Freelance Visa", "duration": "up to 3 years", "min_income": "varies"},
        "thailand": {"name": "LTR Visa", "duration": "10 years", "min_income": 80000},
        "indonesia": {"name": "B211A (Remote Work)", "duration": "60 days (extendable)", "min_income": "varies"},
        "mexico": {"name": "Temporary Resident Visa", "duration": "1 year", "min_income": 2600},
        "greece": {"name": "Digital Nomad Visa", "duration": "1 year", "min_income": 3500},
        "estonia": {"name": "Digital Nomad Visa", "duration": "1 year", "min_income": 3504},
        "czech republic": {"name": "Živnostenský List (Trade License)", "duration": "1 year", "min_income": "varies"},
    }

    dest_lower = destination.lower().strip()
    nat_lower = nationality.lower().strip()

    # Detect nationality group
    nat_group = None
    if any(n in nat_lower for n in ["united states", "american", "u.s.", "usa"]):
        nat_group = "us"
    elif any(n in nat_lower for n in ["british", "united kingdom", "uk", "english", "scottish", "welsh"]):
        nat_group = "uk"
    elif any(n in nat_lower for n in ["canadian", "canada"]):
        nat_group = "ca"
    elif any(n in nat_lower for n in ["australian", "australia"]):
        nat_group = "au"
    elif any(n in nat_lower for n in [
        "german", "french", "spanish", "italian", "dutch", "portuguese",
        "belgian", "greek", "austrian", "polish", "swedish", "danish",
        "finnish", "norwegian", "irish", "european", "eu",
    ]):
        nat_group = "eu"

    result = {
        "destination": destination,
        "nationality": nationality,
        "stay_duration_requested": stay_duration,
    }

    # Check Schengen
    is_schengen_dest = dest_lower in schengen_countries
    is_schengen_free = any(n in nat_lower for n in schengen_visa_free) or nat_group == "eu"

    if is_schengen_dest and nat_group == "eu":
        # EU citizens have unlimited stay in Schengen
        result["visa_required"] = False
        result["allowed_stay"] = None
        result["notes"] = "EU citizen: freedom of movement — no visa or stay limit"
    elif is_schengen_dest and is_schengen_free:
        result["visa_required"] = False
        result["allowed_stay"] = 90
        result["notes"] = "Schengen Zone: 90 days within any 180-day period"
        if stay_duration and stay_duration > 90:
            result["warning"] = "Stay exceeds 90-day Schengen limit — consider a digital nomad visa"
    elif nat_group and dest_lower in visa_free.get(nat_group, {}):
        data = visa_free[nat_group][dest_lower]
        result["visa_required"] = False
        result["allowed_stay"] = data["days"]
        result["notes"] = data["notes"]
        if stay_duration and stay_duration > data["days"]:
            result["warning"] = f"Stay exceeds {data['days']}-day allowance — check extension options or nomad visa"
    elif nat_group:
        result["visa_required"] = True
        result["notes"] = "Visa likely required — check embassy for current requirements"
    else:
        result["visa_required"] = None
        result["notes"] = f"Unable to determine visa requirements for '{nationality}' to {destination}. Check your embassy."

    # Add nomad visa info if available
    if dest_lower in nomad_visas:
        nv = nomad_visas[dest_lower]
        result["nomad_visa"] = {
            "name": nv["name"],
            "duration": nv["duration"],
            "min_monthly_income_usd": nv["min_income"],
        }

    result["disclaimer"] = "⚠️ Advisory only — visa rules change frequently. Always verify with the destination's embassy or consulate before travel."

    return result


def suggest_itinerary(
    destinations: List[str],
    start_date: str,
    end_date: str,
    interests: Optional[List[str]] = None,
    budget: str = "moderate"
) -> dict:
    """
    Generate a personalized travel itinerary.
    """
    from datetime import datetime
    
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        total_days = (end - start).days
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}
    
    if total_days <= 0:
        return {"error": "End date must be after start date"}
    
    # Calculate days per destination
    days_per_dest = total_days // len(destinations)
    remainder = total_days % len(destinations)
    
    # Interest-based recommendations
    interest_activities = {
        "coworking": ["Find local coworking space", "Network at tech meetup"],
        "surfing": ["Morning surf session", "Sunset beach time"],
        "nightlife": ["Evening bar crawl", "Late-night dining"],
        "food": ["Local food tour", "Cooking class"],
        "culture": ["Museum visit", "Historical walking tour"],
        "nature": ["Day hike", "Nature reserve visit"],
        "wellness": ["Yoga class", "Spa day"],
    }
    
    budget_estimates = {
        "budget": {"daily": 50, "accommodation": "Hostel/Airbnb shared"},
        "moderate": {"daily": 100, "accommodation": "Private Airbnb/Boutique hotel"},
        "luxury": {"daily": 250, "accommodation": "Luxury hotel"},
    }
    
    budget_info = budget_estimates.get(budget, budget_estimates["moderate"])
    
    itinerary = []
    current_date = start
    
    for i, dest in enumerate(destinations):
        dest_days = days_per_dest + (1 if i < remainder else 0)
        
        activities = []
        for interest in (interests or ["culture", "food"]):
            if interest.lower() in interest_activities:
                activities.extend(interest_activities[interest.lower()])
        
        itinerary.append({
            "destination": dest,
            "arrival": current_date.strftime("%Y-%m-%d"),
            "departure": (current_date + __import__("datetime").timedelta(days=dest_days)).strftime("%Y-%m-%d"),
            "days": dest_days,
            "suggested_activities": activities[:4],
            "accommodation_type": budget_info["accommodation"],
        })
        
        current_date += __import__("datetime").timedelta(days=dest_days)
    
    return {
        "trip_summary": {
            "total_days": total_days,
            "destinations": len(destinations),
            "budget_tier": budget,
            "estimated_daily_cost_usd": budget_info["daily"],
            "estimated_total_cost_usd": budget_info["daily"] * total_days,
        },
        "itinerary": itinerary,
        "tips": [
            "Book accommodations 2-4 weeks in advance for best rates",
            "Check visa requirements for each destination",
            "Consider travel insurance for multi-country trips",
        ],
    }


def save_preference(preference: str, category: str = "general", user_id: str = "user-1") -> dict:
    """Save user preference to memory."""
    try:
        from backend.services.memory_service import memory_service
        success = memory_service.add_memory(
            user_id=user_id, 
            text=preference, 
            metadata={"type": "preference", "category": category}
        )
        return {"status": "success", "message": "Preference saved" if success else "Failed to save preference"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def create_search_watch(location: str, max_price: Optional[float] = None, amenities: Optional[List[str]] = None, user_id: str = "user-1") -> dict:
    """Create a search watch."""
    try:
        from backend.services.watcher_service import watcher_service
        criteria = {"location": location, "max_price": max_price, "amenities": amenities}
        watch = watcher_service.create_watch(user_id, criteria)
        return {"status": "success", "message": f"Sniper Watch active for {location}. I'll notify you if I find anything.", "watch_id": watch["id"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def compare_listings(listing_ids: List[str]) -> dict:
    """Generate comparison data for listings."""
    SessionLocal, models = _get_db()
    db = SessionLocal()
    try:
        # Fetch real listings from DB
        listings = db.query(models.Listing).filter(models.Listing.id.in_(listing_ids)).all()
        
        comparison_data = {
            "metrics": ["Price", "Rating", "Location", "Internet"],
            "listings": []
        }
        
        found_ids = set()
        
        # Process found real listings
        for l in listings:
            found_ids.add(l.id)
            # Safe defaults
            image = l.images[0] if l.images else f"https://source.unsplash.com/random/400x300/?house&sig={l.id}"
            
            # Extract metrics
            values = {
                "Price": f"${l.price_usd}/mo" if l.price_usd else "N/A",
                "Rating": "4.8/5" if not l.reviews else f"{l.reviews[0].rating}/5", # Placeholder until aggregation
                "Location": f"{l.city}, {l.country}",
                "Internet": "Fast WiFi" # Placeholder feature check
            }
            
            # Check features for internet
            if l.features:
                for f in l.features:
                    if "wifi" in f.lower() or "internet" in f.lower():
                        values["Internet"] = f
            
            comparison_data["listings"].append({
                "id": l.id,
                "name": l.name,
                "image": image,
                "url": l.booking_url or l.virtual_tour_url or f"https://example.com/listings/{l.id}",
                "values": values
            })
            
        # Mock fallback for missing IDs (development convenience)
        for lid in listing_ids:
            if lid not in found_ids:
                comparison_data["listings"].append({
                    "id": lid,
                    "name": f"Listing {lid[:4] if len(lid)>4 else lid}",
                    "image": f"https://source.unsplash.com/random/400x300/?interior,house&sig={lid}",
                    "url": "https://airbnb.com/rooms/12345678", # Mock external link
                    "values": {
                        "Price": f"${1000 + (len(lid)*100)}/mo",
                        "Rating": "4.9/5",
                        "Location": "Lisbon, Portugal",
                        "Internet": "100 Mbps"
                    }
                })
        
        return {"type": "comparison_card", "data": comparison_data}
    finally:
        db.close()


def plan_trip(
    destinations: List[str],
    start_date: str = "",
    duration_days: int = 30,
    budget_tier: str = "moderate",
    nationality: str = "United States",
) -> dict:
    """
    Multi-step trip planner that chains destination briefs, visa checks,
    and weather data for each leg. Returns a complete trip dossier.
    """
    from backend.services.scout_agent import get_destination_brief

    legs = []
    total_cost = 0
    warnings = []

    # Parse start date or default to 2 weeks from now
    try:
        from datetime import datetime as dt, timedelta
        if start_date:
            trip_start = dt.strptime(start_date, "%Y-%m-%d").date()
        else:
            trip_start = dt.now().date() + timedelta(days=14)
    except ValueError:
        trip_start = dt.now().date() + timedelta(days=14)

    days_per_dest = duration_days // max(len(destinations), 1)
    current_date = trip_start

    for i, dest in enumerate(destinations):
        # Get month name for weather
        travel_month = current_date.strftime("%B")
        leg_end = current_date + timedelta(days=days_per_dest)

        # Get destination brief
        brief = get_destination_brief(
            location=dest,
            travel_month=travel_month,
            budget_tier=budget_tier,
        )

        # Get visa info
        visa = get_visa_requirements(destination=dest, nationality=nationality)

        # Build leg
        monthly_cost = brief.get("cost_of_living", {}).get("monthly_estimate", 0)
        leg_cost = int(monthly_cost * days_per_dest / 30) if monthly_cost else 0
        total_cost += leg_cost

        leg = {
            "order": i + 1,
            "destination": brief.get("city", dest),
            "country": brief.get("country", ""),
            "dates": f"{current_date.strftime('%b %d')} — {leg_end.strftime('%b %d')}",
            "days": days_per_dest,
            "estimated_cost": leg_cost,
            "nomad_score": brief.get("nomad_score"),
            "neighborhood": brief.get("recommended_neighborhood", {}).get("name", ""),
            "weather": brief.get("weather", {}),
            "visa": visa if isinstance(visa, dict) else {},
            "highlights": brief.get("highlights", [])[:3],
            "watch_outs": brief.get("watch_outs", [])[:2],
        }
        legs.append(leg)

        # Check for visa-related warnings
        visa_days = visa.get("duration_days", 0) if isinstance(visa, dict) else 0
        if visa_days and days_per_dest > visa_days:
            warnings.append(
                f"⚠️ {dest}: your {days_per_dest}-day stay exceeds the {visa_days}-day visa. "
                f"Check extension options."
            )

        current_date = leg_end

    return {
        "trip_summary": {
            "destinations": [l["destination"] for l in legs],
            "total_days": duration_days,
            "total_estimated_cost": total_cost,
            "budget_tier": budget_tier,
            "start_date": trip_start.strftime("%Y-%m-%d"),
            "end_date": current_date.strftime("%Y-%m-%d"),
        },
        "legs": legs,
        "warnings": warnings,
        "next_steps": [
            "Search for specific accommodations at each destination",
            "Book flights between destinations",
            "Set up price watches for each city",
        ],
    }


# --- TOOL DISPATCHER ---
def execute_tool(tool_name: str, arguments: dict) -> dict:
    """Execute a tool by name with given arguments."""
    from backend.services.scout_agent import get_destination_brief, compare_destinations as scout_compare
    from backend.services.host_copilot import (
        generate_auto_replies, get_smart_pricing,
        optimize_listing as host_optimize_listing,
        draft_review_response,
    )
    from backend.services.community_agent import (
        find_travel_buddies, suggest_connections,
        curate_local_events, community_pulse,
    )
    from backend.services.finance_agent import (
        estimate_trip_budget, compare_cost_of_living,
        get_currency_tips, tax_residency_check,
    )
    from backend.services.relocation_agent import (
        plan_relocation, estimate_flights,
        moving_checklist, visa_timeline,
    )
    from backend.services.safety_agent import (
        get_safety_brief, emergency_contacts,
        scam_alerts, health_advisories,
    )

    tools = {
        "search_listings": search_listings,
        "create_booking": create_booking,
        "find_members": find_members,
        "get_hubs": get_hubs,
        "search_all_platforms": search_all_platforms,
        "destination_brief": get_destination_brief,
        "compare_destinations": scout_compare,
        "plan_trip": plan_trip,
        # Host Copilot
        "generate_auto_replies": generate_auto_replies,
        "get_smart_pricing": get_smart_pricing,
        "optimize_listing": host_optimize_listing,
        "draft_review_response": draft_review_response,
        # Community Agent
        "find_travel_buddies": find_travel_buddies,
        "suggest_connections": suggest_connections,
        "curate_local_events": curate_local_events,
        "community_pulse": community_pulse,
        # Finance Agent
        "estimate_trip_budget": estimate_trip_budget,
        "compare_cost_of_living": compare_cost_of_living,
        "get_currency_tips": get_currency_tips,
        "tax_residency_check": tax_residency_check,
        # Relocation Agent
        "plan_relocation": plan_relocation,
        "estimate_flights": estimate_flights,
        "moving_checklist": moving_checklist,
        "visa_timeline": visa_timeline,
        # Safety Agent
        "get_safety_brief": get_safety_brief,
        "emergency_contacts": emergency_contacts,
        "scam_alerts": scam_alerts,
        "health_advisories": health_advisories,
        # General
        "escalate_to_human": escalate_to_human,
        "get_weather": get_weather,
        "get_visa_requirements": get_visa_requirements,
        "suggest_itinerary": suggest_itinerary,
        "save_preference": save_preference,
        "create_search_watch": create_search_watch,
        "compare_listings": compare_listings,
        # Booking pipeline (from concierge_tools — lazy import)
    }

    # Lazily add booking tools only when needed
    if tool_name in ("get_booking_url", "search_bookable_listings", "initiate_booking", "get_booking_status"):
        import asyncio
        initiate_booking, get_booking_status, get_booking_url, search_bookable_listings = _get_concierge_tools()
        tools.update({
            "get_booking_url": get_booking_url,
            "search_bookable_listings": search_bookable_listings,
            "initiate_booking": lambda **kwargs: asyncio.run(initiate_booking(**kwargs)),
            "get_booking_status": get_booking_status,
        })

    if tool_name not in tools:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        # Inject user_id for community agent functions if available
        user_id = arguments.pop("_user_id", "anonymous")

        # Apply production middleware (rate limiting, caching, validation, metrics)
        from backend.services.tool_middleware import with_middleware
        result = with_middleware(tool_name, tools[tool_name], arguments, user_id=user_id)

        # Wrap in result envelope if not already an error
        if "error" in result:
            return result
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

