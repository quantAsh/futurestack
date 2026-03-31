"""
Test suite for Search router.
Tests smart search with mocked search service and error masking.
Run with: pytest backend/tests/test_search.py -v
"""
import pytest
from unittest.mock import patch, MagicMock


class MockListing:
    """Mimics a Listing object returned by smart_search_service."""

    def __init__(self, id, name, city="Bali", country="Indonesia", price_usd=50.0):
        self.id = id
        self.name = name
        self.description = f"A nice place in {city}"
        self.city = city
        self.country = country
        self.price_usd = price_usd


MOCK_LISTINGS = [
    MockListing(id="lst-1", name="Beach Villa", city="Bali", price_usd=80.0),
    MockListing(id="lst-2", name="Mountain Retreat", city="Ubud", price_usd=45.0),
]


class TestSmartSearch:
    """Test POST /api/v1/search/smart."""

    @patch("backend.routers.search.smart_search_service")
    def test_smart_search_returns_results(self, mock_svc, client):
        """Mocked search service returns formatted listings."""
        mock_svc.search_listings.return_value = MOCK_LISTINGS

        response = client.post(
            "/api/v1/search/smart",
            json={"query": "beach villa in Bali"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Beach Villa"
        assert data[1]["name"] == "Mountain Retreat"

    @patch("backend.routers.search.smart_search_service")
    def test_smart_search_empty_results(self, mock_svc, client):
        """Empty query returns empty list."""
        mock_svc.search_listings.return_value = []

        response = client.post(
            "/api/v1/search/smart",
            json={"query": "xyznonexistent"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []

    @patch("backend.routers.search.smart_search_service")
    def test_smart_search_service_error(self, mock_svc, client):
        """Search service exception returns 500 with masked error."""
        mock_svc.search_listings.side_effect = RuntimeError("LLM connection timeout")

        response = client.post(
            "/api/v1/search/smart",
            json={"query": "beach villa"},
        )
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Search service error"
        # Internal error message should NOT leak
        assert "LLM connection timeout" not in str(data)

    def test_smart_search_missing_query(self, client):
        """Missing query field returns 422 validation error."""
        response = client.post(
            "/api/v1/search/smart",
            json={},
        )
        assert response.status_code == 422
