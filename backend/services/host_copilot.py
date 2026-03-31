"""
Host Copilot Agent — AI-powered Property Management Assistant.

Provides hosts with:
- Smart pricing recommendations (dynamic pricing based on market data)
- Auto-reply drafts for common guest questions
- Listing optimization suggestions
- Review response drafts
- Occupancy gap analysis
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.host_copilot")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.host_copilot")

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from backend.services.nomad_data import MARKET_RATES, AUTO_REPLY_TEMPLATES




def generate_auto_replies(
    listing_name: str,
    listing_city: str = "",
    listing_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate smart auto-reply drafts for common guest questions.
    Returns categorized replies ready to use.
    """
    features = listing_features or []
    feature_str = " ".join(features).lower()

    replies = []
    for category, template in AUTO_REPLY_TEMPLATES.items():
        # Build the reply with available context
        reply_text = template["reply"]

        # Fill in defaults or detected values
        for key, value in template.items():
            if key.startswith("default_"):
                param_name = key.replace("default_", "")
                # Try to detect from features
                detected = _detect_from_features(param_name, features, listing_city)
                reply_text = reply_text.replace(f"{{{param_name}}}", detected or value)

        replies.append({
            "category": category,
            "question_example": _get_example_question(category),
            "draft_reply": reply_text,
            "confidence": "high" if any(p in feature_str for p in template["question_patterns"][:2]) else "medium",
        })

    return {
        "listing_name": listing_name,
        "auto_replies": replies,
        "total": len(replies),
        "tip": "Review and personalize these drafts. You can enable one-click sending on your dashboard.",
    }


def get_smart_pricing(
    listing_name: str,
    current_price: float,
    city: str,
    property_type: str = "apartment",
    occupancy_rate: float = 0.7,
    upcoming_vacancy_days: int = 0,
) -> Dict[str, Any]:
    """
    Generate smart pricing recommendations based on market data,
    seasonality, and occupancy.
    """
    city_key = city.lower().strip()
    market = None
    for key, data in MARKET_RATES.items():
        if key in city_key or city_key in key:
            market = data
            break

    current_month = datetime.now().month
    recommendations = []

    if market:
        # Determine season
        is_peak = current_month in market["peak_months"]
        is_low = current_month in market["low_months"]

        market_mid = market["mid"]

        # Smart price detection: if the price is > 3x the market high,
        # it's almost certainly a monthly rate (not nightly).
        # e.g. Bali high=$80/night → anything above $240 is treated as monthly.
        monthly_threshold = market["high"] * 3
        if current_price > monthly_threshold:
            price_per_night = current_price / 30
        else:
            price_per_night = current_price

        # Price position analysis
        if price_per_night > market["high"]:
            position = "above_market"
            position_label = "Above Market"
        elif price_per_night > market["mid"]:
            position = "competitive"
            position_label = "Competitive"
        elif price_per_night > market["low"]:
            position = "value"
            position_label = "Great Value"
        else:
            position = "below_market"
            position_label = "Below Market"

        # Seasonal recommendation
        if is_peak and position in ["value", "below_market"]:
            peak_price = round(price_per_night * 1.15)
            recommendations.append({
                "type": "seasonal_increase",
                "action": f"Raise to ${peak_price}/night (+15%)",
                "reason": f"It's peak season in {city}. Market rates are ${market['mid']}-${market['high']}/night.",
                "impact": "high",
                "emoji": "📈",
            })

        if is_low and occupancy_rate < 0.6:
            promo_price = round(price_per_night * 0.88)
            recommendations.append({
                "type": "fill_calendar",
                "action": f"Drop to ${promo_price}/night (-12%) for 2 weeks",
                "reason": f"Occupancy is {int(occupancy_rate*100)}% in a slow month. A short promo can fill gaps.",
                "impact": "high",
                "emoji": "🎯",
            })

        # Vacancy gap filler
        if upcoming_vacancy_days > 7:
            gap_price = round(price_per_night * 0.85)
            recommendations.append({
                "type": "gap_filler",
                "action": f"Offer ${gap_price}/night for the {upcoming_vacancy_days}-day gap",
                "reason": "Empty nights earn $0. A 15% discount fills the calendar and beats zero revenue.",
                "impact": "medium",
                "emoji": "📅",
            })

        # Long-stay discount
        recommendations.append({
            "type": "long_stay_discount",
            "action": "Offer 10% off for 30+ day stays, 20% for 60+ days",
            "reason": "Digital nomads prefer long stays. Lower turnover = lower costs for you.",
            "impact": "medium",
            "emoji": "🏠",
        })

        # Competitive pricing
        if position == "above_market":
            recommendations.append({
                "type": "market_alignment",
                "action": f"Consider pricing closer to ${market_mid}/night (market midpoint)",
                "reason": f"Your listing is above {city}'s market range. Premium pricing works only with premium amenities.",
                "impact": "high",
                "emoji": "⚠️",
            })

        return {
            "listing_name": listing_name,
            "current_price_per_night": round(price_per_night, 2),
            "market_range": f"${market['low']}–${market['high']}/night",
            "market_midpoint": f"${market_mid}/night",
            "position": position_label,
            "season": "Peak" if is_peak else "Low" if is_low else "Shoulder",
            "occupancy_rate": f"{int(occupancy_rate*100)}%",
            "recommendations": recommendations,
        }
    else:
        # Generic recommendations for unknown cities
        return {
            "listing_name": listing_name,
            "current_price_per_night": round(current_price / 30 if current_price > 200 else current_price, 2),
            "market_range": "Market data not available for this city",
            "recommendations": [
                {
                    "type": "long_stay_discount",
                    "action": "Offer 10% off for 30+ day stays",
                    "reason": "Attracts digital nomads who prefer monthly bookings.",
                    "impact": "medium",
                    "emoji": "🏠",
                },
                {
                    "type": "competitive_research",
                    "action": "Check Airbnb/Booking for similar listings in your area",
                    "reason": "Price within 10% of similar listings for best conversion.",
                    "impact": "high",
                    "emoji": "🔍",
                },
            ],
        }


