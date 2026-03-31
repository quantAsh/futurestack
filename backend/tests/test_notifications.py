"""
Test suite for Notifications router.
Tests list, unread count, mark-read, and mark-all-read.
Run with: pytest backend/tests/test_notifications.py -v
"""
import pytest
from uuid import uuid4


@pytest.fixture
def test_notifications(db, test_user):
    """Create sample notifications for a test user."""
    from backend import models

    notifications = []
    for i in range(3):
        notif = models.Notification(
            id=str(uuid4()),
            user_id=test_user.id,
            type="alert" if i == 0 else "opportunity",
            title=f"Test Notification {i + 1}",
            description=f"Description for notification {i + 1}",
            read=i == 2,  # Third one is already read
        )
        db.add(notif)
        notifications.append(notif)
    db.commit()
    for n in notifications:
        db.refresh(n)
    return notifications


class TestGetNotifications:
    """Test GET /api/v1/notifications/."""

    def test_get_notifications(self, client, test_user, test_notifications):
        """Returns paginated notifications for a user."""
        response = client.get(
            "/api/v1/notifications/",
            params={"user_id": test_user.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 3

    def test_get_notifications_empty(self, client):
        """No notifications for unknown user."""
        response = client.get(
            "/api/v1/notifications/",
            params={"user_id": str(uuid4())},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_get_notifications_pagination(self, client, test_user, test_notifications):
        """Pagination returns correct page size."""
        response = client.get(
            "/api/v1/notifications/",
            params={"user_id": test_user.id, "page": 1, "size": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["pages"] == 2


class TestUnreadCount:
    """Test GET /api/v1/notifications/unread-count."""

    def test_unread_count(self, client, test_user, test_notifications):
        """Returns correct unread count."""
        response = client.get(
            "/api/v1/notifications/unread-count",
            params={"user_id": test_user.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2  # 2 of 3 are unread


class TestMarkRead:
    """Test POST /api/v1/notifications/{id}/mark-read."""

    def test_mark_notification_read(self, client, test_notifications):
        """Marking a notification as read returns success."""
        notif_id = test_notifications[0].id
        response = client.post(f"/api/v1/notifications/{notif_id}/mark-read")
        assert response.status_code == 200
        assert response.json()["status"] == "marked_read"

    def test_mark_notification_not_found(self, client):
        """Marking a non-existent notification returns 404."""
        response = client.post(f"/api/v1/notifications/{uuid4()}/mark-read")
        assert response.status_code == 404

    def test_mark_all_read(self, client, test_user, test_notifications):
        """Mark all notifications as read."""
        response = client.post(
            "/api/v1/notifications/mark-all-read",
            params={"user_id": test_user.id},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "all_marked_read"

        # Verify unread count is now 0
        count_resp = client.get(
            "/api/v1/notifications/unread-count",
            params={"user_id": test_user.id},
        )
        assert count_resp.json()["count"] == 0
