"""
Booking Commission Engine — calculates platform fees on every booking.

Fee structure:
- Guest service fee: 5% (4% on stays ≥ 30 nights)
- Host commission: 3%
- Combined: NomadNest earns 8% (7% on long stays) per booking

Revenue is tracked per booking for reporting and payout calculation.
"""
from typing import Dict, Any, Optional
from datetime import date
from uuid import uuid4
import logging

logger = logging.getLogger("nomadnest.commissions")

# Commission rates
GUEST_FEE_RATE = 0.05          # 5% guest service fee
GUEST_FEE_RATE_LONG_STAY = 0.04  # 4% for stays ≥ 30 nights
HOST_COMMISSION_RATE = 0.03    # 3% host commission
LONG_STAY_THRESHOLD_NIGHTS = 30


def calculate_commission(
    base_price: float,
    nights: int,
    currency: str = "USD",
) -> Dict[str, Any]:
    """
    Calculate booking commissions.
    
    Args:
        base_price: Total accommodation cost (nightly_rate × nights)
        nights: Number of nights
        currency: Currency code
    
    Returns:
        Breakdown of fees, totals, and what each party pays/receives
    """
    if base_price <= 0 or nights <= 0:
        return {
            "error": "Base price and nights must be positive",
            "guest_fee": 0,
            "host_commission": 0,
            "platform_revenue": 0,
        }

    # Determine guest fee rate (discount for long stays)
    is_long_stay = nights >= LONG_STAY_THRESHOLD_NIGHTS
    guest_fee_rate = GUEST_FEE_RATE_LONG_STAY if is_long_stay else GUEST_FEE_RATE

    # Calculate fees
    guest_fee = round(base_price * guest_fee_rate, 2)
    host_commission = round(base_price * HOST_COMMISSION_RATE, 2)
    platform_revenue = round(guest_fee + host_commission, 2)

    # What each party pays/receives
    guest_total = round(base_price + guest_fee, 2)
    host_payout = round(base_price - host_commission, 2)
    nightly_rate = round(base_price / nights, 2)

    return {
        "base_price": base_price,
        "currency": currency,
        "nights": nights,
        "nightly_rate": nightly_rate,
        "is_long_stay": is_long_stay,
        # Guest side
        "guest_fee_rate": guest_fee_rate,
        "guest_fee": guest_fee,
        "guest_total": guest_total,
        # Host side
        "host_commission_rate": HOST_COMMISSION_RATE,
        "host_commission": host_commission,
        "host_payout": host_payout,
        # Platform
        "platform_revenue": platform_revenue,
        "platform_rate": round(guest_fee_rate + HOST_COMMISSION_RATE, 4),
    }


def apply_commission_to_booking(
    db,
    booking_id: str,
    base_price: float,
    nights: int,
    currency: str = "USD",
) -> Dict[str, Any]:
    """
    Calculate and persist commission for a booking.
    Updates the booking record with fee breakdown.
    """
    from backend import models

    commission = calculate_commission(base_price, nights, currency)

    # Update booking with commission data
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if booking:
        # Store commission metadata (JSON or individual columns depending on model)
        booking.total_price = commission["guest_total"]
        booking.platform_fee = commission["platform_revenue"]
        booking.host_payout = commission["host_payout"]
        db.commit()

        logger.info(
            f"Commission applied: booking={booking_id} "
            f"base={base_price} guest_fee={commission['guest_fee']} "
            f"host_comm={commission['host_commission']} "
            f"platform={commission['platform_revenue']}"
        )

    return commission


def get_commission_summary(db, start_date: date, end_date: date) -> Dict[str, Any]:
    """
    Generate platform revenue report for a date range.
    """
    from backend import models

    bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.start_date >= start_date,
            models.Booking.start_date <= end_date,
        )
        .all()
    )

    total_gmv = 0.0        # Gross Merchandise Value
    total_revenue = 0.0     # Platform revenue (fees)
    total_bookings = 0
    long_stay_count = 0

    for b in bookings:
        price = getattr(b, "total_price", 0) or 0
        fee = getattr(b, "platform_fee", 0) or 0
        total_gmv += price
        total_revenue += fee
        total_bookings += 1

        # Estimate if long stay
        if b.start_date and b.end_date:
            nights = (b.end_date - b.start_date).days
            if nights >= LONG_STAY_THRESHOLD_NIGHTS:
                long_stay_count += 1

    return {
        "period": {"start": str(start_date), "end": str(end_date)},
        "total_bookings": total_bookings,
        "total_gmv": round(total_gmv, 2),
        "total_platform_revenue": round(total_revenue, 2),
        "average_commission_rate": round(total_revenue / total_gmv, 4) if total_gmv > 0 else 0,
        "long_stay_bookings": long_stay_count,
        "long_stay_percentage": round(long_stay_count / total_bookings * 100, 1) if total_bookings > 0 else 0,
    }
