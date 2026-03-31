"""
Cost of Living API Router.

Compare cost of living across cities for digital nomads.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend import models

router = APIRouter(prefix="/api/cost-of-living", tags=["cost-of-living"])


# ============================================================================
# Schemas
# ============================================================================

class CityLivingCostResponse(BaseModel):
    id: str
    city: str
    country: str
    country_code: Optional[str] = None
    
    # Monthly costs
    rent_studio: Optional[float] = None
    rent_1br: Optional[float] = None
    coworking: Optional[float] = None
    meal_cheap: Optional[float] = None
    meal_mid: Optional[float] = None
    coffee: Optional[float] = None
    groceries: Optional[float] = None
    transport: Optional[float] = None
    utilities: Optional[float] = None
    internet: Optional[float] = None
    gym: Optional[float] = None
    
    # Scores
    wifi_quality: Optional[float] = None
    safety_score: Optional[float] = None
    weather_score: Optional[float] = None
    nightlife_score: Optional[float] = None
    outdoor_score: Optional[float] = None
    english_level: Optional[float] = None
    nomad_score: Optional[float] = None
    
    # Visa
    visa_type: Optional[str] = None
    visa_duration_days: Optional[int] = None
    timezone: Optional[str] = None
    
    # Computed
    monthly_total: Optional[float] = None  # Calculated total
    
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class CityComparisonRequest(BaseModel):
    cities: List[str] = Field(..., min_length=2, max_length=5, example=["Lisbon", "Medellin", "Bangkok"])
    lifestyle: str = Field(default="moderate", example="moderate")

    class Config:
        json_schema_extra = {
            "example": {
                "cities": ["Lisbon", "Medellin", "Chiang Mai"],
                "lifestyle": "moderate"
            }
        }


class CityComparisonResponse(BaseModel):
    comparisons: List[CityLivingCostResponse]
    cheapest: Optional[str] = None
    most_expensive: Optional[str] = None
    recommendation: Optional[str] = None


class PopularCitiesResponse(BaseModel):
    cities: List[CityLivingCostResponse]
    total: int


# ============================================================================
# Helper Functions
# ============================================================================

def calculate_monthly_total(city: models.CityLivingCost, lifestyle: str = "moderate") -> float:
    """Calculate estimated monthly cost based on lifestyle."""
    multiplier = {
        "budget": 0.7,
        "moderate": 1.0,
        "comfortable": 1.4,
        "luxury": 2.0,
    }.get(lifestyle, 1.0)
    
    total = 0.0
    
    # Rent (use 1br for moderate+, studio for budget)
    if lifestyle == "budget" and city.rent_studio:
        total += city.rent_studio
    elif city.rent_1br:
        total += city.rent_1br
    
    # Coworking
    if city.coworking:
        total += city.coworking
    
    # Food (20 cheap meals + 8 mid-range meals)
    if city.meal_cheap:
        total += city.meal_cheap * 20 * multiplier
    if city.meal_mid:
        total += city.meal_mid * 8 * multiplier
    
    # Groceries
    if city.groceries:
        total += city.groceries
    
    # Transport
    if city.transport:
        total += city.transport
    
    # Utilities
    if city.utilities:
        total += city.utilities
    
    # Internet
    if city.internet:
        total += city.internet
    
    return round(total, 2)


def city_to_response(city: models.CityLivingCost, lifestyle: str = "moderate") -> CityLivingCostResponse:
    """Convert model to response schema with calculated total."""
    return CityLivingCostResponse(
        id=city.id,
        city=city.city,
        country=city.country,
        country_code=city.country_code,
        rent_studio=city.rent_studio,
        rent_1br=city.rent_1br,
        coworking=city.coworking,
        meal_cheap=city.meal_cheap,
        meal_mid=city.meal_mid,
        coffee=city.coffee,
        groceries=city.groceries,
        transport=city.transport,
        utilities=city.utilities,
        internet=city.internet,
        gym=city.gym,
        wifi_quality=city.wifi_quality,
        safety_score=city.safety_score,
        weather_score=city.weather_score,
        nightlife_score=city.nightlife_score,
        outdoor_score=city.outdoor_score,
        english_level=city.english_level,
        nomad_score=city.nomad_score,
        visa_type=city.visa_type,
        visa_duration_days=city.visa_duration_days,
        timezone=city.timezone,
        monthly_total=calculate_monthly_total(city, lifestyle),
        last_updated=city.last_updated,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/cities", response_model=PopularCitiesResponse)
def get_popular_cities(
    limit: int = Query(default=20, le=50),
    sort_by: str = Query(default="nomad_score", example="nomad_score"),
    db: Session = Depends(get_db),
):
    """
    Get popular nomad cities with cost data.
    
    Sort options: nomad_score, rent_1br, monthly_total, safety_score
    """
    query = db.query(models.CityLivingCost)
    
    # Sort
    if sort_by == "nomad_score":
        query = query.order_by(models.CityLivingCost.nomad_score.desc().nulls_last())
    elif sort_by == "rent_1br":
        query = query.order_by(models.CityLivingCost.rent_1br.asc().nulls_last())
    elif sort_by == "safety_score":
        query = query.order_by(models.CityLivingCost.safety_score.desc().nulls_last())
    else:
        query = query.order_by(models.CityLivingCost.nomad_score.desc().nulls_last())
    
    cities = query.limit(limit).all()
    
    return PopularCitiesResponse(
        cities=[city_to_response(c) for c in cities],
        total=len(cities),
    )


@router.get("/city/{city_name}", response_model=CityLivingCostResponse)
def get_city_cost(
    city_name: str,
    lifestyle: str = Query(default="moderate"),
    db: Session = Depends(get_db),
):
    """Get cost of living data for a specific city."""
    city = db.query(models.CityLivingCost).filter(
        models.CityLivingCost.city.ilike(city_name)
    ).first()
    
    if not city:
        raise HTTPException(status_code=404, detail=f"City '{city_name}' not found")
    
    return city_to_response(city, lifestyle)


@router.post("/compare", response_model=CityComparisonResponse)
def compare_cities(
    data: CityComparisonRequest,
    db: Session = Depends(get_db),
):
    """
    Compare cost of living across multiple cities.
    
    Lifestyle options:
    - `budget`: Shared housing, cheap eats, public transport
    - `moderate`: 1BR apartment, mix of cooking/eating out
    - `comfortable`: Nice 1BR, coworking, eating out regularly
    - `luxury`: Premium apartment, private workspace, dining out
    """
    comparisons = []
    
    for city_name in data.cities:
        city = db.query(models.CityLivingCost).filter(
            models.CityLivingCost.city.ilike(city_name)
        ).first()
        
        if city:
            comparisons.append(city_to_response(city, data.lifestyle))
    
    if not comparisons:
        raise HTTPException(status_code=404, detail="No cities found")
    
    # Find cheapest and most expensive
    sorted_by_cost = sorted(comparisons, key=lambda x: x.monthly_total or float('inf'))
    cheapest = sorted_by_cost[0].city if sorted_by_cost else None
    most_expensive = sorted_by_cost[-1].city if sorted_by_cost else None
    
    # Generate recommendation
    recommendation = None
    if len(comparisons) >= 2:
        best = sorted_by_cost[0]
        recommendation = f"{best.city} is the most budget-friendly at ${best.monthly_total:.0f}/month"
        if best.nomad_score and best.nomad_score >= 7:
            recommendation += f" with a great nomad score of {best.nomad_score}/10."
        else:
            recommendation += "."
    
    return CityComparisonResponse(
        comparisons=comparisons,
        cheapest=cheapest,
        most_expensive=most_expensive,
        recommendation=recommendation,
    )


@router.get("/search")
def search_cities(
    q: str = Query(..., min_length=2, example="Lis"),
    limit: int = Query(default=10, le=20),
    db: Session = Depends(get_db),
):
    """Search cities by name (autocomplete)."""
    cities = db.query(models.CityLivingCost).filter(
        models.CityLivingCost.city.ilike(f"{q}%")
    ).limit(limit).all()
    
    return {
        "query": q,
        "results": [
            {"city": c.city, "country": c.country, "monthly_total": calculate_monthly_total(c)}
            for c in cities
        ]
    }
