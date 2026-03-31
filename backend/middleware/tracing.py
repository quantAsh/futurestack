import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from backend.utils.context import set_request_id

# Setup basic tracing to console
provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add OpenTelemetry tracing and Request ID correlation.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or generate Request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}", kind=trace.SpanKind.SERVER
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.request_id", request_id)

            start_time = time.time()
            try:
                response = await call_next(request)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise e
            finally:
                duration = time.time() - start_time
                span.set_attribute("http.duration_seconds", duration)

            span.set_attribute("http.status_code", response.status_code)
            
            # Propagate Request ID back in response
            response.headers["X-Request-ID"] = request_id
            return response
