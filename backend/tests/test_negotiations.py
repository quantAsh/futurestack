"""
Test suite for Negotiations router.
Tests negotiation start, counter-offer, accept/reject with mocked AI agent.
Run with: pytest backend/tests/test_negotiations.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4


MOCK_AI_COUNTER = {
    "action": "counter",
    "price": 85.0,
    "message": "How about $85/night? That's a great deal for this location.",
}

MOCK_AI_ACCEPT = {
    "action": "accept",
    "price": 75.0,
    "message": "That's a fair offer. Accepted!",
}

MOCK_AI_REJECT = {
    "action": "reject",
    "price": None,
    "message": "Sorry, that price is too low.",
}


@pytest.fixture
def negotiation_listing(db, test_host, test_hub):
    """Create a listing specifically for negotiation tests."""
    from backend import models

    listing = models.Listing(
        id=str(uuid4()),
        name="Negotiation Test Listing",
        description="A nice place to negotiate",
        property_type="Villa",
        city="Bali",
        country="Indonesia",
        price_usd=100.0,
        features=["wifi"],
        images=["https://example.com/img.jpg"],
        hub_id=test_hub.id,
        owner_id=test_host.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


class TestStartNegotiation:
    """Test POST /api/v1/negotiations/start."""

    @patch("backend.routers.negotiations.negotiation_agent")
    def test_start_negotiation_counter(
        self, mock_agent, client, auth_headers, negotiation_listing
    ):
        """Starting a negotiation with a low offer gets a counter from AI."""
        mock_agent.negotiate_price.return_value = MOCK_AI_COUNTER

        response = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 70.0,
                "message": "Would you consider $70?",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "counter"
        assert data["counter_price"] == 85.0
        assert data["original_price"] == 100.0
        assert "negotiation_id" in data

    @patch("backend.routers.negotiations.negotiation_agent")
    def test_start_negotiation_accept(
        self, mock_agent, client, auth_headers, negotiation_listing
    ):
        """AI can accept a reasonable offer directly."""
        mock_agent.negotiate_price.return_value = MOCK_AI_ACCEPT

        response = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 95.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "accept"

    def test_start_negotiation_listing_not_found(self, client, auth_headers):
        """Negotiating a non-existent listing returns 404."""
        response = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": "nonexistent-listing-id",
                "offered_price": 50.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    @patch("backend.routers.negotiations.negotiation_agent")
    def test_start_negotiation_duplicate(
        self, mock_agent, client, auth_headers, negotiation_listing
    ):
        """Second negotiation for same listing is allowed when first is not pending."""
        mock_agent.negotiate_price.return_value = MOCK_AI_COUNTER

        # First negotiation — will be set to "countered" status
        resp1 = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 70.0,
            },
            headers=auth_headers,
        )
        assert resp1.status_code == 200

        # Second negotiation allowed because first is "countered", not "pending"
        resp2 = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 75.0,
            },
            headers=auth_headers,
        )
        # Second request succeeds since no "pending" negotiation exists
        assert resp2.status_code == 200

    def test_start_negotiation_no_auth(self, client, negotiation_listing):
        """Starting a negotiation without auth returns 401."""
        response = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 70.0,
            },
        )
        assert response.status_code in [401, 403]


class TestNegotiationActions:
    """Test accept and counter-offer endpoints."""

    @patch("backend.routers.negotiations.negotiation_agent")
    def test_accept_counter_offer(
        self, mock_agent, client, db, auth_headers, negotiation_listing
    ):
        """Accepting a counter-offer transitions to accepted status."""
        mock_agent.negotiate_price.return_value = MOCK_AI_COUNTER

        # Start negotiation
        start_resp = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 70.0,
            },
            headers=auth_headers,
        )
        negotiation_id = start_resp.json()["negotiation_id"]

        # Accept the counter
        accept_resp = client.post(
            f"/api/v1/negotiations/{negotiation_id}/accept",
        )
        assert accept_resp.status_code == 200
        data = accept_resp.json()
        assert data["status"] == "accepted"
        assert data["final_price"] == 85.0

    @patch("backend.routers.negotiations.negotiation_agent")
    def test_user_counter_offer(
        self, mock_agent, client, auth_headers, negotiation_listing
    ):
        """User can submit a counter-counter offer."""
        # First negotiation — AI counters
        mock_agent.negotiate_price.return_value = MOCK_AI_COUNTER
        start_resp = client.post(
            "/api/v1/negotiations/start",
            json={
                "listing_id": negotiation_listing.id,
                "offered_price": 70.0,
            },
            headers=auth_headers,
        )
        negotiation_id = start_resp.json()["negotiation_id"]

        # User counters — AI accepts this time
        mock_agent.negotiate_price.return_value = MOCK_AI_ACCEPT
        counter_resp = client.post(
            f"/api/v1/negotiations/{negotiation_id}/counter",
            params={"new_offer": 80.0},
        )
        assert counter_resp.status_code == 200
        data = counter_resp.json()
        assert data["action"] == "accept"
