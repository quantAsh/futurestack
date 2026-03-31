import time
import functools
import random
import structlog
from typing import Callable, Any, Type, Tuple, Optional

logger = structlog.get_logger("nomadnest.resilience")


def with_retry(
    retries: int = 3,
    backoff_factor: float = 0.5,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    status_codes_to_retry: Tuple[int, ...] = (500, 502, 503, 504),
):
    """
    Retry decorator with exponential backoff and jitter.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # If it's an HTTP exception, check the status code
                    if (
                        hasattr(e, "status_code")
                        and e.status_code not in status_codes_to_retry
                    ):
                        raise

                    if attempt == retries:
                        logger.error("retry_final_attempt_failed", func=func.__name__, error=str(e))
                        break

                    wait_time = (backoff_factor * (2**attempt)) + random.uniform(
                        0, 0.1
                    )
                    logger.warning(
                        "retry_attempt_failed",
                        func=func.__name__,
                        attempt=attempt + 1,
                        error=str(e),
                        retry_in_s=round(wait_time, 2),
                    )
                    time.sleep(wait_time)
            raise last_exception

        return wrapper

    return decorator


class CircuitBreaker:
    """
    Simple Circuit Breaker to prevent cascading failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def __call__(self, func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    logger.info(
                        "circuit_breaker_half_open", breaker=self.name
                    )
                else:
                    raise Exception(
                        f"Circuit Breaker '{self.name}' is OPEN. Failing fast."
                    )

            try:
                result = func(*args, **kwargs)

                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                    logger.info("circuit_breaker_reset", breaker=self.name)

                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(
                        "circuit_breaker_open", breaker=self.name
                    )

                raise e

        return wrapper
