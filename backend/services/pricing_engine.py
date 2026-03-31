"""
Dynamic Pricing Engine - AI-powered price suggestions based on demand and seasonality.
"""
from datetime import datetime, date
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models

# Seasonality multipliers (month -> multiplier)
SEASONALITY = {
    1: 0.85,  # January - low season
    2: 0.90,  # February
    3: 1.00,  # March
    4: 1.05,  # April - spring
    5: 1.10,  # May
    6: 1.20,  # June - high season starts
    7: 1.25,  # July - peak
    8: 1.25,  # August - peak
    9: 1.10,  # September
    10: 1.00,  # October
    11: 0.90,  # November
    12: 1.15,  # December - holidays
}

# Day of week multipliers (0=Monday, 6=Sunday)
DAY_OF_WEEK = {
    0: 0.95,  # Monday
    1: 0.95,  # Tuesday
    2: 1.00,  # Wednesday
    3: 1.00,  # Thursday
    4: 1.10,  # Friday
    5: 1.15,  # Saturday
    6: 1.05,  # Sunday
}


def get_demand_multiplier(listing_id: str, month: int) -> float:
    """
    Calculate demand multiplier based on historical bookings.
    Higher bookings = higher demand = higher price.
    """
    db = SessionLocal()
    try:
        # Count bookings for this listing in the target month
        booking_count = (
            db.query(models.Booking)
            .filter(models.Booking.listing_id == listing_id)
            .count()
        )

        # Simple demand curve: more bookings = higher multiplier
        if booking_count >= 10:
            return 1.20  # Very high demand
        elif booking_count >= 5:
            return 1.10  # High demand
        elif booking_count >= 2:
            return 1.05  # Moderate demand
        else:
            return 1.00  # Normal
    finally:
        db.close()


def calculate_dynamic_price(
    listing_id: str, target_date: date, base_price: Optional[float] = None
) -> Dict:
    """
    Calculate dynamic price for a specific date.

    Returns:
        {
            "base_price": float,
            "suggested_price": float,
            "multiplier": float,
            "factors": {...}
        }
    """
    db = SessionLocal()
    try:
        listing = (
            db.query(models.Listing).filter(models.Listing.id == listing_id).first()
        )
        if not listing:
            return {"error": "Listing not found"}

        base = base_price or listing.price_usd

        # Get multipliers
        season_mult = SEASONALITY.get(target_date.month, 1.0)
        day_mult = DAY_OF_WEEK.get(target_date.weekday(), 1.0)
        demand_mult = get_demand_multiplier(listing_id, target_date.month)

        # Combine multipliers
        total_mult = season_mult * day_mult * demand_mult
        suggested_price = round(base * total_mult, 2)

        return {
            "listing_id": listing_id,
            "base_price": base,
            "suggested_price": suggested_price,
            "multiplier": round(total_mult, 3),
            "date": target_date.isoformat(),
            "factors": {
                "seasonality": {
                    "month": target_date.month,
                    "multiplier": season_mult,
                    "label": "Peak"
                    if season_mult >= 1.2
                    else "Normal"
                    if season_mult >= 1.0
                    else "Low",
                },
                "day_of_week": {
                    "day": target_date.strftime("%A"),
                    "multiplier": day_mult,
                },
                "demand": {
                    "multiplier": demand_mult,
                    "label": "High" if demand_mult >= 1.1 else "Normal",
                },
            },
        }
    finally:
        db.close()


def get_price_suggestions_for_month(
    listing_id: str, year: int, month: int
) -> List[Dict]:
    """Get price suggestions for each day in a month."""
    from calendar import monthrange

    suggestions = []
    days_in_month = monthrange(year, month)[1]

    for day in range(1, days_in_month + 1):
        target = date(year, month, day)
        suggestion = calculate_dynamic_price(listing_id, target)
        if "error" not in suggestion:
            suggestions.append(suggestion)

    return suggestions


def get_ai_pricing_recommendation(listing_id: str) -> Dict:
    """
    Generate an AI-powered pricing recommendation with explanation.
    """
    today = date.today()

    # Get current month suggestions
    suggestions = get_price_suggestions_for_month(listing_id, today.year, today.month)

    if not suggestions:
        return {"error": "Could not generate recommendations"}

    # Calculate averages
    avg_suggested = sum(s["suggested_price"] for s in suggestions) / len(suggestions)
    base_price = suggestions[0]["base_price"]

    # Find peak days
    peak_days = [s for s in suggestions if s["multiplier"] >= 1.15]

    # Generate recommendation
    price_change_pct = ((avg_suggested - base_price) / base_price) * 100

    if price_change_pct > 10:
        recommendation = "INCREASE"
        reason = f"High demand detected. Consider raising your base price by {price_change_pct:.0f}%."
    elif price_change_pct < -5:
        recommendation = "DECREASE"
        reason = f"Low season. Consider a {abs(price_change_pct):.0f}% discount to attract bookings."
    else:
        recommendation = "MAINTAIN"
        reason = "Your current pricing is well-aligned with market conditions."

    return {
        "listing_id": listing_id,
        "current_base_price": base_price,
        "recommended_avg_price": round(avg_suggested, 2),
        "recommendation": recommendation,
        "reason": reason,
        "peak_days_this_month": len(peak_days),
        "analysis_period": f"{today.strftime('%B %Y')}",
    }
