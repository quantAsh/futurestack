from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import uuid4

from backend import models


class CommissionTracker:
    def __init__(self, db: Session):
        self.db = db

    def create_ota_booking(
        self,
        user_id: str,
        external_listing_id: str,
        provider_id: str,
        start_date: date,
        end_date: date,
        total_price: float,
        currency: str = "USD",
        status: str = "pending",
        external_ref: Optional[str] = None,
    ) -> models.OTABooking:
        # Get provider commission rate
        provider = (
            self.db.query(models.OTAProvider)
            .filter(models.OTAProvider.id == provider_id)
            .first()
        )
        rate = provider.commission_rate if provider else 0.0

        commission = total_price * rate

        booking = models.OTABooking(
            id=str(uuid4()),
            user_id=user_id,
            external_listing_id=external_listing_id,
            provider_id=provider_id,
            start_date=start_date,
            end_date=end_date,
            total_price=total_price,
            currency=currency,
            commission_earned=commission,
            booking_status=status,
            external_booking_ref=external_ref,
        )

        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def get_commission_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate commission report"""

        bookings = (
            self.db.query(models.OTABooking)
            .filter(
                models.OTABooking.created_at >= start_date,
                models.OTABooking.created_at <= end_date,
                models.OTABooking.booking_status.in_(["confirmed", "completed"]),
            )
            .all()
        )

        total_commission = sum(b.commission_earned for b in bookings)

        by_provider = {}
        for b in bookings:
            p_name = b.provider.name if b.provider else b.provider_id
            if p_name not in by_provider:
                by_provider[p_name] = {"count": 0, "commission": 0.0, "revenue": 0.0}

            by_provider[p_name]["count"] += 1
            by_provider[p_name]["commission"] += b.commission_earned
            by_provider[p_name]["revenue"] += b.total_price

        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "total_bookings": len(bookings),
            "total_commission": round(total_commission, 2),
            "breakdown": by_provider,
        }
