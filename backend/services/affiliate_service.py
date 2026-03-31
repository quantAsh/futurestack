"""
Affiliate Service — Centralized affiliate link generation, click tracking, and reporting.

Partners:
  SafetyWing  — Nomad health insurance    ($10/signup)
  Airalo      — eSIM for travelers        ($3-5/sale)
  Kiwi.com    — Flight search             (3% commission)
  NordVPN     — Privacy/VPN               ($7/signup)
  Wise        — International transfers   ($5/transfer)
"""
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from collections import defaultdict

logger = logging.getLogger("nomadnest.affiliates")

# ── Partner Configuration ──────────────────────────────────────
AFFILIATE_PARTNERS = {
    "safetywing": {
        "name": "SafetyWing",
        "category": "insurance",
        "base_url": "https://safetywing.com/nomad-insurance",
        "ref_param": "referenceID",
        "ref_id": "nomadnest",
        "commission_type": "per_signup",
        "commission_value": 10.00,
        "description": "Nomad health insurance — coverage in 180+ countries",
        "cta": "Get Covered →",
        "icon": "🛡️",
    },
    "airalo": {
        "name": "Airalo",
        "category": "connectivity",
        "base_url": "https://www.airalo.com",
        "ref_param": "ref",
        "ref_id": "nomadnest",
        "commission_type": "per_sale",
        "commission_value": 4.00,
        "description": "eSIM data plans — instant connectivity in 200+ countries",
        "cta": "Get eSIM →",
        "icon": "📱",
    },
    "kiwi": {
        "name": "Kiwi.com",
        "category": "flights",
        "base_url": "https://www.kiwi.com/deep",
        "ref_param": "affilid",
        "ref_id": "nomadnest",
        "commission_type": "percentage",
        "commission_value": 0.03,
        "description": "Cheap flights with flexible routing and virtual interlining",
        "cta": "Search Flights →",
        "icon": "✈️",
    },
    "nordvpn": {
        "name": "NordVPN",
        "category": "vpn",
        "base_url": "https://nordvpn.com/nomadnest",
        "ref_param": "coupon",
        "ref_id": "nomadnest",
        "commission_type": "per_signup",
        "commission_value": 7.00,
        "description": "Secure VPN — access content and protect your data anywhere",
        "cta": "Get VPN →",
        "icon": "🔐",
    },
    "wise": {
        "name": "Wise",
        "category": "banking",
        "base_url": "https://wise.com/invite",
        "ref_param": "ref",
        "ref_id": "nomadnest",
        "commission_type": "per_transfer",
        "commission_value": 5.00,
        "description": "International money transfers at the real exchange rate",
        "cta": "Send Money →",
        "icon": "💸",
    },
}


# ── In-Memory Click Tracker ───────────────────────────────────
# In production, use Redis or DB
_click_log: List[Dict[str, Any]] = []
_conversion_log: List[Dict[str, Any]] = []


def generate_affiliate_link(
    partner: str,
    context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Generate a tracked affiliate link for a partner.

    Args:
        partner: Partner key (safetywing, airalo, kiwi, nordvpn, wise)
        context: Optional context params (e.g. destination, dates for Kiwi)

    Returns:
        Dict with url, partner info, and tracking metadata
    """
    config = AFFILIATE_PARTNERS.get(partner)
    if not config:
        return {"error": f"Unknown partner: {partner}"}

    # Build URL
    url = f"{config['base_url']}?{config['ref_param']}={config['ref_id']}"

    # Add context params
    if context:
        if partner == "kiwi" and "destination" in context:
            url += f"&to={context['destination']}"
        if context.get("utm_source"):
            url += f"&utm_source={context['utm_source']}"

    return {
        "partner": partner,
        "name": config["name"],
        "category": config["category"],
        "url": url,
        "description": config["description"],
        "cta": config["cta"],
        "icon": config["icon"],
        "commission_type": config["commission_type"],
        "commission_value": config["commission_value"],
    }


def generate_all_links(context: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Generate affiliate links for all partners."""
    return [generate_affiliate_link(p, context) for p in AFFILIATE_PARTNERS]


def track_click(
    partner: str,
    user_id: Optional[str] = None,
    source: str = "concierge",
) -> Dict[str, Any]:
    """
    Track an affiliate link click.

    Args:
        partner: Partner key
        user_id: Optional user who clicked
        source: Where the click originated (concierge, safety_brief, pricing_page)
    """
    if partner not in AFFILIATE_PARTNERS:
        return {"error": f"Unknown partner: {partner}"}

    click = {
        "partner": partner,
        "user_id": user_id,
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
        "ts": time.time(),
    }
    _click_log.append(click)

    logger.info(f"affiliate_click partner={partner} user={user_id} source={source}")
    return {"tracked": True, "partner": partner}


def track_conversion(
    partner: str,
    user_id: Optional[str] = None,
    amount: float = 0.0,
) -> Dict[str, Any]:
    """Track an affiliate conversion (signup/purchase)."""
    config = AFFILIATE_PARTNERS.get(partner)
    if not config:
        return {"error": f"Unknown partner: {partner}"}

    commission = config["commission_value"]
    if config["commission_type"] == "percentage":
        commission = round(amount * config["commission_value"], 2)

    conversion = {
        "partner": partner,
        "user_id": user_id,
        "amount": amount,
        "commission": commission,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _conversion_log.append(conversion)

    logger.info(f"affiliate_conversion partner={partner} commission=${commission}")
    return {"tracked": True, "commission": commission}


def get_affiliate_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Generate affiliate revenue report.

    Returns per-partner breakdown of clicks, conversions, and estimated revenue.
    """
    report = {}
    for partner, config in AFFILIATE_PARTNERS.items():
        clicks = [c for c in _click_log if c["partner"] == partner]
        conversions = [c for c in _conversion_log if c["partner"] == partner]

        total_commission = sum(c.get("commission", 0) for c in conversions)

        report[partner] = {
            "name": config["name"],
            "category": config["category"],
            "clicks": len(clicks),
            "conversions": len(conversions),
            "conversion_rate": round(len(conversions) / max(len(clicks), 1) * 100, 1),
            "total_commission": round(total_commission, 2),
            "commission_type": config["commission_type"],
            "commission_per_unit": config["commission_value"],
        }

    total_clicks = sum(r["clicks"] for r in report.values())
    total_conversions = sum(r["conversions"] for r in report.values())
    total_revenue = sum(r["total_commission"] for r in report.values())

    return {
        "summary": {
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_revenue": round(total_revenue, 2),
            "avg_conversion_rate": round(total_conversions / max(total_clicks, 1) * 100, 1),
        },
        "partners": report,
    }


def get_contextual_recommendations(
    destination: Optional[str] = None,
    features: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Get contextually relevant affiliate recommendations.
    Called by agents to embed affiliate links in responses.

    Args:
        destination: User's destination city/country
        features: Relevant features (e.g., ["insurance", "esim", "flights"])
    """
    recommendations = []
    feature_map = {
        "insurance": "safetywing",
        "esim": "airalo",
        "sim": "airalo",
        "flights": "kiwi",
        "vpn": "nordvpn",
        "banking": "wise",
        "money": "wise",
        "transfer": "wise",
    }

    if features:
        for feat in features:
            partner = feature_map.get(feat.lower())
            if partner:
                link = generate_affiliate_link(
                    partner,
                    context={"destination": destination} if destination else None,
                )
                if "error" not in link:
                    recommendations.append(link)
    else:
        # Default: suggest insurance + eSIM for any destination
        for p in ["safetywing", "airalo"]:
            link = generate_affiliate_link(p)
            recommendations.append(link)

    return recommendations
