"""
Serendipity Engine - Proactive AI suggestions for connections and opportunities.
"""
import json
import structlog
from uuid import uuid4
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models


def generate_connection_suggestions(user_id: str) -> list:
    """
    Find potential connections for a user based on:
    - Same hub membership
    - Complementary skills (future: from user.skills)
    - Similar goals
    """
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return []

        # Find other users (simple: just get other users for now)
        other_users = (
            db.query(models.User).filter(models.User.id != user_id).limit(5).all()
        )

        suggestions = []
        for other in other_users:
            # Generate a reason for connection
            reasons = []
            if user.is_host and not other.is_host:
                reasons.append("They might be looking for a place to stay")
            if not user.is_host and other.is_host:
                reasons.append("They're a host with listings available")
            if user.bio and other.bio:
                reasons.append("You both have detailed profiles")

            if reasons:
                suggestions.append(
                    {
                        "user_id": other.id,
                        "user_name": other.name,
                        "reason": reasons[0],
                        "type": "connection",
                    }
                )

        return suggestions[:3]  # Top 3
    finally:
        db.close()


def generate_hub_suggestions(user_id: str) -> list:
    """Suggest hubs the user might be interested in."""
    db = SessionLocal()
    try:
        hubs = db.query(models.Hub).limit(3).all()
        return [
            {
                "hub_id": h.id,
                "hub_name": h.name,
                "reason": f"Check out {h.name} - {h.mission}",
                "type": "hub_recommendation",
            }
            for h in hubs
        ]
    finally:
        db.close()


def create_serendipity_notifications(user_id: str) -> int:
    """
    Generate and store serendipity notifications for a user.
    Returns count of notifications created.
    """
    db = SessionLocal()
    try:
        created = 0

        # Connection suggestions
        connections = generate_connection_suggestions(user_id)
        for conn in connections:
            notification = models.Notification(
                id=str(uuid4()),
                user_id=user_id,
                type="connection",
                title=f"Connect with {conn['user_name']}",
                description=conn["reason"],
                action_type="view_profile",
                action_data=json.dumps({"target_user_id": conn["user_id"]}),
            )
            db.add(notification)
            created += 1

        # Hub suggestions
        hubs = generate_hub_suggestions(user_id)
        for hub in hubs[:1]:  # Just one hub suggestion
            notification = models.Notification(
                id=str(uuid4()),
                user_id=user_id,
                type="opportunity",
                title=f"Discover {hub['hub_name']}",
                description=hub["reason"],
                action_type="view_hub",
                action_data=json.dumps({"hub_id": hub["hub_id"]}),
            )
            db.add(notification)
            created += 1

        db.commit()
        return created
    except Exception as e:
        db.rollback()
        structlog.get_logger("nomadnest.serendipity").error("notification_create_failed", error=str(e))
        return 0
    finally:
        db.close()
