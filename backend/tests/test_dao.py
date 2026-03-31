from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal, engine
from backend import models
from sqlalchemy import text
import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    # Force schema update (note: create_all doesn't add columns to existing tables)
    # For a dev/test environment, we can drop and recreate if needed,
    # but here we just ensure Base.metadata.create_all is called (it is in main.py)
    # If it fails, it means the table exists and needs a migration.
    # To fix this without migrations for now, we'll try to add the column if it's missing.
    db = SessionLocal()
    try:
        db.execute(
            text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS total_price_usd FLOAT")
        )
        db.execute(
            text(
                "ALTER TABLE experience_bookings ADD COLUMN IF NOT EXISTS total_price_usd FLOAT"
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    db.close()


def test_get_treasury():
    response = client.get("/api/v1/dao/treasury")
    assert response.status_code == 200
    data = response.json()
    assert "balance_usd" in data
    assert data["token_symbol"] == "NEST"


def test_get_proposals():
    response = client.get("/api/v1/dao/proposals?status=active")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_tally():
    response = client.post("/api/v1/dao/proposals/tally")
    assert response.status_code == 200
    assert "tallied" in response.json()
