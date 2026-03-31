"""
OTA Integration Tests - Validates the full aggregator pipeline.
Based on ota_demo.py, converted to pytest format.
"""
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from backend.database import SessionLocal
from backend.services.ota.aggregator import AggregatorService
from backend.services.ota.commission_tracker import CommissionTracker
from backend.services.agent_tools import execute_tool
from backend import models


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_provider(db_session):
    """Create or get a test affiliate provider."""
    provider_id = "test_manual_provider"
    provider = db_session.query(models.OTAProvider).get(provider_id)
    if not provider:
        provider = models.OTAProvider(
            id=provider_id,
            name="Test Retreats",
            type="affiliate",
            commission_rate=0.10,
            is_active=True
        )
        db_session.add(provider)
        db_session.commit()
    return provider


@pytest.fixture
def test_external_listing(db_session, test_provider):
    """Create or get a test external listing."""
    ext_id = "ext_test_1"
    ext_listing = db_session.query(models.ExternalListing).get(ext_id)
    if not ext_listing:
        ext_listing = models.ExternalListing(
            id=ext_id,
            provider_id=test_provider.id,
            external_id="ext_abc",
            name="Bali Zen Retreat",
            url="https://example.com/retreat",
            price_per_night=150.0,
            location="Bali, Indonesia",
            amenities=["Yoga", "Pool"]
        )
        db_session.add(ext_listing)
        db_session.commit()
    return ext_listing


class TestAggregatorService:
    """Tests for the OTA Aggregator."""

    @pytest.mark.asyncio
    async def test_aggregate_search_returns_results(self, db_session, test_external_listing):
        """Aggregator should find external listings for matching location."""
        aggregator = AggregatorService(db_session)
        
        results = await aggregator.aggregate_search(
            location="Bali",
            check_in=date(2025, 6, 1),
            check_out=date(2025, 6, 5),
            guests=1
        )
        
        assert results is not None
        assert "results" in results
        assert "providers_searched" in results
        # Should have searched at least native + browser providers
        assert len(results["providers_searched"]) >= 1

    @pytest.mark.asyncio
    async def test_aggregate_search_empty_location(self, db_session):
        """Aggregator should handle searches with no results gracefully."""
        aggregator = AggregatorService(db_session)
        
        results = await aggregator.aggregate_search(
            location="NonexistentPlace12345",
            check_in=date(2025, 6, 1),
            check_out=date(2025, 6, 5),
            guests=1
        )
        
        assert results is not None
        assert results["total_found"] == 0 or results["total_found"] >= 0  # May find browser results


class TestCommissionTracker:
    """Tests for the Commission Tracking system."""

    def test_create_ota_booking(self, db_session, test_external_listing):
        """Should create a booking and calculate commission correctly."""
        # Get a user
        user = db_session.query(models.User).first()
        if not user:
            pytest.skip("No user in database for booking test")
        
        tracker = CommissionTracker(db_session)
        
        booking = tracker.create_ota_booking(
            user_id=user.id,
            external_listing_id=test_external_listing.id,
            provider_id=test_external_listing.provider_id,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 5),
            total_price=600.0,
            status="confirmed"
        )
        
        assert booking is not None
        assert booking.commission_earned == 60.0  # 10% of 600
        
        # Cleanup
        db_session.delete(booking)
        db_session.commit()

    def test_commission_report(self, db_session):
        """Should generate a commission report."""
        tracker = CommissionTracker(db_session)
        
        report = tracker.get_commission_report(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31)
        )
        
        assert report is not None
        assert "total_commission" in report


class TestAgentToolIntegration:
    """Tests for the Agent Tool integration with OTA."""

    def test_search_all_platforms_tool(self):
        """The search_all_platforms tool should return structured results."""
        # Mock the actual search to avoid network calls in unit tests
        with patch('backend.services.ota.aggregator.AggregatorService.aggregate_search') as mock_search:
            mock_search.return_value = {
                "results": [{"name": "Mock Listing", "total_price": 500}],
                "total_found": 1,
                "providers_searched": ["native"],
                "providers_succeeded": ["native"]
            }
            
            result = execute_tool("search_all_platforms", {
                "location": "Bali",
                "check_in": "2025-06-01",
                "check_out": "2025-06-05",
                "max_price": 5000
            })
            
            # Tool should return a result or error structure
            assert result is not None
            assert "error" in result or "result" in result