def optimize_listing(
    listing_name: str,
    description: str = "",
    amenities: Optional[List[str]] = None,
    photos_count: int = 0,
    city: str = "",
) -> Dict[str, Any]:
    """
    Analyze a listing and suggest optimizations to increase bookings.
    """
    amenities = amenities or []
    amenity_str = " ".join(amenities).lower()
    suggestions = []

    # Photo analysis
    if photos_count < 5:
        suggestions.append({
            "category": "📸 Photos",
            "priority": "critical",
            "suggestion": f"Add more photos (currently {photos_count}). Listings with 15+ photos get 2x more bookings.",
            "tips": [
                "Hero shot: wide-angle of the main living area with natural light",
                "Workspace: show the desk, chair, and monitor setup",
                "Kitchen: open fridge with basics, coffee maker ready",
                "View: balcony or window with the best angle",
                "Neighborhood: nearest cafe, coworking, street scene",
            ],
        })
    elif photos_count < 15:
        suggestions.append({
            "category": "📸 Photos",
            "priority": "medium",
            "suggestion": f"You have {photos_count} photos — good, but 15+ is optimal. Add workspace and neighborhood shots.",
        })

    # Amenity gaps for nomads
    nomad_essentials = {
        "wifi": "High-speed wifi (mention actual Mbps in description)",
        "desk": "Dedicated workspace with desk and ergonomic chair",
        "kitchen": "Fully equipped kitchen (nomads cook to save money)",
        "washer": "Washing machine (essential for long stays)",
        "ac": "Air conditioning (critical in tropical destinations)",
    }

    missing = []
    for amenity, tip in nomad_essentials.items():
        if amenity not in amenity_str:
            missing.append(tip)

    if missing:
        suggestions.append({
            "category": "🏠 Nomad Essentials",
            "priority": "high",
            "suggestion": f"Add or highlight these {len(missing)} nomad must-haves:",
            "missing": missing,
        })

    # Description optimization
    if len(description) < 100:
        suggestions.append({
            "category": "✍️ Description",
            "priority": "high",
            "suggestion": "Your description is too short. Aim for 300-500 words covering:",
            "tips": [
                "Lead with the vibe: 'A sun-drenched apartment in the heart of Nimman...'",
                "Mention wifi speed explicitly: 'Dedicated 100Mbps fiber connection'",
                "Address pain points: 'Quiet neighborhood perfect for video calls'",
                "Local tips: 'Walking distance to 5 cafes and 2 coworking spaces'",
                "Long-stay benefits: 'Monthly stays get a dedicated workspace setup'",
            ],
        })

    # Title optimization
    title_keywords = ["apartment", "studio", "villa", "condo", "room", "house"]
    has_type = any(kw in listing_name.lower() for kw in title_keywords)
    if not has_type:
        suggestions.append({
            "category": "📝 Title",
            "priority": "medium",
            "suggestion": "Include property type in your title. 'Modern Studio in Nimman' converts better than just a name.",
        })

    # City-specific tips
    from backend.services.scout_agent import DESTINATION_DATA
    city_key = city.lower().strip()
    for key, data in DESTINATION_DATA.items():
        if key in city_key or city_key in key:
            neighborhoods = data.get("neighborhoods", {})
            best_hood = max(neighborhoods.items(), key=lambda x: x[1].get("wifi_avg_mbps", 0)) if neighborhoods else None
            if best_hood:
                suggestions.append({
                    "category": "📍 Location Marketing",
                    "priority": "medium",
                    "suggestion": f"Highlight proximity to {best_hood[0].replace('_', ' ').title()}'s amenities in your description.",
                    "tips": [
                        f"Mention nearby coworking: {', '.join(best_hood[1].get('coworking_spaces', [])[:2])}",
                        f"Walkability score: {best_hood[1].get('walkability', 'N/A')}/100",
                        f"Cafe scene: {best_hood[1].get('cafe_scene', 'N/A')}",
                    ],
                })
            break

    score = max(0, 100 - (len(suggestions) * 15))

    return {
        "listing_name": listing_name,
        "optimization_score": score,
        "grade": "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D",
        "suggestions": suggestions,
        "total_suggestions": len(suggestions),
        "summary": f"{'Great listing!' if score >= 85 else 'Good foundation — a few tweaks will boost bookings significantly.' if score >= 50 else 'Several improvements needed to compete in this market.'}",
    }


