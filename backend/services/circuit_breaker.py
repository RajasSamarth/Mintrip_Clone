"""Circuit breaker for external API resilience.

Tracks failures per external service and opens the circuit after a threshold,
preventing repeated calls to failing services. After a recovery timeout, the
circuit goes half-open and allows a single trial request.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.config import get_settings


@dataclass
class CircuitState:
    failures: int = 0
    last_failure_time: Optional[float] = None
    state: str = "closed"  # closed | open | half_open


class CircuitBreaker:
    """Thread-safe circuit breaker for external API calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        settings = get_settings()
        self.failure_threshold = settings.circuit_breaker_failure_threshold
        self.recovery_timeout = settings.circuit_breaker_recovery_timeout
        self._state = CircuitState()
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs):
        """Execute func through the circuit breaker."""
        with self._lock:
            state = self._state
            if state.state == "open":
                if state.last_failure_time and (
                    time.time() - state.last_failure_time
                ) > self.recovery_timeout:
                    state.state = "half_open"
                    state.failures = 0
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry after {self.recovery_timeout}s."
                    )

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._record_failure()
            raise exc

        with self._lock:
            if self._state.state == "half_open":
                self._state.state = "closed"
                self._state.failures = 0
            return result

    def _record_failure(self) -> None:
        with self._lock:
            state = self._state
            state.failures += 1
            state.last_failure_time = time.time()
            if state.failures >= self.failure_threshold:
                state.state = "open"


class CircuitBreakerOpenError(Exception):
    pass


# Registry of circuit breakers per external service
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_breaker(name: str) -> CircuitBreaker:
    with _breakers_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name)
        return _breakers[name]


def call_with_breaker(name: str, func: Callable, *args, **kwargs):
    return get_breaker(name).call(func, *args, **kwargs)
