"""
SLO (Service Level Objectives) Monitoring Service.

Tracks error rates, latency percentiles, and error budgets.
"""
import time
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import threading


@dataclass
class SLOConfig:
    """SLO target configuration."""
    name: str
    target: float  # e.g., 0.999 for 99.9%
    window_seconds: int = 86400  # 24 hours
    description: str = ""


@dataclass
class RequestMetric:
    """Single request metric data point."""
    timestamp: float
    latency_ms: float
    is_error: bool
    endpoint: str = ""


class SLOTracker:
    """
    Tracks SLO metrics in a rolling window.
    
    Thread-safe implementation using deque with maxlen.
    """

    def __init__(self, window_seconds: int = 86400, max_samples: int = 100000):
        self.window_seconds = window_seconds
        self._metrics: deque[RequestMetric] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def record(self, latency_ms: float, is_error: bool, endpoint: str = ""):
        """Record a request metric."""
        metric = RequestMetric(
            timestamp=time.time(),
            latency_ms=latency_ms,
            is_error=is_error,
            endpoint=endpoint,
        )
        with self._lock:
            self._metrics.append(metric)

    def _get_window_metrics(self) -> List[RequestMetric]:
        """Get metrics within the rolling window."""
        cutoff = time.time() - self.window_seconds
        with self._lock:
            return [m for m in self._metrics if m.timestamp >= cutoff]

    def get_error_rate(self) -> float:
        """Calculate current error rate."""
        metrics = self._get_window_metrics()
        if not metrics:
            return 0.0
        errors = sum(1 for m in metrics if m.is_error)
        return errors / len(metrics)

    def get_availability(self) -> float:
        """Calculate availability (1 - error_rate)."""
        return 1.0 - self.get_error_rate()

    def get_latency_percentile(self, percentile: float) -> float:
        """Calculate latency at given percentile (e.g., 0.99 for P99)."""
        metrics = self._get_window_metrics()
        if not metrics:
            return 0.0
        latencies = sorted(m.latency_ms for m in metrics)
        index = int(len(latencies) * percentile)
        index = min(index, len(latencies) - 1)
        return latencies[index]

    def get_request_count(self) -> int:
        """Get total request count in window."""
        return len(self._get_window_metrics())

    def get_error_count(self) -> int:
        """Get error count in window."""
        metrics = self._get_window_metrics()
        return sum(1 for m in metrics if m.is_error)


@dataclass
class SLOStatus:
    """Current SLO status and metrics."""
    name: str
    target: float
    current: float
    is_breached: bool
    error_budget_remaining: float
    window_seconds: int
    request_count: int
    error_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


class SLOService:
    """
    Service for defining and monitoring SLOs.
    
    Tracks:
    - Availability (% of successful requests)
    - Latency percentiles (P50, P95, P99)
    - Error budget consumption
    """

    def __init__(self):
        self._trackers: Dict[str, SLOTracker] = {}
        self._configs: Dict[str, SLOConfig] = {}
        self._global_tracker = SLOTracker()
        self._setup_default_slos()

    def _setup_default_slos(self):
        """Configure default SLOs."""
        self.define_slo(SLOConfig(
            name="availability",
            target=0.999,  # 99.9%
            window_seconds=86400,  # 24 hours
            description="API availability - percentage of non-error responses",
        ))
        self.define_slo(SLOConfig(
            name="latency_p99",
            target=1000,  # 1000ms
            window_seconds=3600,  # 1 hour
            description="P99 latency should be under 1000ms",
        ))
        self.define_slo(SLOConfig(
            name="latency_p95",
            target=500,  # 500ms
            window_seconds=3600,
            description="P95 latency should be under 500ms",
        ))

    def define_slo(self, config: SLOConfig):
        """Define or update an SLO."""
        self._configs[config.name] = config
        if config.name not in self._trackers:
            self._trackers[config.name] = SLOTracker(window_seconds=config.window_seconds)

    def record_request(self, latency_ms: float, is_error: bool, endpoint: str = ""):
        """Record a request for SLO tracking."""
        self._global_tracker.record(latency_ms, is_error, endpoint)

    def get_slo_status(self, slo_name: str) -> Optional[SLOStatus]:
        """Get current status for an SLO."""
        config = self._configs.get(slo_name)
        if not config:
            return None

        tracker = self._global_tracker  # Use global tracker for all SLOs

        availability = tracker.get_availability()
        error_rate = tracker.get_error_rate()
        p50 = tracker.get_latency_percentile(0.50)
        p95 = tracker.get_latency_percentile(0.95)
        p99 = tracker.get_latency_percentile(0.99)

        # Determine current value and breach status based on SLO type
        if slo_name == "availability":
            current = availability
            is_breached = current < config.target
            budget_remaining = max(0, (current - config.target) / (1 - config.target)) if config.target < 1 else 1.0
        elif slo_name == "latency_p99":
            current = p99
            is_breached = current > config.target
            budget_remaining = max(0, 1 - (current / config.target)) if current <= config.target else 0
        elif slo_name == "latency_p95":
            current = p95
            is_breached = current > config.target
            budget_remaining = max(0, 1 - (current / config.target)) if current <= config.target else 0
        else:
            current = 0
            is_breached = False
            budget_remaining = 1.0

        return SLOStatus(
            name=slo_name,
            target=config.target,
            current=current,
            is_breached=is_breached,
            error_budget_remaining=budget_remaining,
            window_seconds=config.window_seconds,
            request_count=tracker.get_request_count(),
            error_count=tracker.get_error_count(),
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
        )

    def get_all_slo_statuses(self) -> List[SLOStatus]:
        """Get status for all defined SLOs."""
        return [self.get_slo_status(name) for name in self._configs.keys()]

    def get_error_budget_summary(self) -> Dict:
        """Get summary of error budget consumption."""
        statuses = self.get_all_slo_statuses()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "slos": [
                {
                    "name": s.name,
                    "target": s.target,
                    "current": round(s.current, 4) if s.current < 10 else round(s.current, 1),
                    "is_breached": s.is_breached,
                    "error_budget_remaining_pct": round(s.error_budget_remaining * 100, 2),
                }
                for s in statuses if s
            ],
            "overall_health": "healthy" if not any(s.is_breached for s in statuses if s) else "degraded",
            "request_count": statuses[0].request_count if statuses and statuses[0] else 0,
        }


# Singleton instance
_slo_service: Optional[SLOService] = None


def get_slo_service() -> SLOService:
    """Get the singleton SLO service instance."""
    global _slo_service
    if _slo_service is None:
        _slo_service = SLOService()
    return _slo_service
