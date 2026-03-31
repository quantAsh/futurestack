from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend import models
import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    db = SessionLocal()
    # Ensure test user exists
    user = db.query(models.User).filter(models.User.id == "test_host").first()
    if not user:
        user = models.User(id="test_host", name="Test Host", is_host=True)
        db.add(user)
    db.commit()
    db.close()


def test_create_experience():
    payload = {
        "name": "Lisbon Surf Retreat",
        "type": "Retreat",
        "curator_id": "test_host",
        "city": "Lisbon",
        "price_usd": 1200.0,
    }
    response = client.post("/api/v1/creator/experiences", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "published"
    assert data["name"] == "Lisbon Surf Retreat"


def test_get_host_earnings():
    response = client.get("/api/v1/creator/host/earnings?host_id=test_host")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "total_net_usd" in data["summary"]
