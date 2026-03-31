"""
Log Aggregation Service - Optional handlers for external aggregators.
Supports Datadog, CloudWatch, Loki, and generic JSON output.

Note: structlog is configured once in config/observability.py.
This module provides optional log handlers and context utilities.
"""
import os
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Dict, Any
import structlog

# Aggregator configuration
LOG_AGGREGATOR = os.getenv("LOG_AGGREGATOR", "stdout")  # datadog, cloudwatch, loki, stdout
SERVICE_NAME = os.getenv("SERVICE_NAME", "nomadnest-api")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logger = structlog.get_logger("nomadnest.logging")


class JSONFormatter(logging.Formatter):
    """JSON log formatter for external aggregators."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
            "environment": ENVIRONMENT,
            "logger": record.name,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        
        # Add standard fields for aggregators
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        return json.dumps(log_entry)


class DatadogHandler(logging.Handler):
    """Handler for sending logs to Datadog."""
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("DATADOG_API_KEY")
        self.site = os.getenv("DATADOG_SITE", "datadoghq.com")
        self.formatter = JSONFormatter()
    
    def emit(self, record: logging.LogRecord):
        if not self.api_key:
            return
        
        try:
            import httpx
            
            log_entry = json.loads(self.formatter.format(record))
            log_entry["ddsource"] = "python"
            log_entry["ddtags"] = f"service:{SERVICE_NAME},env:{ENVIRONMENT}"
            
            httpx.post(
                f"https://http-intake.logs.{self.site}/api/v2/logs",
                headers={
                    "DD-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                },
                json=[log_entry],
                timeout=5.0,
            )
        except Exception:
            pass  # Don't break on logging failures


class CloudWatchHandler(logging.Handler):
    """Handler for sending logs to AWS CloudWatch."""
    
    def __init__(self):
        super().__init__()
        self.log_group = os.getenv("CLOUDWATCH_LOG_GROUP", f"/nomadnest/{ENVIRONMENT}")
        self.log_stream = os.getenv("CLOUDWATCH_LOG_STREAM", SERVICE_NAME)
        self.formatter = JSONFormatter()
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("logs")
            except ImportError:
                pass
        return self._client
    
    def emit(self, record: logging.LogRecord):
        if not self.client:
            return
        
        try:
            self.client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=self.log_stream,
                logEvents=[
                    {
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                        "message": self.formatter.format(record),
                    }
                ],
            )
        except Exception:
            pass


def add_aggregator_handler():
    """Optionally add an external aggregator handler to the root logger."""
    if LOG_AGGREGATOR == "datadog":
        handler = DatadogHandler()
    elif LOG_AGGREGATOR == "cloudwatch":
        handler = CloudWatchHandler()
    else:
        return  # stdout is already handled by observability.py
    
    logging.getLogger().addHandler(handler)
    logger.info("aggregator_handler_added", aggregator=LOG_AGGREGATOR)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name or SERVICE_NAME)


# Request context for correlation — thread-safe via contextvars
_log_context: ContextVar[Dict[str, Any]] = ContextVar("_log_context", default={})


class LogContext:
    """Request-scoped context for log correlation. Uses contextvars for thread safety."""
    
    @classmethod
    def set(cls, key: str, value: Any):
        ctx = _log_context.get().copy()
        ctx[key] = value
        _log_context.set(ctx)
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return _log_context.get().get(key, default)
    
    @classmethod
    def clear(cls):
        _log_context.set({})
    
    @classmethod
    def bind_to_logger(cls, bound_logger: structlog.BoundLogger) -> structlog.BoundLogger:
        return bound_logger.bind(**_log_context.get())
