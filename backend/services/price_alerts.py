"""
Price Drop Alerts Service.

Monitors listings and notifies users when prices drop.
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from uuid import uuid4

from backend import models

logger = structlog.get_logger(__name__)


class PriceAlertService:
    """
    Price alert management and monitoring.
    
    Features:
    - Create alerts for specific listings
    - Create alerts for search criteria
    - Track price history
    - Check for triggered alerts
    """
    
    def create_listing_alert(
        self,
        db: Session,
        user_id: str,
        listing_id: str,
        target_price: Optional[float] = None,
        drop_percent: Optional[float] = None,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
    ) -> models.PriceAlert:
        """Create a price alert for a specific listing."""
        # Get current listing price
        listing = db.query(models.Listing).filter(
            models.Listing.id == listing_id
        ).first()
        
        if not listing:
            raise ValueError("Listing not found")
        
        original_price = listing.price_per_night or listing.price_per_month
        
        alert = models.PriceAlert(
            id=str(uuid4()),
            user_id=user_id,
            alert_type="listing",
            listing_id=listing_id,
            target_price=target_price,
            drop_percent=drop_percent or 10.0,  # Default 10% drop
            original_price=original_price,
            check_in_date=datetime.strptime(check_in, "%Y-%m-%d").date() if check_in else None,
            check_out_date=datetime.strptime(check_out, "%Y-%m-%d").date() if check_out else None,
        )
        
        db.add(alert)
        
        # Record current price in history
        self._record_price(db, listing_id, original_price)
        
        db.commit()
        db.refresh(alert)
        
        logger.info("price_alert_created", alert_id=alert.id, listing_id=listing_id)
        return alert
    
    def create_search_alert(
        self,
        db: Session,
        user_id: str,
        city: str,
        max_price: float,
        criteria: Optional[Dict] = None,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
    ) -> models.PriceAlert:
        """Create a price alert for search criteria."""
        search_criteria = {
            "city": city,
            "max_price": max_price,
            **(criteria or {}),
        }
        
        alert = models.PriceAlert(
            id=str(uuid4()),
            user_id=user_id,
            alert_type="search",
            city=city,
            target_price=max_price,
            search_criteria=search_criteria,
            check_in_date=datetime.strptime(check_in, "%Y-%m-%d").date() if check_in else None,
            check_out_date=datetime.strptime(check_out, "%Y-%m-%d").date() if check_out else None,
        )
        
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        logger.info("search_alert_created", alert_id=alert.id, city=city)
        return alert
    
    def get_user_alerts(
        self,
        db: Session,
        user_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get all alerts for a user."""
        query = db.query(models.PriceAlert).filter(
            models.PriceAlert.user_id == user_id
        )
        
        if not include_inactive:
            query = query.filter(models.PriceAlert.is_active == True)
        
        alerts = query.order_by(models.PriceAlert.created_at.desc()).all()
        
        result = []
        for alert in alerts:
            listing = None
            current_price = None
            price_change = None
            
            if alert.listing_id:
                listing = db.query(models.Listing).filter(
                    models.Listing.id == alert.listing_id
                ).first()
                
                if listing:
                    current_price = listing.price_per_night or listing.price_per_month
                    if alert.original_price and current_price:
                        price_change = ((current_price - alert.original_price) / alert.original_price) * 100
            
            result.append({
                "id": alert.id,
                "alert_type": alert.alert_type,
                "listing": {
                    "id": listing.id,
                    "title": listing.title,
                    "city": listing.city,
                    "image": listing.images[0] if listing and listing.images else None,
                } if listing else None,
                "city": alert.city,
                "search_criteria": alert.search_criteria,
                "target_price": alert.target_price,
                "drop_percent": alert.drop_percent,
                "original_price": alert.original_price,
                "current_price": current_price,
                "price_change_percent": round(price_change, 1) if price_change else None,
                "is_active": alert.is_active,
                "times_triggered": alert.times_triggered,
                "last_notified": alert.last_notified.isoformat() if alert.last_notified else None,
                "check_in": alert.check_in_date.isoformat() if alert.check_in_date else None,
                "check_out": alert.check_out_date.isoformat() if alert.check_out_date else None,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            })
        
        return result
    
    def delete_alert(
        self,
        db: Session,
        alert_id: str,
        user_id: str,
    ) -> bool:
        """Delete an alert."""
        alert = db.query(models.PriceAlert).filter(
            models.PriceAlert.id == alert_id,
            models.PriceAlert.user_id == user_id,
        ).first()
        
        if not alert:
            return False
        
        db.delete(alert)
        db.commit()
        
        logger.info("price_alert_deleted", alert_id=alert_id)
        return True
    
    def toggle_alert(
        self,
        db: Session,
        alert_id: str,
        user_id: str,
    ) -> Optional[bool]:
        """Toggle alert active status."""
        alert = db.query(models.PriceAlert).filter(
            models.PriceAlert.id == alert_id,
            models.PriceAlert.user_id == user_id,
        ).first()
        
        if not alert:
            return None
        
        alert.is_active = not alert.is_active
        db.commit()
        
        return alert.is_active
    
    def _record_price(
        self,
        db: Session,
        listing_id: str,
        price: float,
        price_type: str = "nightly",
    ):
        """Record a price point in history."""
        history = models.PriceHistory(
            id=str(uuid4()),
            listing_id=listing_id,
            price=price,
            price_type=price_type,
        )
        db.add(history)
    
    def get_price_history(
        self,
        db: Session,
        listing_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get price history for a listing."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        history = db.query(models.PriceHistory).filter(
            models.PriceHistory.listing_id == listing_id,
            models.PriceHistory.recorded_at >= cutoff,
        ).order_by(models.PriceHistory.recorded_at).all()
        
        return [
            {
                "price": h.price,
                "date": h.recorded_at.isoformat(),
            }
            for h in history
        ]
    
    def check_alerts(
        self,
        db: Session,
    ) -> List[Dict[str, Any]]:
        """
        Check all active alerts for triggered conditions.
        Returns list of triggered alerts with details.
        """
        triggered = []
        
        alerts = db.query(models.PriceAlert).filter(
            models.PriceAlert.is_active == True
        ).all()
        
        for alert in alerts:
            if alert.alert_type == "listing" and alert.listing_id:
                listing = db.query(models.Listing).filter(
                    models.Listing.id == alert.listing_id
                ).first()
                
                if not listing:
                    continue
                
                current_price = listing.price_per_night or listing.price_per_month
                
                # Check target price
                if alert.target_price and current_price and current_price <= alert.target_price:
                    triggered.append(self._trigger_alert(db, alert, current_price, "below_target"))
                    continue
                
                # Check drop percent
                if alert.drop_percent and alert.original_price and current_price:
                    drop = ((alert.original_price - current_price) / alert.original_price) * 100
                    if drop >= alert.drop_percent:
                        triggered.append(self._trigger_alert(db, alert, current_price, "percent_drop", drop))
            
            elif alert.alert_type == "search" and alert.search_criteria:
                # Find matching listings below target price
                criteria = alert.search_criteria
                city = criteria.get("city")
                max_price = criteria.get("max_price")
                
                if city and max_price:
                    matches = db.query(models.Listing).filter(
                        models.Listing.city.ilike(f"%{city}%"),
                        or_(
                            models.Listing.price_per_night <= max_price,
                            models.Listing.price_per_month <= max_price * 30,
                        )
                    ).limit(5).all()
                    
                    if matches:
                        triggered.append({
                            "alert_id": alert.id,
                            "user_id": alert.user_id,
                            "type": "search_match",
                            "city": city,
                            "matches_count": len(matches),
                            "matches": [
                                {"id": m.id, "title": m.title, "price": m.price_per_night}
                                for m in matches
                            ],
                        })
        
        return triggered
    
    def _trigger_alert(
        self,
        db: Session,
        alert: models.PriceAlert,
        current_price: float,
        reason: str,
        drop_percent: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Mark alert as triggered and return notification data."""
        alert.times_triggered += 1
        alert.last_notified = datetime.utcnow()
        alert.last_checked = datetime.utcnow()
        db.commit()
        
        return {
            "alert_id": alert.id,
            "user_id": alert.user_id,
            "listing_id": alert.listing_id,
            "reason": reason,
            "original_price": alert.original_price,
            "current_price": current_price,
            "drop_percent": drop_percent,
            "target_price": alert.target_price,
        }
    
    def get_savings_summary(
        self,
        db: Session,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get summary of potential savings from alerts."""
        alerts = db.query(models.PriceAlert).filter(
            models.PriceAlert.user_id == user_id,
            models.PriceAlert.times_triggered > 0,
        ).all()
        
        total_saved = 0
        for alert in alerts:
            if alert.original_price and alert.listing_id:
                listing = db.query(models.Listing).filter(
                    models.Listing.id == alert.listing_id
                ).first()
                if listing:
                    current = listing.price_per_night or listing.price_per_month
                    if current and alert.original_price > current:
                        total_saved += alert.original_price - current
        
        return {
            "total_alerts": len(alerts),
            "times_triggered": sum(a.times_triggered for a in alerts),
            "potential_savings_usd": round(total_saved, 2),
        }


# Singleton
price_alert_service = PriceAlertService()
