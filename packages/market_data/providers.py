from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from .contracts import Candle, MarketDataRequest, ProviderHealth, Quote
from .http import HTTPProviderBase, utc_from_epoch
from .interface import MarketDataProvider
from .symbols import SymbolMapper
from .timeframes import timeframe_delta


def _close_time(open_time: datetime, timeframe: str) -> datetime:
    return open_time + timeframe_delta(timeframe)


def _observed_at(raw: object, fallback: datetime) -> datetime:
    if not raw:
        return fallback
    value = datetime.fromisoformat(str(raw))
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TwelveDataProvider(HTTPProviderBase, MarketDataProvider):
    id = "twelvedata"
    version = "v1"

    def __init__(self, *, api_key: str, symbols: SymbolMapper, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(api_key=api_key, base_url="https://api.twelvedata.com", client=client)
        self.symbols = symbols

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        mapping = self.symbols.resolve(self.id, request.asset)
        timeframe = request.timeframe or "1h"
        received = datetime.now(UTC)
        data = await self._get(
            "/time_series",
            {
                "symbol": mapping.provider_symbol,
                "interval": timeframe,
                "outputsize": request.limit,
                "apikey": self.api_key,
            },
        )
        values = data.get("values", [])
        if not values:
            raise RuntimeError("Twelve Data returned no candle rows")
        meta = data.get("meta", {})
        observed = _observed_at(meta.get("last_refresh") or values[0].get("datetime"), received)
        return [
            Candle(
                asset=request.asset,
                venue=request.venue,
                symbol=request.asset,
                timeframe=timeframe,
                open_time=_observed_at(x["datetime"], received),
                close_time=_close_time(_observed_at(x["datetime"], received), timeframe),
                open=Decimal(str(x["open"])),
                high=Decimal(str(x["high"])),
                low=Decimal(str(x["low"])),
                close=Decimal(str(x["close"])),
                volume=Decimal(str(x["volume"])) if x.get("volume") not in (None, "") else None,
                provider=self.id,
                provider_version=self.version,
                observed_at=observed,
                received_at=received,
            )
            for x in values
        ]

    async def quote(self, request: MarketDataRequest) -> Quote:
        m = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        d = await self._get("/quote", {"symbol": m.provider_symbol, "apikey": self.api_key})
        observed = _observed_at(d.get("datetime"), received)
        return Quote(
            asset=request.asset, venue=request.venue, symbol=request.asset,
            last=Decimal(str(d["close"])), provider=self.id, provider_version=self.version,
            observed_at=observed, received_at=received,
        )

    async def health(self) -> ProviderHealth:
        try:
            await self._get("/quote", {"symbol": "BTC/USD", "apikey": self.api_key})
            return ProviderHealth(provider=self.id, available=True, checked_at=datetime.now(UTC))
        except Exception as exc:
            return ProviderHealth(provider=self.id, available=False, checked_at=datetime.now(UTC), error=str(exc))


class FinnhubProvider(HTTPProviderBase, MarketDataProvider):
    id = "finnhub"
    version = "v1"

    def __init__(self, *, api_key: str, symbols: SymbolMapper, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(api_key=api_key, base_url="https://finnhub.io/api", client=client)
        self.symbols = symbols

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        m = self.symbols.resolve(self.id, request.asset)
        timeframe = request.timeframe or "1h"
        resolution = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}.get(timeframe)
        if resolution is None:
            raise ValueError(f"Unsupported Finnhub timeframe: {timeframe}")
        import time
        end = int(time.time())
        start = end - (request.limit * 86400 if resolution == "D" else request.limit * int(timeframe_delta(timeframe).total_seconds()))
        data = await self._get(
            "/v1/stock/candle",
            {"symbol": m.provider_symbol, "resolution": resolution, "from": start, "to": end, "token": self.api_key},
        )
        if data.get("s") != "ok":
            raise RuntimeError(f"Finnhub candle status: {data.get('s')}")
        timestamps = data.get("t", [])
        if not timestamps:
            raise RuntimeError("Finnhub returned no candle rows")
        received = datetime.now(UTC)
        observed = utc_from_epoch(int(timestamps[-1]))
        return [
            Candle(
                asset=request.asset, venue=request.venue, symbol=request.asset, timeframe=timeframe,
                open_time=utc_from_epoch(int(ts)),
                close_time=_close_time(utc_from_epoch(int(ts)), timeframe),
                open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(l)), close=Decimal(str(c)),
                volume=Decimal(str(v)) if v is not None else None,
                provider=self.id, provider_version=self.version, observed_at=observed, received_at=received,
            )
            for ts, o, h, l, c, v in zip(
                data["t"], data["o"], data["h"], data["l"], data["c"],
                data.get("v", [None] * len(data["t"])),
            )
        ]

    async def quote(self, request: MarketDataRequest) -> Quote:
        m = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        d = await self._get("/v1/quote", {"symbol": m.provider_symbol, "token": self.api_key})
        observed = utc_from_epoch(int(d["t"])) if d.get("t") else received
        return Quote(
            asset=request.asset, venue=request.venue, symbol=request.asset, last=Decimal(str(d["c"])),
            provider=self.id, provider_version=self.version, observed_at=observed, received_at=received,
        )

    async def health(self) -> ProviderHealth:
        try:
            await self.quote(MarketDataRequest(asset="BTC/USD", venue="spot"))
            return ProviderHealth(provider=self.id, available=True, checked_at=datetime.now(UTC))
        except Exception as exc:
            return ProviderHealth(provider=self.id, available=False, checked_at=datetime.now(UTC), error=str(exc))


