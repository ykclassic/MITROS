from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from .contracts import Candle, DataQuality, MarketDataRequest
from .interface import MarketDataProvider
from .routing import ProviderConfiguration, ProviderRoute
from .timeframes import timeframe_delta
from .verification import MarketDataVerificationError, compare_series, verify_series


class MarketDataIngestor:
    def __init__(
        self,
        providers: list[MarketDataProvider],
        freshness_seconds: int = 120,
        *,
        configuration: ProviderConfiguration | None = None,
        cross_validation_tolerance: Decimal = Decimal("0"),
    ) -> None:
        if not providers:
            raise ValueError("At least one market-data provider is required")
        if freshness_seconds < 0:
            raise ValueError("freshness_seconds cannot be negative")
        if cross_validation_tolerance < 0:
            raise ValueError("cross_validation_tolerance cannot be negative")
        self.providers = {provider.id: provider for provider in providers}
        self.freshness_seconds = freshness_seconds
        self.configuration = configuration
        self.cross_validation_tolerance = cross_validation_tolerance

    async def _routes(self, request: MarketDataRequest) -> tuple[ProviderRoute, ...]:
        timeframe = request.timeframe or "1h"
        if self.configuration is not None:
            routes = await self.configuration.routes(
                asset=request.asset, venue=request.venue, timeframe=timeframe
            )
            if not routes:
                raise RuntimeError(
                    f"No active authoritative provider route for "
                    f"{request.asset}/{request.venue}/{timeframe}"
                )
            return routes
        return tuple(
            ProviderRoute(
                provider_key=provider.id,
                provider_version=provider.version,
                priority=index,
                role="PRIMARY" if index == 0 else "SECONDARY",
                active=True,
                cross_validate=False,
                supported_timeframes=(),
                supported_venues=(),
            )
            for index, provider in enumerate(self.providers.values(), start=1)
        )

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
        routes = await self._routes(request)

        for route in routes:
            provider = self.providers.get(route.provider_key)
            if provider is None:
                errors.append(f"{route.provider_key}: configured provider is not registered")
                continue
            try:
                candles = await provider.candles(request)
                stamped = [
                    candle.model_copy(
                        update={
                            "request_id": request_id,
                            "symbol": candle.symbol or request.asset,
                        }
                    )
                    for candle in candles
                ]
                verified = verify_series(
                    stamped,
                    now=reference,
                    interval=expected_interval,
                    max_age_seconds=self.freshness_seconds,
                )
                if not verified:
                    errors.append(f"{provider.id}: no verified candles")
                    continue

                if route.cross_validate:
                    for secondary_route in routes:
                        if secondary_route.provider_key == route.provider_key:
                            continue
                        secondary = self.providers.get(secondary_route.provider_key)
                        if secondary is None:
                            continue
                        try:
                            other = await secondary.candles(request)
                            other_stamped = [
                                item.model_copy(
                                    update={
                                        "request_id": request_id,
                                        "symbol": item.symbol or request.asset,
                                    }
                                )
                                for item in other
                            ]
                            other_verified = verify_series(
                                other_stamped,
                                now=reference,
                                interval=expected_interval,
                                max_age_seconds=self.freshness_seconds,
                            )
                            compare_series(
                                verified,
                                other_verified,
                                price_tolerance=self.cross_validation_tolerance,
                            )
                        except MarketDataVerificationError as exc:
                            if exc.quality is DataQuality.CONFLICTED:
                                raise
                            errors.append(f"{secondary.id}: cross-validation unavailable: {exc}")
                        except Exception as exc:
                            errors.append(f"{secondary.id}: cross-validation unavailable: {exc}")

                return verified
            except MarketDataVerificationError as exc:
                errors.append(f"{provider.id} [{exc.quality}]: {exc}")
            except (ValueError, RuntimeError) as exc:
                errors.append(f"{provider.id}: {exc}")
            except Exception as exc:
                errors.append(f"{provider.id}: unexpected provider error: {exc}")

        raise RuntimeError(
            "No authoritative verified market data available: " + " | ".join(errors)
        )
