from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .contracts import Candle, MarketDataRequest
from .interface import MarketDataProvider
from .timeframes import timeframe_delta
from .verification import MarketDataVerificationError, verify_series


class MarketDataIngestor:
    def __init__(
        self,
        providers: list[MarketDataProvider],
        freshness_seconds: int = 120,
    ) -> None:
        if not providers:
            raise ValueError("At least one market-data provider is required")
        if freshness_seconds < 0:
            raise ValueError("freshness_seconds cannot be negative")
        self.providers = tuple(providers)
        self.freshness_seconds = freshness_seconds

    async def candles(
        self,
        request: MarketDataRequest,
        *,
        interval: timedelta | None = None,
        now: datetime | None = None,
    ) -> list[Candle]:
        reference = (now or datetime.now(UTC)).astimezone(UTC)
        expected_interval = interval or timeframe_delta(request.timeframe or "1h")
        request_id = uuid4()
        errors: list[str] = []

        for provider in self.providers:
            try:
                candles = await provider.candles(request)
                stamped = [
                    candle.model_copy(update={"request_id": request_id})
                    for candle in candles
                ]
                verified = verify_series(
                    stamped,
                    now=reference,
                    interval=expected_interval,
                    max_age_seconds=self.freshness_seconds,
                )
                if verified:
                    return verified
                errors.append(f"{provider.id}: no verified candles")
            except (MarketDataVerificationError, ValueError, RuntimeError) as exc:
                errors.append(f"{provider.id}: {exc}")
            except Exception as exc:
                errors.append(f"{provider.id}: unexpected provider error: {exc}")

        raise RuntimeError(
            "No authoritative verified market data available: " + " | ".join(errors)
        )
