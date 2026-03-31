"""
Test configuration and fixtures for NomadNest backend tests.
Uses SQLite in-memory database for fast, isolated tests.
"""
import os
import pytest
from typing import Generator
from uuid import uuid4

# Set test environment before imports
os.environ["USE_SQLITE"] = "true"
os.environ["TESTING"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend import models


# Create test database engine (in-memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override dependency to use test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the database dependency
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables before tests run."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Generator:
    """Get a database session for a test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db) -> TestClient:
    """Get a test client for the FastAPI app with DB overrides for all routers."""
    from backend.database import get_db as database_get_db

    # Import all router-level get_db functions that need overriding
    from backend.routers import auth, bookings, listings, users
    from backend.routers import hubs, admin, availability, experiences
    from backend.routers import reviews, negotiations

    def override_get_db():
        yield db

    # Override database-level get_db
    app.dependency_overrides[database_get_db] = override_get_db

    # Override all router-level get_db wrappers
    for module in [auth, bookings, listings, users, hubs, admin, availability, experiences]:
        if hasattr(module, "get_db"):
            app.dependency_overrides[module.get_db] = override_get_db

    # Override get_db_dep wrappers in reviews and negotiations
    for module in [reviews, negotiations]:
        if hasattr(module, "get_db_dep"):
            app.dependency_overrides[module.get_db_dep] = override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db) -> models.User:
    """Create a test user."""
    user = models.User(
        id=str(uuid4()),
        email=f"test-{uuid4().hex[:8]}@example.com",
        name="Test User",
        hashed_password="hashed_test_password",
        is_host=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db) -> models.User:
    """Create a test admin user."""
    admin = models.User(
        id=str(uuid4()),
        email=f"admin-{uuid4().hex[:8]}@example.com",
        name="Admin User",
        hashed_password="hashed_admin_password",
        is_host=True,
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def test_host(db) -> models.User:
    """Create a test host user."""
    host = models.User(
        id=str(uuid4()),
        email=f"host-{uuid4().hex[:8]}@example.com",
        name="Host User",
        hashed_password="hashed_host_password",
        is_host=True,
    )
    db.add(host)
    db.commit()
    db.refresh(host)
    return host


@pytest.fixture
def test_hub(db, test_host) -> models.Hub:
    """Create a test hub."""
    hub = models.Hub(
        id=str(uuid4()),
        name="Test Hub",
        mission="A test co-living hub",
        type="Coliving",
        logo="https://example.com/logo.png",
        charter="Test charter",
        lat=0.0,
        lng=0.0,
    )
    db.add(hub)
    db.commit()
    db.refresh(hub)
    return hub


@pytest.fixture
def test_listing(db, test_hub, test_host) -> models.Listing:
    """Create a test listing."""
    listing = models.Listing(
        id=str(uuid4()),
        name="Test Listing",
        description="A cozy test space",
        property_type="Apartment",
        city="Test City",
        country="Test Country",
        price_usd=100.0,
        features=["wifi", "kitchen"],
        images=["https://example.com/img.jpg"],
        hub_id=test_hub.id,
        owner_id=test_host.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@pytest.fixture
def test_event(db) -> models.Event:
    """Create a test event."""
    from datetime import datetime, timedelta
    
    event = models.Event(
        id=str(uuid4()),
        name="Test Festival",
        description="Annual test festival",
        event_type="festival",
        location="Test City",
        start_date=datetime.utcnow() + timedelta(days=30),
        end_date=datetime.utcnow() + timedelta(days=32),
        price_impact_percent=15.0,
        tags=["festival", "music"],
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@pytest.fixture
def test_service(db, test_hub) -> models.Service:
    """Create a test service."""
    service = models.Service(
        id=str(uuid4()),
        hub_id=test_hub.id,
        name="Test Consulting",
        description="Expert test consulting",
        category="consulting",
        price=50.0,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Generate auth headers with a real JWT for a test user."""
    from backend.utils import create_access_token
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin) -> dict:
    """Generate auth headers with a real JWT for an admin user."""
    from backend.utils import create_access_token
    token = create_access_token(subject=test_admin.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def host_auth_headers(test_host) -> dict:
    """Generate auth headers with a real JWT for a host user."""
    from backend.utils import create_access_token
    token = create_access_token(subject=test_host.id)
    return {"Authorization": f"Bearer {token}"}


# Aliases for clearer test naming
@pytest.fixture
def sample_user(test_user):
    """Alias for test_user fixture."""
    return test_user


@pytest.fixture
def sample_listing(test_listing):
    """Alias for test_listing fixture."""
    return test_listing


@pytest.fixture
def db_session(db):
    """Alias for db fixture."""
    return db

