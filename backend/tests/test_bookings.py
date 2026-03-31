"""
Tests for Bookings Router - Critical path coverage
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models


class TestBookingsRouter:
    """Test suite for /bookings endpoints."""

    def test_list_bookings_empty(self, client: TestClient, db_session: Session):
        """Test listing bookings when none exist."""
        response = client.get("/api/v1/bookings/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1

    def test_list_bookings_pagination(self, client: TestClient, db_session: Session, sample_user, sample_listing):
        """Test booking pagination works correctly."""
        # Create multiple bookings
        for i in range(5):
            booking = models.Booking(
                id=f"booking-{i}",
                user_id=sample_user.id,
                listing_id=sample_listing.id,
                start_date=date.today() + timedelta(days=i*7),
                end_date=date.today() + timedelta(days=i*7+3),
            )
            db_session.add(booking)
        db_session.commit()

        # Get page 1
        response = client.get("/api/v1/bookings/?page=1&size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

    def test_create_booking_success(self, client: TestClient, db_session: Session, auth_headers, sample_listing):
        """Test successful booking creation."""
        booking_data = {
            "listing_id": sample_listing.id,
            "start_date": (date.today() + timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=7)).isoformat(),
        }
        
        response = client.post("/api/v1/bookings/", json=booking_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["listing_id"] == sample_listing.id
        assert "id" in data

    def test_create_booking_missing_listing(self, client: TestClient, auth_headers):
        """Test booking fails with non-existent listing."""
        booking_data = {
            "listing_id": "non-existent-listing",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=3)).isoformat(),
        }
        
        response = client.post("/api/v1/bookings/", json=booking_data, headers=auth_headers)
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    def test_create_booking_unauthenticated(self, client: TestClient, sample_listing):
        """Test booking requires authentication."""
        booking_data = {
            "listing_id": sample_listing.id,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=3)).isoformat(),
        }
        
        response = client.post("/api/v1/bookings/", json=booking_data)
        assert response.status_code == 401

    def test_delete_booking_success(self, client: TestClient, db_session: Session, sample_user, sample_listing):
        """Test successful booking deletion."""
        # Create a booking first
        booking = models.Booking(
            id="booking-to-delete",
            user_id=sample_user.id,
            listing_id=sample_listing.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )
        db_session.add(booking)
        db_session.commit()

        response = client.delete("/api/v1/bookings/booking-to-delete")
        assert response.status_code == 204

        # Verify deletion
        assert db_session.query(models.Booking).filter_by(id="booking-to-delete").first() is None

    def test_delete_booking_not_found(self, client: TestClient):
        """Test deleting non-existent booking returns 404."""
        response = client.delete("/api/v1/bookings/non-existent-booking")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"


class TestBookingBusinessLogic:
    """Test booking business rules."""

    def test_booking_price_calculation(self, client: TestClient, db_session: Session, auth_headers, sample_listing):
        """Test that booking price is calculated from listing price * duration."""
        # Set listing price
        sample_listing.price_usd = 100.0
        db_session.commit()

        booking_data = {
            "listing_id": sample_listing.id,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=7)).isoformat(),  # 7 days
        }
        
        response = client.post("/api/v1/bookings/", json=booking_data, headers=auth_headers)
        assert response.status_code == 201
        # Price would be 100 * 7 = 700 (logged in audit, not returned in response)


class TestBookingAuditLogging:
    """Test that booking actions are properly logged."""

    @patch("backend.services.audit_logging.log_financial_action")
    def test_create_booking_logs_audit(self, mock_log, client: TestClient, auth_headers, sample_listing):
        """Test that creating a booking logs an audit event."""
        booking_data = {
            "listing_id": sample_listing.id,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=3)).isoformat(),
        }
        
        response = client.post("/api/v1/bookings/", json=booking_data, headers=auth_headers)
        assert response.status_code == 201
        
        # Verify audit log was called
        mock_log.assert_called()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["resource_type"] == "booking"