class AlphaVantageProvider(HTTPProviderBase, MarketDataProvider):
    id = "alphavantage"
    version = "v1"

    def __init__(self, *, api_key: str, symbols: SymbolMapper, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(api_key=api_key, base_url="https://www.alphavantage.co", client=client)
        self.symbols = symbols

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        m = self.symbols.resolve(self.id, request.asset)
        timeframe = request.timeframe or "1h"
        interval = {"1h": "60min"}.get(timeframe, timeframe)
        if interval not in {"1m", "5m", "15m", "30m", "60min"}:
            raise ValueError(f"Unsupported Alpha Vantage timeframe: {timeframe}")
        function = "CRYPTO_INTRADAY" if "/" in request.asset else "TIME_SERIES_INTRADAY"
        params: dict[str, str | int] = {
            "function": function, "symbol": m.provider_symbol, "interval": interval,
            "outputsize": "full", "apikey": self.api_key,
        }
        if function == "CRYPTO_INTRADAY":
            params["market"] = "USD"
        data = await self._get("/query", params)
        key = next((k for k in data if k.startswith(("Time Series Crypto", "Time Series ("))), None)
        if key is None:
            raise RuntimeError(
                f"Alpha Vantage returned no time-series payload: "
                f"{data.get('Note') or data.get('Error Message')}"
            )
        rows = data[key]
        items = list(rows.items())[:request.limit]
        if not items:
            raise RuntimeError("Alpha Vantage returned no candle rows")
        received = datetime.now(UTC)
        observed = _observed_at(items[0][0], received)
        return [
            Candle(
                asset=request.asset, venue=request.venue, symbol=request.asset, timeframe=timeframe,
                open_time=_observed_at(ts, received),
                close_time=_close_time(_observed_at(ts, received), timeframe),
                open=Decimal(str(row.get("1. open") or row.get("1a. open (USD)"))),
                high=Decimal(str(row.get("2. high") or row.get("2a. high (USD)"))),
                low=Decimal(str(row.get("3. low") or row.get("3a. low (USD)"))),
                close=Decimal(str(row.get("4. close") or row.get("4a. close (USD)"))),
                volume=Decimal(str(row.get("5. volume") or row.get("5. volume (USD)") or "0")),
                provider=self.id, provider_version=self.version, observed_at=observed, received_at=received,
            )
            for ts, row in items
        ]

    async def quote(self, request: MarketDataRequest) -> Quote:
        m = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        if "/" in request.asset:
            base, quote_currency = request.asset.split("/", 1)
            data = await self._get("/query", {
                "function": "CURRENCY_EXCHANGE_RATE", "from_currency": base,
                "to_currency": quote_currency, "apikey": self.api_key,
            })
            q = data.get("Realtime Currency Exchange Rate", {})
            if "5. Exchange Rate" not in q:
                raise RuntimeError("Alpha Vantage returned no realtime exchange rate")
            observed = _observed_at(q.get("6. Last Refreshed"), received)
            price = Decimal(str(q["5. Exchange Rate"]))
        else:
            data = await self._get("/query", {"function": "GLOBAL_QUOTE", "symbol": m.provider_symbol, "apikey": self.api_key})
            q = data.get("Global Quote", {})
            if "05. price" not in q:
                raise RuntimeError("Alpha Vantage returned no global quote price")
            observed = received
            price = Decimal(str(q["05. price"]))
        return Quote(
            asset=request.asset, venue=request.venue, symbol=request.asset, last=price,
            provider=self.id, provider_version=self.version, observed_at=observed, received_at=received,
        )

    async def health(self) -> ProviderHealth:
        try:
            await self.quote(MarketDataRequest(asset="BTC/USD", venue="spot"))
            return ProviderHealth(provider=self.id, available=True, checked_at=datetime.now(UTC))
        except Exception as exc:
            return ProviderHealth(provider=self.id, available=False, checked_at=datetime.now(UTC), error=str(exc))


class CoinbaseProvider(HTTPProviderBase, MarketDataProvider):
    id = "coinbase"
    version = "v1-exchange-rest"
    _GRANULARITY: ClassVar[dict[str, int]] = {"15m": 900, "1h": 3600, "4h": 14400}

    def __init__(self, *, symbols: SymbolMapper, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(base_url="https://api.exchange.coinbase.com", client=client)
        self.symbols = symbols

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        timeframe = request.timeframe or "1h"
        granularity = self._GRANULARITY.get(timeframe)
        if granularity is None:
            raise ValueError(f"Unsupported Coinbase timeframe: {timeframe}")
        mapping = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        end = int(received.timestamp())
        start = end - request.limit * granularity
        data = await self._get_json(
            f"/products/{mapping.provider_symbol}/candles",
            {"granularity": granularity, "start": start, "end": end},
        )
        if not isinstance(data, list) or not data:
            raise RuntimeError("Coinbase returned no candle rows")
        candles: list[Candle] = []
        for row in sorted(data, key=lambda item: int(item[0])):
            if not isinstance(row, list) or len(row) < 6:
                continue
            open_time = utc_from_epoch(float(row[0]))
            candles.append(
                Candle(
                    asset=request.asset, venue=request.venue, symbol=request.asset, timeframe=timeframe,
                    open_time=open_time, close_time=open_time + timedelta(seconds=granularity),
                    open=Decimal(str(row[3])), high=Decimal(str(row[2])), low=Decimal(str(row[1])),
                    close=Decimal(str(row[4])), volume=Decimal(str(row[5])),
                    provider=self.id, provider_version=self.version,
                    observed_at=received, received_at=received,
                )
            )
        if not candles:
            raise RuntimeError("Coinbase returned no parseable candle rows")
        return candles[-request.limit :]

    async def quote(self, request: MarketDataRequest) -> Quote:
        mapping = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        data = await self._get(f"/products/{mapping.provider_symbol}/ticker", {})
        observed = _observed_at(data.get("time"), received)
        return Quote(
            asset=request.asset, venue=request.venue, symbol=request.asset,
            last=Decimal(str(data["price"])),
            bid=Decimal(str(data["bid"])) if data.get("bid") else None,
            ask=Decimal(str(data["ask"])) if data.get("ask") else None,
            provider=self.id, provider_version=self.version,
            observed_at=observed, received_at=received,
        )

    async def health(self) -> ProviderHealth:
        try:
            await self.quote(MarketDataRequest(asset="BTC/USD", venue="spot"))
            return ProviderHealth(provider=self.id, available=True, checked_at=datetime.now(UTC))
        except Exception as exc:
            return ProviderHealth(provider=self.id, available=False, checked_at=datetime.now(UTC), error=str(exc))


class KrakenProvider(HTTPProviderBase, MarketDataProvider):
    id = "kraken"
    version = "v1-spot-rest"
    _INTERVAL_MINUTES: ClassVar[dict[str, int]] = {"15m": 15, "1h": 60, "4h": 240}

    def __init__(self, *, symbols: SymbolMapper, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(base_url="https://api.kraken.com/0/public", client=client)
        self.symbols = symbols

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        timeframe = request.timeframe or "1h"
        interval = self._INTERVAL_MINUTES.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported Kraken timeframe: {timeframe}")
        mapping = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        data = await self._get(
            "/OHLC", {"pair": mapping.provider_symbol, "interval": interval, "assetVersion": 1}
        )
        result = data.get("result")
        if not isinstance(result, dict):
            raise TypeError("Kraken returned no OHLC result")
        rows = next(
            (value for key, value in result.items() if key != "last" and isinstance(value, list)),
            None,
        )
        if not rows:
            raise RuntimeError("Kraken returned no OHLC rows")
        candles: list[Candle] = []
        for row in sorted(rows, key=lambda item: int(item[0])):
            if not isinstance(row, list) or len(row) < 7:
                continue
            open_time = utc_from_epoch(float(row[0]))
            candles.append(
                Candle(
                    asset=request.asset, venue=request.venue, symbol=request.asset, timeframe=timeframe,
                    open_time=open_time, close_time=open_time + timedelta(minutes=interval),
                    open=Decimal(str(row[1])), high=Decimal(str(row[2])), low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])), volume=Decimal(str(row[6])),
                    provider=self.id, provider_version=self.version,
                    observed_at=received, received_at=received,
                )
            )
        if not candles:
            raise RuntimeError("Kraken returned no parseable OHLC rows")
        return candles[-request.limit :]

    async def quote(self, request: MarketDataRequest) -> Quote:
        mapping = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        data = await self._get("/Ticker", {"pair": mapping.provider_symbol, "assetVersion": 1})
        result = data.get("result")
        if not isinstance(result, dict) or not result:
            raise RuntimeError("Kraken returned no ticker result")
        ticker = next(iter(result.values()))
        if not isinstance(ticker, dict) or not ticker.get("c"):
            raise RuntimeError("Kraken returned no ticker price")
        return Quote(
            asset=request.asset, venue=request.venue, symbol=request.asset,
            bid=Decimal(str(ticker["b"][0])) if ticker.get("b") else None,
            ask=Decimal(str(ticker["a"][0])) if ticker.get("a") else None,
            last=Decimal(str(ticker["c"][0])),
            provider=self.id, provider_version=self.version,
            observed_at=received, received_at=received,
        )

    async def health(self) -> ProviderHealth:
        try:
            await self.quote(MarketDataRequest(asset="BTC/USD", venue="spot"))
            return ProviderHealth(provider=self.id, available=True, checked_at=datetime.now(UTC))
        except Exception as exc:
            return ProviderHealth(provider=self.id, available=False, checked_at=datetime.now(UTC), error=str(exc))