def draft_review_response(
    guest_name: str,
    rating: int,
    review_text: str,
    listing_name: str,
) -> Dict[str, Any]:
    """
    Draft a personalized response to a guest review.
    """
    if rating >= 4:
        tone = "warm and grateful"
        response = (
            f"Thank you so much, {guest_name}! 🙏 We're thrilled you enjoyed your stay at {listing_name}. "
            f"Your kind words mean the world to us. "
            f"We'd love to host you again — returning guests always get priority booking and a special rate. "
            f"Safe travels! 🌏"
        )
    elif rating == 3:
        tone = "appreciative and improvement-focused"
        response = (
            f"Thank you for your feedback, {guest_name}. We appreciate your honest review of {listing_name}. "
            f"We're always looking to improve and your insights help us do that. "
            f"We've noted your comments and are working on improvements. "
            f"We hope to welcome you back in the future for an even better experience!"
        )
    elif rating == 2:
        tone = "professional and solution-oriented"
        response = (
            f"Thank you for sharing your experience, {guest_name}. We sincerely apologize that {listing_name} "
            f"didn't meet your expectations. Your feedback is valuable and we take it seriously. "
            f"We've already started addressing the issues you mentioned. "
            f"We'd welcome the chance to make it right — please reach out directly so we can discuss."
        )
    else:
        # 1-star: lead with empathy before solutions
        tone = "empathetic and damage-control"
        response = (
            f"We're truly sorry, {guest_name}. We completely understand your frustration and sincerely apologize "
            f"for the experience you had at {listing_name}. This is not the standard we hold ourselves to. "
            f"We take full responsibility and have already escalated the issues you raised to our team. "
            f"Please reach out to us directly — we want to make this right and ensure this never happens again."
        )

    return {
        "guest_name": guest_name,
        "rating": rating,
        "tone": tone,
        "draft_response": response,
        "tips": [
            "Personalize by referencing specific details from their review",
            "Never be defensive — acknowledge and address concerns",
            "Keep it concise — 3-4 sentences is optimal",
            "Include a forward-looking statement (invite back, mention improvements)",
        ],
    }


# --- Helper Functions ---

def _detect_from_features(param: str, features: List[str], city: str) -> Optional[str]:
    """Try to detect a parameter value from listing features."""
    feature_str = " ".join(features).lower()

    if param == "wifi_speed":
        for f in features:
            if "mbps" in f.lower():
                import re
                match = re.search(r"(\d+)\s*mbps", f.lower())
                if match:
                    return match.group(1)
        return None

    return None


def _get_example_question(category: str) -> str:
    """Get a natural-sounding example question for a category."""
    examples = {
        "wifi": "Is the internet reliable for work calls?",
        "checkin": "What time can I arrive?",
        "checkout": "Can I get a late checkout?",
        "extension": "Can I extend my stay if I like it?",
        "coworking": "How far is the nearest coworking space?",
        "laundry": "Is there a washing machine?",
        "transport": "How do I get around? Is Uber available?",
        "kitchen": "Is the kitchen fully equipped for cooking?",
    }
    return examples.get(category, "")
