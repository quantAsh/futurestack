"""
Finance Agent — Budget Planning & Cost Intelligence for Digital Nomads.

Provides the Concierge with financial tools:
- Multi-city trip budget estimation with per-category breakdown
- Side-by-side cost of living comparison
- Currency & payment tips per country
- Tax residency threshold alerts (183-day rule)
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.finance_agent")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.finance_agent")

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from backend.services.nomad_data import COST_DATA, CURRENCY_TIPS, TAX_THRESHOLDS





def estimate_trip_budget(
    destinations: List[str],
    days_per_destination: Optional[List[int]] = None,
    total_days: int = 90,
    budget_tier: str = "moderate",
    include_transport: bool = True,
) -> Dict[str, Any]:
    """
    Estimate total budget for a multi-city trip with per-city and per-category breakdown.
    """
    if not days_per_destination:
        days_per_destination = [total_days // len(destinations)] * len(destinations)
        # Distribute remainder
        remainder = total_days - sum(days_per_destination)
        for i in range(remainder):
            days_per_destination[i] += 1

    legs = []
    total_cost = 0
    total_breakdown = {}

    for i, dest in enumerate(destinations):
        dest_key = dest.lower().strip()
        cost_info = None
        for key, data in COST_DATA.items():
            if key in dest_key or dest_key in key:
                cost_info = data
                break

        days = days_per_destination[i] if i < len(days_per_destination) else 30
        daily_rate = cost_info["daily"].get(budget_tier, cost_info["daily"]["moderate"]) if cost_info else 60

        leg_cost = daily_rate * days

        # Per-category breakdown (prorate from monthly)
        breakdown = {}
        if cost_info and f"breakdown_{budget_tier}" in cost_info:
            monthly = cost_info[f"breakdown_{budget_tier}"]
            for cat, val in monthly.items():
                prorated = round(val * days / 30)
                breakdown[cat] = prorated
                total_breakdown[cat] = total_breakdown.get(cat, 0) + prorated

        total_cost += leg_cost

        legs.append({
            "destination": cost_info["city"] if cost_info else dest.title(),
            "country": cost_info["country"] if cost_info else "Unknown",
            "days": days,
            "daily_rate": daily_rate,
            "subtotal": leg_cost,
            "currency": cost_info["currency"] if cost_info else "USD",
            "breakdown": breakdown,
        })

    # Add inter-city transport
    transport_costs = []
    if include_transport and len(legs) > 1:
        for i in range(len(legs) - 1):
            from_city = legs[i]["destination"]
            to_city = legs[i + 1]["destination"]
            # Estimate flight cost based on distance
            est = 200 if legs[i]["country"] != legs[i + 1]["country"] else 80
            transport_costs.append({
                "from": from_city,
                "to": to_city,
                "estimated_cost": est,
                "type": "flight" if legs[i]["country"] != legs[i + 1]["country"] else "train/bus",
            })
            total_cost += est

    return {
        "budget_tier": budget_tier,
        "total_days": total_days,
        "total_estimated_cost": total_cost,
        "daily_average": round(total_cost / total_days) if total_days > 0 else 0,
        "legs": legs,
        "transport": transport_costs,
        "total_breakdown": total_breakdown,
        "savings_tips": _get_savings_tips(budget_tier, legs),
    }


def compare_cost_of_living(
    cities: List[str],
    budget_tier: str = "moderate",
) -> Dict[str, Any]:
    """
    Side-by-side cost of living comparison for multiple cities.
    """
    comparisons = []
    for city in cities:
        city_key = city.lower().strip()
        cost_info = None
        for key, data in COST_DATA.items():
            if key in city_key or city_key in key:
                cost_info = data
                break

        if cost_info:
            monthly = cost_info["monthly"].get(budget_tier, cost_info["monthly"]["moderate"])
            breakdown = cost_info.get(f"breakdown_{budget_tier}", {})
            comparisons.append({
                "city": cost_info["city"],
                "country": cost_info["country"],
                "monthly_total": monthly,
                "daily_average": cost_info["daily"].get(budget_tier, cost_info["daily"]["moderate"]),
                "currency": cost_info["currency"],
                "breakdown": breakdown,
                "biggest_expense": max(breakdown, key=breakdown.get) if breakdown else "rent",
            })

    if not comparisons:
        return {"error": "No cost data found for the specified cities."}

    cheapest = min(comparisons, key=lambda x: x["monthly_total"])
    most_expensive = max(comparisons, key=lambda x: x["monthly_total"])
    savings = most_expensive["monthly_total"] - cheapest["monthly_total"]

    return {
        "budget_tier": budget_tier,
        "comparison": comparisons,
        "cheapest": cheapest["city"],
        "most_expensive": most_expensive["city"],
        "monthly_savings": savings,
        "insight": f"Living in {cheapest['city']} instead of {most_expensive['city']} saves ${savings}/month ({round(savings/most_expensive['monthly_total']*100)}%).",
    }


def get_currency_tips(
    country_or_currency: str,
) -> Dict[str, Any]:
    """
    Get practical currency and payment tips for a destination.
    """
    query = country_or_currency.upper().strip()

    # Try direct currency code match
    if query in CURRENCY_TIPS:
        tips = CURRENCY_TIPS[query]
        return {
            "currency": query,
            **tips,
        }

    # Try country name → currency lookup
    country_to_currency = {
        "BALI": "IDR", "INDONESIA": "IDR",
        "THAILAND": "THB", "CHIANG MAI": "THB", "BANGKOK": "THB",
        "PORTUGAL": "EUR", "LISBON": "EUR", "SPAIN": "EUR", "BARCELONA": "EUR",
        "MEXICO": "MXN", "MEXICO CITY": "MXN", "CDMX": "MXN",
    }

    currency = country_to_currency.get(query)
    if currency and currency in CURRENCY_TIPS:
        tips = CURRENCY_TIPS[currency]
        return {
            "country": country_or_currency.title(),
            "currency": currency,
            **tips,
        }

    return {
        "country": country_or_currency,
        "data_available": False,
        "message": f"No currency tips for {country_or_currency} yet. Available: Bali/Indonesia, Thailand, Portugal/Spain, Mexico.",
        "generic_tips": [
            "Use Wise or Revolut for best exchange rates",
            "Avoid airport exchange counters",
            "Always pay in local currency, never choose 'pay in USD'",
        ],
    }


def tax_residency_check(
    countries_and_days: Dict[str, int],
) -> Dict[str, Any]:
    """
    Check if stay durations trigger tax residency in any country.
    Input: {"Portugal": 95, "Thailand": 45, "Indonesia": 60}
    """
    alerts = []
    warnings = []
    ok = []

    for country, days in countries_and_days.items():
        threshold_info = None
        for key, data in TAX_THRESHOLDS.items():
            if key.lower() in country.lower() or country.lower() in key.lower():
                threshold_info = data
                threshold_info["country"] = key
                break

        if not threshold_info:
            ok.append({
                "country": country,
                "days": days,
                "status": "unknown",
                "note": "No tax threshold data — consult a tax advisor.",
            })
            continue

        threshold = threshold_info["days"]
        if days >= threshold:
            alerts.append({
                "country": threshold_info["country"],
                "days_stayed": days,
                "threshold": threshold,
                "status": "exceeded",
                "risk": threshold_info["risk"],
                "rule": threshold_info["rule"],
                "action": f"⚠️ You've exceeded the {threshold}-day threshold. Consult a tax professional.",
            })
        elif days >= threshold - 14:
            warnings.append({
                "country": threshold_info["country"],
                "days_stayed": days,
                "threshold": threshold,
                "days_remaining": threshold - days,
                "status": "approaching",
                "risk": threshold_info["risk"],
                "action": f"🟡 {threshold - days} days until tax residency threshold. Plan your exit.",
            })
        else:
            ok.append({
                "country": threshold_info["country"],
                "days_stayed": days,
                "threshold": threshold,
                "days_remaining": threshold - days,
                "status": "safe",
            })

    return {
        "summary": f"{len(alerts)} alert(s), {len(warnings)} warning(s), {len(ok)} OK",
        "alerts": alerts,
        "warnings": warnings,
        "ok": ok,
        "disclaimer": "This is informational only — tax rules are complex and vary by your home country. Always consult a qualified tax advisor.",
    }


def _get_savings_tips(budget_tier: str, legs: List[Dict]) -> List[str]:
    """Generate contextual savings tips based on the trip."""
    tips = []
    if budget_tier == "luxury":
        tips.append("Consider 'moderate' tier in SEA — luxury quality at 40% less than Europe")
    if any(l["days"] >= 28 for l in legs):
        tips.append("Book monthly stays for 20-40% savings over nightly rates")
    if len(legs) > 2:
        tips.append("Book flights 6-8 weeks ahead for best prices between destinations")
    if any(l.get("country") == "Thailand" for l in legs):
        tips.append("Thailand: eat street food for $2/meal — tastier and 80% cheaper than restaurants")
    if any(l.get("country") == "Indonesia" for l in legs):
        tips.append("Bali: rent a scooter ($60/mo) instead of Grab rides to save $100+/month")
    if any(l.get("country") == "Portugal" for l in legs):
        tips.append("Lisbon: cook at home 3x/week using Mercado da Ribeira produce — saves €200/month")
    tips.append("Use Wise card globally — saves 1-3% on every transaction vs traditional banks")
    return tips[:5]
