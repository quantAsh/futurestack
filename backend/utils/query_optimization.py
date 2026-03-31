"""
Query Optimization Utilities - Avoid N+1 queries and slow database calls.
"""
from sqlalchemy.orm import joinedload, selectinload
from backend import models


# ============================================================================
# EAGER LOADING PRESETS
# ============================================================================

def listing_with_relations():
    """
    Eager load common listing relationships.
    
    Usage:
        query = db.query(models.Listing).options(*listing_with_relations())
    """
    return [
        selectinload(models.Listing.reviews),
        joinedload(models.Listing.owner),
        joinedload(models.Listing.hub),
    ]


def booking_with_relations():
    """
    Eager load common booking relationships.
    
    Usage:
        query = db.query(models.Booking).options(*booking_with_relations())
    """
    return [
        joinedload(models.Booking.listing),
        joinedload(models.Booking.user),
    ]


def user_with_subscription():
    """
    Eager load user with subscription data.
    """
    return [
        joinedload(models.User.subscription),
    ]


def experience_with_host():
    """
    Eager load experience with host/organizer data.
    """
    return [
        joinedload(models.Experience.organizer),
    ]


# ============================================================================
# QUERY LOGGING (Development Only)
# ============================================================================

import logging
import time
from contextlib import contextmanager
from backend.config import settings

query_logger = logging.getLogger("sqlalchemy.engine")


@contextmanager
def log_slow_queries(threshold_ms: float = 100.0):
    """
    Context manager to log queries slower than threshold.
    
    Usage:
        with log_slow_queries(threshold_ms=50):
            results = db.query(models.Listing).all()
    
    Only active in development environment.
    """
    if settings.ENVIRONMENT != "development":
        yield
        return
    
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    if elapsed_ms > threshold_ms:
        query_logger.warning(f"⚠️ Slow query detected: {elapsed_ms:.2f}ms (threshold: {threshold_ms}ms)")


def enable_query_logging():
    """
    Enable SQLAlchemy query logging for development debugging.
    
    Call this in your test setup or debug script:
        from backend.utils.query_optimization import enable_query_logging
        enable_query_logging()
    """
    import structlog
    _logger = structlog.get_logger("nomadnest.query_optimization")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    _logger.info("sqlalchemy_query_logging_enabled")


def disable_query_logging():
    """Disable SQLAlchemy query logging."""
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
