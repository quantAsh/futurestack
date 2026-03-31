"""
Notification Preferences Service - Manage user notification settings.
"""
from typing import Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from backend import models


def get_preferences(user_id: str, db: Session) -> Optional[models.NotificationPreferences]:
    """
    Get notification preferences for a user.
    Creates defaults if none exist.
    """
    prefs = db.query(models.NotificationPreferences).filter_by(user_id=user_id).first()
    
    if not prefs:
        # Create default preferences
        prefs = models.NotificationPreferences(
            id=str(uuid4()),
            user_id=user_id,
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    
    return prefs


def update_preferences(
    user_id: str,
    db: Session,
    email_marketing: Optional[bool] = None,
    email_transactional: Optional[bool] = None,
    email_digest: Optional[bool] = None,
    push_bookings: Optional[bool] = None,
    push_messages: Optional[bool] = None,
    push_community: Optional[bool] = None,
    push_ai_insights: Optional[bool] = None,
    digest_frequency: Optional[str] = None,
    quiet_hours_enabled: Optional[bool] = None,
    quiet_hours_start: Optional[int] = None,
    quiet_hours_end: Optional[int] = None,
    timezone: Optional[str] = None,
) -> models.NotificationPreferences:
    """
    Update notification preferences for a user.
    Only updates fields that are provided (not None).
    """
    prefs = get_preferences(user_id, db)
    
    # Update only provided fields
    if email_marketing is not None:
        prefs.email_marketing = email_marketing
    if email_transactional is not None:
        prefs.email_transactional = email_transactional
    if email_digest is not None:
        prefs.email_digest = email_digest
    if push_bookings is not None:
        prefs.push_bookings = push_bookings
    if push_messages is not None:
        prefs.push_messages = push_messages
    if push_community is not None:
        prefs.push_community = push_community
    if push_ai_insights is not None:
        prefs.push_ai_insights = push_ai_insights
    if digest_frequency is not None:
        prefs.digest_frequency = digest_frequency
    if quiet_hours_enabled is not None:
        prefs.quiet_hours_enabled = quiet_hours_enabled
    if quiet_hours_start is not None:
        prefs.quiet_hours_start = quiet_hours_start
    if quiet_hours_end is not None:
        prefs.quiet_hours_end = quiet_hours_end
    if timezone is not None:
        prefs.timezone = timezone
    
    db.commit()
    db.refresh(prefs)
    
    return prefs


def should_send_notification(
    user_id: str,
    notification_type: str,
    channel: str,  # 'email' or 'push'
    db: Session,
) -> bool:
    """
    Check if a notification should be sent based on user preferences.
    
    Args:
        user_id: User ID
        notification_type: Type of notification (booking, message, community, ai_insight, marketing)
        channel: Delivery channel ('email' or 'push')
        db: Database session
    
    Returns:
        True if notification should be sent
    """
    prefs = get_preferences(user_id, db)
    
    if channel == "email":
        if notification_type == "marketing":
            return prefs.email_marketing
        elif notification_type in ["booking", "payment"]:
            return prefs.email_transactional
        else:
            return prefs.email_transactional
    
    elif channel == "push":
        # Check quiet hours
        if prefs.quiet_hours_enabled:
            from datetime import datetime
            import pytz
            
            try:
                user_tz = pytz.timezone(prefs.timezone)
                now = datetime.now(user_tz)
                current_hour = now.hour
                
                # Check if in quiet hours
                if prefs.quiet_hours_start > prefs.quiet_hours_end:
                    # Spans midnight (e.g., 22:00 to 08:00)
                    if current_hour >= prefs.quiet_hours_start or current_hour < prefs.quiet_hours_end:
                        return False
                else:
                    # Same day (e.g., 01:00 to 06:00)
                    if prefs.quiet_hours_start <= current_hour < prefs.quiet_hours_end:
                        return False
            except:
                pass  # If timezone fails, send anyway
        
        # Check notification type
        if notification_type == "booking":
            return prefs.push_bookings
        elif notification_type == "message":
            return prefs.push_messages
        elif notification_type == "community":
            return prefs.push_community
        elif notification_type == "ai_insight":
            return prefs.push_ai_insights
        else:
            return True  # Default to sending unknown types
    
    return True


def get_digest_users(frequency: str, db: Session) -> list:
    """
    Get users who should receive digest notifications.
    
    Args:
        frequency: 'daily' or 'weekly'
        db: Database session
    
    Returns:
        List of user IDs
    """
    from datetime import datetime
    
    prefs_list = db.query(models.NotificationPreferences).filter(
        models.NotificationPreferences.email_digest == True,
        models.NotificationPreferences.digest_frequency == frequency,
    ).all()
    
    # For weekly digests, also check the day
    if frequency == "weekly":
        current_day = datetime.utcnow().weekday()
        prefs_list = [p for p in prefs_list if p.digest_day == current_day]
    
    return [p.user_id for p in prefs_list]
