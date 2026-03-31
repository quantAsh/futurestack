"""
FutureStack AI Infrastructure Advisor — Domain-specific concierge tools
for infrastructure planning, cost estimation, solution comparison, and impact forecasting.
"""
import json
import structlog
from typing import Dict, Any, List
from litellm import completion
from backend.config import settings

logger = structlog.get_logger("futurestack.infra_advisor")

MODEL = "gemini/gemini-2.0-flash"


# ─── Vertical Knowledge Base ──────────────────────────────────────────

VERTICAL_CONTEXT = {
    "water": {
        "unit_costs": {"purification_plant_per_lpd": 9, "well_drilling_per_meter": 150,
                      "pipe_per_km": 25000, "iot_sensor": 850},
        "benchmarks": {"liters_per_person_day": 50, "quality_score_target": 95},
    },
    "energy": {
        "unit_costs": {"solar_per_kw": 900, "wind_per_kw": 1300, "battery_per_kwh": 350,
                      "smart_meter": 120, "microgrid_controller": 15000},
        "benchmarks": {"kwh_per_household_day": 8, "uptime_target_pct": 99},
    },
    "ai_infrastructure": {
        "unit_costs": {"gpu_server_a100": 250000, "gpu_server_l40s": 85000,
                      "networking_per_rack": 20000, "cooling_per_kw": 500},
        "benchmarks": {"tflops_per_1000_users": 5, "latency_target_ms": 100},
    },
    "food_security": {
        "unit_costs": {"vertical_farm_container": 95000, "greenhouse_per_sqm": 120,
                      "cold_storage_per_ton": 8000, "irrigation_per_hectare": 3000},
        "benchmarks": {"calories_per_person_day": 2000, "tons_per_vertical_unit_year": 2},
    },
    "education": {
        "unit_costs": {"digital_classroom_pod": 35000, "tablet_per_student": 200,
                      "starlink_annual": 1200, "content_platform_annual": 5000},
        "benchmarks": {"students_per_pod": 30, "completion_rate_target_pct": 75},
    },
    "transport": {
        "unit_costs": {"ev_shuttle_12pax": 180000, "charging_station": 25000,
                      "route_optimization_annual": 12000, "bike_share_per_unit": 800},
        "benchmarks": {"trips_per_shuttle_day": 20, "km_per_charge": 250},
    },
}


# ─── Tool Functions ───────────────────────────────────────────────────

