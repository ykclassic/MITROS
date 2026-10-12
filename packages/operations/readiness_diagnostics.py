from __future__ import annotations

import asyncio

import httpx

from packages.exchanges.xt import XTSpotError


def xt_failure_reason(exc: Exception) -> str:
    """Map XT failures to stable codes without inspecting exception text."""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return "xt_provider_timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return "xt_provider_http_error"
    if isinstance(exc, httpx.HTTPError):
        return "xt_transport_error"
    if isinstance(exc, XTSpotError):
        return "xt_api_error"
    return "xt_check_failed"


def market_data_failure_reason(exc: Exception) -> str:
    """Map market-data failures to safe codes without serializing exception data."""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return "market_data_provider_timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return "market_data_provider_http_error"
    if isinstance(exc, httpx.HTTPError):
        return "market_data_transport_error"
    if isinstance(exc, ValueError):
        return "market_data_validation_failed"
    if isinstance(exc, RuntimeError):
        return "market_data_provider_unavailable"
    return "market_data_verification_failed"


def phase4_readiness_is_ready(checks: dict[str, bool]) -> bool:
    """Compute readiness from authoritative checks only; diagnostics are informational."""
    required = (
        "database_configured",
        "risk_policy_configured",
        "xt_credentials_configured",
        "live_trading_disabled",
        "phase4_schema_applied",
        "xt_read_only_connection",
        "verified_market_data",
    )
    return all(checks.get(name, False) for name in required)
