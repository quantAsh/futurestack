"""
Test suite for Concierge router.
Tests chat endpoint, demo mode fallback, session clearing, and status.
Run with: pytest backend/tests/test_concierge.py -v
"""
import pytest
from unittest.mock import patch, MagicMock


MOCK_AI_RESPONSE = {
    "response": "I found a great listing in Bali for you!",
    "tool_calls": [
        {
            "tool": "search_listings",
            "arguments": {"location": "Bali"},
            "result": [{"id": "lst-1", "name": "Beach Villa"}],
        }
    ],
    "session_id": "test-session",
}

MOCK_DEMO_RESPONSE = {
    "response": "Welcome to NomadNest! Here are some demo listings.",
    "tool_calls": [],
    "session_id": "test-session",
    "demo_mode": True,
}


class TestChatConcierge:
    """Test POST /api/v1/concierge/chat."""

    @patch("backend.routers.concierge.has_llm_api_key", return_value=True)
    @patch("backend.routers.concierge.ai_concierge")
    def test_chat_with_ai(self, mock_ai, mock_key, client):
        """When LLM key is present, uses real AI."""
        mock_ai.agentic_chat.return_value = MOCK_AI_RESPONSE

        response = client.post(
            "/api/v1/concierge/chat",
            json={"query": "Find me a place in Bali", "session_id": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["demo_mode"] is False
        mock_ai.agentic_chat.assert_called_once()

    @patch("backend.routers.concierge.has_llm_api_key", return_value=False)
    @patch("backend.routers.concierge.demo_concierge")
    def test_chat_demo_mode(self, mock_demo, mock_key, client):
        """When no LLM key, falls back to demo mode."""
        mock_demo.demo_chat.return_value = MOCK_DEMO_RESPONSE

        response = client.post(
            "/api/v1/concierge/chat",
            json={"query": "hello", "session_id": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["demo_mode"] is True
        mock_demo.demo_chat.assert_called_once()

    def test_chat_missing_query(self, client):
        """Missing query field returns 422."""
        response = client.post(
            "/api/v1/concierge/chat",
            json={},
        )
        assert response.status_code == 422


class TestClearSession:
    """Test POST /api/v1/concierge/clear-session."""

    @patch("backend.routers.concierge.ai_concierge")
    def test_clear_session(self, mock_ai, client):
        """Clearing a session returns success."""
        response = client.post(
            "/api/v1/concierge/clear-session",
            json={"session_id": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
        assert data["session_id"] == "test-session"
        mock_ai.clear_conversation.assert_called_once_with("test-session")


class TestConciergeStatus:
    """Test GET /api/v1/concierge/status."""

    @patch("backend.routers.concierge.has_llm_api_key", return_value=True)
    def test_status_ai_available(self, mock_key, client):
        """Status endpoint when LLM key is present."""
        response = client.get("/api/v1/concierge/status")
        assert response.status_code == 200
        data = response.json()
        assert data["llm_available"] is True
        assert data["demo_mode"] is False

    @patch("backend.routers.concierge.has_llm_api_key", return_value=False)
    def test_status_demo_mode(self, mock_key, client):
        """Status endpoint when no LLM key."""
        response = client.get("/api/v1/concierge/status")
        assert response.status_code == 200
        data = response.json()
        assert data["llm_available"] is False
        assert data["demo_mode"] is True
