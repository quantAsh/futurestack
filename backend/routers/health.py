import time
import structlog
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend import schemas

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

router = APIRouter()
logger = structlog.get_logger("nomadnest.health")


def _check_database(db: Session) -> Dict[str, Any]:
    start_time = time.time()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "ok",
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as exc:
        logger.error("db_health_check_failed", error=str(exc))
        return {
            "status": "error",
            "error": str(exc),
        }


def _check_redis() -> Dict[str, Any]:
    if not settings.REDIS_URL or redis is None:
        return {
            "status": "skipped",
            "details": "Redis not configured.",
        }

    start_time = time.time()
    try:
        client = redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        client.ping()
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": "ok",
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as exc:
        logger.error("redis_health_check_failed", error=str(exc))
        return {
            "status": "error",
            "error": str(exc),
        }


def _check_ai_config() -> Dict[str, Any]:
    providers = {
        "openai": bool(settings.OPENAI_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
    }
    configured = any(providers.values())
    return {
        "status": "ok" if configured else "degraded",
        "providers": providers,
    }


@router.get("/health", response_model=schemas.HealthCheck)
def health_check(db: Session = Depends(get_db)):
    """
    Health check for the API service.
    Now includes a lightweight DB connectivity check to ensure the service is truly usable.
    """
    try:
        # Fast query to ensure connection is valid
        db.execute(text("SELECT 1"))
        return {"status": "ok", "version": settings.VERSION}
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        # Return 503 Service Unavailable if critical dependency is missing
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service Unavailable: Database Unreachable")


@router.get("/health/ready", response_model=schemas.ReadinessCheck)
def readiness_check(db: Session = Depends(get_db)):
    """Deep readiness check across critical dependencies."""
    checks = {
        "database": _check_database(db),
        "redis": _check_redis(),
        "ai": _check_ai_config(),
    }

    status = "ok"
    if checks["database"]["status"] != "ok":
        status = "error"
    elif any(
        check["status"] == "error"
        for check in (checks["redis"], checks["ai"])
        if check["status"] != "skipped"
    ):
        status = "degraded"

    return {"status": status, "version": settings.VERSION, "checks": checks}


@router.get("/health/db", response_model=schemas.DependencyCheck)
def health_check_db(db: Session = Depends(get_db)):
    """Database-only health check with latency."""
    return _check_database(db)


@router.get("/health/slos")
def get_slo_status():
    """Get current SLO status for all defined objectives."""
    try:
        from backend.services.slo_monitoring import slo_monitor
        return {
            "slos": slo_monitor.get_all_slos(),
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error("slo_check_failed", error=str(e))
        return {"error": str(e), "slos": []}


@router.get("/health/slos/{slo_name}")
def get_slo_detail(slo_name: str):
    """Get detailed status for a specific SLO."""
    try:
        from backend.services.slo_monitoring import slo_monitor
        return slo_monitor.calculate_slo(slo_name)
    except Exception as e:
        logger.error("slo_detail_check_failed", error=str(e))
        return {"error": str(e)}


@router.get("/health/secrets")
def check_secrets_config():
    """Check which required secrets are configured (admin use)."""
    try:
        from backend.services.secrets_manager import secrets
        return secrets.get_required_secrets()
    except Exception as e:
        logger.error("secrets_check_failed", error=str(e))
        return {"error": str(e)}

