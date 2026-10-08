from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from packages.market_data.contracts import MarketDataRequest
from packages.market_data.providers import CoinbaseProvider, CoinGeckoProvider, KrakenProvider
from packages.market_data.symbols import SymbolMapper


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=self.payload, request=request)


@pytest.mark.asyncio
@pytest.mark.parametrize("timeframe", ["15m", "1h", "4h"])
async def test_coinbase_parser_supports_canonical_timeframes(timeframe: str) -> None:
    payload = [
        [1700000000, "34900", "35100", "35000", "35050", "12.5"],
        [1700003600, "35000", "35200", "35050", "35150", "11.5"],
    ]
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        provider = CoinbaseProvider(
            symbols=SymbolMapper({"coinbase": {"BTC/USD": "BTC-USD"}}),
            client=client,
        )
        candles = await provider.candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe=timeframe, limit=2)
        )
    assert len(candles) == 2
    assert candles[0].provider == "coinbase"
    assert candles[0].open == Decimal("35000")
    assert candles[0].close == Decimal("35050")


@pytest.mark.asyncio
@pytest.mark.parametrize("timeframe", ["15m", "1h", "4h"])
async def test_kraken_parser_supports_canonical_timeframes(timeframe: str) -> None:
    interval = {"15m": 15, "1h": 60, "4h": 240}[timeframe]
    payload = {
        "error": [],
        "result": {
            "BTC/USD": [
                [1700000000, "35000", "35100", "34900", "35050", "35020", "12.5", 100],
                [1700000000 + interval * 60, "35050", "35200", "35000", "35150", "35120", "11.5", 90],
            ],
            "last": 1700000000 + interval * 120,
        },
    }
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        provider = KrakenProvider(
            symbols=SymbolMapper({"kraken": {"BTC/USD": "BTC/USD"}}),
            client=client,
        )
        candles = await provider.candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe=timeframe, limit=2)
        )
    assert len(candles) == 2
    assert candles[0].provider == "kraken"
    assert candles[0].close == Decimal("35050")


@pytest.mark.asyncio
async def test_coingecko_parser_reconstructs_hourly_and_four_hour_candles() -> None:
    prices = []
    start = datetime(2026, 10, 1, tzinfo=UTC)
    for hour in range(12):
        prices.append([int((start.timestamp() + hour * 3600) * 1000), 100 + hour])
    payload = {"prices": prices, "market_caps": [], "total_volumes": []}
    async with httpx.AsyncClient(transport=MockTransport(payload)) as client:
        provider = CoinGeckoProvider(
            symbols=SymbolMapper({"coingecko": {"BTC/USD": "bitcoin"}}),
            client=client,
        )
        one_hour = await provider.candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="1h", limit=4)
        )
        four_hour = await provider.candles(
            MarketDataRequest(asset="BTC/USD", venue="spot", timeframe="4h", limit=2)
        )
    assert len(one_hour) == 4
    assert one_hour[-1].close == Decimal("111")
    assert len(four_hour) == 2
    assert four_hour[0].open == Decimal("104")
    assert four_hour[0].close == Decimal("107")


def test_symbol_mappings_are_canonical_for_replacement_providers() -> None:
    mapper = SymbolMapper(
        {
            "coinbase": {"BTC/USD": "BTC-USD"},
            "kraken": {"BTC/USD": "BTC/USD"},
            "coingecko": {"BTC/USD": "bitcoin"},
        }
    )
    assert mapper.resolve("coinbase", "BTC/USD").provider_symbol == "BTC-USD"
    assert mapper.resolve("kraken", "BTC/USD").provider_symbol == "BTC/USD"
    assert mapper.resolve("coingecko", "BTC/USD").provider_symbol == "bitcoin"
