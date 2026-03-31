"""
Vertical Calculators Router — Deterministic sizing and engineering tools per vertical.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.vertical_calculators import (
    WaterCalculator, EnergyCalculator, FoodCalculator,
    EducationCalculator, TransportCalculator,
)

router = APIRouter()


# --- Water ---

class WaterSizingRequest(BaseModel):
    population: int
    safety_factor: float = 1.2

class PipeNetworkRequest(BaseModel):
    households: int
    avg_distance_m: float = 200

class WaterQualityRequest(BaseModel):
    ph: float
    turbidity: float  # NTU
    chlorine: float  # mg/L

@router.post("/calc/water/purification")
def calc_water_purification(req: WaterSizingRequest):
    """Size a water purification plant for a community."""
    return WaterCalculator.size_purification_plant(req.population, req.safety_factor)

@router.post("/calc/water/pipes")
def calc_pipe_network(req: PipeNetworkRequest):
    """Estimate pipe distribution network."""
    return WaterCalculator.calculate_pipe_network(req.households, req.avg_distance_m)

@router.post("/calc/water/quality")
def calc_water_quality(req: WaterQualityRequest):
    """Calculate water quality index from sensor readings."""
    return WaterCalculator.water_quality_index(req.ph, req.turbidity, req.chlorine)


# --- Energy ---

class SolarSizingRequest(BaseModel):
    households: int
    sun_hours: float = 5.0
    battery_autonomy_hours: float = 12

class DemandForecastRequest(BaseModel):
    current_households: int
    growth_rate_pct: float = 3.0
    years: int = 5

@router.post("/calc/energy/solar")
def calc_solar_microgrid(req: SolarSizingRequest):
    """Size a community solar microgrid with battery storage."""
    return EnergyCalculator.size_solar_microgrid(req.households, req.sun_hours, req.battery_autonomy_hours)

@router.post("/calc/energy/forecast")
def calc_demand_forecast(req: DemandForecastRequest):
    """Forecast grid demand growth over N years."""
    return EnergyCalculator.grid_demand_forecast(req.current_households, req.growth_rate_pct, req.years)


# --- Food ---

class FarmSizingRequest(BaseModel):
    population: int
    crop_mix: str = "leafy_greens"

@router.post("/calc/food/vertical-farm")
def calc_vertical_farm(req: FarmSizingRequest):
    """Size a vertical farm to supplement community food needs."""
    return FoodCalculator.size_vertical_farm(req.population, req.crop_mix)


# --- Education ---

class LearningNetworkRequest(BaseModel):
    student_population: int
    shifts_per_day: int = 2

@router.post("/calc/education/learning-network")
def calc_learning_network(req: LearningNetworkRequest):
    """Size a digital learning pod network."""
    return EducationCalculator.size_learning_network(req.student_population, req.shifts_per_day)


# --- Transport ---

class ShuttleFleetRequest(BaseModel):
    daily_passengers: int
    route_km: float
    trips_per_day: int = 20

@router.post("/calc/transport/shuttle-fleet")
def calc_shuttle_fleet(req: ShuttleFleetRequest):
    """Size an electric shuttle fleet for a community."""
    return TransportCalculator.size_shuttle_fleet(req.daily_passengers, req.route_km, req.trips_per_day)
