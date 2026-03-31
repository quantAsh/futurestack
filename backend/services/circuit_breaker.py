"""
Circuit Breaker Pattern - Auto-disable failing external services.
Implements exponential backoff and automatic recovery for OTA providers.
"""
import time
import threading
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, all calls blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes to close from half-open
    timeout_seconds: int = 60           # Time before half-open from open
    half_open_max_calls: int = 3        # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    Usage:
        breaker = CircuitBreaker("booking_api")
        
        try:
            result = breaker.call(lambda: external_api.fetch())
        except CircuitOpenError:
            # Use fallback
            result = fallback_data
    """
    
    def __init__(self, name: str, config: CircuitConfig = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self.opened_at: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = threading.Lock()
    
    def call(self, func: Callable[[], Any], fallback: Callable[[], Any] = None) -> Any:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: The function to execute
            fallback: Optional fallback if circuit is open
        
        Returns:
            Result of func or fallback
        
        Raises:
            CircuitOpenError: If circuit is open and no fallback
        """
        with self._lock:
            if not self._can_execute():
                if fallback:
                    logger.warning(f"Circuit {self.name} OPEN, using fallback")
                    return fallback()
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
        
        try:
            result = func()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise
    
    def _can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.opened_at and datetime.utcnow() - self.opened_at > timedelta(
                seconds=self.config.timeout_seconds
            ):
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls
        
        return False
    
    def _record_success(self):
        """Record a successful call."""
        with self._lock:
            self.stats.successes += 1
            self.stats.last_success_time = datetime.utcnow()
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
    
    def _record_failure(self, error: Exception):
        """Record a failed call."""
        with self._lock:
            self.stats.failures += 1
            self.stats.last_failure_time = datetime.utcnow()
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            
            logger.warning(
                f"Circuit {self.name} failure #{self.stats.consecutive_failures}",
                error=str(error),
            )
            
            if self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        
        logger.info(
            f"Circuit {self.name}: {old_state.value} -> {new_state.value}",
            failures=self.stats.consecutive_failures,
        )
        
        if new_state == CircuitState.OPEN:
            self.opened_at = datetime.utcnow()
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes = 0
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self.opened_at = None
            self.half_open_calls = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "consecutive_failures": self.stats.consecutive_failures,
            "last_failure": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            "last_success": self.stats.last_success_time.isoformat() if self.stats.last_success_time else None,
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open and call is blocked."""
    pass


# ============================================
# CIRCUIT BREAKER REGISTRY
# ============================================

class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get(self, name: str, config: CircuitConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]
    
    def get_all_status(self) -> list:
        """Get status of all circuit breakers."""
        return [cb.get_status() for cb in self._breakers.values()]
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self._breakers.values():
            cb.reset()


# Singleton registry
circuit_registry = CircuitBreakerRegistry()


# ============================================
# OTA PROVIDER CIRCUIT BREAKERS
# ============================================

# Pre-configured circuit breakers for OTA providers
OTA_CIRCUIT_CONFIG = CircuitConfig(
    failure_threshold=3,
    success_threshold=2,
    timeout_seconds=120,  # 2 minutes before retry
    half_open_max_calls=2,
)


def get_ota_circuit(provider: str) -> CircuitBreaker:
    """Get circuit breaker for an OTA provider."""
    return circuit_registry.get(f"ota_{provider}", OTA_CIRCUIT_CONFIG)


def ota_call_with_circuit(provider: str, func: Callable, fallback=None):
    """Execute an OTA call with circuit breaker protection."""
    circuit = get_ota_circuit(provider)
    return circuit.call(func, fallback)
