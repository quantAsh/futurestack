"""
AI Trip Planner API Router.

Multi-city itinerary planning with budget and visa awareness.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.trip_planner import ai_trip_planner

router = APIRouter(prefix="/api/trips", tags=["trips"])


# ============================================================================
# Schemas
# ============================================================================

class ItineraryCreate(BaseModel):
    name: str = Field(..., max_length=100, example="European Summer 2026")
    start_date: datetime
    end_date: datetime
    passport_country_code: Optional[str] = Field(None, max_length=3)
    budget_usd: Optional[float] = Field(None, ge=0)
    preferences: Optional[dict] = None


class StopCreate(BaseModel):
    city: str = Field(..., max_length=100)
    country: str = Field(..., max_length=100)
    country_code: Optional[str] = Field(None, max_length=3)
    arrival_date: datetime
    departure_date: datetime
    transport_from_previous: Optional[str] = None
    listing_id: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
    activities: Optional[List[str]] = None


class ItinerarySummary(BaseModel):
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    total_days: int
    budget_usd: Optional[float]
    estimated_cost_usd: Optional[float]
    optimization_score: Optional[float]
    status: str
    stop_count: int

    class Config:
        from_attributes = True


# ============================================================================
# Itinerary Endpoints
# ============================================================================

@router.post("/itineraries")
async def create_itinerary(
    data: ItineraryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new trip itinerary."""
    if data.end_date <= data.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    itinerary = ai_trip_planner.create_itinerary(
        db=db,
        user_id=current_user.id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        passport_country_code=data.passport_country_code,
        budget_usd=data.budget_usd,
        preferences=data.preferences,
    )
    
    return {
        "id": itinerary.id,
        "name": itinerary.name,
        "total_days": itinerary.total_days,
        "message": "Itinerary created! Add stops to start planning.",
    }


