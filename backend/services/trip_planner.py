"""
AI Trip Planner Service - Multi-city itinerary optimization with budget and visa awareness.
"""
import structlog
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import uuid4
import math

from backend import models
from backend.services.visa_wizard import visa_wizard_service

logger = structlog.get_logger(__name__)


# Popular nomad destinations with metadata
CITY_DATA = {
    "Lisbon": {"country": "Portugal", "code": "PT", "cost_per_day": 80, "avg_temp": {1: 12, 7: 25}, "timezone": "WET"},
    "Porto": {"country": "Portugal", "code": "PT", "cost_per_day": 65, "avg_temp": {1: 10, 7: 23}, "timezone": "WET"},
    "Barcelona": {"country": "Spain", "code": "ES", "cost_per_day": 90, "avg_temp": {1: 11, 7: 27}, "timezone": "CET"},
    "Madrid": {"country": "Spain", "code": "ES", "cost_per_day": 85, "avg_temp": {1: 8, 7: 32}, "timezone": "CET"},
    "Berlin": {"country": "Germany", "code": "DE", "cost_per_day": 95, "avg_temp": {1: 2, 7: 23}, "timezone": "CET"},
    "Prague": {"country": "Czech Republic", "code": "CZ", "cost_per_day": 55, "avg_temp": {1: 0, 7: 20}, "timezone": "CET"},
    "Budapest": {"country": "Hungary", "code": "HU", "cost_per_day": 50, "avg_temp": {1: 2, 7: 27}, "timezone": "CET"},
    "Bangkok": {"country": "Thailand", "code": "TH", "cost_per_day": 45, "avg_temp": {1: 28, 7: 30}, "timezone": "ICT"},
    "Chiang Mai": {"country": "Thailand", "code": "TH", "cost_per_day": 35, "avg_temp": {1: 22, 7: 28}, "timezone": "ICT"},
    "Bali": {"country": "Indonesia", "code": "ID", "cost_per_day": 50, "avg_temp": {1: 27, 7: 27}, "timezone": "WITA"},
    "Mexico City": {"country": "Mexico", "code": "MX", "cost_per_day": 55, "avg_temp": {1: 15, 7: 18}, "timezone": "CST"},
    "Medellin": {"country": "Colombia", "code": "CO", "cost_per_day": 45, "avg_temp": {1: 22, 7: 22}, "timezone": "COT"},
    "Buenos Aires": {"country": "Argentina", "code": "AR", "cost_per_day": 40, "avg_temp": {1: 25, 7: 12}, "timezone": "ART"},
    "Tokyo": {"country": "Japan", "code": "JP", "cost_per_day": 110, "avg_temp": {1: 6, 7: 27}, "timezone": "JST"},
    "Tbilisi": {"country": "Georgia", "code": "GE", "cost_per_day": 35, "avg_temp": {1: 3, 7: 27}, "timezone": "GET"},
    "Dubai": {"country": "UAE", "code": "AE", "cost_per_day": 120, "avg_temp": {1: 20, 7: 42}, "timezone": "GST"},
}

# Transport costs (approximate)
TRANSPORT_COSTS = {
    ("PT", "ES"): {"type": "train", "cost": 40, "hours": 3},
    ("ES", "PT"): {"type": "train", "cost": 40, "hours": 3},
    ("ES", "FR"): {"type": "train", "cost": 80, "hours": 4},
    ("FR", "DE"): {"type": "train", "cost": 100, "hours": 4},
    ("DE", "CZ"): {"type": "train", "cost": 50, "hours": 4},
    ("CZ", "HU"): {"type": "train", "cost": 30, "hours": 5},
    ("TH", "ID"): {"type": "flight", "cost": 120, "hours": 3},
    ("MX", "CO"): {"type": "flight", "cost": 250, "hours": 5},
    # Default for unknown routes
    "default_same_continent": {"type": "flight", "cost": 150, "hours": 2},
    "default_intercontinental": {"type": "flight", "cost": 500, "hours": 10},
}


