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
        assert DEFAULT_SYMBOL_MAPPINGS["kraken"][canonical_asset] == kraken_symbol
        assert DEFAULT_SYMBOL_MAPPINGS["coinbase"][canonical_asset] == coinbase_symbol
        assert kraken_symbol != canonical_asset.replace("/", "")
        assert coinbase_symbol != canonical_asset.replace("/", "")


def test_phase4_risk_gate_timeframe_is_supported_by_primary_and_cross_validator() -> None:
    assert KrakenProvider._INTERVAL_MINUTES["1m"] == 1
    assert CoinbaseProvider._GRANULARITY["1m"] == "ONE_MINUTE"


def test_auth_diagnostics_map_jwt_failures_to_safe_reason_codes() -> None:
    assert _jwt_failure_reason(jwt.ExpiredSignatureError()) == "token_expired"
    assert _jwt_failure_reason(jwt.InvalidAudienceError()) == "audience_mismatch"
    assert _jwt_failure_reason(jwt.InvalidIssuerError()) == "issuer_mismatch"
    assert _jwt_failure_reason(jwt.InvalidSignatureError()) == "signature_invalid"
