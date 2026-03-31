"""
Tests for Stripe Payment Service - Critical payment path coverage
"""
import pytest
from unittest.mock import patch, MagicMock
from backend.services.stripe_service import (
    create_checkout_session,
    handle_webhook,
    create_portal_session,
)


class TestStripeCheckout:
    """Test Stripe checkout flow."""

    @patch("backend.services.stripe_service.stripe.Customer.create")
    @patch("backend.services.stripe_service.stripe.checkout.Session.create")
    @patch("backend.services.stripe_service.settings")
    def test_create_checkout_session_success(self, mock_settings, mock_session_create, mock_customer_create):
        """Test successful checkout session creation."""
        mock_settings.STRIPE_API_KEY = "sk_test_fake"
        mock_settings.STRIPE_PRO_PRICE_ID = "price_pro_test"
        mock_settings.STRIPE_UNLIMITED_PRICE_ID = "price_unlimited_test"

        mock_customer_create.return_value = MagicMock(id="cus_test_123")
        mock_session_create.return_value = MagicMock(
            id="cs_test_123",
            url="https://checkout.stripe.com/test"
        )
        
        result = create_checkout_session(
            user_id="user-123",
            user_email="test@example.com",
            tier="pro",
            success_url="https://app.test/success",
            cancel_url="https://app.test/cancel"
        )
        
        assert result is not None
        assert result["session_id"] == "cs_test_123"
        assert result["url"] == "https://checkout.stripe.com/test"
        mock_session_create.assert_called_once()

    @patch("backend.services.stripe_service.settings")
    def test_create_checkout_session_no_api_key(self, mock_settings):
        """Test checkout fails without API key."""
        mock_settings.STRIPE_API_KEY = ""

        with pytest.raises(ValueError, match="Stripe API key not configured"):
            create_checkout_session(
                user_id="user-123",
                user_email="test@example.com",
                tier="pro",
                success_url="https://app.test/success",
                cancel_url="https://app.test/cancel"
            )


class TestStripeWebhook:
    """Test Stripe webhook handling."""

    @patch("backend.services.stripe_service.stripe.Webhook.construct_event")
    @patch("backend.services.stripe_service.settings")
    def test_webhook_parses_checkout_completed(self, mock_settings, mock_construct):
        """Test that webhook parsing handles checkout.session.completed."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

        mock_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_123",
                    "subscription": "sub_test_123",
                    "metadata": {"user_id": "user-123", "tier": "pro"}
                }
            }
        }
        mock_construct.return_value = mock_event
        
        result = handle_webhook(b'{"test": "payload"}', "sig_test")
        assert result is not None
        assert result["event_type"] == "checkout.session.completed"
        assert result["processed"] is True
        assert result["user_id"] == "user-123"
        assert result["tier"] == "pro"

    @patch("backend.services.stripe_service.settings")
    def test_webhook_no_secret_raises(self, mock_settings):
        """Test that missing webhook secret raises error."""
        mock_settings.STRIPE_WEBHOOK_SECRET = ""

        with pytest.raises(ValueError, match="Stripe webhook secret not configured"):
            handle_webhook(b'{"test": "payload"}', "sig_test")


class TestCustomerPortal:
    """Test Stripe customer portal."""

    @patch("backend.services.stripe_service.stripe.billing_portal.Session.create")
    def test_create_portal_session_success(self, mock_create):
        """Test customer portal session creation."""
        mock_create.return_value = MagicMock(
            url="https://billing.stripe.com/session/test"
        )
        
        result = create_portal_session(
            stripe_customer_id="cus_test_123",
            return_url="https://app.test/settings"
        )
        
        assert result is not None
        mock_create.assert_called_once()