def estimate_transport(from_code: str, to_code: str) -> Dict[str, Any]:
    """Estimate transport between two country codes."""
    key = (from_code, to_code)
    if key in TRANSPORT_COSTS:
        return TRANSPORT_COSTS[key]
    
    # Group continents
    europe = {"PT", "ES", "FR", "DE", "CZ", "HU", "IT", "NL", "GR", "PL"}
    asia = {"TH", "ID", "JP", "VN", "MY", "SG", "KR", "IN"}
    americas = {"US", "MX", "CO", "AR", "BR", "CL", "PE"}
    
    same_continent = (
        (from_code in europe and to_code in europe) or
        (from_code in asia and to_code in asia) or
        (from_code in americas and to_code in americas)
    )
    
    if same_continent:
        return TRANSPORT_COSTS["default_same_continent"]
    return TRANSPORT_COSTS["default_intercontinental"]


def calculate_route_efficiency(stops: List[Dict]) -> float:
    """
    Calculate route efficiency score (0-100).
    Penalizes backtracking and long flights.
    """
    if len(stops) < 2:
        return 100.0
    
    total_transport_hours = 0
    backtrack_penalty = 0
    
    visited_countries = set()
    for i, stop in enumerate(stops):
        code = stop.get("country_code", "")
        if code in visited_countries:
            backtrack_penalty += 10  # Penalize revisiting
        visited_countries.add(code)
        
        if i > 0:
            transport = estimate_transport(stops[i-1].get("country_code", ""), code)
            total_transport_hours += transport.get("hours", 2)
    
    # Base score
    total_days = sum(s.get("nights", 1) for s in stops)
    travel_ratio = total_transport_hours / (total_days * 24) if total_days > 0 else 0
    
    # Lower travel ratio = better efficiency
    efficiency = max(0, 100 - (travel_ratio * 200) - backtrack_penalty)
    return round(efficiency, 1)


