"""
Test suite for Auth endpoints.
Tests register, login, password change, and token validation.
Run with: pytest backend/tests/test_auth.py -v
"""
import pytest
from backend.utils import get_password_hash


# A password that satisfies the policy: 8+ chars, upper, lower, digit, special
VALID_PASSWORD = "T3stP@ssword!"
VALID_PASSWORD_2 = "N3wP@ssword!"


class TestRegister:
    """Test POST /api/v1/auth/register."""

    def test_register_new_user(self, client):
        """Registering with a fresh email returns 201."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "name": "New User",
                "password": VALID_PASSWORD,
                "is_host": False,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert "id" in data

    def test_register_duplicate_email(self, client):
        """Registering an existing email returns 400."""
        payload = {
            "email": "duplicate@example.com",
            "name": "First User",
            "password": VALID_PASSWORD,
            "is_host": False,
        }
        # First registration
        resp1 = client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        # Duplicate
        resp2 = client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 400

    def test_register_weak_password(self, client):
        """Password policy violations return 400."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weakpw@example.com",
                "name": "Weak PW",
                "password": "short",  # fails length + complexity
                "is_host": False,
            },
        )
        # FastAPI may return 422 for min_length, or 400 for policy
        assert response.status_code in [400, 422]


class TestLogin:
    """Test POST /api/v1/auth/login."""

    def test_login_valid_credentials(self, client, db):
        """Logging in with correct credentials returns access token."""
        from backend import models
        from uuid import uuid4

        user_id = str(uuid4())
        user = models.User(
            id=user_id,
            email="login_test@example.com",
            name="Login Test",
            hashed_password=get_password_hash(VALID_PASSWORD),
            is_host=False,
        )
        db.add(user)
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "login_test@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db):
        """Wrong password returns 401."""
        from backend import models
        from uuid import uuid4

        user = models.User(
            id=str(uuid4()),
            email="wrongpw@example.com",
            name="Wrong PW",
            hashed_password=get_password_hash(VALID_PASSWORD),
            is_host=False,
        )
        db.add(user)
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrongpw@example.com", "password": "Wr0ng@Passw0rd!"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Non-existent email returns 401."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 401


class TestChangePassword:
    """Test POST /api/v1/auth/change-password."""

    def test_change_password_success(self, client, db):
        """Changing password with valid current password succeeds."""
        from backend import models
        from backend.utils import create_access_token
        from uuid import uuid4

        user = models.User(
            id=str(uuid4()),
            email="changepw@example.com",
            name="Change PW",
            hashed_password=get_password_hash(VALID_PASSWORD),
            is_host=False,
        )
        db.add(user)
        db.commit()

        token = create_access_token(subject=user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": VALID_PASSWORD,
                "new_password": VALID_PASSWORD_2,
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "password_updated"

    def test_change_password_wrong_current(self, client, db):
        """Wrong current password returns 401."""
        from backend import models
        from backend.utils import create_access_token
        from uuid import uuid4

        user = models.User(
            id=str(uuid4()),
            email="wrongcurrent@example.com",
            name="Wrong Current",
            hashed_password=get_password_hash(VALID_PASSWORD),
            is_host=False,
        )
        db.add(user)
        db.commit()

        token = create_access_token(subject=user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "Wr0ng@Passw0rd!",
                "new_password": VALID_PASSWORD_2,
            },
            headers=headers,
        )
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test that auth guards actually work with real JWTs."""

    def test_no_token_raises_error(self):
        """get_current_user raises when no token provided."""
        import pytest
        from unittest.mock import MagicMock, AsyncMock
        from backend.utils import get_current_user
        import asyncio

        # Simulate a request with no Authorization header
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.cookies = {}
        mock_db = MagicMock()

        # get_current_user should raise HTTPException for missing token
        with pytest.raises(Exception):  # HTTPException or similar
            asyncio.get_event_loop().run_until_complete(
                get_current_user(request=mock_request, db=mock_db)
            )

    def test_invalid_token_raises_error(self):
        """get_current_user raises when token is invalid."""
        import pytest
        from unittest.mock import MagicMock
        from backend.utils import get_current_user
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {"authorization": "Bearer garbage-token-value"}
        mock_request.cookies = {}
        mock_db = MagicMock()

        with pytest.raises(Exception):
            asyncio.get_event_loop().run_until_complete(
                get_current_user(request=mock_request, db=mock_db)
            )

    def test_valid_token_passes_auth(self, client, test_user, auth_headers):
        """A valid JWT from conftest passes the auth guard."""
        # GET users/{id} with auth should work (user exists)
        response = client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers,
        )
        # Should not be 401 — auth passed
        assert response.status_code != 401
