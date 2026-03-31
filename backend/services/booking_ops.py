"""
Booking Operations — Admin panel analytics for the booking pipeline.

Provides:
    1. Job Pipeline     — booking requests by status (queued → running → completed/failed)
    2. Payment Gates    — pre-auth, pending, and completed payments
    3. Funnel Analytics — drop-off analysis through the 9-step booking flow
    4. Agent Jobs       — browser-agent task execution history
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List


# ═══════════════════════════════════════════════════════════════
# 1. BOOKING JOB PIPELINE
# ═══════════════════════════════════════════════════════════════

def get_booking_pipeline() -> Dict[str, Any]:
    """Get booking requests grouped by pipeline stage."""
    now = datetime.now(timezone.utc)

    jobs = [
        {"id": "BK-001", "user": "Sarah M.", "destination": "Bali", "budget": 1200, "status": "completed", "progress": 100, "step": "Booking confirmed!", "created": (now - timedelta(hours=3)).isoformat(), "duration_min": 12},
        {"id": "BK-002", "user": "Jake R.", "destination": "Chiang Mai", "budget": 800, "status": "awaiting_approval", "progress": 70, "step": "Awaiting user approval", "created": (now - timedelta(hours=1)).isoformat(), "duration_min": None},
        {"id": "BK-003", "user": "Kim L.", "destination": "Lisbon", "budget": 2000, "status": "searching", "progress": 35, "step": "Checking availability...", "created": (now - timedelta(minutes=15)).isoformat(), "duration_min": None},
        {"id": "BK-004", "user": "Tom W.", "destination": "Mexico City", "budget": 600, "status": "failed", "progress": 45, "step": "No availability found", "created": (now - timedelta(hours=5)).isoformat(), "duration_min": 8, "error": "All matched listings fully booked for requested dates"},
        {"id": "BK-005", "user": "Anna P.", "destination": "Medellín", "budget": 1500, "status": "pending", "progress": 0, "step": "In queue", "created": (now - timedelta(minutes=2)).isoformat(), "duration_min": None},
        {"id": "BK-006", "user": "Marcus D.", "destination": "Bangkok", "budget": 900, "status": "completed", "progress": 100, "step": "Booking confirmed!", "created": (now - timedelta(hours=8)).isoformat(), "duration_min": 15},
        {"id": "BK-007", "user": "Priya K.", "destination": "Da Nang", "budget": 700, "status": "comparing", "progress": 55, "step": "Comparing 3 options...", "created": (now - timedelta(minutes=30)).isoformat(), "duration_min": None},
        {"id": "BK-008", "user": "Leo G.", "destination": "Tbilisi", "budget": 500, "status": "cancelled", "progress": 25, "step": "Cancelled by user", "created": (now - timedelta(hours=2)).isoformat(), "duration_min": 5},
    ]

    pipeline = {"pending": [], "searching": [], "comparing": [], "awaiting_approval": [], "booking": [], "completed": [], "failed": [], "cancelled": []}
    for j in jobs:
        pipeline.setdefault(j["status"], []).append(j)

    return {
        "timestamp": now.isoformat(),
        "total_jobs": len(jobs),
        "pipeline": {
            "pending": len(pipeline.get("pending", [])),
            "active": len(pipeline.get("searching", [])) + len(pipeline.get("comparing", [])) + len(pipeline.get("booking", [])),
            "awaiting_approval": len(pipeline.get("awaiting_approval", [])),
            "completed": len(pipeline.get("completed", [])),
            "failed": len(pipeline.get("failed", [])),
            "cancelled": len(pipeline.get("cancelled", [])),
        },
        "success_rate_pct": round(len(pipeline.get("completed", [])) / max(len(jobs), 1) * 100, 1),
        "avg_duration_min": round(sum(j["duration_min"] for j in jobs if j["duration_min"]) / max(sum(1 for j in jobs if j["duration_min"]), 1)),
        "jobs": jobs,
    }


# ═══════════════════════════════════════════════════════════════
# 2. PAYMENT GATES
# ═══════════════════════════════════════════════════════════════

def get_payment_gates() -> Dict[str, Any]:
    """Get payment authorization and settlement status."""
    now = datetime.now(timezone.utc)

    payments = [
        {"booking_id": "BK-001", "user": "Sarah M.", "amount": 980, "status": "settled", "method": "Stripe", "authorized_at": (now - timedelta(hours=3)).isoformat(), "settled_at": (now - timedelta(hours=2, minutes=45)).isoformat()},
        {"booking_id": "BK-002", "user": "Jake R.", "amount": 650, "status": "pre_authorized", "method": "Stripe", "authorized_at": (now - timedelta(hours=1)).isoformat(), "settled_at": None},
        {"booking_id": "BK-006", "user": "Marcus D.", "amount": 1120, "status": "settled", "method": "Stripe", "authorized_at": (now - timedelta(hours=8)).isoformat(), "settled_at": (now - timedelta(hours=7, minutes=30)).isoformat()},
        {"booking_id": "BK-007", "user": "Priya K.", "amount": 540, "status": "pending", "method": "Stripe", "authorized_at": None, "settled_at": None},
        {"booking_id": "BK-004", "user": "Tom W.", "amount": 0, "status": "voided", "method": "N/A", "authorized_at": None, "settled_at": None},
    ]

    settled_total = sum(p["amount"] for p in payments if p["status"] == "settled")
    pre_auth_total = sum(p["amount"] for p in payments if p["status"] == "pre_authorized")

    return {
        "total_payments": len(payments),
        "settled": sum(1 for p in payments if p["status"] == "settled"),
        "pre_authorized": sum(1 for p in payments if p["status"] == "pre_authorized"),
        "pending": sum(1 for p in payments if p["status"] == "pending"),
        "voided": sum(1 for p in payments if p["status"] == "voided"),
        "settled_total_usd": settled_total,
        "pre_auth_hold_usd": pre_auth_total,
        "payments": payments,
    }


# ═══════════════════════════════════════════════════════════════
# 3. BOOKING FUNNEL — 9-step drop-off analysis
# ═══════════════════════════════════════════════════════════════

def get_booking_funnel() -> Dict[str, Any]:
    """Get booking funnel drop-off through the 9 workflow steps."""
    steps = [
        {"step": 0, "name": "Analyze Request", "entered": 100, "completed": 98, "dropped": 2},
        {"step": 1, "name": "Search Listings", "entered": 98, "completed": 92, "dropped": 6},
        {"step": 2, "name": "Check Availability", "entered": 92, "completed": 78, "dropped": 14},
        {"step": 3, "name": "Compare Options", "entered": 78, "completed": 72, "dropped": 6},
        {"step": 4, "name": "Verify Details", "entered": 72, "completed": 70, "dropped": 2},
        {"step": 5, "name": "Await Approval", "entered": 70, "completed": 52, "dropped": 18},
        {"step": 6, "name": "Initiate Booking", "entered": 52, "completed": 48, "dropped": 4},
        {"step": 7, "name": "Confirm Payment", "entered": 48, "completed": 45, "dropped": 3},
        {"step": 8, "name": "Finalize", "entered": 45, "completed": 44, "dropped": 1},
    ]

    # Biggest drop-off
    worst = max(steps, key=lambda s: s["dropped"])

    return {
        "period": "last_30_days",
        "total_started": 100,
        "total_completed": 44,
        "overall_conversion_pct": 44.0,
        "biggest_dropoff": {"step": worst["name"], "dropped": worst["dropped"], "pct": round(worst["dropped"] / max(worst["entered"], 1) * 100, 1)},
        "steps": steps,
    }


# ═══════════════════════════════════════════════════════════════
# 4. AGENT JOBS — Browser agent execution history
# ═══════════════════════════════════════════════════════════════

def get_agent_jobs() -> Dict[str, Any]:
    """Get browser agent job execution history."""
    now = datetime.now(timezone.utc)

    jobs = [
        {"id": "AJ-001", "url": "booking.com/hotel-xyz", "goal": "Check availability for 14 nights", "status": "completed", "steps_completed": 6, "total_steps": 6, "duration_sec": 32, "started": (now - timedelta(hours=3)).isoformat()},
        {"id": "AJ-002", "url": "hostelworld.com/hostel-abc", "goal": "Book dorm bed for 7 nights", "status": "stopped_at_payment", "steps_completed": 5, "total_steps": 6, "duration_sec": 28, "started": (now - timedelta(hours=2)).isoformat()},
        {"id": "AJ-003", "url": "airbnb.com/listing-456", "goal": "Reserve apartment for 30 nights", "status": "failed", "steps_completed": 2, "total_steps": 6, "duration_sec": 8, "started": (now - timedelta(hours=5)).isoformat(), "error": "Navigation timeout — site loaded slowly"},
        {"id": "AJ-004", "url": "booking.com/hotel-def", "goal": "Check pricing for week stay", "status": "completed", "steps_completed": 6, "total_steps": 6, "duration_sec": 25, "started": (now - timedelta(hours=8)).isoformat()},
        {"id": "AJ-005", "url": "hostelworld.com/hostel-ghi", "goal": "Book private room", "status": "running", "steps_completed": 3, "total_steps": 6, "duration_sec": None, "started": (now - timedelta(minutes=1)).isoformat()},
    ]

    return {
        "total_jobs": len(jobs),
        "completed": sum(1 for j in jobs if j["status"] == "completed"),
        "running": sum(1 for j in jobs if j["status"] == "running"),
        "failed": sum(1 for j in jobs if j["status"] == "failed"),
        "stopped_at_payment": sum(1 for j in jobs if j["status"] == "stopped_at_payment"),
        "avg_duration_sec": round(sum(j["duration_sec"] for j in jobs if j["duration_sec"]) / max(sum(1 for j in jobs if j["duration_sec"]), 1)),
        "jobs": jobs,
    }
