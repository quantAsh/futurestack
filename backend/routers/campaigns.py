"""
Campaigns Router - Marketing campaigns and referrals.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    campaign_type: str
    code: Optional[str] = None
    discount_percent: float = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    campaign_type: str = "referral"
    code: Optional[str] = None
    discount_percent: float = 0


@router.get("/", response_model=List[CampaignOut])
def list_campaigns(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """List campaigns."""
    query = db.query(models.Campaign)
    if active_only:
        query = query.filter(models.Campaign.is_active == True)
    campaigns = query.order_by(models.Campaign.created_at.desc()).all()
    return [CampaignOut.model_validate(c) for c in campaigns]


@router.get("/code/{code}")
def get_by_code(
    code: str,
    db: Session = Depends(get_db),
):
    """Get campaign by promo/referral code."""
    campaign = db.query(models.Campaign).filter(
        models.Campaign.code == code,
        models.Campaign.is_active == True
    ).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Invalid or expired code")

    return CampaignOut.model_validate(campaign)


@router.post("/use/{code}")
def use_campaign_code(
    code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Apply a campaign code."""
    campaign = db.query(models.Campaign).filter(
        models.Campaign.code == code,
        models.Campaign.is_active == True
    ).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Invalid code")

    campaign.usage_count += 1
    db.commit()

    return {
        "status": "applied",
        "discount_percent": campaign.discount_percent,
        "campaign_name": campaign.name,
    }


@router.post("/", response_model=CampaignOut, status_code=201)
def create_campaign(
    data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a campaign (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    campaign = models.Campaign(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        campaign_type=data.campaign_type,
        code=data.code or str(uuid.uuid4())[:8].upper(),
        discount_percent=data.discount_percent,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return CampaignOut.model_validate(campaign)
