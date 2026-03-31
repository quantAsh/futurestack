"""
Price Drop Alerts API Router.

Monitor listings and get notified on price drops.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.price_alerts import price_alert_service

router = APIRouter(prefix="/api/price-alerts", tags=["price-alerts"])


# ============================================================================
# Schemas
# ============================================================================

class ListingAlertCreate(BaseModel):
    listing_id: str
    target_price: Optional[float] = None
    drop_percent: Optional[float] = Field(default=10.0, ge=1, le=90)
    check_in: Optional[str] = None
    check_out: Optional[str] = None


class SearchAlertCreate(BaseModel):
    city: str = Field(..., max_length=100)
    max_price: float = Field(..., ge=1)
    amenities: Optional[List[str]] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None


# ============================================================================
# Alert Endpoints
# ============================================================================

@router.get("/")
async def list_alerts(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all your price alerts."""
    alerts = price_alert_service.get_user_alerts(
        db, current_user.id, include_inactive
    )
    return {"alerts": alerts, "total": len(alerts)}


@router.post("/listing")
async def create_listing_alert(
    data: ListingAlertCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a price alert for a specific listing."""
    try:
        alert = price_alert_service.create_listing_alert(
            db=db,
            user_id=current_user.id,
            listing_id=data.listing_id,
            target_price=data.target_price,
            drop_percent=data.drop_percent,
            check_in=data.check_in,
            check_out=data.check_out,
        )
        return {
            "alert_id": alert.id,
            "message": "🔔 Alert created! We'll notify you when the price drops.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/search")
async def create_search_alert(
    data: SearchAlertCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a price alert for search criteria."""
    alert = price_alert_service.create_search_alert(
        db=db,
        user_id=current_user.id,
        city=data.city,
        max_price=data.max_price,
        criteria={"amenities": data.amenities} if data.amenities else None,
        check_in=data.check_in,
        check_out=data.check_out,
    )
    return {
        "alert_id": alert.id,
        "message": f"🔔 Watching {data.city} for listings under ${data.max_price}/night!",
    }


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a price alert."""
    success = price_alert_service.delete_alert(db, alert_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted"}


@router.post("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Toggle alert active/inactive."""
    is_active = price_alert_service.toggle_alert(db, alert_id, current_user.id)
    if is_active is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"is_active": is_active}


# ============================================================================
# History & Stats
# ============================================================================

@router.get("/listing/{listing_id}/history")
async def get_price_history(
    listing_id: str,
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get price history for a listing."""
    history = price_alert_service.get_price_history(db, listing_id, days)
    return {"listing_id": listing_id, "history": history, "days": days}


@router.get("/savings")
async def get_savings_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get your savings summary from triggered alerts."""
    summary = price_alert_service.get_savings_summary(db, current_user.id)
    return summary