async def assess_infrastructure_needs(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess infrastructure needs for a community.
    Input: population, location, vertical, current_situation
    Output: recommended solution, sizing, estimated cost
    """
    population = params.get("population", 1000)
    vertical = params.get("vertical", "energy")
    location = params.get("location", "rural community")
    situation = params.get("current_situation", "no existing infrastructure")

    context = VERTICAL_CONTEXT.get(vertical, {})

    prompt = f"""You are an infrastructure planning expert for FutureStack, a civic tech platform.

Assess the infrastructure needs for this community:
- Population: {population}
- Location: {location}
- Vertical: {vertical}
- Current situation: {situation}

Reference costs: {json.dumps(context.get('unit_costs', {}))}
Benchmarks: {json.dumps(context.get('benchmarks', {}))}

Provide a JSON response with:
{{
    "recommended_solution": "description of recommended approach",
    "sizing": {{"key_spec": "value"}},
    "estimated_budget_usd": number,
    "timeline_months": number,
    "impact_projection": {{"metric": "projected_value"}},
    "phasing": ["phase 1 description", "phase 2 description"],
    "risks": ["risk 1", "risk 2"],
    "quick_wins": ["immediate action 1", "immediate action 2"]
}}"""

    try:
        response = completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error("assess_needs_failed", error=str(e))
        return _fallback_assessment(vertical, population, context)


async def estimate_project_cost(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate costs for an infrastructure project.
    Input: vertical, scope details
    Output: itemized cost breakdown
    """
    vertical = params.get("vertical", "energy")
    scope = params.get("scope", {})
    context = VERTICAL_CONTEXT.get(vertical, {})
    unit_costs = context.get("unit_costs", {})

    # Calculate from known unit costs
    line_items = []
    total = 0

    for item, qty in scope.items():
        if item in unit_costs:
            cost = unit_costs[item] * qty
            line_items.append({
                "item": item,
                "quantity": qty,
                "unit_cost_usd": unit_costs[item],
                "total_usd": cost,
            })
            total += cost

    # Add standard contingencies
    contingency = total * 0.15
    project_management = total * 0.10
    installation = total * 0.20

    return {
        "vertical": vertical,
        "line_items": line_items,
        "subtotal_usd": round(total, 2),
        "installation_usd": round(installation, 2),
        "project_management_usd": round(project_management, 2),
        "contingency_usd": round(contingency, 2),
        "total_estimated_usd": round(total + installation + project_management + contingency, 2),
        "confidence": "medium" if line_items else "low",
        "note": "Estimate based on FutureStack benchmark data. Request vendor quotes for final pricing.",
    }


async def compare_solutions(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI-powered solution comparison.
    Input: solution descriptions or IDs
    Output: comparison matrix with recommendation
    """
    solutions = params.get("solutions", [])
    criteria = params.get("criteria", ["price", "reliability", "scalability", "local_support"])

    prompt = f"""You are a procurement advisor for FutureStack, a civic infrastructure platform.

Compare these infrastructure solutions:
{json.dumps(solutions, indent=2)}

Evaluation criteria: {criteria}

Return a JSON response with:
{{
    "comparison_matrix": [
        {{"solution": "name", "scores": {{"criterion": score_1_to_10}}, "strengths": ["..."], "weaknesses": ["..."]}}
    ],
    "recommendation": "which solution and why",
    "best_value": "name",
    "best_performance": "name",
    "considerations": ["important factor 1", "important factor 2"]
}}"""

    try:
        response = completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error("compare_solutions_failed", error=str(e))
        return {"error": "Comparison failed", "solutions": solutions}


async def forecast_impact(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Forecast projected impact metrics for a planned project.
    Input: vertical, solution specs, population served
    Output: projected metrics over 1, 3, 5 years
    """
    vertical = params.get("vertical", "energy")
    specs = params.get("specifications", {})
    population = params.get("population", 1000)
    benchmarks = VERTICAL_CONTEXT.get(vertical, {}).get("benchmarks", {})

    prompt = f"""You are an impact forecasting expert for FutureStack.

Forecast the impact of this infrastructure project:
- Vertical: {vertical}
- Specifications: {json.dumps(specs)}
- Population served: {population}
- Industry benchmarks: {json.dumps(benchmarks)}

Return a JSON response with:
{{
    "year_1": {{"metric_name": projected_value}},
    "year_3": {{"metric_name": projected_value}},
    "year_5": {{"metric_name": projected_value}},
    "roi_pct": number,
    "payback_period_years": number,
    "social_impact_score": number_1_to_100,
    "environmental_impact": {{"co2_offset_tons": number, "resource_savings": "description"}},
    "methodology": "brief description of how projections were calculated"
}}"""

    try:
        response = completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error("forecast_impact_failed", error=str(e))
        return _fallback_forecast(vertical, population, benchmarks)


async def find_funding(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Match a project to potential funding sources.
    Input: vertical, budget, region
    Output: matching funding opportunities
    """
    vertical = params.get("vertical", "energy")
    budget = params.get("budget_usd", 500000)
    region = params.get("region", "Africa")

    return {
        "funding_sources": [
            {
                "type": "dao_treasury",
                "name": "FutureStack Community Treasury",
                "available": True,
                "description": "Community-governed fund from platform revenue. Requires DAO proposal + vote.",
                "typical_amount_usd": "Up to $100,000",
                "process": "Submit proposal → 7-day vote → Disbursement",
            },
            {
                "type": "fractional_investment",
                "name": "FutureStack Micro-Investment",
                "available": True,
                "description": "Fractional ownership from platform investors. Investors earn yield from operational revenue.",
                "typical_amount_usd": "Up to 80% of project budget",
                "process": "List as investment opportunity → Investors buy shares",
            },
            {
                "type": "grant",
                "name": f"International {vertical.title()} Development Fund",
                "available": True,
                "description": f"Multilateral grants for {vertical} projects in {region}.",
                "typical_amount_usd": "$50,000 - $2,000,000",
                "process": "Application → Review (6-12 weeks) → Disbursement",
            },
            {
                "type": "impact_bond",
                "name": "Social Impact Bond",
                "available": budget > 200000,
                "description": "Pay-for-success financing. Investors paid based on verified impact metrics.",
                "typical_amount_usd": "$200,000 - $10,000,000",
                "process": "Structure bond → Attract investors → Deliver → Verify impact → Payout",
            },
        ],
        "recommended_mix": {
            "dao_treasury_pct": 15,
            "micro_investment_pct": 50,
            "grants_pct": 25,
            "impact_bonds_pct": 10,
        },
        "total_needed_usd": budget,
    }


# ─── Fallback Functions (no AI needed) ────────────────────────────────

def _fallback_assessment(vertical: str, population: int, context: dict) -> dict:
    """Deterministic fallback when AI is unavailable."""
    unit_costs = context.get("unit_costs", {})
    benchmarks = context.get("benchmarks", {})

    if vertical == "water":
        liters_needed = population * benchmarks.get("liters_per_person_day", 50)
        units_needed = max(1, liters_needed // 5000)
        cost = units_needed * unit_costs.get("purification_plant_per_lpd", 9) * 5000
        return {
            "recommended_solution": f"{units_needed} solar-powered purification units",
            "sizing": {"capacity_liters_day": liters_needed, "units": units_needed},
            "estimated_budget_usd": cost,
            "timeline_months": 6,
            "impact_projection": {"liters_per_day": liters_needed, "households_served": population // 5},
        }
    elif vertical == "energy":
        kwh_needed = population * benchmarks.get("kwh_per_household_day", 8) / 4  # avg household size
        kw_needed = kwh_needed / 5  # 5 sun-hours
        cost = kw_needed * unit_costs.get("solar_per_kw", 900)
        return {
            "recommended_solution": f"{kw_needed:.0f}kW community solar microgrid",
            "sizing": {"capacity_kw": round(kw_needed), "daily_kwh": round(kwh_needed)},
            "estimated_budget_usd": round(cost),
            "timeline_months": 9,
            "impact_projection": {"kwh_daily": round(kwh_needed), "co2_offset_kg_annual": round(kwh_needed * 365 * 0.5)},
        }
    else:
        return {
            "recommended_solution": f"Comprehensive {vertical} solution for {population} people",
            "estimated_budget_usd": population * 500,
            "timeline_months": 12,
        }


def _fallback_forecast(vertical: str, population: int, benchmarks: dict) -> dict:
    """Deterministic impact forecast fallback."""
    base_metrics = {}
    if vertical == "energy":
        kwh = population * benchmarks.get("kwh_per_household_day", 8) / 4
        base_metrics = {"kwh_generated": round(kwh * 365)}
    elif vertical == "water":
        liters = population * benchmarks.get("liters_per_person_day", 50)
        base_metrics = {"liters_purified": round(liters * 365)}

    return {
        "year_1": base_metrics,
        "year_3": {k: round(v * 1.1) for k, v in base_metrics.items()},
        "year_5": {k: round(v * 1.2) for k, v in base_metrics.items()},
        "social_impact_score": 75,
        "methodology": "Calculated from FutureStack benchmark data (fallback mode)",
    }


# ─── Tool Registry (for concierge agent) ─────────────────────────────

INFRA_TOOLS = [
    {
        "name": "assess_infrastructure_needs",
        "description": "Assess what infrastructure a community needs based on population, location, and current situation. Returns recommended solution with sizing and cost estimate.",
        "handler": assess_infrastructure_needs,
        "parameters": {
            "population": "int — number of people to serve",
            "vertical": "str — water, energy, ai_infrastructure, food_security, education, transport",
            "location": "str — geographic description",
            "current_situation": "str — what exists currently",
        },
    },
    {
        "name": "estimate_project_cost",
        "description": "Get itemized cost estimate for an infrastructure project based on scope and vertical.",
        "handler": estimate_project_cost,
        "parameters": {
            "vertical": "str — infrastructure vertical",
            "scope": "dict — items and quantities, e.g. {'solar_per_kw': 500, 'battery_per_kwh': 200}",
        },
    },
    {
        "name": "compare_solutions",
        "description": "Compare multiple infrastructure solutions side-by-side with scoring and recommendation.",
        "handler": compare_solutions,
        "parameters": {
            "solutions": "list of solution descriptions or specs to compare",
            "criteria": "list of evaluation criteria",
        },
    },
    {
        "name": "forecast_impact",
        "description": "Forecast project impact metrics over 1, 3, and 5 years including ROI and social impact score.",
        "handler": forecast_impact,
        "parameters": {
            "vertical": "str — infrastructure vertical",
            "specifications": "dict — solution specs",
            "population": "int — people served",
        },
    },
    {
        "name": "find_funding",
        "description": "Find matching funding sources (DAO treasury, micro-investments, grants, impact bonds) for a project.",
        "handler": find_funding,
        "parameters": {
            "vertical": "str — infrastructure vertical",
            "budget_usd": "float — total budget needed",
            "region": "str — geographic region",
        },
    },
]
