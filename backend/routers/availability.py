"""
Availability Router - Manage listing availability and blocked dates.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from backend import models, database

router = APIRouter()


def get_db():
    yield from database.get_db()


class BlockedDatesUpdate(BaseModel):
    blocked_dates: List[str]  # List of YYYY-MM-DD strings


class AvailabilityResponse(BaseModel):
    listing_id: str
    listing_name: str
    blocked_dates: List[str]
    bookings: List[dict]


class DateRangeCheck(BaseModel):
    start_date: str
    end_date: str


@router.get("/{listing_id}", response_model=AvailabilityResponse)
def get_listing_availability(listing_id: str, db: Session = Depends(get_db)):
    """Get availability for a listing including blocked dates and existing bookings."""
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Get existing bookings
    bookings = (
        db.query(models.Booking).filter(models.Booking.listing_id == listing_id).all()
    )

    booking_data = [
        {
            "id": b.id,
            "start_date": b.start_date.isoformat() if b.start_date else None,
            "end_date": b.end_date.isoformat() if b.end_date else None,
            "user_id": b.user_id,
        }
        for b in bookings
    ]

    # For now, blocked_dates would be stored on listing (to be added)
    # Using empty list as placeholder since column not yet added
    blocked = []

    return {
        "listing_id": listing_id,
        "listing_name": listing.name,
        "blocked_dates": blocked,
        "bookings": booking_data,
    }


@router.post("/{listing_id}/check")
def check_availability(
    listing_id: str, date_range: DateRangeCheck, db: Session = Depends(get_db)
):
    """Check if a listing is available for a date range."""
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    start = datetime.fromisoformat(date_range.start_date)
    end = datetime.fromisoformat(date_range.end_date)

    # Check for overlapping bookings
    overlapping = (
        db.query(models.Booking)
        .filter(models.Booking.listing_id == listing_id)
        .filter(models.Booking.start_date < end)
        .filter(models.Booking.end_date > start)
        .first()
    )

    if overlapping:
        return {
            "available": False,
            "reason": "Dates overlap with existing booking",
            "conflict_booking_id": overlapping.id,
        }

    return {
        "available": True,
        "listing_id": listing_id,
        "start_date": date_range.start_date,
        "end_date": date_range.end_date,
    }


@router.get("/calendar/{listing_id}")
def get_calendar_data(
    listing_id: str, year: int, month: int, db: Session = Depends(get_db)
):
    """Get calendar data for a specific month showing availability."""
    from calendar import monthrange

    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Get all bookings for the month
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    bookings = (
        db.query(models.Booking)
        .filter(models.Booking.listing_id == listing_id)
        .filter(models.Booking.start_date <= last_day)
        .filter(models.Booking.end_date >= first_day)
        .all()
    )

    # Build list of booked dates
    booked_dates = set()
    for b in bookings:
        current = (
            b.start_date.date() if isinstance(b.start_date, datetime) else b.start_date
        )
        end_d = b.end_date.date() if isinstance(b.end_date, datetime) else b.end_date
        while current <= end_d:
            if first_day <= current <= last_day:
                booked_dates.add(current.isoformat())
            current = date.fromordinal(current.toordinal() + 1)

    return {
        "listing_id": listing_id,
        "year": year,
        "month": month,
        "booked_dates": sorted(list(booked_dates)),
        "total_days": monthrange(year, month)[1],
    }
