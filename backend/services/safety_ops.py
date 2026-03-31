"""
Safety & Escalations Operations — Admin panel analytics for user safety.

Provides:
    1. Escalation Queue  — open tickets by severity with SLA tracking
    2. Safety Map         — traveler distribution with risk overlay
    3. Incident Timeline  — recent safety events
    4. Coverage Stats     — safety data coverage, response times
"""
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from uuid import uuid4


# ═══════════════════════════════════════════════════════════════
# 1. ESCALATION QUEUE
# ═══════════════════════════════════════════════════════════════

SEVERITY_CONFIG = {
    "critical": {"sla_minutes": 15, "color": "#ef4444", "icon": "🔴"},
    "high":     {"sla_minutes": 60, "color": "#f59e0b", "icon": "🟠"},
    "medium":   {"sla_minutes": 240, "color": "#3b82f6", "icon": "🔵"},
    "low":      {"sla_minutes": 1440, "color": "#10b981", "icon": "🟢"},
}


def get_escalation_dashboard() -> Dict[str, Any]:
    """Get live escalation queue with SLA tracking."""
    now = datetime.now(timezone.utc)

    # Demo escalations (production: query Escalation table)
    escalations = [
        {
            "id": "ESC-001", "severity": "critical", "type": "safety_emergency",
            "title": "Traveler stranded after hostel fire — Chiang Mai",
            "user": "Sarah M.", "location": "Chiang Mai, Thailand",
            "created_at": (now - timedelta(minutes=8)).isoformat(),
            "status": "open", "assigned_to": None,
        },
        {
            "id": "ESC-002", "severity": "high", "type": "scam_report",
            "title": "Overcharged $400 by taxi — Bali airport",
            "user": "Jake R.", "location": "Bali, Indonesia",
            "created_at": (now - timedelta(minutes=45)).isoformat(),
            "status": "assigned", "assigned_to": "Agent Diana",
        },
        {
            "id": "ESC-003", "severity": "medium", "type": "health_concern",
            "title": "Food poisoning — requesting hospital recommendation",
            "user": "Kim L.", "location": "Mexico City, Mexico",
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "status": "in_progress", "assigned_to": "Agent Maya",
        },
        {
            "id": "ESC-004", "severity": "high", "type": "accommodation_issue",
            "title": "Listing doesn't match description — no wifi, no AC",
            "user": "Tom W.", "location": "Lisbon, Portugal",
            "created_at": (now - timedelta(hours=1, minutes=20)).isoformat(),
            "status": "assigned", "assigned_to": "Agent Carlos",
        },
        {
            "id": "ESC-005", "severity": "low", "type": "refund_request",
            "title": "Requesting refund for cancelled experience",
            "user": "Anna P.", "location": "Bali, Indonesia",
            "created_at": (now - timedelta(hours=6)).isoformat(),
            "status": "open", "assigned_to": None,
        },
        {
            "id": "ESC-006", "severity": "critical", "type": "safety_emergency",
            "title": "Passport stolen — embassy assistance needed",
            "user": "Marcus D.", "location": "Mexico City, Mexico",
            "created_at": (now - timedelta(minutes=22)).isoformat(),
            "status": "assigned", "assigned_to": "Agent Safety-Bot",
        },
    ]

    # Compute SLA status for each
    for esc in escalations:
        sla_min = SEVERITY_CONFIG[esc["severity"]]["sla_minutes"]
        created = datetime.fromisoformat(esc["created_at"])
        elapsed_min = (now - created).total_seconds() / 60
        esc["sla_minutes"] = sla_min
        esc["elapsed_minutes"] = round(elapsed_min)
        esc["sla_remaining_minutes"] = max(0, round(sla_min - elapsed_min))
        esc["sla_breached"] = elapsed_min > sla_min
        esc["severity_icon"] = SEVERITY_CONFIG[esc["severity"]]["icon"]

    open_count = sum(1 for e in escalations if e["status"] == "open")
    breached = sum(1 for e in escalations if e["sla_breached"])

    return {
        "timestamp": now.isoformat(),
        "total": len(escalations),
        "open": open_count,
        "assigned": sum(1 for e in escalations if e["status"] == "assigned"),
        "in_progress": sum(1 for e in escalations if e["status"] == "in_progress"),
        "sla_breached": breached,
        "avg_response_minutes": round(sum(e["elapsed_minutes"] for e in escalations) / max(len(escalations), 1)),
        "escalations": sorted(escalations, key=lambda e: list(SEVERITY_CONFIG.keys()).index(e["severity"])),
    }


# ═══════════════════════════════════════════════════════════════
# 2. SAFETY MAP — Traveler distribution with risk levels
# ═══════════════════════════════════════════════════════════════

