from packages.market_data.default_symbols import DEFAULT_SYMBOL_MAPPINGS
from packages.market_data.providers import CoinbaseProvider, KrakenProvider


def test_phase4_usdt_symbols_are_explicit_for_primary_and_cross_validator() -> None:
    assert DEFAULT_SYMBOL_MAPPINGS["kraken"]["BTC/USDT"] == "XBTUSDT"
    assert DEFAULT_SYMBOL_MAPPINGS["coinbase"]["BTC/USDT"] == "BTC-USDT"


def test_phase4_risk_gate_timeframe_is_supported_by_primary_and_cross_validator() -> None:
    assert KrakenProvider._INTERVAL_MINUTES["1m"] == 1
    assert CoinbaseProvider._GRANULARITY["1m"] == "ONE_MINUTE"
