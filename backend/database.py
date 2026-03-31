from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool
from backend.config import settings
import os
import structlog

_db_logger = structlog.get_logger("nomadnest.database")

# Determine database URL with SQLite fallback for local development
def get_database_url():
    """Get database URL, falling back to SQLite if PostgreSQL unavailable."""
    db_url = settings.DATABASE_URL
    
    # Check if we should use SQLite fallback
    use_sqlite = os.getenv("USE_SQLITE", "").lower() in ("true", "1", "yes")
    
    if use_sqlite or "sqlite" in db_url:
        sqlite_path = os.path.join(os.path.dirname(__file__), "..", "nomadnest_dev.db")
        return f"sqlite:///{os.path.abspath(sqlite_path)}"
    
    # Try PostgreSQL, fallback to SQLite on connection failure
    if "postgresql" in db_url:
        try:
            from sqlalchemy import text
            test_engine = create_engine(db_url, pool_pre_ping=True)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return db_url
        except Exception as e:
            _db_logger.warning("postgresql_unavailable", error=str(e))
            _db_logger.info("falling_back_to_sqlite")
            sqlite_path = os.path.join(os.path.dirname(__file__), "..", "nomadnest_dev.db")
            return f"sqlite:///{os.path.abspath(sqlite_path)}"
    
    return db_url


DATABASE_URL = get_database_url()
IS_SQLITE = "sqlite" in DATABASE_URL

# Configure engine based on database type
if IS_SQLITE:
    # SQLite needs different settings
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _db_logger.info("database_engine_ready", backend="sqlite")
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    _db_logger.info("database_engine_ready", backend="postgresql")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from contextlib import contextmanager

@contextmanager
def get_db_context():
    """
    Context manager for DB sessions outside of FastAPI request lifecycle.
    Use in services, background tasks, and scripts — guarantees db.close().

    Usage:
        with get_db_context() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables (creates them if they don't exist)."""
    Base.metadata.create_all(bind=engine)
    _db_logger.info("database_tables_initialized")



