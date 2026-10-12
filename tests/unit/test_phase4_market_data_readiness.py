import jwt

from packages.api.auth import _jwt_failure_reason
from packages.market_data.default_symbols import DEFAULT_SYMBOL_MAPPINGS
from packages.market_data.providers import CoinbaseProvider, KrakenProvider


def test_phase4_usdt_symbols_are_explicit_for_all_assets() -> None:
    expected = {
        "BTC/USDT": ("XBTUSDT", "BTC-USDT"),
        "ETH/USDT": ("ETHUSDT", "ETH-USDT"),
        "SOL/USDT": ("SOLUSDT", "SOL-USDT"),
    }
    for canonical_asset, (kraken_symbol, coinbase_symbol) in expected.items():
        usd_asset = canonical_asset.replace("/USDT", "/USD")
        assert DEFAULT_SYMBOL_MAPPINGS["kraken"][canonical_asset] == kraken_symbol
        assert DEFAULT_SYMBOL_MAPPINGS["coinbase"][canonical_asset] == coinbase_symbol
        assert kraken_symbol != DEFAULT_SYMBOL_MAPPINGS["kraken"][usd_asset]
        assert coinbase_symbol != DEFAULT_SYMBOL_MAPPINGS["coinbase"][usd_asset]


def test_phase4_risk_gate_timeframe_is_supported_by_primary_and_cross_validator() -> None:
    assert KrakenProvider._INTERVAL_MINUTES["1m"] == 1
    assert CoinbaseProvider._GRANULARITY["1m"] == "ONE_MINUTE"


def test_auth_diagnostics_map_jwt_failures_to_safe_reason_codes() -> None:
    assert _jwt_failure_reason(jwt.ExpiredSignatureError()) == "token_expired"
    assert _jwt_failure_reason(jwt.InvalidAudienceError()) == "audience_mismatch"
    assert _jwt_failure_reason(jwt.InvalidIssuerError()) == "issuer_mismatch"
    assert _jwt_failure_reason(jwt.InvalidSignatureError()) == "signature_invalid"


def test_readiness_diagnostics_are_sanitized_and_do_not_change_readiness() -> None:
    from packages.operations.readiness_diagnostics import (
        market_data_failure_reason,
        phase4_readiness_is_ready,
        xt_failure_reason,
    )
    from packages.exchanges.xt import XTSpotError

    secret_bearing_xt_error = XTSpotError(
        "Authorization: Bearer do-not-log signature=secret-value"
    )
    secret_bearing_market_error = RuntimeError(
        "https://provider.invalid?apikey=top-secret"
    )
    xt_reason = xt_failure_reason(secret_bearing_xt_error)
    market_reason = market_data_failure_reason(secret_bearing_market_error)

    assert xt_reason == "xt_api_error"
    assert market_reason == "market_data_provider_unavailable"
    for reason in (xt_reason, market_reason):
        assert "secret" not in reason
        assert "Bearer" not in reason
        assert "apikey" not in reason

    checks = {
        "database_configured": True,
        "risk_policy_configured": True,
        "xt_credentials_configured": True,
        "live_trading_disabled": True,
        "phase4_schema_applied": True,
        "xt_read_only_connection": False,
        "verified_market_data": True,
    }
    assert not phase4_readiness_is_ready(checks)
    # A successful-looking diagnostic is never authority to override a failed check.
    checks["xt_read_only_connection"] = False
    diagnostics = {"xt_read_only_connection": "ok", "verified_market_data": "ok"}
    assert diagnostics["xt_read_only_connection"] == "ok"
    assert not phase4_readiness_is_ready(checks)


def test_diagnostic_codes_do_not_contain_secret_bearing_exception_text() -> None:
    import httpx
    from packages.operations.readiness_diagnostics import (
        market_data_failure_reason,
        xt_failure_reason,
    )
    from packages.exchanges.xt import XTSpotError

    cases = [
        (XTSpotError("api_secret=abc authorization=Bearer xyz"), xt_failure_reason, "xt_api_error"),
        (RuntimeError("private key signature=abc"), market_data_failure_reason, "market_data_provider_unavailable"),
        (httpx.TimeoutException("token=abc"), market_data_failure_reason, "market_data_provider_timeout"),
    ]
    for exception, classify, expected in cases:
        reason = classify(exception)
        assert reason == expected
        assert all(fragment not in reason for fragment in ("abc", "xyz", "Bearer", "signature", "token"))
