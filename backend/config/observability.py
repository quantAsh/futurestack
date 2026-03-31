"""
Observability configuration: Structured Logging and OpenTelemetry Tracing.

This is the SINGLE SOURCE OF TRUTH for structlog configuration.
Called once from main.py at startup. No other module should call structlog.configure().
"""
import os
import sys
import logging
import structlog


def setup_logging():
    """
    Configure structlog as the unified logging system.
    
    - Dev (ENVIRONMENT != production): colored console output
    - Prod: JSON output for log aggregators (Datadog, CloudWatch, etc.)
    
    Also bridges stdlib logging so third-party libraries
    (uvicorn, sqlalchemy, etc.) emit through the same pipeline.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    is_production = environment == "production"

    # Shared processors for both structlog and stdlib bridge
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if is_production:
        # JSON for log aggregators
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colored console for local dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging through structlog's formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Replace all existing handlers on root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def setup_tracing(service_name: str = "nomadnest-backend"):
    """Configure OpenTelemetry tracing."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    except Exception as e:
        logger = structlog.get_logger("nomadnest.tracing")
        logger.warning("otlp_exporter_unavailable", error=str(e))

    trace.set_tracer_provider(provider)
    return provider
