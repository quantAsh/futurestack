import time
import structlog
import json
from typing import Dict, Any, Optional
from backend.config import settings
from backend.database import SessionLocal
from backend.models import AIMetric

logger = structlog.get_logger("nomadnest.monitoring")


class AIMonitor:
    """Service for tracking AI metrics and costs."""

    @staticmethod
    def log_completion(
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: float,
        session_id: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log a successful LLM completion with metrics."""
        # Simple cost calculation heuristics (dollars per 1k tokens)
        costs = {
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
            "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
            "gemini/gemini-1.5-flash": {
                "prompt": 0.000075,
                "completion": 0.0003,
            },  # Adjusted 2024 pricing
            "gemini/gemini-1.5-pro": {"prompt": 0.0035, "completion": 0.0105},
        }

        cost_config = costs.get(model, {"prompt": 0, "completion": 0})
        total_cost = (prompt_tokens / 1000) * cost_config["prompt"] + (
            completion_tokens / 1000
        ) * cost_config["completion"]

        # Log to File/Console
        metric_data = {
            "metric_type": "ai_completion",
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "duration_ms": round(duration_ms, 2),
            "estimated_cost_usd": round(total_cost, 6),
            "session_id": session_id,
            "user_id": user_id,
        }
        if metadata:
            metric_data.update(metadata)
        logger.info("ai_completion", **metric_data)

        # Persist to Database
        db = SessionLocal()
        try:
            metric = AIMetric(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                duration_ms=duration_ms,
                estimated_cost_usd=total_cost,
                session_id=session_id,
                user_id=user_id,
                metric_type="completion",
            )
            db.add(metric)
            db.commit()
        except Exception as e:
            logger.error("ai_metric_persist_failed", error=str(e))
        finally:
            db.close()

    @staticmethod
    def log_error(model: str, error_msg: str, session_id: str, user_id: str):
        """Log an AI service error."""
        error_data = {
            "metric_type": "ai_error",
            "model": model,
            "error": error_msg,
            "session_id": session_id,
            "user_id": user_id,
        }
        logger.error("ai_error", **error_data)

        # Persist to Database
        db = SessionLocal()
        try:
            metric = AIMetric(
                model=model,
                session_id=session_id,
                user_id=user_id,
                metric_type="error",
                error_message=error_msg,
                estimated_cost_usd=0,
            )
            db.add(metric)
            db.commit()
        except Exception as e:
            logger.error("ai_error_metric_persist_failed", error=str(e))
        finally:
            db.close()


monitoring_service = AIMonitor()
