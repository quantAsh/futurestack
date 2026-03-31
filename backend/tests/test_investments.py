from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models
import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    db = SessionLocal()
    # Ensure test hub exists
    hub = db.query(models.Hub).filter(models.Hub.id == "test_hub").first()
    if not hub:
        hub = models.Hub(id="test_hub", name="Test Hub", type="Coliving")
        db.add(hub)

    # Ensure test user exists
    user = db.query(models.User).filter(models.User.id == "test_user").first()
    if not user:
        user = models.User(id="test_user", name="Test User")
        db.add(user)

    db.commit()
    db.close()


def test_get_opportunities():
    response = client.get("/api/v1/investments/opportunities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "hub_name" in data[0]


def test_invest():
    # Setup - need a hub_id from opportunities
    opps = client.get("/api/v1/investments/opportunities").json()
    hub_id = opps[0]["hub_id"]

    payload = {"user_id": "test_user", "hub_id": hub_id, "amount_usd": 500.0}
    response = client.post("/api/v1/investments/invest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["amount_usd"] == 500.0
    assert data["shares"] == 0.5
