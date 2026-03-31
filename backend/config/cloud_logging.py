"""
GCP Cloud Logging Integration.
Configures structured JSON logging for Cloud Logging in production.
"""
import os
import sys
import logging
import structlog
from typing import Optional


def setup_cloud_logging(
    log_level: str = "INFO",
    project_id: Optional[str] = None,
    service_name: str = "nomadnest-backend",
):
    """
    Configure logging for GCP Cloud Logging.
    
    In GCP, logs are automatically picked up from stdout/stderr
    when formatted as JSON with specific fields.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    is_production = environment == "production"
    
    # Cloud Logging JSON format for production
    if is_production:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # GCP Cloud Logging JSON format
            _gcp_json_renderer,
        ]
    else:
        # Human-readable for local development
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Try to use Google Cloud Logging client if available
    if is_production:
        try:
            import google.cloud.logging
            client = google.cloud.logging.Client(project=project_id)
            client.setup_logging()
            structlog.get_logger().info(
                "cloud_logging_initialized",
                project_id=project_id or "auto-detected"
            )
        except ImportError:
            structlog.get_logger().warning(
                "google_cloud_logging_not_installed",
                message="Using stdout JSON logging for Cloud Run"
            )


def _gcp_json_renderer(logger, method_name, event_dict):
    """
    Render log events in GCP Cloud Logging JSON format.
    
    See: https://cloud.google.com/logging/docs/structured-logging
    """
    import json
    
    # Map log levels to GCP severity
    severity_map = {
        "debug": "DEBUG",
        "info": "INFO",
        "warning": "WARNING",
        "error": "ERROR",
        "critical": "CRITICAL",
    }
    
    # Build GCP-formatted log entry
    log_entry = {
        "severity": severity_map.get(event_dict.pop("level", "info"), "INFO"),
        "message": event_dict.pop("event", ""),
        "timestamp": event_dict.pop("timestamp", None),
        "logging.googleapis.com/labels": {
            "logger": event_dict.pop("logger", ""),
            "service": os.getenv("K_SERVICE", "nomadnest-backend"),
            "revision": os.getenv("K_REVISION", "unknown"),
        },
    }
    
    # Add remaining fields as jsonPayload
    if event_dict:
        log_entry["jsonPayload"] = event_dict
    
    return json.dumps(log_entry)


# Performance tracing for Cloud Trace
def get_trace_context() -> Optional[str]:
    """
    Extract trace context from environment or request headers.
    For Cloud Run, the X-Cloud-Trace-Context header is automatically set.
    """
    import os
    return os.getenv("X_CLOUD_TRACE_CONTEXT")


def log_with_trace(logger, level: str, event: str, **kwargs):
    """Log with Cloud Trace context if available."""
    trace = get_trace_context()
    if trace:
        kwargs["logging.googleapis.com/trace"] = trace
    getattr(logger, level)(event, **kwargs)
