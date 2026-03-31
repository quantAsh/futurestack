"""
Augmented Reality Router - Virtual tours and AR assets.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend import models
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


class ARAssetUpdate(BaseModel):
    virtual_tour_url: Optional[str] = None
    ar_model_url: Optional[str] = None


@router.get("/listings/{listing_id}/ar-assets")
def get_ar_assets(listing_id: str, db: Session = Depends(get_db_dep)):
    """Get AR assets for a listing."""
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return {
        "listing_id": listing_id,
        "virtual_tour_url": listing.virtual_tour_url,
        "ar_model_url": listing.ar_model_url,
        "is_ar_enabled": bool(listing.ar_model_url or listing.virtual_tour_url),
    }


@router.post("/listings/{listing_id}/virtual-tour")
def update_virtual_tour(
    listing_id: str, assets: ARAssetUpdate, db: Session = Depends(get_db_dep)
):
    """Update virtual tour or AR model URLs."""
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if assets.virtual_tour_url is not None:
        listing.virtual_tour_url = assets.virtual_tour_url

    if assets.ar_model_url is not None:
        listing.ar_model_url = assets.ar_model_url

    db.commit()

    return {
        "status": "updated",
        "listing_id": listing_id,
        "virtual_tour_url": listing.virtual_tour_url,
        "ar_model_url": listing.ar_model_url,
    }
