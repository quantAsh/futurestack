"""
Circuit Breaker - Resilience pattern for external service calls.
Prevents cascading failures by failing fast when services are down.
"""
import time
import asyncio
from typing import Callable, Optional
from enum import Enum
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger("nomadnest.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    Usage:
        breaker = CircuitBreaker("booking_api")
        result = await breaker.call(some_async_function, arg1, arg2)
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: int = 30  # seconds
    half_open_max_calls: int = 3
    
    # State tracking
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    last_failure_time: float = field(default=0)
    half_open_calls: int = field(default=0)
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        
        # Check if circuit should be tested
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
            else:
                raise CircuitOpenError(f"Circuit {self.name} is open")
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitOpenError(f"Circuit {self.name} testing limit reached")
            self.half_open_calls += 1
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset circuit
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("circuit_recovered", name=self.name)
        self._reset()
    
    def _on_failure(self, error: Exception):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.warning(
            "circuit_failure",
            name=self.name,
            count=self.failure_count,
            error=str(error)[:100]
        )
        
        if self.failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, state: CircuitState):
        """Transition circuit to new state."""
        if self.state != state:
            logger.info("circuit_state_change", name=self.name, from_state=self.state.value, to_state=state.value)
            self.state = state
            if state == CircuitState.HALF_OPEN:
                self.half_open_calls = 0
    
    def _reset(self):
        """Reset circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# --- Exponential Backoff ---

async def with_retry(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs
):
    """
    Execute function with exponential backoff retry.
    
    Usage:
        result = await with_retry(fetch_data, url, max_retries=5)
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            # Check if retryable
            if not _is_retryable(e):
                raise
            
            # Calculate delay with exponential backoff + jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * 0.1 * (time.time() % 1)  # 10% jitter
            actual_delay = delay + jitter
            
            logger.warning(
                "retry_attempt",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=actual_delay,
                error=str(e)[:100]
            )
            
            await asyncio.sleep(actual_delay)
    
    raise last_error


def _is_retryable(error: Exception) -> bool:
    """Check if error is retryable."""
    # Common retryable errors
    error_str = str(error).lower()
    retryable_patterns = [
        "timeout",
        "connection",
        "rate limit",
        "429",
        "503",
        "502",
        "504",
        "temporarily unavailable",
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


# --- Global Circuit Breakers ---

_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _breakers[name]
