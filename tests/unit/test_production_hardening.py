from contracts.operations import CheckStatus, ReadinessStatus
from packages.operations.circuit_breaker import CircuitBreaker, CircuitState
from packages.operations.config import ExecutionMode, ProductionConfig
from packages.operations.readiness import ReadinessProbe, ReadinessService
from packages.operations.redaction import redact_mapping


def test_paper_mode_is_safe_by_default() -> None:
    config = ProductionConfig.from_env({})
    assert config.execution_mode is ExecutionMode.PAPER
    assert config.live_trading_enabled is False


def test_live_mode_requires_explicit_acknowledgement() -> None:
    try:
        ProductionConfig.from_env({
            "MITROS_EXECUTION_MODE": "live",
            "MITROS_LIVE_TRADING_ENABLED": "true",
        })
    except ValueError as exc:
        assert "acknowledgement" in str(exc)
    else:
        raise AssertionError("live mode must fail closed without acknowledgement")


def test_readiness_is_fail_closed() -> None:
    report = ReadinessService([
        ReadinessProbe("database", lambda: None),
        ReadinessProbe("execution", lambda: "venue unavailable"),
    ]).check()
    assert report.status is ReadinessStatus.NOT_READY
    assert report.checks[1].status is CheckStatus.FAIL


def test_probe_exception_is_not_exposed() -> None:
    report = ReadinessService([
        ReadinessProbe(
            "database",
            lambda: (_ for _ in ()).throw(RuntimeError("secret detail")),
        ),
    ]).check()
    assert report.status is ReadinessStatus.NOT_READY
    assert "secret detail" not in report.checks[0].detail


def test_circuit_breaker_fails_closed() -> None:
    breaker = CircuitBreaker(2)
    assert breaker.allow()
    breaker.record_failure()
    assert breaker.allow()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow() is False
    breaker.reset()
    assert breaker.allow()


def test_redaction_removes_operational_secrets() -> None:
    value = redact_mapping({
        "api_key": "abc",
        "nested": {"access_token": "xyz", "safe": "ok"},
    })
    assert value == {
        "api_key": "[REDACTED]",
        "nested": {"access_token": "[REDACTED]", "safe": "ok"},
    }
