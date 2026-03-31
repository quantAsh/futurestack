"""
Visa Wizard API Router.

Visa requirements and Schengen zone tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.visa_wizard import visa_wizard_service, SCHENGEN_COUNTRIES

router = APIRouter(prefix="/api/visa", tags=["visa"])


# ============================================================================
# Schemas
# ============================================================================

class VisaCheckRequest(BaseModel):
    passport_country_code: str = Field(..., min_length=2, max_length=3, example="US")
    destination_country_code: str = Field(..., min_length=2, max_length=3, example="PT")


class VisaRequirementResponse(BaseModel):
    passport_country: str
    passport_country_code: str
    destination_country: str
    destination_country_code: str
    visa_type: str  # visa_free, visa_on_arrival, e_visa, visa_required
    duration_days: Optional[int]
    dnv_available: bool
    dnv_duration_months: Optional[int]
    dnv_min_income_usd: Optional[float]
    dnv_cost_usd: Optional[float]
    is_schengen: bool
    notes: Optional[str]
    application_url: Optional[str]

    class Config:
        from_attributes = True


class SchengenStayCreate(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=3, example="PT")
    entry_date: datetime
    exit_date: Optional[datetime] = None


class SchengenCalculation(BaseModel):
    days_used: int
    days_remaining: int
    max_days: int
    window_days: int
    reference_date: str
    status: str  # ok, warning, exceeded
    stays: List[dict]
    next_available_date: Optional[str]


class DigitalNomadVisa(BaseModel):
    destination_country: str
    destination_country_code: str
    duration_months: Optional[int]
    min_income_usd: Optional[float]
    cost_usd: Optional[float]
    notes: Optional[str]
    application_url: Optional[str]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/check")
async def check_visa_requirements(
    passport: str = Query(..., min_length=2, max_length=3, description="Your passport country code (e.g., US, UK, IN)"),
    destination: str = Query(..., min_length=2, max_length=3, description="Destination country code (e.g., PT, TH)"),
    db: Session = Depends(get_db),
):
    """
    Check visa requirements for a specific passport + destination combination.
    
    Returns visa type, duration, and digital nomad visa info if available.
    """
    req = visa_wizard_service.get_visa_requirements(
        db, passport.upper(), destination.upper()
    )
    
    if not req:
        # Return generic info for unknown combinations
        is_schengen = visa_wizard_service.is_schengen_country(destination)
        return {
            "passport_country_code": passport.upper(),
            "destination_country_code": destination.upper(),
            "visa_type": "unknown",
            "duration_days": None,
            "is_schengen": is_schengen,
            "message": "Visa requirements not in our database. Please check official sources.",
            "dnv_available": False,
        }
    
    return req


@router.get("/destinations/{passport_code}")
async def get_visa_free_destinations(
    passport_code: str,
    visa_type: Optional[str] = Query(None, description="Filter by visa_free, visa_on_arrival, e_visa"),
    db: Session = Depends(get_db),
):
    """
    Get all destinations and their visa requirements for a passport holder.
    
    Optionally filter by visa type.
    """
    requirements = visa_wizard_service.get_requirements_for_passport(
        db, passport_code.upper(), visa_type
    )
    
    # Group by visa type
    grouped = {
        "visa_free": [],
        "visa_on_arrival": [],
        "e_visa": [],
        "visa_required": [],
    }
    
    for req in requirements:
        if req.visa_type in grouped:
            grouped[req.visa_type].append({
                "country": req.destination_country,
                "code": req.destination_country_code,
                "duration_days": req.duration_days,
                "is_schengen": req.is_schengen,
                "dnv_available": req.dnv_available,
            })
    
    return {
        "passport": passport_code.upper(),
        "total_countries": len(requirements),
        "visa_free_count": len(grouped["visa_free"]),
        "destinations": grouped,
    }


@router.get("/digital-nomad-visas/{passport_code}", response_model=List[DigitalNomadVisa])
async def get_digital_nomad_visas(
    passport_code: str,
    max_income_required: Optional[float] = Query(None, description="Max monthly income requirement in USD"),
    db: Session = Depends(get_db),
):
    """
    Get all countries offering Digital Nomad Visas for a passport holder.
    
    Sorted by cost (cheapest first).
    """
    visas = visa_wizard_service.get_digital_nomad_visas(db, passport_code.upper())
    
    result = []
    for v in visas:
        # Filter by income requirement if specified
        if max_income_required and v.dnv_min_income_usd and v.dnv_min_income_usd > max_income_required:
            continue
        
        result.append(DigitalNomadVisa(
            destination_country=v.destination_country,
            destination_country_code=v.destination_country_code,
            duration_months=v.dnv_duration_months,
            min_income_usd=v.dnv_min_income_usd,
            cost_usd=v.dnv_cost_usd,
            notes=v.notes,
            application_url=v.application_url,
        ))
    
    return result


# ============================================================================
# Schengen Calculator
# ============================================================================

@router.get("/schengen/countries")
async def get_schengen_countries():
    """Get list of all Schengen zone countries."""
    return {
        "countries": [
            {"code": code, "name": name}
            for code, name in sorted(SCHENGEN_COUNTRIES.items(), key=lambda x: x[1])
        ],
        "total": len(SCHENGEN_COUNTRIES),
    }


@router.get("/schengen/calculate", response_model=SchengenCalculation)
async def calculate_schengen_days(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Calculate your Schengen 90/180 day status.
    
    Shows days used, days remaining, and when more days become available.
    """
    return visa_wizard_service.calculate_schengen_days(db, current_user.id)


@router.get("/schengen/can-stay")
async def check_can_stay(
    days: int = Query(..., ge=1, le=90, description="Planned number of days"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Check if you can stay for a planned number of days."""
    return visa_wizard_service.can_stay(db, current_user.id, days)


@router.post("/schengen/stays")
async def log_schengen_stay(
    data: SchengenStayCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Log a Schengen zone stay for tracking.
    
    Entry date is required. Exit date can be added later.
    """
    try:
        stay = visa_wizard_service.log_schengen_stay(
            db=db,
            user_id=current_user.id,
            country_code=data.country_code,
            entry_date=data.entry_date,
            exit_date=data.exit_date,
        )
        
        # Return updated calculation
        calc = visa_wizard_service.calculate_schengen_days(db, current_user.id)
        
        return {
            "stay_id": stay.id,
            "message": "Stay logged",
            "schengen_status": calc,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/schengen/stays/{stay_id}")
async def update_schengen_stay(
    stay_id: str,
    exit_date: datetime,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update a Schengen stay with exit date."""
    stay = visa_wizard_service.update_schengen_stay(
        db=db,
        user_id=current_user.id,
        stay_id=stay_id,
        exit_date=exit_date,
    )
    
    if not stay:
        raise HTTPException(status_code=404, detail="Stay not found")
    
    return {"message": "Stay updated", "stay_id": stay_id}


@router.get("/schengen/stays")
async def get_my_schengen_stays(
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get your Schengen stay history."""
    stays = visa_wizard_service.get_user_stays(db, current_user.id, limit)
    
    return {
        "stays": [
            {
                "id": s.id,
                "country_code": s.country_code,
                "country_name": SCHENGEN_COUNTRIES.get(s.country_code, s.country_code),
                "entry_date": s.entry_date.isoformat(),
                "exit_date": s.exit_date.isoformat() if s.exit_date else None,
                "days": (s.exit_date - s.entry_date).days if s.exit_date else None,
            }
            for s in stays
        ],
        "total": len(stays),
    }
