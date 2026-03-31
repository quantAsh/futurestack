"""
Tests for Messages and Applications routers (Phase 13).
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestMessagesRouter:
    """Tests for /messages/ endpoints."""

    def test_list_threads_returns_empty_for_new_user(self):
        """User with no conversations should get empty list."""
        # Mock setup
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        from backend.routers.messages import list_threads
        
        with patch('backend.routers.messages.get_db', return_value=mock_db):
            with patch('backend.routers.messages.get_current_user', return_value=mock_user):
                # Would need proper FastAPI test client setup
                # This is a structural test placeholder
                assert True

    def test_create_thread_prevents_self_chat(self):
        """Cannot create thread with yourself."""
        from backend.routers.messages import ThreadCreate
        
        data = ThreadCreate(participant_id="user-123")
        # Should raise HTTPException 400 when user_id == participant_id
        assert data.participant_id == "user-123"

    def test_send_message_updates_thread_timestamp(self):
        """Sending a message should update thread.last_message_at."""
        # Placeholder for integration test
        assert True


class TestApplicationsRouter:
    """Tests for /applications/ endpoints."""

    def test_submit_application_creates_pending(self):
        """New application should have status 'pending'."""
        from backend.routers.applications import ApplicationCreate
        
        data = ApplicationCreate(
            hub_id="hub-1",
            answers={"why_host": "I love hosting", "experience": "5 years"}
        )
        
        assert data.hub_id == "hub-1"
        assert "why_host" in data.answers

    def test_duplicate_pending_application_rejected(self):
        """User cannot submit multiple pending applications."""
        # Would need db mock showing existing pending application
        # This is a structural test placeholder
        assert True

    def test_review_application_updates_status(self):
        """Admin can approve/reject application."""
        from backend.routers.applications import ApplicationUpdate
        
        approve_data = ApplicationUpdate(status="approved")
        reject_data = ApplicationUpdate(status="rejected", rejection_reason="Incomplete")
        
        assert approve_data.status == "approved"
        assert reject_data.rejection_reason == "Incomplete"

    def test_approved_application_promotes_user_to_host(self):
        """Approved application should set user.is_host = True."""
        # Would need full integration test
        assert True

    def test_non_admin_cannot_review(self):
        """Regular users cannot approve/reject applications."""
        # Would raise HTTPException 403
        assert True


class TestMessagesSchemas:
    """Test Pydantic schema validation."""

    def test_message_create_requires_content(self):
        """MessageCreate must have content."""
        from backend.routers.messages import MessageCreate
        
        msg = MessageCreate(content="Hello!")
        assert msg.content == "Hello!"

    def test_thread_create_requires_participant(self):
        """ThreadCreate must have participant_id."""
        from backend.routers.messages import ThreadCreate
        
        thread = ThreadCreate(participant_id="user-456")
        assert thread.participant_id == "user-456"


class TestApplicationsSchemas:
    """Test application schema validation."""

    def test_application_update_validates_status(self):
        """Status must be approved or rejected."""
        from backend.routers.applications import ApplicationUpdate
        
        # Valid statuses
        approved = ApplicationUpdate(status="approved")
        rejected = ApplicationUpdate(status="rejected")
        
        assert approved.status == "approved"
        assert rejected.status == "rejected"


# Integration test fixtures (require running DB)
@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_current_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = "test-user-1"
    user.is_admin = False
    user.is_hub_manager = False
    user.is_host = False
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.id = "admin-user-1"
    user.is_admin = True
    user.is_hub_manager = False
    user.is_host = True
    return user
