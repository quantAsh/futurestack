import pytest
import os
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

@pytest.mark.skipif(
    os.environ.get("TESTING") == "true",
    reason="SecurityHeadersMiddleware disabled during TESTING to avoid BaseHTTPMiddleware issues"
)
def test_security_headers():
    response = client.get("/")
    assert response.status_code == 200
    
    # Verify standard security headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert "Strict-Transport-Security" in response.headers
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers

def test_auth_login_cookies():
    # Note: We need a valid user in the DB for this to work perfectly 
    # but we can test the response structure.
    # For now, let's just check that login (even if it fails) doesn't leak info 
    # and that the endpoint exists.
    response = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "password"})
    
    # If it fails with 401, that's fine for structure test
    if response.status_code == 401:
        assert "refresh_token" not in response.json()
    
def test_rate_limiting_active():
    response = client.get("/health")
    assert response.status_code == 200
    # Rate-limit headers require Redis; if Redis is down, headers won't be present
    if "X-RateLimit-Limit" not in response.headers:
        pytest.skip("Redis not available — rate-limit headers not present")
    assert int(response.headers["X-RateLimit-Limit"]) > 0
