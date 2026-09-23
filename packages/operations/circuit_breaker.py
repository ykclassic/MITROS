from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"


class CircuitBreaker:
    """Fail-closed breaker for repeated operational failures."""

    def __init__(self, failure_threshold: int) -> None:
        if failure_threshold < 1:
            raise ValueError("failure threshold must be positive")
        self._threshold = failure_threshold
        self._failures = 0
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    def allow(self) -> bool:
        return self._state is CircuitState.CLOSED

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