def get_safety_map() -> Dict[str, Any]:
    """Get traveler locations with safety risk overlay."""
    locations = [
        {"city": "Bali", "country": "Indonesia", "travelers": 47, "risk_level": "moderate", "active_alerts": 2, "top_concern": "Taxi scams"},
        {"city": "Chiang Mai", "country": "Thailand", "travelers": 32, "risk_level": "low", "active_alerts": 1, "top_concern": "Air quality"},
        {"city": "Lisbon", "country": "Portugal", "travelers": 28, "risk_level": "low", "active_alerts": 0, "top_concern": "Pickpocketing"},
        {"city": "Mexico City", "country": "Mexico", "travelers": 19, "risk_level": "elevated", "active_alerts": 3, "top_concern": "Water safety"},
        {"city": "Medellín", "country": "Colombia", "travelers": 15, "risk_level": "moderate", "active_alerts": 1, "top_concern": "Express kidnapping"},
        {"city": "Bangkok", "country": "Thailand", "travelers": 22, "risk_level": "moderate", "active_alerts": 2, "top_concern": "Gem scams"},
        {"city": "Tbilisi", "country": "Georgia", "travelers": 11, "risk_level": "low", "active_alerts": 0, "top_concern": "None reported"},
        {"city": "Da Nang", "country": "Vietnam", "travelers": 8, "risk_level": "low", "active_alerts": 0, "top_concern": "Road safety"},
    ]

    return {
        "total_travelers": sum(l["travelers"] for l in locations),
        "total_locations": len(locations),
        "locations": locations,
        "risk_summary": {
            "low": sum(1 for l in locations if l["risk_level"] == "low"),
            "moderate": sum(1 for l in locations if l["risk_level"] == "moderate"),
            "elevated": sum(1 for l in locations if l["risk_level"] == "elevated"),
            "high": sum(1 for l in locations if l["risk_level"] == "high"),
        },
    }


# ═══════════════════════════════════════════════════════════════
# 3. INCIDENT TIMELINE — Recent safety events
# ═══════════════════════════════════════════════════════════════

def get_incident_timeline() -> Dict[str, Any]:
    """Get recent safety incidents for the timeline."""
    now = datetime.now(timezone.utc)
    incidents = [
        {"time": (now - timedelta(minutes=8)).isoformat(), "type": "🔥 Emergency", "summary": "Hostel fire evacuation — Chiang Mai. All travelers safe.", "severity": "critical"},
        {"time": (now - timedelta(minutes=22)).isoformat(), "type": "🛂 Document", "summary": "Passport theft reported — Mexico City embassy notified.", "severity": "critical"},
        {"time": (now - timedelta(minutes=45)).isoformat(), "type": "💸 Scam", "summary": "Taxi overcharge $400 — Bali. Dispute filed with local police.", "severity": "high"},
        {"time": (now - timedelta(hours=2)).isoformat(), "type": "🏥 Health", "summary": "Food poisoning case — CDMX. Traveler referred to Hospital ABC.", "severity": "medium"},
        {"time": (now - timedelta(hours=4)).isoformat(), "type": "🏠 Accommodation", "summary": "Listing mismatch complaint — Lisbon. Host contacted.", "severity": "medium"},
        {"time": (now - timedelta(hours=8)).isoformat(), "type": "✅ Resolved", "summary": "Scam refund processed — Bali taxi case resolved ($400 refunded).", "severity": "low"},
        {"time": (now - timedelta(hours=12)).isoformat(), "type": "✅ Resolved", "summary": "Passport replacement fast-tracked — Bangkok embassy confirmed.", "severity": "low"},
        {"time": (now - timedelta(hours=24)).isoformat(), "type": "📋 Advisory", "summary": "Air quality warning issued for Chiang Mai (AQI > 150).", "severity": "medium"},
    ]

    return {
        "total_24h": len(incidents),
        "critical_24h": sum(1 for i in incidents if i["severity"] == "critical"),
        "resolved_24h": sum(1 for i in incidents if "Resolved" in i["type"]),
        "incidents": incidents,
    }


# ═══════════════════════════════════════════════════════════════
# 4. COVERAGE & RESPONSE STATS
# ═══════════════════════════════════════════════════════════════

def get_safety_stats() -> Dict[str, Any]:
    """Get overall safety coverage and response metrics."""
    return {
        "coverage": {
            "cities_covered": 4,
            "cities_with_travelers": 8,
            "coverage_pct": 50,
            "missing": ["Medellín", "Bangkok", "Tbilisi", "Da Nang"],
        },
        "response_metrics": {
            "avg_first_response_min": 12,
            "avg_resolution_hours": 4.2,
            "sla_compliance_pct": 87,
            "csat_score": 4.3,
        },
        "last_30_days": {
            "total_escalations": 42,
            "resolved": 38,
            "avg_severity": "medium",
            "repeat_offender_hosts": 2,
        },
    }
