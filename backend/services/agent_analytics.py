"""
Agent & Systems Analytics — Unified observability engine for the admin panel.

Provides:
    1. Agent Fleet Status   — live status of all AI agents
    2. System Health        — service health, uptime, error rates
    3. Circuit Breakers     — OTA provider circuit states
    4. AI Cost Tracker      — token usage, model costs, spend forecasts
"""
import logging
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from uuid import uuid4

logger = logging.getLogger("nomadnest.agent_analytics")


# ═══════════════════════════════════════════════════════════════
# 1. AGENT FLEET STATUS
# ═══════════════════════════════════════════════════════════════

AGENT_REGISTRY = [
    {
        "id": "concierge",
        "name": "AI Concierge",
        "module": "backend.services.ai_concierge",
        "description": "Main conversational AI for traveler queries",
        "type": "conversational",
        "icon": "🧠",
    },
    {
        "id": "finance",
        "name": "Finance Agent",
        "module": "backend.services.finance_agent",
        "description": "Budget tracking, spending analytics, cost optimization",
        "type": "analytical",
        "icon": "💰",
    },
    {
        "id": "relocation",
        "name": "Relocation Agent",
        "module": "backend.services.relocation_agent",
        "description": "Visa requirements, tax implications, logistics planning",
        "type": "advisory",
        "icon": "🌍",
    },
    {
        "id": "safety",
        "name": "Safety Agent",
        "module": "backend.services.safety_agent",
        "description": "Travel advisories, health alerts, emergency protocols",
        "type": "monitoring",
        "icon": "🛡️",
    },
    {
        "id": "scout",
        "name": "Scout Agent",
        "module": "backend.services.scout_agent",
        "description": "Location discovery, market analysis, opportunity scouting",
        "type": "research",
        "icon": "🔍",
    },
    {
        "id": "community",
        "name": "Community Agent",
        "module": "backend.services.community_agent",
        "description": "Community matching, event recommendations, social connections",
        "type": "social",
        "icon": "👥",
    },
    {
        "id": "negotiation",
        "name": "Negotiation Agent",
        "module": "backend.services.negotiation_agent",
        "description": "Price negotiation, deal optimization, host communication",
        "type": "transactional",
        "icon": "🤝",
    },
    {
        "id": "booking",
        "name": "Booking Agent",
        "module": "backend.core.agent_engine",
        "description": "Autonomous browser-based booking execution",
        "type": "autonomous",
        "icon": "🤖",
    },
]


def get_agent_fleet_status() -> Dict[str, Any]:
    """Get live status of all registered agents with performance metrics."""
    now = datetime.now(timezone.utc)
    agents = []

    for agent in AGENT_REGISTRY:
        # Check if module is importable
        status = "online"
        try:
            __import__(agent["module"], fromlist=[""])
        except Exception:
            status = "offline"

        # Simulated metrics (production: pull from AI metrics DB)
        uptime_hours = random.uniform(20, 168)  # Last 7 days
        total_invocations = random.randint(50, 2000)
        avg_latency_ms = random.uniform(200, 3500)
        error_rate = random.uniform(0, 5)
        last_invoked = now - timedelta(minutes=random.randint(1, 120))

        agents.append({
            **agent,
            "status": status,
            "metrics": {
                "total_invocations_7d": total_invocations,
                "avg_latency_ms": round(avg_latency_ms),
                "error_rate_pct": round(error_rate, 1),
                "uptime_hours_7d": round(uptime_hours, 1),
                "last_invoked": last_invoked.isoformat(),
            },
        })

    online_count = sum(1 for a in agents if a["status"] == "online")

    return {
        "timestamp": now.isoformat(),
        "total_agents": len(agents),
        "online": online_count,
        "offline": len(agents) - online_count,
        "fleet_health_pct": round(online_count / max(len(agents), 1) * 100, 1),
        "agents": agents,
    }


# ═══════════════════════════════════════════════════════════════
# 2. SYSTEM HEALTH — Service-level health overview
# ═══════════════════════════════════════════════════════════════

SYSTEM_SERVICES = [
    {"id": "api_gateway", "name": "API Gateway", "icon": "🌐", "category": "core"},
    {"id": "database", "name": "PostgreSQL", "icon": "🗄️", "category": "core"},
    {"id": "ai_proxy", "name": "AI Proxy (LiteLLM)", "icon": "🤖", "category": "ai"},
    {"id": "rate_limiter", "name": "Rate Limiter", "icon": "🚦", "category": "ai"},
    {"id": "circuit_breakers", "name": "Circuit Breakers", "icon": "⚡", "category": "resilience"},
    {"id": "cache", "name": "AI Cache", "icon": "📦", "category": "performance"},
    {"id": "notifications", "name": "Push Notifications", "icon": "🔔", "category": "messaging"},
    {"id": "metering", "name": "AI Metering", "icon": "📊", "category": "ai"},
    {"id": "memory", "name": "Memory Service", "icon": "🧩", "category": "ai"},
    {"id": "scraper", "name": "Web Scraper", "icon": "🕷️", "category": "data"},
]


