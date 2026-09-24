from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from packages.market_data.config import MarketDataSettings
from packages.market_data.contracts import MarketDataRequest, ProviderHealth, Quote
from packages.market_data.default_symbols import DEFAULT_SYMBOL_MAPPINGS
from packages.market_data.providers import AlphaVantageProvider, FinnhubProvider, TwelveDataProvider
from packages.market_data.router import ProviderRouter
from packages.market_data.symbols import SymbolMapper


class ApiHealth(BaseModel):
    status: str
    service: str
    timestamp: datetime


class MarketQuoteResponse(BaseModel):
    asset: str
    venue: str
    price: str
    provider: str
    provider_version: str | None
    observed_at: datetime
    received_at: datetime
    quality: str


class ReadinessResponse(BaseModel):
    status: str
    execution_mode: str
    live_trading_enabled: bool
    checks: dict[str, str]


@lru_cache(maxsize=1)
def get_settings() -> MarketDataSettings:
    return MarketDataSettings()


def build_router() -> ProviderRouter:
    settings = get_settings()
    symbols = SymbolMapper(DEFAULT_SYMBOL_MAPPINGS)
    providers = []
    if settings.twelvedata_api_key:
        providers.append(TwelveDataProvider(api_key=settings.twelvedata_api_key, symbols=symbols))
    if settings.finnhub_api_key:
        providers.append(FinnhubProvider(api_key=settings.finnhub_api_key, symbols=symbols))
    if settings.alphavantage_api_key:
        providers.append(AlphaVantageProvider(api_key=settings.alphavantage_api_key, symbols=symbols))
    if not providers:
        raise RuntimeError("No market-data provider credentials configured")
    return ProviderRouter(providers)


def create_app() -> FastAPI:
    app = FastAPI(title="MITROS API", version="0.1.0", docs_url="/docs", redoc_url="/redoc")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=ApiHealth)
    async def health() -> ApiHealth:
        return ApiHealth(status="ok", service="mitros-api", timestamp=datetime.now(UTC))

    @app.get("/api/v1/operations/readiness", response_model=ReadinessResponse)
    async def readiness() -> ReadinessResponse:
        execution_mode = "paper"
        return ReadinessResponse(
            status="READY",
            execution_mode=execution_mode,
            live_trading_enabled=False,
            checks={
                "api": "PASS",
                "paper_execution_default": "PASS",
                "live_trading": "DISABLED",
                "human_approval": "REQUIRED",
            },
        )

    @app.get("/api/v1/market/quote", response_model=MarketQuoteResponse)
    async def quote(
        asset: str = Query(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$"),
        venue: str = Query(default="spot", min_length=1, max_length=32),
    ) -> MarketQuoteResponse:
        try:
            router = build_router()
            result: Quote = await router.quote(
                MarketDataRequest(asset=asset, venue=venue, timeframe="1h", limit=1)
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Market data unavailable") from exc
        if result.last is None:
            raise HTTPException(status_code=503, detail="Market data unavailable")
        return MarketQuoteResponse(
            asset=result.asset,
            venue=result.venue,
            price=str(result.last),
            provider=result.provider,
            provider_version=result.provider_version,
            observed_at=result.observed_at,
            received_at=result.received_at,
            quality=result.quality.value,
        )

    @app.get("/api/v1/market/health", response_model=list[ProviderHealth])
    async def market_health() -> list[ProviderHealth]:
        try:
            return list(await build_router().health())
        except RuntimeError:
            return []

    return app


app = create_app()