class CoinGeckoProvider(HTTPProviderBase, MarketDataProvider):
    id = "coingecko"
    version = "v1-market-chart-hourly"
    _SUPPORTED: ClassVar[set[str]] = {"1h", "4h"}

    def __init__(
        self,
        *,
        api_key: str = "",
        symbols: SymbolMapper,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        headers = {"x-cg-demo-api-key": api_key} if api_key else {}
        super().__init__(
            api_key=api_key,
            base_url="https://api.coingecko.com/api/v3",
            client=client,
            headers=headers,
        )
        self.symbols = symbols

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        timeframe = request.timeframe or "1h"
        if timeframe not in self._SUPPORTED:
            raise ValueError("CoinGecko emergency provider supports only 1h and 4h")
        mapping = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        hours_needed = request.limit * (4 if timeframe == "4h" else 1)
        days = max(3, min(90, (hours_needed + 23) // 24 + 2))
        data = await self._get(
            f"/coins/{mapping.provider_symbol}/market_chart",
            {"vs_currency": "usd", "days": days},
        )
        prices = data.get("prices")
        if not isinstance(prices, list) or not prices:
            raise RuntimeError("CoinGecko returned no market-chart prices")

        buckets: dict[datetime, list[Decimal]] = {}
        for point in prices:
            if not isinstance(point, list) or len(point) < 2:
                continue
            dt = datetime.fromtimestamp(int(point[0]) / 1000, tz=UTC)
            bucket = dt.replace(minute=0, second=0, microsecond=0)
            buckets.setdefault(bucket, []).append(Decimal(str(point[1])))

        hourly: list[Candle] = []
        for open_time in sorted(buckets):
            values = buckets[open_time]
            hourly.append(
                Candle(
                    asset=request.asset, venue=request.venue, symbol=request.asset, timeframe="1h",
                    open_time=open_time, close_time=open_time + timedelta(hours=1),
                    open=values[0], high=max(values), low=min(values), close=values[-1],
                    volume=None, provider=self.id, provider_version=self.version,
                    observed_at=received, received_at=received,
                )
            )

        if timeframe == "1h":
            return hourly[-request.limit :]

        by_time = {item.open_time: item for item in hourly}
        grouped: list[Candle] = []
        for start in sorted(by_time):
            if start.hour % 4 != 0:
                continue
            parts = [by_time.get(start + timedelta(hours=index)) for index in range(4)]
            if any(part is None for part in parts):
                continue
            valid_parts = [part for part in parts if part is not None]
            grouped.append(
                Candle(
                    asset=request.asset, venue=request.venue, symbol=request.asset, timeframe="4h",
                    open_time=start, close_time=start + timedelta(hours=4),
                    open=valid_parts[0].open, high=max(part.high for part in valid_parts),
                    low=min(part.low for part in valid_parts), close=valid_parts[-1].close,
                    volume=None, provider=self.id, provider_version=self.version,
                    observed_at=received, received_at=received,
                )
            )
        return grouped[-request.limit :]

    async def quote(self, request: MarketDataRequest) -> Quote:
        mapping = self.symbols.resolve(self.id, request.asset)
        received = datetime.now(UTC)
        data = await self._get(
            "/simple/price", {"ids": mapping.provider_symbol, "vs_currencies": "usd"}
        )
        coin = data.get(mapping.provider_symbol)
        if not isinstance(coin, dict) or "usd" not in coin:
            raise RuntimeError("CoinGecko returned no USD price")
        return Quote(
            asset=request.asset, venue=request.venue, symbol=request.asset,
            last=Decimal(str(coin["usd"])), provider=self.id,
            provider_version=self.version, observed_at=received, received_at=received,
        )

    async def health(self) -> ProviderHealth:
        try:
            await self.quote(MarketDataRequest(asset="BTC/USD", venue="spot"))
            return ProviderHealth(provider=self.id, available=True, checked_at=datetime.now(UTC))
        except Exception as exc:
            return ProviderHealth(provider=self.id, available=False, checked_at=datetime.now(UTC), error=str(exc))
