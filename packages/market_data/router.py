from .contracts import Candle, MarketDataRequest, Quote, ProviderHealth
from .interface import MarketDataProvider


class ProviderRouter:
    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        self.providers = tuple(providers)

    async def quote(self, request: MarketDataRequest) -> Quote:
        errors: list[str] = []
        for provider in self.providers:
            try:
                quote = await provider.quote(request)
                if quote.last is not None:
                    return quote
                errors.append(f"{provider.id}: empty quote")
            except Exception as exc:
                errors.append(f"{provider.id}: {exc}")
        raise RuntimeError("All market-data providers failed: " + " | ".join(errors))

    async def candles(self, request: MarketDataRequest) -> list[Candle]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                candles = await provider.candles(request)
                if candles:
                    return candles
                errors.append(f"{provider.id}: empty candles")
            except Exception as exc:
                errors.append(f"{provider.id}: {exc}")
        raise RuntimeError("All market-data providers failed for candles: " + " | ".join(errors))

    async def health(self) -> tuple[ProviderHealth, ...]:
        return tuple([await provider.health() for provider in self.providers])
