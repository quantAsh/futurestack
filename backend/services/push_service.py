"""
Push Notification Service - Web Push notifications via VAPID.
"""
import json
from typing import Optional
from pywebpush import webpush, WebPushException
from backend.config import settings


def send_push_notification(
    subscription_info: dict,
    title: str,
    body: str,
    icon: Optional[str] = None,
    url: Optional[str] = None,
    data: Optional[dict] = None,
) -> bool:
    """
    Send a Web Push notification to a subscriber.
    
    Args:
        subscription_info: Push subscription object containing endpoint and keys
        title: Notification title
        body: Notification body text
        icon: Optional icon URL
        url: Optional click-through URL
        data: Optional additional data payload
    
    Returns:
        True if notification sent successfully
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        raise ValueError("VAPID keys not configured")

    payload = {
        "title": title,
        "body": body,
        "icon": icon or "/icons/notification-icon.png",
        "badge": "/icons/badge-icon.png",
        "data": {
            "url": url or "/",
            **(data or {}),
        },
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": settings.VAPID_CLAIM_EMAIL,
            },
        )
        return True
    except WebPushException as e:
        # 410 Gone means subscription expired/invalid
        if e.response and e.response.status_code == 410:
            return False  # Caller should remove this subscription
        raise


def send_notification_to_user(
    db,
    user_id: str,
    title: str,
    body: str,
    icon: Optional[str] = None,
    url: Optional[str] = None,
    data: Optional[dict] = None,
) -> dict:
    """
    Send push notification to all devices registered for a user.
    
    Args:
        db: Database session
        user_id: Target user ID
        title: Notification title
        body: Notification body
        icon: Optional icon URL
        url: Optional click-through URL
        data: Optional additional data
    
    Returns:
        dict with success count and failed subscriptions
    """
    from backend import models

    subscriptions = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.user_id == user_id)
        .all()
    )

    sent = 0
    failed_endpoints = []

    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh_key,
                "auth": sub.auth_key,
            },
        }

        try:
            success = send_push_notification(
                subscription_info=subscription_info,
                title=title,
                body=body,
                icon=icon,
                url=url,
                data=data,
            )
            if success:
                sent += 1
            else:
                failed_endpoints.append(sub.endpoint)
        except Exception:
            failed_endpoints.append(sub.endpoint)

    # Clean up invalid subscriptions
    if failed_endpoints:
        db.query(models.PushSubscription).filter(
            models.PushSubscription.endpoint.in_(failed_endpoints)
        ).delete(synchronize_session=False)
        db.commit()

    return {
        "sent": sent,
        "failed": len(failed_endpoints),
        "cleaned_up": failed_endpoints,
    }


def generate_vapid_keys() -> dict:
    """
    Generate new VAPID keys for push notifications.
    
    Returns:
        dict with public_key and private_key (base64 encoded)
    """
    from py_vapid import Vapid

    vapid = Vapid()
    vapid.generate_keys()

    return {
        "public_key": vapid.public_key.urlsafe_b64encode().decode(),
        "private_key": vapid.private_key.to_base64().decode(),
    }