@router.get("/itineraries")
async def list_itineraries(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List your trip itineraries."""
    itineraries = ai_trip_planner.get_user_itineraries(db, current_user.id, status)
    
    result = []
    for it in itineraries:
        stop_count = len(it.stops) if it.stops else 0
        result.append({
            "id": it.id,
            "name": it.name,
            "start_date": it.start_date.isoformat(),
            "end_date": it.end_date.isoformat(),
            "total_days": it.total_days,
            "budget_usd": it.budget_usd,
            "estimated_cost_usd": it.estimated_cost_usd,
            "optimization_score": it.optimization_score,
            "status": it.status,
            "stop_count": stop_count,
        })
    
    return {"itineraries": result, "total": len(result)}


@router.get("/itineraries/{itinerary_id}")
async def get_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get full itinerary with all stops."""
    result = ai_trip_planner.get_itinerary(db, itinerary_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return result


@router.delete("/itineraries/{itinerary_id}")
async def delete_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete an itinerary and all its stops."""
    success = ai_trip_planner.delete_itinerary(db, itinerary_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return {"message": "Itinerary deleted"}


@router.patch("/itineraries/{itinerary_id}")
def update_itinerary_status(
    itinerary_id: str,
    status: str = Query(..., pattern="^(draft|planned|booked|completed)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update itinerary status."""
    itinerary = db.query(models.TripItinerary).filter(
        models.TripItinerary.id == itinerary_id,
        models.TripItinerary.user_id == current_user.id,
    ).first()
    
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    itinerary.status = status
    db.commit()
    return {"message": f"Status updated to {status}"}


# ============================================================================
# Stop Endpoints
# ============================================================================

@router.post("/itineraries/{itinerary_id}/stops")
def add_stop(
    itinerary_id: str,
    data: StopCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a stop to the itinerary."""
    # Verify ownership
    itinerary = db.query(models.TripItinerary).filter(
        models.TripItinerary.id == itinerary_id,
        models.TripItinerary.user_id == current_user.id,
    ).first()
    
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    if data.departure_date <= data.arrival_date:
        raise HTTPException(status_code=400, detail="Departure must be after arrival")
    
    try:
        stop = ai_trip_planner.add_stop(
            db=db,
            itinerary_id=itinerary_id,
            city=data.city,
            country=data.country,
            country_code=data.country_code,
            arrival_date=data.arrival_date,
            departure_date=data.departure_date,
            transport_from_previous=data.transport_from_previous,
            listing_id=data.listing_id,
            notes=data.notes,
            activities=data.activities,
        )
        
        return {
            "id": stop.id,
            "city": stop.city,
            "nights": stop.nights,
            "daily_cost": stop.daily_living_cost,
            "transport_cost": stop.transport_cost,
            "visa_required": stop.visa_required,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/itineraries/{itinerary_id}/stops/{stop_id}")
def delete_stop(
    itinerary_id: str,
    stop_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a stop from the itinerary."""
    # Verify ownership
    itinerary = db.query(models.TripItinerary).filter(
        models.TripItinerary.id == itinerary_id,
        models.TripItinerary.user_id == current_user.id,
    ).first()
    
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    stop = db.query(models.TripStop).filter(
        models.TripStop.id == stop_id,
        models.TripStop.itinerary_id == itinerary_id,
    ).first()
    
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    
    db.delete(stop)
    db.commit()
    
    return {"message": "Stop deleted"}


# ============================================================================
# AI Features
# ============================================================================

@router.get("/itineraries/{itinerary_id}/suggestions")
def get_ai_suggestions(
    itinerary_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get AI-generated suggestions for the itinerary."""
    # Verify ownership
    itinerary = db.query(models.TripItinerary).filter(
        models.TripItinerary.id == itinerary_id,
        models.TripItinerary.user_id == current_user.id,
    ).first()
    
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    suggestions = ai_trip_planner.generate_ai_suggestions(db, itinerary_id)
    
    return {
        "suggestions": suggestions,
        "optimization_score": itinerary.optimization_score,
        "estimated_cost": itinerary.estimated_cost_usd,
        "budget": itinerary.budget_usd,
    }


@router.get("/suggest-cities")
async def suggest_cities(
    budget_per_day: Optional[float] = Query(None, description="Max daily budget in USD"),
    region: Optional[str] = Query(None, description="europe, asia, or americas"),
    passport: Optional[str] = Query(None, description="Your passport country code"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get city suggestions based on preferences."""
    cities = ai_trip_planner.suggest_cities(
        db=db,
        user_id=current_user.id,
        budget_per_day=budget_per_day,
        region=region,
        passport_code=passport,
    )
    
    return {
        "cities": cities,
        "total": len(cities),
        "filters": {
            "budget_per_day": budget_per_day,
            "region": region,
        }
    }


@router.post("/quick-plan")
async def quick_plan(
    start_city: str = Query(..., description="Starting city"),
    days: int = Query(..., ge=7, le=180, description="Total trip days"),
    budget_usd: Optional[float] = Query(None, description="Total budget"),
    region: str = Query(default="europe", description="europe, asia, americas"),
    passport: str = Query(default="US", description="Passport country code"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Quick AI-generated trip plan.
    Returns a suggested multi-city itinerary based on preferences.
    """
    from datetime import timedelta
    
    # Get suggested cities for the region
    cities = ai_trip_planner.suggest_cities(
        db=db,
        user_id=current_user.id,
        budget_per_day=budget_usd / days if budget_usd else None,
        region=region,
        passport_code=passport,
    )
    
    if not cities:
        return {"error": "No cities found for the given criteria"}
    
    # Create a draft itinerary
    start_date = datetime.now() + timedelta(days=30)
    end_date = start_date + timedelta(days=days)
    
    itinerary = ai_trip_planner.create_itinerary(
        db=db,
        user_id=current_user.id,
        name=f"{region.title()} Trip ({days} days)",
        start_date=start_date,
        end_date=end_date,
        passport_country_code=passport,
        budget_usd=budget_usd,
        preferences={"region": region, "auto_generated": True},
    )
    
    # Distribute days across cities (aim for 5-14 nights per stop)
    num_cities = min(len(cities), max(2, days // 10))
    days_per_city = days // num_cities
    
    current_date = start_date
    suggested_stops = []
    
    for i in range(num_cities):
        city = cities[i]
        nights = days_per_city if i < num_cities - 1 else days - sum(s["nights"] for s in suggested_stops)
        
        stop = ai_trip_planner.add_stop(
            db=db,
            itinerary_id=itinerary.id,
            city=city["city"],
            country=city["country"],
            country_code=city["country_code"],
            arrival_date=current_date,
            departure_date=current_date + timedelta(days=nights),
        )
        
        suggested_stops.append({
            "city": city["city"],
            "country": city["country"],
            "nights": nights,
            "daily_cost": city["cost_per_day"],
        })
        
        current_date += timedelta(days=nights)
    
    # Generate suggestions
    ai_trip_planner.generate_ai_suggestions(db, itinerary.id)
    
    # Get full itinerary
    result = ai_trip_planner.get_itinerary(db, itinerary.id, current_user.id)
    
    return result
