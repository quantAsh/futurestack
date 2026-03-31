"""
Proactive AI Notification Service.
Generates AI-driven insights and pushes them to users via WebSocket.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

try:
    import structlog
    logger = structlog.get_logger("nomadnest.proactive_ai")
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.proactive_ai")

from backend.database import SessionLocal
from backend import models


# --- Notification Types ---

async def check_price_drops(db: Session, user_id: str) -> List[dict]:
    """
    Check for price drops on listings the user has viewed or saved.
    Returns list of notification dicts.
    """
    notifications = []
    
    # Get user's recent bookings to understand their preferences
    recent_bookings = db.query(models.Booking).filter(
        models.Booking.user_id == user_id,
        models.Booking.created_at > datetime.utcnow() - timedelta(days=90)
    ).limit(5).all()
    
    if not recent_bookings:
        return notifications
    
    # Get cities user has stayed in
    booked_listing_ids = [b.listing_id for b in recent_bookings]
    booked_listings = db.query(models.Listing).filter(
        models.Listing.id.in_(booked_listing_ids)
    ).all()
    
    cities = list(set(l.city for l in booked_listings if l.city))
    
    if cities:
        # Find listings in those cities with lower prices
        for city in cities[:2]:  # Limit to 2 cities
            affordable_listings = db.query(models.Listing).filter(
                models.Listing.city.ilike(f"%{city}%"),
                models.Listing.price_usd.isnot(None)
            ).order_by(models.Listing.price_usd).limit(1).all()
            
            for listing in affordable_listings:
                if listing.id not in booked_listing_ids:
                    notifications.append({
                        "type": "price_drop",
                        "title": f"New deal in {city}!",
                        "message": f"{listing.name} is available at ${listing.price_usd}/month",
                        "listing_id": listing.id,
                        "city": city,
                        "priority": "low"
                    })
    
    return notifications


async def generate_travel_suggestions(db: Session, user_id: str) -> List[dict]:
    """
    Generate personalized travel suggestions based on user preferences.
    """
    notifications = []
    
    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return notifications
    
    # Check for upcoming journey gaps
    upcoming_bookings = db.query(models.Booking).filter(
        models.Booking.user_id == user_id,
        models.Booking.end_date >= datetime.now().date(),
        models.Booking.end_date <= datetime.now().date() + timedelta(days=30)
    ).first()
    
    if upcoming_bookings:
        # User has a booking ending soon - suggest next destination
        end_date = upcoming_bookings.end_date
        
        # Find hubs with availability
        hubs = db.query(models.Hub).limit(3).all()
        if hubs:
            hub = hubs[0]
            notifications.append({
                "type": "travel_suggestion",
                "title": "Plan your next destination",
                "message": f"Your stay ends on {end_date.strftime('%b %d')}. Consider {hub.name} for your next adventure!",
                "hub_id": hub.id,
                "priority": "medium"
            })
    
    return notifications


async def check_booking_reminders(db: Session, user_id: str) -> List[dict]:
    """
    Generate reminders for upcoming bookings.
    """
    notifications = []
    
    # Check for bookings starting in 3 days
    start_threshold = datetime.now().date() + timedelta(days=3)
    
    upcoming = db.query(models.Booking).filter(
        models.Booking.user_id == user_id,
        models.Booking.start_date == start_threshold
    ).first()
    
    if upcoming:
        listing = db.query(models.Listing).filter(
            models.Listing.id == upcoming.listing_id
        ).first()
        
        if listing:
            notifications.append({
                "type": "booking_reminder",
                "title": "Upcoming Stay Reminder",
                "message": f"Your stay at {listing.name} begins in 3 days. Get ready! 🧳",
                "booking_id": upcoming.id,
                "listing_id": listing.id,
                "priority": "high"
            })
    
    return notifications


async def check_community_activity(db: Session, user_id: str) -> List[dict]:
    """
    Notify about community activity at user's hubs.
    """
    notifications = []
    
    # Find user's current or upcoming booking
    current_booking = db.query(models.Booking).filter(
        models.Booking.user_id == user_id,
        models.Booking.start_date <= datetime.now().date(),
        models.Booking.end_date >= datetime.now().date()
    ).first()
    
    if current_booking:
        # Check for upcoming events at this hub
        listing = db.query(models.Listing).filter(
            models.Listing.id == current_booking.listing_id
        ).first()
        
        if listing and listing.hub_id:
            upcoming_events = db.query(models.CommunityEvent).filter(
                models.CommunityEvent.hub_id == listing.hub_id,
                models.CommunityEvent.date >= datetime.now(),
                models.CommunityEvent.date <= datetime.now() + timedelta(days=7)
            ).limit(1).all()
            
            for event in upcoming_events:
                notifications.append({
                    "type": "community_event",
                    "title": f"Upcoming: {event.name}",
                    "message": f"Join the community event on {event.date.strftime('%b %d')}!",
                    "event_id": event.id,
                    "hub_id": listing.hub_id,
                    "priority": "medium"
                })
    
    return notifications


# --- Main Proactive Loop ---

async def check_ota_price_watches(db: Session, user_id: str) -> List[dict]:
    """
    Check user's search watches against live OTA prices.
    Triggers a notification if prices dropped since last check.
    """
    notifications = []
    
    try:
        from backend.services.watcher_service import watcher_service
        watches = watcher_service.get_user_watches(user_id)
        
        for watch in watches[:3]:  # Limit to 3 watches
            criteria = watch.get("criteria", {})
            location = criteria.get("location")
            max_price = criteria.get("max_price")
            
            if not location:
                continue
            
            # Use scout agent for quick price intel (no live OTA call to avoid rate limits)
            from backend.services.scout_agent import get_destination_brief
            brief = get_destination_brief(location, budget_tier="budget")
            
            cost = brief.get("cost_of_living", {})
            estimate = cost.get("monthly_estimate")
            
            if estimate and max_price and estimate <= max_price:
                notifications.append({
                    "type": "price_watch",
                    "title": f"🎯 Sniper Alert: {location}",
                    "message": f"Budget stays in {location} start at ~${estimate}/mo — within your ${max_price} target. Want me to search for specific dates?",
                    "watch_id": watch.get("id"),
                    "priority": "high",
                })
    except Exception as e:
        logger.warning("ota_price_watch_error", error=str(e))
    
    return notifications


async def check_visa_warnings(db: Session, user_id: str) -> List[dict]:
    """
    Warn users about upcoming visa expirations based on booking dates.
    """
    notifications = []
    
    # Find bookings ending in 7-14 days
    warning_start = datetime.now().date() + timedelta(days=7)
    warning_end = datetime.now().date() + timedelta(days=14)
    
    ending_bookings = db.query(models.Booking).filter(
        models.Booking.user_id == user_id,
        models.Booking.end_date >= warning_start,
        models.Booking.end_date <= warning_end
    ).all()
    
    for booking in ending_bookings:
        listing = db.query(models.Listing).filter(
            models.Listing.id == booking.listing_id
        ).first()
        
        if listing and listing.country:
            notifications.append({
                "type": "visa_warning",
                "title": f"🛂 Stay ending in {listing.country}",
                "message": f"Your booking at {listing.name} ends on {booking.end_date.strftime('%b %d')}. Check your visa status and plan your next destination.",
                "booking_id": booking.id,
                "country": listing.country,
                "priority": "high",
            })
    
    return notifications


async def generate_proactive_notifications(user_id: str) -> List[dict]:
    """
    Generate all proactive notifications for a user.
    Returns list of notification dicts ready to emit.
    """
    db = SessionLocal()
    try:
        all_notifications = []
        
        # Run all checks
        all_notifications.extend(await check_booking_reminders(db, user_id))
        all_notifications.extend(await check_visa_warnings(db, user_id))
        all_notifications.extend(await check_ota_price_watches(db, user_id))
        all_notifications.extend(await check_community_activity(db, user_id))
        all_notifications.extend(await generate_travel_suggestions(db, user_id))
        all_notifications.extend(await check_price_drops(db, user_id))
        
        # Limit to top 3 most relevant
        # Sort by priority: high > medium > low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_notifications.sort(key=lambda n: priority_order.get(n.get("priority", "low"), 2))
        
        return all_notifications[:3]
    finally:
        db.close()


async def proactive_notification_loop(interval_minutes: int = 60):
    """
    Background task that periodically generates and emits proactive notifications.
    Should be started on app startup.
    """
    from backend.socket_server import emit_proactive_insight
    
    logger.info("proactive_notification_loop_started", interval=interval_minutes)
    
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            
            db = SessionLocal()
            try:
                # Get active users (those with recent activity)
                active_users = db.query(models.User).filter(
                    models.User.created_at > datetime.utcnow() - timedelta(days=30)
                ).limit(100).all()
                
                for user in active_users:
                    notifications = await generate_proactive_notifications(user.id)
                    
                    for notif in notifications:
                        try:
                            await emit_proactive_insight(user.id, notif)
                            logger.info("proactive_notification_sent",
                                       user_id=user.id,
                                       type=notif.get("type"))
                        except Exception as e:
                            logger.warning("proactive_notification_error",
                                          user_id=user.id,
                                          error=str(e))
            finally:
                db.close()
                
        except asyncio.CancelledError:
            logger.info("proactive_notification_loop_cancelled")
            break
        except Exception as e:
            logger.error("proactive_notification_loop_error", error=str(e))
            await asyncio.sleep(60)  # Wait before retrying
