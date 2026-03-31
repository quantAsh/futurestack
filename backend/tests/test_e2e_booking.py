import os
from uuid import uuid4

import pytest
from playwright.async_api import async_playwright

# This is a smoke test to verify the core booking and negotiation flow
# It assumes the backend is running and reachable

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


@pytest.mark.skip(reason="E2E test requires running server and Playwright browser")
@pytest.mark.asyncio
async def test_booking_negotiation_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        api_request = page.context.request

        # 1. Access the API Health Check
        response = await api_request.get(f"{BASE_URL}/health")
        assert response.status == 200
        content = await response.json()
        assert content["status"] == "ok"

        # 2. Seed a listing for downstream checks
        listing_payload = {
            "name": "Nomad Nest Lisbon Loft",
            "description": "Sunny loft with fast Wi-Fi and coworking nearby.",
            "property_type": "Loft",
            "city": "Lisbon",
            "country": "Portugal",
            "price_usd": 125.0,
            "features": ["wifi", "coworking", "kitchen"],
            "images": ["https://example.com/listing.jpg"],
        }
        response = await api_request.post(
            f"{BASE_URL}/api/v1/listings/", json=listing_payload
        )
        assert response.status == 200

        # 3. Check Listings
        response = await api_request.get(f"{BASE_URL}/api/v1/listings/")
        assert response.status == 200
        listings = await response.json()
        assert len(listings) > 0

        # 3. Access AI Concierge (Mock Flow)
        # In a real E2E we would interact with the chat UI,
        # but here we test the backend contract
        chat_payload = {
            "session_id": "test_session",
            "query": "I want to book a stay in Lisbon for January",
        }
        # Use playwright to make the POST request
        response = await api_request.post(
            f"{BASE_URL}/api/v1/concierge/chat", json=chat_payload
        )
        assert response.status == 200
        chat_response = await response.json()
        assert "response" in chat_response

        await browser.close()


@pytest.mark.skip(reason="E2E test requires running server and Playwright browser")
@pytest.mark.asyncio
async def test_investment_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        api_request = page.context.request

        # Seed a hub for investment opportunities
        hub_payload = {
            "name": "NomadNest Hub Lisbon",
            "mission": "Community-first coliving for remote workers.",
            "type": "Coliving",
            "logo": "https://example.com/logo.png",
            "charter": "Build thriving nomad communities.",
            "lat": 38.7223,
            "lng": -9.1393,
            "member_ids": [],
            "amenity_ids": [],
            "listing_ids": [],
        }
        response = await api_request.post(f"{BASE_URL}/api/v1/hubs/", json=hub_payload)
        assert response.status == 200

        # Create a user for the investment flow
        email = f"investor-{uuid4().hex[:8]}@example.com"
        register_payload = {
            "email": email,
            "name": "Test Investor",
            "password": "Password123!",
            "is_host": False,
        }
        response = await api_request.post(
            f"{BASE_URL}/api/v1/auth/register", json=register_payload
        )
        assert response.status == 200
        user = await response.json()
        user_id = user["id"]

        # 1. Get Opportunities
        response = await api_request.get(f"{BASE_URL}/api/v1/investments/opportunities")
        assert response.status == 200
        opportunities = await response.json()
        assert len(opportunities) > 0
        hub_id = opportunities[0]["hub_id"]

        # 2. Make Investment
        invest_payload = {"user_id": user_id, "hub_id": hub_id, "amount_usd": 1000.0}
        response = await api_request.post(
            f"{BASE_URL}/api/v1/investments/invest", json=invest_payload
        )
        assert response.status == 200
        invest_result = await response.json()
        assert invest_result["status"] == "confirmed"
        assert invest_result["amount_usd"] == 1000.0

        await browser.close()
