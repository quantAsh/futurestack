"""
FutureStack Civic Infrastructure Tests — Projects, Marketplace, RFP, Impact, Calculators.
"""
import pytest
import os
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# ─── Seed ──────────────────────────────────────────────────────────────

class TestSeed:
    def test_seed_civic_data(self):
        resp = client.post("/api/v1/infra/seed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("seeded", "already_seeded")
        if data["status"] == "seeded":
            assert data["projects"] >= 7
            assert data["solutions"] >= 7


# ─── Infrastructure Projects ──────────────────────────────────────────

class TestInfraProjects:
    def test_create_project(self):
        resp = client.post("/api/v1/infra/projects", json={
            "name": "Test Solar Farm",
            "vertical": "energy",
            "location_name": "Test City",
            "country": "Kenya",
            "target_budget_usd": 500000,
            "beneficiary_count": 2000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertical"] == "energy"
        assert data["status"] == "planning"
        return data["id"]

    def test_create_project_invalid_vertical(self):
        resp = client.post("/api/v1/infra/projects", json={
            "name": "Bad Project",
            "vertical": "teleportation",
        })
        assert resp.status_code == 400

    def test_list_projects(self):
        resp = client.get("/api/v1/infra/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "projects" in data

    def test_list_projects_filter_vertical(self):
        resp = client.get("/api/v1/infra/projects?vertical=energy")
        assert resp.status_code == 200
        data = resp.json()
        for p in data["projects"]:
            assert p["vertical"] == "energy"

    def test_get_project_detail(self):
        # Use seeded project
        resp = client.get("/api/v1/infra/projects/proj-water-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertical"] == "water"
        assert "funding" in data
        assert "impact" in data
        assert "latest_metrics" in data

    def test_project_status_transition(self):
        # Create a new project
        create_resp = client.post("/api/v1/infra/projects", json={
            "name": "Transition Test",
            "vertical": "water",
        })
        pid = create_resp.json()["id"]

        # Valid: planning → funding
        resp = client.post(f"/api/v1/infra/projects/{pid}/transition", json={"status": "funding"})
        assert resp.status_code == 200
        assert resp.json()["to"] == "funding"

        # Invalid: funding → operational (skip)
        resp = client.post(f"/api/v1/infra/projects/{pid}/transition", json={"status": "operational"})
        assert resp.status_code == 400

    def test_vertical_summary(self):
        resp = client.get("/api/v1/infra/verticals/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        verticals = [v["vertical"] for v in data]
        assert "water" in verticals
        assert "energy" in verticals


# ─── Solution Marketplace ──────────────────────────────────────────────

class TestMarketplace:
    def test_create_solution(self):
        resp = client.post("/api/v1/marketplace/solutions", json={
            "vendor_id": "test-vendor-001",
            "vertical": "energy",
            "name": "Test Solar Panel Kit",
            "solution_type": "product",
            "price_usd": 5000,
            "specifications": {"capacity_kw": 5, "warranty_years": 10},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "listed"

    def test_search_solutions(self):
        resp = client.get("/api/v1/marketplace/solutions")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "solutions" in data

    def test_search_solutions_by_vertical(self):
        resp = client.get("/api/v1/marketplace/solutions?vertical=water")
        assert resp.status_code == 200
        for s in resp.json()["solutions"]:
            assert s["vertical"] == "water"

    def test_get_solution_detail(self):
        resp = client.get("/api/v1/marketplace/solutions/sol-water-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertical"] == "water"
        assert "specifications" in data
        assert "certifications" in data

    def test_compare_solutions(self):
        resp = client.post("/api/v1/marketplace/solutions/compare", json=["sol-water-001", "sol-water-002"])
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["comparison"]) == 2

    def test_marketplace_stats(self):
        resp = client.get("/api/v1/marketplace/marketplace/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_listings" in data
        assert "by_vertical" in data


# ─── RFP ───────────────────────────────────────────────────────────────

class TestRFP:
    def test_create_rfp(self):
        resp = client.post("/api/v1/rfp/rfps", json={
            "project_id": "proj-water-002",
            "title": "Water Purification System for Jodhpur",
            "vertical": "water",
            "requirements": {"min_capacity_liters_day": 50000},
            "budget_min_usd": 100000,
            "budget_max_usd": 200000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "open"
        return data["id"]

    def test_list_rfps(self):
        resp = client.get("/api/v1/rfp/rfps")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_submit_proposal(self):
        # Create an RFP first
        rfp_resp = client.post("/api/v1/rfp/rfps", json={
            "project_id": "proj-energy-002",
            "title": "Solar Equipment Bid",
            "vertical": "energy",
            "budget_min_usd": 50000,
            "budget_max_usd": 150000,
        })
        rfp_id = rfp_resp.json()["id"]

        # Submit a proposal
        resp = client.post(f"/api/v1/rfp/rfps/{rfp_id}/proposals", json={
            "vendor_id": "test-vendor-001",
            "price_usd": 95000,
            "timeline_days": 90,
            "cover_letter": "We have 10 years experience in solar installations.",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

    def test_duplicate_proposal_rejected(self):
        rfp_resp = client.post("/api/v1/rfp/rfps", json={
            "project_id": "proj-energy-001",
            "title": "Duplicate Test RFP",
            "vertical": "energy",
        })
        rfp_id = rfp_resp.json()["id"]

        # First proposal OK
        client.post(f"/api/v1/rfp/rfps/{rfp_id}/proposals", json={
            "vendor_id": "dup-vendor",
            "price_usd": 50000,
        })

        # Duplicate rejected
        resp = client.post(f"/api/v1/rfp/rfps/{rfp_id}/proposals", json={
            "vendor_id": "dup-vendor",
            "price_usd": 45000,
        })
        assert resp.status_code == 400


# ─── Impact Metrics ───────────────────────────────────────────────────

class TestImpact:
    def test_record_metric(self):
        resp = client.post("/api/v1/impact/metrics", json={
            "project_id": "proj-energy-001",
            "metric_type": "kwh_generated",
            "value": 2500,
            "period": "daily",
            "source": "iot",
        })
        assert resp.status_code == 200
        assert resp.json()["unit"] == "kwh"

    def test_record_batch(self):
        resp = client.post("/api/v1/impact/metrics/batch", json={
            "project_id": "proj-water-001",
            "metrics": [
                {"metric_type": "liters_purified", "value": 48000},
                {"metric_type": "households_served", "value": 2800},
            ],
            "source": "manual",
        })
        assert resp.status_code == 200
        assert resp.json()["recorded"] == 2

    def test_get_project_metrics(self):
        resp = client.get("/api/v1/impact/metrics/proj-water-001")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0

    def test_impact_dashboard(self):
        resp = client.get("/api/v1/impact/impact/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_projects" in data
        assert "metrics" in data

    def test_metric_types_reference(self):
        resp = client.get("/api/v1/impact/impact/metric-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "water" in data
        assert "energy" in data
        assert "liters_purified" in data["water"]


# ─── Vertical Calculators ─────────────────────────────────────────────

class TestCalculators:
    def test_water_purification_sizing(self):
        resp = client.post("/api/v1/infra/calc/water/purification", json={"population": 5000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["population"] == 5000
        assert data["purification_units"] > 0
        assert data["estimated_cost_usd"] > 0

    def test_water_quality_index(self):
        resp = client.post("/api/v1/infra/calc/water/quality", json={"ph": 7.0, "turbidity": 1.0, "chlorine": 0.5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["wqi"] > 80
        assert data["safe_to_drink"] is True

    def test_solar_microgrid_sizing(self):
        resp = client.post("/api/v1/infra/calc/energy/solar", json={"households": 200, "sun_hours": 5.5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["solar_capacity_kw"] > 0
        assert data["battery_capacity_kwh"] > 0
        assert "cost_breakdown" in data
        assert data["payback_years"] > 0

    def test_demand_forecast(self):
        resp = client.post("/api/v1/infra/calc/energy/forecast", json={"current_households": 500, "years": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert data[-1]["households"] > 500

    def test_vertical_farm_sizing(self):
        resp = client.post("/api/v1/infra/calc/food/vertical-farm", json={"population": 10000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["containers_needed"] > 0
        assert data["jobs_created"] > 0

    def test_learning_network_sizing(self):
        resp = client.post("/api/v1/infra/calc/education/learning-network", json={"student_population": 1000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["pods_needed"] > 0
        assert data["tablets_needed"] > 0

    def test_shuttle_fleet_sizing(self):
        resp = client.post("/api/v1/infra/calc/transport/shuttle-fleet", json={
            "daily_passengers": 500,
            "route_km": 15,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["shuttles_needed"] > 0
        assert data["annual_emissions_saved_kg"] > 0
