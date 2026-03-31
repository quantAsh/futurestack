"""
SLO Monitoring Service - Define and track Service Level Objectives.
Provides metrics collection for response times, error rates, and availability.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import threading


class SLOType(str, Enum):
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    THROUGHPUT = "throughput"


@dataclass
class SLODefinition:
    """Definition of a Service Level Objective."""
    name: str
    slo_type: SLOType
    target: float  # Target value (e.g., 99.9 for 99.9% availability)
    threshold: float  # Threshold for alerts (e.g., 99.5)
    window_minutes: int = 60  # Measurement window
    description: str = ""


@dataclass
class SLOMetric:
    """Individual metric data point."""
    timestamp: datetime
    value: float
    success: bool
    endpoint: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# Default SLO definitions for NomadNest
DEFAULT_SLOS = [
    SLODefinition(
        name="api_availability",
        slo_type=SLOType.AVAILABILITY,
        target=99.9,
        threshold=99.5,
        window_minutes=60,
        description="API endpoint availability",
    ),
    SLODefinition(
        name="api_latency_p95",
        slo_type=SLOType.LATENCY,
        target=500,  # 500ms
        threshold=1000,  # 1s
        window_minutes=15,
        description="95th percentile API latency (ms)",
    ),
    SLODefinition(
        name="ai_error_rate",
        slo_type=SLOType.ERROR_RATE,
        target=1.0,  # <1% error rate
        threshold=5.0,  # <5% warning
        window_minutes=60,
        description="AI concierge error rate (%)",
    ),
    SLODefinition(
        name="booking_success_rate",
        slo_type=SLOType.AVAILABILITY,
        target=99.0,
        threshold=95.0,
        window_minutes=1440,  # 24 hours
        description="Booking completion success rate",
    ),
]


class SLOMonitor:
    """Monitor and track SLO metrics."""
    
    def __init__(self, slo_definitions: List[SLODefinition] = None):
        self.slos = {slo.name: slo for slo in (slo_definitions or DEFAULT_SLOS)}
        self.metrics: Dict[str, List[SLOMetric]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def record_request(
        self,
        endpoint: str,
        latency_ms: float,
        success: bool,
        extra: Dict[str, Any] = None,
    ):
        """Record an API request for SLO tracking."""
        metric = SLOMetric(
            timestamp=datetime.utcnow(),
            value=latency_ms,
            success=success,
            endpoint=endpoint,
            extra=extra or {},
        )
        
        with self._lock:
            self.metrics["api_availability"].append(metric)
            self.metrics["api_latency_p95"].append(metric)
    
    def record_ai_request(self, success: bool, latency_ms: float = 0):
        """Record an AI request for error rate tracking."""
        metric = SLOMetric(
            timestamp=datetime.utcnow(),
            value=latency_ms,
            success=success,
            endpoint="ai_concierge",
        )
        
        with self._lock:
            self.metrics["ai_error_rate"].append(metric)
    
    def record_booking(self, success: bool):
        """Record a booking attempt."""
        metric = SLOMetric(
            timestamp=datetime.utcnow(),
            value=1 if success else 0,
            success=success,
            endpoint="booking",
        )
        
        with self._lock:
            self.metrics["booking_success_rate"].append(metric)
    
    def _get_window_metrics(
        self, slo_name: str, window_minutes: int
    ) -> List[SLOMetric]:
        """Get metrics within the time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        
        with self._lock:
            return [
                m for m in self.metrics.get(slo_name, [])
                if m.timestamp >= cutoff
            ]
    
    def calculate_slo(self, slo_name: str) -> Dict[str, Any]:
        """Calculate current SLO status."""
        if slo_name not in self.slos:
            return {"error": f"Unknown SLO: {slo_name}"}
        
        slo = self.slos[slo_name]
        metrics = self._get_window_metrics(slo_name, slo.window_minutes)
        
        if not metrics:
            return {
                "name": slo_name,
                "status": "unknown",
                "message": "No data in window",
            }
        
        if slo.slo_type == SLOType.AVAILABILITY:
            success_count = sum(1 for m in metrics if m.success)
            current = (success_count / len(metrics)) * 100
        
        elif slo.slo_type == SLOType.ERROR_RATE:
            error_count = sum(1 for m in metrics if not m.success)
            current = (error_count / len(metrics)) * 100
        
        elif slo.slo_type == SLOType.LATENCY:
            values = sorted([m.value for m in metrics])
            p95_index = int(len(values) * 0.95)
            current = values[p95_index] if values else 0
        
        else:
            current = sum(m.value for m in metrics) / len(metrics)
        
        # Determine status
        if slo.slo_type in (SLOType.AVAILABILITY,):
            # Higher is better
            if current >= slo.target:
                status = "healthy"
            elif current >= slo.threshold:
                status = "warning"
            else:
                status = "critical"
        else:
            # Lower is better (error rate, latency)
            if current <= slo.target:
                status = "healthy"
            elif current <= slo.threshold:
                status = "warning"
            else:
                status = "critical"
        
        return {
            "name": slo_name,
            "type": slo.slo_type.value,
            "description": slo.description,
            "current": round(current, 2),
            "target": slo.target,
            "threshold": slo.threshold,
            "status": status,
            "window_minutes": slo.window_minutes,
            "sample_count": len(metrics),
        }
    
    def get_all_slos(self) -> List[Dict[str, Any]]:
        """Get status of all SLOs."""
        return [self.calculate_slo(name) for name in self.slos]
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Remove metrics older than max_age_hours."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        with self._lock:
            for slo_name in self.metrics:
                self.metrics[slo_name] = [
                    m for m in self.metrics[slo_name]
                    if m.timestamp >= cutoff
                ]


# Singleton instance
slo_monitor = SLOMonitor()


# FastAPI middleware helper
class SLOMiddleware:
    """ASGI middleware for automatic SLO tracking."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = (time.time() - start_time) * 1000
            endpoint = scope.get("path", "/")
            success = 200 <= status_code < 500
            
            slo_monitor.record_request(
                endpoint=endpoint,
                latency_ms=latency_ms,
                success=success,
            )
