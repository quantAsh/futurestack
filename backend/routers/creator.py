"""
Creator Economy Router - Paid experiences and host earnings.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import uuid4

from backend import models
from backend.database import get_db
from backend.services.experience_generator import experience_generator

router = APIRouter()

PLATFORM_FEE_RATE = 0.15  # 15% platform fee (default)
MIN_HOST_SHARE = 0.70  # Hosts must keep at least 70%
TREASURY_FEE_RATE = 0.01  # 1% goes to community treasury


def get_db_dep():
    yield from get_db()


class ExperienceBookingRequest(BaseModel):
    user_id: str
    experience_id: str
    booking_date: str  # YYYY-MM-DD
    num_guests: int = 1


class ExperiencePriceUpdate(BaseModel):
    price_usd: float
    max_guests: Optional[int] = None
    revenue_share_rate: Optional[float] = None  # Host's share (0.70 to 0.99)


class ExperienceCreate(BaseModel):
    name: str
    type: str  # Residency or Retreat
    theme: Optional[str] = None
    mission: Optional[str] = None
    curator_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    price_usd: Optional[float] = None
    city: Optional[str] = None
    country: Optional[str] = None
    amenities: Optional[list[str]] = []
    activities: Optional[list[str]] = []


@router.post("/experiences")
def create_experience(experience: ExperienceCreate, db: Session = Depends(get_db_dep)):
    """Publish a new experience."""
    new_experience = models.Experience(
        id=str(uuid4()),
        name=experience.name,
        type=experience.type,
        theme=experience.theme,
        mission=experience.mission,
        curator_id=experience.curator_id,
        start_date=experience.start_date,
        end_date=experience.end_date,
        price_usd=experience.price_usd,
        city=experience.city,
        country=experience.country,
        amenities=experience.amenities,
        activities=experience.activities,
    )
    db.add(new_experience)
    db.commit()
    db.refresh(new_experience)

    return {
        "status": "published",
        "experience_id": new_experience.id,
        "name": new_experience.name,
        "revenue_split": {
            "host_share": f"{(1 - PLATFORM_FEE_RATE - TREASURY_FEE_RATE) * 100:.0f}%",
            "platform_fee": f"{PLATFORM_FEE_RATE * 100:.0f}%",
            "treasury_fee": f"{TREASURY_FEE_RATE * 100:.0f}%",
        },
    }


@router.post("/experiences/{experience_id}/generate-promo")
async def generate_experience_promo(
    experience_id: str, db: Session = Depends(get_db_dep)
):
    """Generate AI promotional content for an experience."""
    experience = (
        db.query(models.Experience)
        .filter(models.Experience.id == experience_id)
        .first()
    )
    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    experience_data = {
        "name": experience.name,
        "type": experience.type,
        "theme": experience.theme,
        "mission": experience.mission,
        "city": experience.city,
    }

    promo = await experience_generator.generate_promo_block(experience_data)
    return promo


@router.post("/experiences/{experience_id}/book")
def book_experience(
    experience_id: str,
    request: ExperienceBookingRequest,
    db: Session = Depends(get_db_dep),
):
    """Book a paid experience."""
    experience = (
        db.query(models.Experience)
        .filter(models.Experience.id == experience_id)
        .first()
    )

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    # Calculate price
    price_per_guest = getattr(experience, "price_usd", 50) or 50
    total_price = price_per_guest * request.num_guests

    # Use per-experience revenue share rate (or default)
    host_share_rate = getattr(experience, "revenue_share_rate", None) or (1 - PLATFORM_FEE_RATE - TREASURY_FEE_RATE)
    platform_fee = total_price * PLATFORM_FEE_RATE
    treasury_fee = total_price * TREASURY_FEE_RATE
    net_amount = total_price - platform_fee - treasury_fee

    # Create booking
    booking = models.ExperienceBooking(
        id=str(uuid4()),
        experience_id=experience_id,
        user_id=request.user_id,
        booking_date=datetime.fromisoformat(request.booking_date),
        num_guests=request.num_guests,
        total_price_usd=total_price,
        status="confirmed",
    )
    db.add(booking)

    # Create host earnings with transparent split
    earnings = models.HostEarnings(
        id=str(uuid4()),
        host_id=experience.host_id or experience.curator_id,
        source_type="experience",
        source_id=experience_id,
        gross_amount_usd=total_price,
        platform_fee_usd=platform_fee,
        net_amount_usd=net_amount,
        status="pending",
    )
    db.add(earnings)
    db.commit()

    return {
        "booking_id": booking.id,
        "experience": experience.name,
        "total_price_usd": total_price,
        "status": "confirmed",
        "revenue_split": {
            "host_earnings_usd": round(net_amount, 2),
            "platform_fee_usd": round(platform_fee, 2),
            "treasury_fee_usd": round(treasury_fee, 2),
        },
        "message": f"Booked {experience.name} for {request.num_guests} guest(s)",
    }


@router.get("/host/earnings")
def get_host_earnings(host_id: str, db: Session = Depends(get_db_dep)):
    """Get host earnings dashboard."""
    earnings = (
        db.query(models.HostEarnings)
        .filter(models.HostEarnings.host_id == host_id)
        .all()
    )

    total_gross = sum(e.gross_amount_usd for e in earnings)
    total_fees = sum(e.platform_fee_usd for e in earnings)
    total_net = sum(e.net_amount_usd for e in earnings)
    pending = sum(e.net_amount_usd for e in earnings if e.status == "pending")
    paid = sum(e.net_amount_usd for e in earnings if e.status == "paid")

    # By source type
    by_type = {}
    for e in earnings:
        if e.source_type not in by_type:
            by_type[e.source_type] = 0
        by_type[e.source_type] += e.net_amount_usd

    return {
        "host_id": host_id,
        "summary": {
            "total_gross_usd": round(total_gross, 2),
            "platform_fees_usd": round(total_fees, 2),
            "total_net_usd": round(total_net, 2),
            "pending_payout_usd": round(pending, 2),
            "paid_out_usd": round(paid, 2),
        },
        "by_source_type": {k: round(v, 2) for k, v in by_type.items()},
        "transaction_count": len(earnings),
    }


@router.get("/host/payouts")
def get_pending_payouts(host_id: str, db: Session = Depends(get_db_dep)):
    """Get pending payouts for a host."""
    pending = (
        db.query(models.HostEarnings)
        .filter(models.HostEarnings.host_id == host_id)
        .filter(models.HostEarnings.status == "pending")
        .order_by(models.HostEarnings.created_at.desc())
        .all()
    )

    return {
        "host_id": host_id,
        "pending_count": len(pending),
        "total_pending_usd": round(sum(e.net_amount_usd for e in pending), 2),
        "transactions": [
            {
                "id": e.id,
                "source_type": e.source_type,
                "gross_usd": e.gross_amount_usd,
                "net_usd": e.net_amount_usd,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in pending
        ],
    }


@router.post("/host/request-payout")
def request_payout(host_id: str, db: Session = Depends(get_db_dep)):
    """Request payout of pending earnings."""
    pending = (
        db.query(models.HostEarnings)
        .filter(models.HostEarnings.host_id == host_id)
        .filter(models.HostEarnings.status == "pending")
        .all()
    )

    if not pending:
        raise HTTPException(status_code=400, detail="No pending earnings to payout")

    total = sum(e.net_amount_usd for e in pending)

    # Mark as paid (in production, this would trigger actual payment)
    for e in pending:
        e.status = "paid"
        e.payout_date = datetime.now()

    db.commit()

    return {
        "status": "payout_initiated",
        "amount_usd": round(total, 2),
        "transactions_processed": len(pending),
        "message": f"Payout of ${total:.2f} initiated. Funds will arrive in 2-3 business days.",
    }


@router.get("/experience-bookings")
def get_experience_bookings(
    user_id: Optional[str] = None,
    experience_id: Optional[str] = None,
    db: Session = Depends(get_db_dep),
):
    """Get experience bookings."""
    query = db.query(models.ExperienceBooking)

    if user_id:
        query = query.filter(models.ExperienceBooking.user_id == user_id)
    if experience_id:
        query = query.filter(models.ExperienceBooking.experience_id == experience_id)

    bookings = query.order_by(models.ExperienceBooking.created_at.desc()).all()

    result = []
    for b in bookings:
        exp = (
            db.query(models.Experience)
            .filter(models.Experience.id == b.experience_id)
            .first()
        )
        result.append(
            {
                "booking_id": b.id,
                "experience_id": b.experience_id,
                "experience_name": exp.name if exp else "Unknown",
                "booking_date": b.booking_date.isoformat() if b.booking_date else None,
                "num_guests": b.num_guests,
                "total_price_usd": b.total_price_usd,
                "status": b.status,
            }
        )

    return result


@router.get("/host/revenue-split/{experience_id}")
def get_revenue_split(experience_id: str, db: Session = Depends(get_db_dep)):
    """Get transparent revenue split breakdown for an experience."""
    experience = (
        db.query(models.Experience)
        .filter(models.Experience.id == experience_id)
        .first()
    )
    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    host_rate = getattr(experience, "revenue_share_rate", None) or (1 - PLATFORM_FEE_RATE - TREASURY_FEE_RATE)
    price = experience.price_usd or 0

    return {
        "experience_id": experience_id,
        "experience_name": experience.name,
        "price_usd": price,
        "split": {
            "host_rate": round(host_rate, 4),
            "host_amount_usd": round(price * host_rate, 2),
            "platform_rate": PLATFORM_FEE_RATE,
            "platform_fee_usd": round(price * PLATFORM_FEE_RATE, 2),
            "treasury_rate": TREASURY_FEE_RATE,
            "treasury_fee_usd": round(price * TREASURY_FEE_RATE, 2),
        },
        "configurable": True,
        "min_host_share": MIN_HOST_SHARE,
    }


@router.put("/experiences/{experience_id}/revenue-share")
def update_revenue_share(
    experience_id: str,
    update: ExperiencePriceUpdate,
    db: Session = Depends(get_db_dep),
):
    """Update experience pricing and revenue share rate."""
    experience = (
        db.query(models.Experience)
        .filter(models.Experience.id == experience_id)
        .first()
    )
    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    if update.price_usd is not None:
        experience.price_usd = update.price_usd
    if update.max_guests is not None:
        experience.max_guests = update.max_guests
    if update.revenue_share_rate is not None:
        if update.revenue_share_rate < MIN_HOST_SHARE:
            raise HTTPException(
                status_code=400,
                detail=f"Host share cannot be below {MIN_HOST_SHARE * 100:.0f}%",
            )
        if update.revenue_share_rate > 0.99:
            raise HTTPException(status_code=400, detail="Host share cannot exceed 99%")
        experience.revenue_share_rate = update.revenue_share_rate

    db.commit()
    return {
        "status": "updated",
        "experience_id": experience_id,
        "price_usd": experience.price_usd,
        "revenue_share_rate": experience.revenue_share_rate,
    }