class AITripPlannerService:
    """
    AI-powered trip planning service.
    
    Features:
    - Multi-city itinerary generation
    - Budget estimation with COL data
    - Visa requirement checking
    - Route optimization
    """
    
    def create_itinerary(
        self,
        db: Session,
        user_id: str,
        name: str,
        start_date: datetime,
        end_date: datetime,
        passport_country_code: Optional[str] = None,
        budget_usd: Optional[float] = None,
        preferences: Optional[Dict] = None,
    ) -> models.TripItinerary:
        """Create a new trip itinerary."""
        total_days = (end_date - start_date).days
        
        itinerary = models.TripItinerary(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            passport_country_code=passport_country_code,
            budget_usd=budget_usd,
            preferences=preferences or {},
            status="draft",
        )
        db.add(itinerary)
        db.commit()
        db.refresh(itinerary)
        
        logger.info("itinerary_created", user_id=user_id, name=name, days=total_days)
        return itinerary
    
    def add_stop(
        self,
        db: Session,
        itinerary_id: str,
        city: str,
        country: str,
        arrival_date: datetime,
        departure_date: datetime,
        country_code: Optional[str] = None,
        transport_from_previous: Optional[str] = None,
        listing_id: Optional[str] = None,
        notes: Optional[str] = None,
        activities: Optional[List[str]] = None,
    ) -> models.TripStop:
        """Add a stop to the itinerary."""
        itinerary = db.query(models.TripItinerary).filter(
            models.TripItinerary.id == itinerary_id
        ).first()
        
        if not itinerary:
            raise ValueError("Itinerary not found")
        
        # Get next order
        max_order = db.query(models.TripStop).filter(
            models.TripStop.itinerary_id == itinerary_id
        ).count()
        
        nights = (departure_date - arrival_date).days
        
        # Estimate costs
        city_info = CITY_DATA.get(city, {})
        daily_cost = city_info.get("cost_per_day", 60)
        
        # Transport cost
        transport_cost = None
        transport_hours = None
        if max_order > 0:
            prev_stop = db.query(models.TripStop).filter(
                models.TripStop.itinerary_id == itinerary_id,
                models.TripStop.order == max_order - 1
            ).first()
            if prev_stop and prev_stop.country_code and country_code:
                transport = estimate_transport(prev_stop.country_code, country_code)
                transport_cost = transport["cost"]
                transport_hours = transport["hours"]
                transport_from_previous = transport_from_previous or transport["type"]
        
        # Visa check
        visa_required = False
        visa_type = None
        if itinerary.passport_country_code and country_code:
            req = visa_wizard_service.get_visa_requirements(
                db, itinerary.passport_country_code, country_code
            )
            if req:
                visa_type = req.visa_type
                visa_required = visa_type in ["visa_required", "e_visa"]
        
        stop = models.TripStop(
            id=str(uuid4()),
            itinerary_id=itinerary_id,
            order=max_order,
            city=city,
            country=country,
            country_code=country_code or city_info.get("code"),
            arrival_date=arrival_date,
            departure_date=departure_date,
            nights=nights,
            listing_id=listing_id,
            transport_from_previous=transport_from_previous,
            transport_cost=transport_cost,
            transport_duration_hours=transport_hours,
            daily_living_cost=daily_cost,
            visa_required=visa_required,
            visa_type=visa_type,
            notes=notes,
            activities=activities or [],
            avg_temp_celsius=city_info.get("avg_temp", {}).get(arrival_date.month),
        )
        db.add(stop)
        
        # Update itinerary estimated cost
        self._recalculate_itinerary(db, itinerary)
        
        db.commit()
        db.refresh(stop)
        return stop
    
    def _recalculate_itinerary(self, db: Session, itinerary: models.TripItinerary):
        """Recalculate itinerary costs and optimization score."""
        stops = db.query(models.TripStop).filter(
            models.TripStop.itinerary_id == itinerary.id
        ).order_by(models.TripStop.order).all()
        
        total_cost = 0
        stop_data = []
        
        for stop in stops:
            # Accommodation
            if stop.accommodation_cost:
                total_cost += stop.accommodation_cost
            
            # Transport
            if stop.transport_cost:
                total_cost += stop.transport_cost
            
            # Living costs
            if stop.daily_living_cost and stop.nights:
                total_cost += stop.daily_living_cost * stop.nights
            
            stop_data.append({
                "city": stop.city,
                "country_code": stop.country_code,
                "nights": stop.nights,
            })
        
        itinerary.estimated_cost_usd = total_cost
        itinerary.optimization_score = calculate_route_efficiency(stop_data)
    
    def generate_ai_suggestions(
        self,
        db: Session,
        itinerary_id: str,
    ) -> List[Dict[str, Any]]:
        """Generate AI suggestions for the itinerary."""
        itinerary = db.query(models.TripItinerary).filter(
            models.TripItinerary.id == itinerary_id
        ).first()
        
        if not itinerary:
            return []
        
        stops = db.query(models.TripStop).filter(
            models.TripStop.itinerary_id == itinerary_id
        ).order_by(models.TripStop.order).all()
        
        suggestions = []
        
        # Budget suggestions
        if itinerary.budget_usd and itinerary.estimated_cost_usd:
            if itinerary.estimated_cost_usd > itinerary.budget_usd:
                over = itinerary.estimated_cost_usd - itinerary.budget_usd
                suggestions.append({
                    "type": "budget",
                    "priority": "high",
                    "message": f"Trip is ${over:.0f} over budget. Consider shorter stays or cheaper cities.",
                    "action": "reduce_duration",
                })
        
        # Visa suggestions
        visa_stops = [s for s in stops if s.visa_required]
        if visa_stops:
            suggestions.append({
                "type": "visa",
                "priority": "high",
                "message": f"{len(visa_stops)} stops require visas. Apply early!",
                "details": [{"city": s.city, "visa_type": s.visa_type} for s in visa_stops],
            })
        
        # Schengen warning
        schengen_days = sum(s.nights for s in stops if s.country_code in 
            ["PT", "ES", "FR", "DE", "IT", "NL", "BE", "AT", "CH", "GR", "CZ", "HU", "PL"])
        if schengen_days > 85:
            suggestions.append({
                "type": "schengen",
                "priority": "warning",
                "message": f"You're planning {schengen_days} days in Schengen zone (max 90). Consider adjustments.",
            })
        
        # Pace suggestions
        avg_nights = sum(s.nights for s in stops) / len(stops) if stops else 0
        if avg_nights < 3:
            suggestions.append({
                "type": "pace",
                "priority": "low",
                "message": "Fast pace detected. Consider staying longer to reduce travel fatigue.",
            })
        
        # Weather warnings
        for stop in stops:
            if stop.avg_temp_celsius:
                if stop.avg_temp_celsius > 35:
                    suggestions.append({
                        "type": "weather",
                        "priority": "low",
                        "message": f"{stop.city} will be very hot ({stop.avg_temp_celsius}°C). Pack accordingly!",
                    })
                elif stop.avg_temp_celsius < 5:
                    suggestions.append({
                        "type": "weather",
                        "priority": "low",
                        "message": f"{stop.city} will be cold ({stop.avg_temp_celsius}°C). Bring layers!",
                    })
        
        # Save suggestions
        itinerary.ai_suggestions = suggestions
        db.commit()
        
        return suggestions
    
    def suggest_cities(
        self,
        db: Session,
        user_id: str,
        budget_per_day: Optional[float] = None,
        region: Optional[str] = None,  # europe, asia, americas
        passport_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Suggest cities based on preferences."""
        cities = []
        
        for city_name, info in CITY_DATA.items():
            # Budget filter
            if budget_per_day and info["cost_per_day"] > budget_per_day:
                continue
            
            # Region filter
            if region:
                europe_codes = {"PT", "ES", "FR", "DE", "CZ", "HU", "IT", "NL", "GR"}
                asia_codes = {"TH", "ID", "JP", "VN", "MY", "SG"}
                americas_codes = {"US", "MX", "CO", "AR", "BR"}
                
                code = info["code"]
                if region == "europe" and code not in europe_codes:
                    continue
                if region == "asia" and code not in asia_codes:
                    continue  
                if region == "americas" and code not in americas_codes:
                    continue
            
            # Visa info
            visa_info = None
            if passport_code:
                req = visa_wizard_service.get_visa_requirements(db, passport_code, info["code"])
                if req:
                    visa_info = {
                        "type": req.visa_type,
                        "days": req.duration_days,
                    }
            
            cities.append({
                "city": city_name,
                "country": info["country"],
                "country_code": info["code"],
                "cost_per_day": info["cost_per_day"],
                "timezone": info.get("timezone"),
                "visa": visa_info,
            })
        
        # Sort by cost
        cities.sort(key=lambda x: x["cost_per_day"])
        return cities
    
    def get_itinerary(
        self,
        db: Session,
        itinerary_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get full itinerary with stops."""
        itinerary = db.query(models.TripItinerary).filter(
            models.TripItinerary.id == itinerary_id,
            models.TripItinerary.user_id == user_id,
        ).first()
        
        if not itinerary:
            return None
        
        stops = db.query(models.TripStop).filter(
            models.TripStop.itinerary_id == itinerary_id
        ).order_by(models.TripStop.order).all()
        
        return {
            "id": itinerary.id,
            "name": itinerary.name,
            "description": itinerary.description,
            "start_date": itinerary.start_date.isoformat(),
            "end_date": itinerary.end_date.isoformat(),
            "total_days": itinerary.total_days,
            "budget_usd": itinerary.budget_usd,
            "estimated_cost_usd": itinerary.estimated_cost_usd,
            "optimization_score": itinerary.optimization_score,
            "status": itinerary.status,
            "stops": [
                {
                    "id": s.id,
                    "order": s.order,
                    "city": s.city,
                    "country": s.country,
                    "country_code": s.country_code,
                    "arrival_date": s.arrival_date.isoformat(),
                    "departure_date": s.departure_date.isoformat(),
                    "nights": s.nights,
                    "transport": s.transport_from_previous,
                    "transport_cost": s.transport_cost,
                    "daily_cost": s.daily_living_cost,
                    "visa_required": s.visa_required,
                    "visa_type": s.visa_type,
                    "activities": s.activities,
                    "notes": s.notes,
                    "avg_temp": s.avg_temp_celsius,
                }
                for s in stops
            ],
            "ai_suggestions": itinerary.ai_suggestions,
        }
    
    def get_user_itineraries(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[models.TripItinerary]:
        """Get user's itineraries."""
        query = db.query(models.TripItinerary).filter(
            models.TripItinerary.user_id == user_id
        )
        
        if status:
            query = query.filter(models.TripItinerary.status == status)
        
        return query.order_by(models.TripItinerary.start_date.desc()).all()
    
    def delete_itinerary(
        self,
        db: Session,
        itinerary_id: str,
        user_id: str,
    ) -> bool:
        """Delete an itinerary."""
        itinerary = db.query(models.TripItinerary).filter(
            models.TripItinerary.id == itinerary_id,
            models.TripItinerary.user_id == user_id,
        ).first()
        
        if not itinerary:
            return False
        
        db.delete(itinerary)
        db.commit()
        return True


# Singleton
ai_trip_planner = AITripPlannerService()
