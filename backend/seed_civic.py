"""
FutureStack Seed Data — Sample projects, solutions, and impact metrics
across all 6 infrastructure verticals.
"""
from uuid import uuid4
from datetime import datetime, timedelta


def seed_civic_data(db):
    """Seed the civic infrastructure tables with demo data."""
    from backend.models_civic import (
        InfrastructureProject, SolutionListing, ImpactMetric,
        CommunityRFP, VendorProposal,
    )

    # Check if already seeded
    existing = db.query(InfrastructureProject).first()
    if existing:
        return {"status": "already_seeded"}

    now = datetime.utcnow()
    projects = []
    solutions = []
    metrics = []

    # ─── 💧 WATER ──────────────────────────────────────────────────

    water_project = InfrastructureProject(
        id="proj-water-001",
        name="Kisumu Community Water Purification",
        description="Solar-powered water purification plant serving 12 villages around Lake Victoria. "
                    "Produces 50,000 liters of clean drinking water daily using UV + ceramic filtration.",
        vertical="water",
        status="operational",
        location_name="Kisumu County",
        latitude=-0.1022,
        longitude=34.7617,
        region="East Africa",
        country="Kenya",
        target_budget_usd=450000,
        funded_usd=450000,
        beneficiary_count=15000,
        impact_targets={"liters_per_day": 50000, "households_served": 3000, "water_quality_score": 98},
        start_date=now - timedelta(days=365),
        actual_completion=now - timedelta(days=90),
    )
    projects.append(water_project)

    water_project_2 = InfrastructureProject(
        id="proj-water-002",
        name="Rajasthan Rainwater Harvesting Network",
        description="Network of 200 underground cisterns with smart sensors for monsoon capture. "
                    "AI-optimized distribution to 40 villages during dry season.",
        vertical="water",
        status="funding",
        location_name="Jodhpur District",
        latitude=26.2389,
        longitude=73.0243,
        region="South Asia",
        country="India",
        target_budget_usd=800000,
        funded_usd=340000,
        beneficiary_count=25000,
        impact_targets={"liters_per_day": 120000, "distribution_km": 85},
    )
    projects.append(water_project_2)

    # Water solutions
    solutions.extend([
        SolutionListing(
            id="sol-water-001",
            vendor_id="vendor-001",
            vertical="water",
            name="SolarPure UV-C Water Treatment Unit",
            description="Self-contained solar-powered UV-C water purification. Treats 5,000L/day. "
                        "No chemicals, no moving parts, 10-year lifespan.",
            solution_type="product",
            category="water_purification",
            price_usd=12500,
            price_model="fixed",
            specifications={"capacity_liters_day": 5000, "power_source": "solar", "lifespan_years": 10,
                          "removal_rate_bacteria": 99.99, "weight_kg": 45},
            certifications=["WHO Certified", "NSF/ANSI 55"],
            regions_available=["africa", "south_asia", "southeast_asia", "latin_america"],
            impact_rating=4.8,
            review_count=127,
            verified=True,
        ),
        SolutionListing(
            id="sol-water-002",
            vendor_id="vendor-002",
            vertical="water",
            name="AquaSense IoT Water Quality Monitor",
            description="Real-time water quality monitoring with pH, turbidity, chlorine, and bacterial contamination sensors. "
                        "Cloud dashboard with SMS alerts.",
            solution_type="product",
            category="water_monitoring",
            price_usd=850,
            price_model="fixed",
            specifications={"sensors": ["pH", "turbidity", "chlorine", "temperature", "bacteria"],
                          "connectivity": "4G/LoRa", "battery_life_months": 12, "alert_channels": ["sms", "email", "api"]},
            certifications=["CE", "IP68"],
            regions_available=["global"],
            impact_rating=4.5,
            review_count=89,
            verified=True,
        ),
    ])

    # Water metrics
    for day in range(30):
        metrics.append(ImpactMetric(
            id=str(uuid4()),
            project_id="proj-water-001",
            metric_type="liters_purified",
            value=48000 + (day * 100),
            unit="liters",
            period="daily",
            source="iot",
            recorded_at=now - timedelta(days=30 - day),
        ))

    # ─── ⚡ ENERGY ─────────────────────────────────────────────────

    energy_project = InfrastructureProject(
        id="proj-energy-001",
        name="Oaxaca Community Solar Microgrid",
        description="500kW community-owned solar microgrid with Tesla Powerwall battery storage. "
                    "Powers 800 homes, 3 schools, and a community health center.",
        vertical="energy",
        status="operational",
        location_name="Oaxaca Valley",
        latitude=17.0732,
        longitude=-96.7266,
        region="Latin America",
        country="Mexico",
        target_budget_usd=1200000,
        funded_usd=1200000,
        beneficiary_count=4000,
        impact_targets={"kwh_daily": 2500, "co2_offset_kg_annual": 500000, "uptime_pct": 99.5},
        start_date=now - timedelta(days=540),
        actual_completion=now - timedelta(days=180),
    )
    projects.append(energy_project)

    energy_project_2 = InfrastructureProject(
        id="proj-energy-002",
        name="Ghana Wind-Solar Hybrid Farm",
        description="Hybrid 2MW wind + 1MW solar installation for industrial zone power. "
                    "Includes smart metering and demand-response for 50 small businesses.",
        vertical="energy",
        status="construction",
        location_name="Tema Industrial Zone",
        latitude=5.6698,
        longitude=-0.0166,
        region="West Africa",
        country="Ghana",
        target_budget_usd=3500000,
        funded_usd=2800000,
        beneficiary_count=2000,
        impact_targets={"kwh_daily": 8000, "peak_capacity_kw": 3000},
        start_date=now - timedelta(days=120),
        estimated_completion=now + timedelta(days=180),
    )
    projects.append(energy_project_2)

    solutions.extend([
        SolutionListing(
            id="sol-energy-001",
            vendor_id="vendor-003",
            vertical="energy",
            name="MicroGrid-500 Community Solar Kit",
            description="Complete 500kW community solar installation with inverters, racking, and monitoring. "
                        "Includes 200kWh battery storage and cloud-based grid management.",
            solution_type="product",
            category="solar_microgrid",
            price_usd=450000,
            price_model="fixed",
            specifications={"capacity_kw": 500, "battery_kwh": 200, "panel_type": "bifacial_monocrystalline",
                          "efficiency_pct": 22.5, "warranty_years": 25, "monitoring": "cloud_dashboard"},
            certifications=["IEC 61215", "UL 1741", "IEEE 1547"],
            regions_available=["global"],
            impact_rating=4.9,
            review_count=34,
            verified=True,
        ),
        SolutionListing(
            id="sol-energy-002",
            vendor_id="vendor-004",
            vertical="energy",
            name="SmartMeter Pro — Prepaid Energy Management",
            description="Smart prepaid electricity meters with mobile money integration. "
                        "Enables pay-as-you-go solar for off-grid communities.",
            solution_type="product",
            category="smart_metering",
            price_usd=120,
            price_model="per_unit",
            specifications={"connectivity": "NB-IoT", "payment": ["M-Pesa", "MTN MoMo", "card"],
                          "max_load_amps": 60, "tamper_detection": True},
            certifications=["IEC 62052", "STS"],
            regions_available=["africa", "south_asia"],
            impact_rating=4.6,
            review_count=215,
            verified=True,
        ),
    ])

    for day in range(30):
        metrics.append(ImpactMetric(
            id=str(uuid4()),
            project_id="proj-energy-001",
            metric_type="kwh_generated",
            value=2200 + (day * 20),
            unit="kwh",
            period="daily",
            source="iot",
            recorded_at=now - timedelta(days=30 - day),
        ))

    # ─── 🤖 AI INFRASTRUCTURE ──────────────────────────────────────

    ai_project = InfrastructureProject(
        id="proj-ai-001",
        name="Lagos Community AI Hub",
        description="Edge compute center with 8x NVIDIA A100 GPUs serving local AI models. "
                    "Provides API access for 200+ local startups, health diagnostics, and agricultural planning.",
        vertical="ai_infrastructure",
        status="operational",
        location_name="Yaba Tech District",
        latitude=6.5095,
        longitude=3.3711,
        region="West Africa",
        country="Nigeria",
        target_budget_usd=2000000,
        funded_usd=2000000,
        beneficiary_count=5000,
        impact_targets={"compute_tflops": 40, "models_served": 50, "api_calls_daily": 100000},
        start_date=now - timedelta(days=300),
        actual_completion=now - timedelta(days=60),
    )
    projects.append(ai_project)

    solutions.extend([
        SolutionListing(
            id="sol-ai-001",
            vendor_id="vendor-005",
            vertical="ai_infrastructure",
            name="EdgeStack Community AI Server",
            description="Pre-configured edge AI server with 4x NVIDIA L40S, 512GB RAM, and model serving stack. "
                        "Optimized for LLM inference, computer vision, and data processing workloads.",
            solution_type="product",
            category="edge_compute",
            price_usd=85000,
            price_model="fixed",
            specifications={"gpu": "4x NVIDIA L40S", "ram_gb": 512, "storage_tb": 16,
                          "inference_tokens_per_sec": 5000, "power_watts": 2400},
            certifications=["NVIDIA Certified"],
            regions_available=["global"],
            impact_rating=4.7,
            review_count=18,
            verified=True,
        ),
    ])

    # ─── 🌾 FOOD SECURITY ─────────────────────────────────────────

    food_project = InfrastructureProject(
        id="proj-food-001",
        name="Nairobi Vertical Farm Cooperative",
        description="20-story vertical farm using hydroponics and AI-controlled climate. "
                    "Produces 500 tons of leafy greens annually. Community-owned cooperative model.",
        vertical="food_security",
        status="operational",
        location_name="Nairobi Industrial Area",
        latitude=-1.3032,
        longitude=36.8516,
        region="East Africa",
        country="Kenya",
        target_budget_usd=5000000,
        funded_usd=5000000,
        beneficiary_count=50000,
        impact_targets={"calories_produced_daily": 2000000, "meals_served_daily": 5000, "acres_equivalent": 40},
        start_date=now - timedelta(days=730),
        actual_completion=now - timedelta(days=365),
    )
    projects.append(food_project)

    solutions.extend([
        SolutionListing(
            id="sol-food-001",
            vendor_id="vendor-006",
            vertical="food_security",
            name="HydroStack Modular Vertical Farm",
            description="Modular shipping-container vertical farm. Each unit produces 2 tons of greens/year. "
                        "AI-controlled nutrients, LED spectrum, and harvest scheduling.",
            solution_type="product",
            category="vertical_farm",
            price_usd=95000,
            price_model="fixed",
            specifications={"production_tons_year": 2, "crops": ["lettuce", "herbs", "microgreens", "strawberries"],
                          "water_savings_pct": 95, "container_size": "40ft", "power_kw": 25},
            certifications=["USDA Organic Compatible", "GAP Certified"],
            regions_available=["global"],
            impact_rating=4.4,
            review_count=42,
            verified=True,
        ),
    ])

    # ─── 📚 EDUCATION ──────────────────────────────────────────────

    edu_project = InfrastructureProject(
        id="proj-edu-001",
        name="Rwanda Digital Learning Network",
        description="Network of 50 solar-powered digital learning centers with Starlink connectivity. "
                    "AI tutoring in Kinyarwanda, English, and French. STEM and vocational tracks.",
        vertical="education",
        status="construction",
        location_name="Nationwide",
        latitude=-1.9403,
        longitude=29.8739,
        region="East Africa",
        country="Rwanda",
        target_budget_usd=3000000,
        funded_usd=1800000,
        beneficiary_count=100000,
        impact_targets={"students_enrolled": 50000, "courses_offered": 200, "completion_rate_pct": 75},
        start_date=now - timedelta(days=90),
        estimated_completion=now + timedelta(days=365),
    )
    projects.append(edu_project)

    solutions.extend([
        SolutionListing(
            id="sol-edu-001",
            vendor_id="vendor-007",
            vertical="education",
            name="LearnPod — Solar-Powered Digital Classroom",
            description="Self-contained digital classroom with 30 tablets, solar power, Starlink connectivity, "
                        "and offline-capable AI tutor. Pre-loaded with STEM, literacy, and vocational content.",
            solution_type="product",
            category="digital_classroom",
            price_usd=35000,
            price_model="fixed",
            specifications={"tablets": 30, "connectivity": "Starlink + WiFi 6", "power": "solar + battery",
                          "offline_capable": True, "languages": ["english", "french", "swahili", "arabic"]},
            certifications=["UNESCO EdTech Certified"],
            regions_available=["africa", "south_asia", "southeast_asia"],
            impact_rating=4.8,
            review_count=67,
            verified=True,
        ),
    ])

    # ─── 🚗 TRANSPORT ─────────────────────────────────────────────

    transport_project = InfrastructureProject(
        id="proj-transport-001",
        name="Medellín Electric Shuttle Network",
        description="Fleet of 20 autonomous electric shuttles serving hillside comunas. "
                    "AI-optimized routes, solar charging stations, mobile payment integration.",
        vertical="transport",
        status="procurement",
        location_name="Comunas 1, 8, 13",
        latitude=6.2442,
        longitude=-75.5812,
        region="Latin America",
        country="Colombia",
        target_budget_usd=4500000,
        funded_usd=3200000,
        beneficiary_count=80000,
        impact_targets={"trips_daily": 2000, "km_covered_daily": 500, "emissions_saved_kg_annual": 200000},
        estimated_completion=now + timedelta(days=270),
    )
    projects.append(transport_project)

    solutions.extend([
        SolutionListing(
            id="sol-transport-001",
            vendor_id="vendor-008",
            vertical="transport",
            name="AutoShuttle EV-12 — Community Electric Shuttle",
            description="12-passenger autonomous electric shuttle with Level 4 self-driving. "
                        "250km range, solar roof, wheelchair accessible, mobile app integration.",
            solution_type="product",
            category="autonomous_shuttle",
            price_usd=180000,
            price_model="fixed",
            specifications={"passengers": 12, "range_km": 250, "autonomy_level": "L4",
                          "charging_time_hours": 2, "solar_roof": True, "accessibility": "ADA compliant"},
            certifications=["NHTSA Level 4", "UN ECE R157"],
            regions_available=["latin_america", "europe", "north_america"],
            impact_rating=4.3,
            review_count=11,
            verified=True,
        ),
    ])

    # ─── Commit all ────────────────────────────────────────────────

    for p in projects:
        db.add(p)
    for s in solutions:
        db.add(s)
    for m in metrics:
        db.add(m)

    db.commit()

    return {
        "status": "seeded",
        "projects": len(projects),
        "solutions": len(solutions),
        "metrics": len(metrics),
    }
