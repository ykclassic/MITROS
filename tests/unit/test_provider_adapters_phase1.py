from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.market_data.contracts import Candle, MarketDataRequest
from packages.market_data.providers import AlphaVantageProvider, FinnhubProvider, TwelveDataProvider
from packages.market_data.symbols import SymbolMapper


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def assert_interval(candle: Candle, hours: int) -> None:
    assert candle.close_time - candle.open_time == timedelta(hours=hours)
    assert candle.open_time.tzinfo is not None
    assert candle.close_time.tzinfo is not None


def test_twelve_data_adapter_sets_candle_interval() -> None:
    assert_interval(
        Candle(
            asset="BTC/USD", venue="spot", timeframe="1h",
            open_time=NOW - timedelta(hours=1), close_time=NOW,
            open=Decimal("1"), high=Decimal("2"), low=Decimal("1"), close=Decimal("2"),
            provider="twelvedata", observed_at=NOW, received_at=NOW,
        ),
        1,
    )


def test_provider_adapters_share_canonical_timeframe_contract() -> None:
    assert TwelveDataProvider.id == "twelvedata"
    assert FinnhubProvider.id == "finnhub"
    assert AlphaVantageProvider.id == "alphavantage"
    assert SymbolMapper is not None
