"""
Vertical-Specific Logic — Domain calculations for each infrastructure vertical.

Provides sizing calculators, efficiency models, and compliance checks
that don't require AI — pure deterministic engineering formulas.
"""
import math
from typing import Dict, Any


# ═══════════════════════════════════════════════════════════════════════
# 💧 WATER
# ═══════════════════════════════════════════════════════════════════════

class WaterCalculator:
    """Water infrastructure sizing and quality calculations."""

    LITERS_PER_PERSON_DAY = 50  # WHO minimum
    LITERS_PER_PERSON_DAY_COMFORTABLE = 100

    @staticmethod
    def size_purification_plant(population: int, safety_factor: float = 1.2) -> dict:
        """Size a water purification plant for a community."""
        daily_demand = population * WaterCalculator.LITERS_PER_PERSON_DAY_COMFORTABLE
        design_capacity = daily_demand * safety_factor

        # Standard UV-C unit = 5,000 L/day
        units_needed = math.ceil(design_capacity / 5000)
        cost_per_unit = 12500
        total_cost = units_needed * cost_per_unit

        return {
            "population": population,
            "daily_demand_liters": daily_demand,
            "design_capacity_liters": round(design_capacity),
            "purification_units": units_needed,
            "unit_capacity_liters": 5000,
            "estimated_cost_usd": total_cost,
            "solar_panels_needed_kw": round(units_needed * 0.5, 1),
            "maintenance_annual_usd": round(total_cost * 0.05),
        }

    @staticmethod
    def calculate_pipe_network(households: int, avg_distance_m: float = 200) -> dict:
        """Estimate pipe network for water distribution."""
        # Branch and trunk sizing
        total_pipe_m = households * avg_distance_m * 0.4  # 40% efficiency factor
        total_pipe_km = total_pipe_m / 1000
        cost_per_km = 25000

        return {
            "households": households,
            "total_pipe_km": round(total_pipe_km, 1),
            "estimated_cost_usd": round(total_pipe_km * cost_per_km),
            "valves_needed": math.ceil(total_pipe_km * 3),
            "pressure_stations": max(1, math.ceil(total_pipe_km / 5)),
        }

    @staticmethod
    def water_quality_index(ph: float, turbidity: float, chlorine: float) -> dict:
        """Calculate composite water quality index (0-100)."""
        # WHO standards
        ph_score = max(0, 100 - abs(ph - 7.0) * 20)
        turbidity_score = max(0, 100 - turbidity * 10)  # NTU
        chlorine_score = max(0, 100 - abs(chlorine - 0.5) * 50)

        wqi = (ph_score * 0.3 + turbidity_score * 0.4 + chlorine_score * 0.3)

        return {
            "wqi": round(wqi, 1),
            "grade": "A" if wqi >= 90 else "B" if wqi >= 70 else "C" if wqi >= 50 else "F",
            "safe_to_drink": wqi >= 70,
            "components": {
                "ph_score": round(ph_score, 1),
                "turbidity_score": round(turbidity_score, 1),
                "chlorine_score": round(chlorine_score, 1),
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# ⚡ ENERGY
# ═══════════════════════════════════════════════════════════════════════

class EnergyCalculator:
    """Energy infrastructure sizing and grid calculations."""

    KWH_PER_HOUSEHOLD_DAY = 8  # Developing country average

    @staticmethod
    def size_solar_microgrid(
        households: int,
        sun_hours: float = 5.0,
        battery_autonomy_hours: float = 12,
    ) -> dict:
        """Size a community solar microgrid."""
        daily_kwh = households * EnergyCalculator.KWH_PER_HOUSEHOLD_DAY
        peak_kw = daily_kwh / sun_hours
        battery_kwh = daily_kwh * (battery_autonomy_hours / 24)

        solar_cost = peak_kw * 900
        battery_cost = battery_kwh * 350
        inverter_cost = peak_kw * 200
        installation = (solar_cost + battery_cost) * 0.20

        total = solar_cost + battery_cost + inverter_cost + installation

        return {
            "households": households,
            "daily_demand_kwh": round(daily_kwh, 1),
            "solar_capacity_kw": round(peak_kw, 1),
            "battery_capacity_kwh": round(battery_kwh, 1),
            "battery_autonomy_hours": battery_autonomy_hours,
            "cost_breakdown": {
                "solar_panels_usd": round(solar_cost),
                "batteries_usd": round(battery_cost),
                "inverters_usd": round(inverter_cost),
                "installation_usd": round(installation),
            },
            "total_cost_usd": round(total),
            "cost_per_household_usd": round(total / households),
            "co2_offset_tons_year": round(daily_kwh * 365 * 0.5 / 1000, 1),
            "payback_years": round(total / (daily_kwh * 365 * 0.12), 1),  # $0.12/kWh
        }

    @staticmethod
    def grid_demand_forecast(
        current_households: int,
        growth_rate_pct: float = 3.0,
        years: int = 5,
    ) -> list:
        """Forecast grid demand growth over N years."""
        forecasts = []
        hh = current_households

        for year in range(1, years + 1):
            hh = hh * (1 + growth_rate_pct / 100)
            daily_kwh = hh * EnergyCalculator.KWH_PER_HOUSEHOLD_DAY
            peak_kw = daily_kwh / 5

            forecasts.append({
                "year": year,
                "households": round(hh),
                "daily_demand_kwh": round(daily_kwh, 1),
                "required_capacity_kw": round(peak_kw, 1),
            })

        return forecasts


# ═══════════════════════════════════════════════════════════════════════
# 🌾 FOOD SECURITY
# ═══════════════════════════════════════════════════════════════════════

class FoodCalculator:
    """Food security sizing and yield calculations."""

    CALORIES_PER_PERSON_DAY = 2000

    @staticmethod
    def size_vertical_farm(population: int, crop_mix: str = "leafy_greens") -> dict:
        """Size a vertical farm to supplement community food needs."""
        # Each container produces ~2 tons/year of leafy greens
        # 1 kg leafy greens ≈ 200 kcal
        daily_calories_target = population * 500  # Supplement 25% of diet
        daily_kg_needed = daily_calories_target / 200
        annual_tons = daily_kg_needed * 365 / 1000

        containers_needed = math.ceil(annual_tons / 2)
        cost_per_container = 95000

        return {
            "population": population,
            "daily_production_kg": round(daily_kg_needed, 1),
            "annual_production_tons": round(annual_tons, 1),
            "containers_needed": containers_needed,
            "total_cost_usd": containers_needed * cost_per_container,
            "water_liters_day": round(daily_kg_needed * 2),  # Hydroponic: 2L per kg
            "power_kw": containers_needed * 25,
            "jobs_created": containers_needed * 2,
            "diet_coverage_pct": 25,
        }


# ═══════════════════════════════════════════════════════════════════════
# 📚 EDUCATION
# ═══════════════════════════════════════════════════════════════════════

class EducationCalculator:
    """Education infrastructure sizing."""

    STUDENTS_PER_POD = 30

    @staticmethod
    def size_learning_network(student_population: int, shifts_per_day: int = 2) -> dict:
        """Size a digital learning network."""
        effective_capacity = EducationCalculator.STUDENTS_PER_POD * shifts_per_day
        pods_needed = math.ceil(student_population / effective_capacity)
        cost_per_pod = 35000
        starlink_annual = 1200

        return {
            "student_population": student_population,
            "pods_needed": pods_needed,
            "shifts_per_day": shifts_per_day,
            "students_per_shift": EducationCalculator.STUDENTS_PER_POD,
            "capital_cost_usd": pods_needed * cost_per_pod,
            "annual_connectivity_usd": pods_needed * starlink_annual,
            "annual_content_usd": 5000,
            "tablets_needed": pods_needed * EducationCalculator.STUDENTS_PER_POD,
            "teachers_needed": pods_needed * shifts_per_day,
        }


# ═══════════════════════════════════════════════════════════════════════
# 🚗 TRANSPORT
# ═══════════════════════════════════════════════════════════════════════

class TransportCalculator:
    """Transport infrastructure sizing."""

    @staticmethod
    def size_shuttle_fleet(
        daily_passengers: int,
        route_km: float,
        trips_per_day: int = 20,
    ) -> dict:
        """Size an electric shuttle fleet."""
        passengers_per_trip = 12  # shuttle capacity
        trips_needed = math.ceil(daily_passengers / passengers_per_trip)
        shuttles_needed = math.ceil(trips_needed / trips_per_day)

        shuttle_cost = 180000
        charging_stations = math.ceil(shuttles_needed / 3)
        station_cost = 25000

        return {
            "daily_passengers": daily_passengers,
            "shuttles_needed": shuttles_needed,
            "trips_per_day": trips_needed,
            "charging_stations": charging_stations,
            "fleet_cost_usd": shuttles_needed * shuttle_cost,
            "charging_infra_usd": charging_stations * station_cost,
            "total_cost_usd": (shuttles_needed * shuttle_cost) + (charging_stations * station_cost),
            "daily_km": round(route_km * trips_needed, 1),
            "annual_emissions_saved_kg": round(route_km * trips_needed * 365 * 0.2),  # vs diesel
            "drivers_needed": shuttles_needed * 2 if trips_per_day > 10 else shuttles_needed,
        }


# ═══════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════

CALCULATORS = {
    "water": WaterCalculator,
    "energy": EnergyCalculator,
    "food_security": FoodCalculator,
    "education": EducationCalculator,
    "transport": TransportCalculator,
}