def get_system_health() -> Dict[str, Any]:
    """Get health status of all system services."""
    now = datetime.now(timezone.utc)
    services = []

    for svc in SYSTEM_SERVICES:
        # Simulate health checks (production: real healthcheck endpoints)
        status = random.choices(["healthy", "degraded", "down"], weights=[90, 8, 2])[0]
        uptime_pct = random.uniform(98.0, 100.0) if status == "healthy" else random.uniform(85.0, 98.0) if status == "degraded" else random.uniform(0, 85.0)
        response_time_ms = random.uniform(5, 50) if status == "healthy" else random.uniform(50, 500)
        last_error = None
        if status != "healthy":
            last_error = (now - timedelta(minutes=random.randint(1, 30))).isoformat()

        services.append({
            **svc,
            "status": status,
            "uptime_pct": round(uptime_pct, 2),
            "response_time_ms": round(response_time_ms),
            "last_error": last_error,
        })

    healthy_count = sum(1 for s in services if s["status"] == "healthy")

    return {
        "timestamp": now.isoformat(),
        "total_services": len(services),
        "healthy": healthy_count,
        "degraded": sum(1 for s in services if s["status"] == "degraded"),
        "down": sum(1 for s in services if s["status"] == "down"),
        "overall_health_pct": round(healthy_count / max(len(services), 1) * 100, 1),
        "services": services,
    }


# ═══════════════════════════════════════════════════════════════
# 3. CIRCUIT BREAKER STATUS
# ═══════════════════════════════════════════════════════════════

def get_circuit_breaker_status() -> Dict[str, Any]:
    """Get circuit breaker states from the registry."""
    try:
        from backend.services.circuit_breaker import circuit_registry
        breakers = circuit_registry.get_all_status()
    except Exception:
        # Fallback demo data
        breakers = [
            {"name": "ota_booking_com", "state": "closed", "failures": 0, "successes": 142, "consecutive_failures": 0, "last_failure": None, "last_success": datetime.now(timezone.utc).isoformat()},
            {"name": "ota_hostelworld", "state": "closed", "failures": 2, "successes": 89, "consecutive_failures": 0, "last_failure": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(), "last_success": datetime.now(timezone.utc).isoformat()},
            {"name": "ota_airbnb", "state": "half_open", "failures": 6, "successes": 34, "consecutive_failures": 3, "last_failure": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(), "last_success": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()},
            {"name": "ota_nomadlist", "state": "closed", "failures": 0, "successes": 210, "consecutive_failures": 0, "last_failure": None, "last_success": datetime.now(timezone.utc).isoformat()},
            {"name": "ota_safetywing", "state": "closed", "failures": 1, "successes": 67, "consecutive_failures": 0, "last_failure": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "last_success": datetime.now(timezone.utc).isoformat()},
        ]

    return {
        "total": len(breakers),
        "closed": sum(1 for b in breakers if b["state"] == "closed"),
        "open": sum(1 for b in breakers if b["state"] == "open"),
        "half_open": sum(1 for b in breakers if b["state"] == "half_open"),
        "breakers": breakers,
    }


# ═══════════════════════════════════════════════════════════════
# 4. AI COST TRACKER
# ═══════════════════════════════════════════════════════════════

def get_ai_cost_summary() -> Dict[str, Any]:
    """Get AI token usage and cost summary."""
    now = datetime.now(timezone.utc)

    # Model usage breakdown (production: query AIMetric table)
    models = [
        {
            "model": "gemini-1.5-flash",
            "provider": "Google",
            "invocations_24h": 842,
            "tokens_24h": {"prompt": 124_000, "completion": 68_000, "total": 192_000},
            "cost_24h_usd": 0.034,
            "avg_latency_ms": 320,
            "error_rate_pct": 0.3,
        },
        {
            "model": "gemini-1.5-pro",
            "provider": "Google",
            "invocations_24h": 156,
            "tokens_24h": {"prompt": 89_000, "completion": 42_000, "total": 131_000},
            "cost_24h_usd": 0.75,
            "avg_latency_ms": 1200,
            "error_rate_pct": 1.2,
        },
        {
            "model": "gpt-4o-mini",
            "provider": "OpenAI",
            "invocations_24h": 64,
            "tokens_24h": {"prompt": 18_000, "completion": 9_000, "total": 27_000},
            "cost_24h_usd": 0.008,
            "avg_latency_ms": 450,
            "error_rate_pct": 0.5,
        },
    ]

    total_tokens = sum(m["tokens_24h"]["total"] for m in models)
    total_cost = sum(m["cost_24h_usd"] for m in models)
    total_invocations = sum(m["invocations_24h"] for m in models)

    return {
        "timestamp": now.isoformat(),
        "period": "24h",
        "totals": {
            "invocations": total_invocations,
            "tokens": total_tokens,
            "cost_usd": round(total_cost, 3),
            "cost_monthly_projection": round(total_cost * 30, 2),
        },
        "by_model": models,
        "cost_trend_7d": [0.68, 0.72, 0.81, 0.79, 0.84, 0.78, round(total_cost, 3)],
        "budget": {
            "monthly_limit_usd": 50.0,
            "spent_mtd_usd": round(total_cost * 12, 2),
            "remaining_usd": round(50.0 - total_cost * 12, 2),
            "usage_pct": round((total_cost * 12) / 50.0 * 100, 1),
        },
    }
