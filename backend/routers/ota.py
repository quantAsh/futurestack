from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from backend.database import get_db
from backend.services.ota.aggregator import AggregatorService
from backend.services.ota.commission_tracker import CommissionTracker
from backend import models

router = APIRouter()


class OTASearchQuery(BaseModel):
    location: str
    check_in: date
    check_out: date
    guests: int = 1
    max_price: Optional[float] = None
    currency: str = "USD"


@router.post("/search")
async def search_accommodations(query: OTASearchQuery, db: Session = Depends(get_db)):
    """
    Search across ALL OTA providers + native listings.
    """
    aggregator = AggregatorService(db)

    results = await aggregator.aggregate_search(
        location=query.location,
        check_in=query.check_in,
        check_out=query.check_out,
        guests=query.guests,
        currency=query.currency,
        max_price=query.max_price,
    )

    return results


@router.get("/admin/commissions")
def get_commissions(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
    # In real app: Add admin auth dependency
):
    tracker = CommissionTracker(db)
    return tracker.get_commission_report(start_date, end_date)
