from __future__ import annotations

import hashlib
import json
import os
import logging
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from itertools import pairwise
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts.consensus import MTFConsensus, StrategyConsensus
from contracts.intelligence import (
    IntelligenceContext,
    IntelligenceSnapshot,
    LiquiditySnapshot,
    MarketStructureSnapshot,
    QuantitativeMetrics,
    CRTSnapshot,
    SMCContextSnapshot,
)
from packages.api.auth import AuthenticatedUser, require_user

from contracts.copilot import ResearchAnswer, ResearchEvidence, EvidenceKind
from contracts.regime import RegimeSnapshot, StatisticalSnapshot
from contracts.research import ResearchArtifactType, ResearchMetric, ResearchQuery, ResearchReport
from contracts.domain import StrategyVote
from contracts.risk import PortfolioState, PositionState, RiskAssessment, RiskLimits
from packages.features.engine import FeatureEngine
from packages.intelligence.engine import MarketIntelligenceEngine
from packages.market_data.cache import AsyncTTLCache
from packages.market_data.config import MarketDataSettings
from packages.market_data.contracts import Candle, MarketDataRequest, ProviderHealth, DataQuality
from packages.market_data.ingestion import MarketDataIngestor
from packages.market_data.service import VerifiedMarketDataService
from packages.market_data.routing import PostgresProviderConfiguration, SupabaseRestProviderConfiguration
from packages.market_data.default_symbols import DEFAULT_SYMBOL_MAPPINGS
from packages.market_data.interface import MarketDataProvider
from packages.market_data.providers import AlphaVantageProvider, FinnhubProvider, TwelveDataProvider
from packages.market_data.router import ProviderRouter
from packages.market_data.symbols import SymbolMapper
from packages.operations.config import ProductionConfig
from packages.research.copilot import GroundedResearchCopilot
from packages.research.platform import ResearchPlatform
from packages.risk.engine import AdvancedRiskEngine
from packages.strategies.base import StrategyContext
from packages.strategies.consensus import StrategyConsensusEngine
from packages.strategies.crt import CRTStrategy
from packages.strategies.smc import SMCStrategy


CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]
logger = logging.getLogger("mitros.api")


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


class ObservationProvenanceResponse(BaseModel):
    provider: str
    provider_version: str | None
    request_id: str | None
    observation_checksum: str
    observed_at: datetime
    received_at: datetime


class IntelligenceProvenanceResponse(BaseModel):
    data_quality: DataQuality
    batch_checksum: str
    observation_count: int
    observations: tuple[ObservationProvenanceResponse, ...]


class IntelligenceSnapshotResponse(BaseModel):
    asset: str
    venue: str
    symbol: str
    timeframe: str
    as_of: datetime
    observation_window: tuple[datetime, datetime]
    engine_version: str
    configuration_version: str
    input_checksums: tuple[str, ...]
    snapshot_checksum: str
    candle_count: int
    latest_close: str
    feature_set_version: str
    features: dict[str, str]
    quantitative: QuantitativeMetrics
    structure: MarketStructureSnapshot
    liquidity: LiquiditySnapshot
    smc_context: SMCContextSnapshot
    crt_analysis: CRTSnapshot
    regime: RegimeSnapshot
    context: IntelligenceContext
    strategy_votes: tuple[StrategyVote, ...]
    consensus: StrategyConsensus
    mtf: MTFConsensus
    provenance: IntelligenceProvenanceResponse
    generated_at: datetime


@lru_cache(maxsize=1)
def get_settings() -> MarketDataSettings:
    return MarketDataSettings()


candle_cache: AsyncTTLCache[list[Candle]] = AsyncTTLCache(ttl_seconds=60.0, max_entries=32)


def build_router() -> ProviderRouter:
    settings = get_settings()
    symbols = SymbolMapper(DEFAULT_SYMBOL_MAPPINGS)
    providers: list[MarketDataProvider] = []
    if settings.twelvedata_api_key:
        providers.append(TwelveDataProvider(api_key=settings.twelvedata_api_key, symbols=symbols))
    if settings.finnhub_api_key:
        providers.append(FinnhubProvider(api_key=settings.finnhub_api_key, symbols=symbols))
    if settings.alphavantage_api_key:
        providers.append(AlphaVantageProvider(api_key=settings.alphavantage_api_key, symbols=symbols))
    if not providers:
        raise RuntimeError("No market-data provider credentials configured")
    return ProviderRouter(providers)


async def load_candles(asset: str, venue: str, timeframe: str, limit: int) -> list[Candle]:
    key = "|".join((asset, venue, timeframe, str(limit)))
    async def fetch() -> list[Candle]:
        return await build_router().candles(
            MarketDataRequest(asset=asset, venue=venue, timeframe=timeframe, limit=limit)
        )
    return await candle_cache.get_or_load(key, fetch)


def _statistical_snapshot(candles: list[Candle]) -> StatisticalSnapshot:
    ordered = sorted(candles, key=lambda c: c.open_time)
    returns = [(current.close / previous.close) - Decimal("1") for previous, current in pairwise(ordered)]
    if not returns:
        raise ValueError("at least two candles are required")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum(((value - mean) ** 2 for value in returns), Decimal("0")) / Decimal(len(returns))
    volatility = variance.sqrt()
    downside = [value for value in returns if value < 0]
    downside_variance = (
        sum((value ** 2 for value in downside), Decimal("0")) / Decimal(len(downside))
        if downside else Decimal("0")
    )
    last = returns[-1]
    z_score = (last - mean) / volatility if volatility else Decimal("0")
    return StatisticalSnapshot(
        sample_size=len(returns),
        mean_return=mean,
        volatility=volatility,
        win_rate=Decimal(sum(value > 0 for value in returns)) / Decimal(len(returns)),
        downside_deviation=downside_variance.sqrt(),
        autocorrelation_1=Decimal("0"),
        z_score=z_score,
        reasons=("statistics are computed from verified provider candles",),
    )


def _artifact_checksum(candles: list[Candle]) -> str:
    payload = [
        {
            "open_time": candle.open_time.isoformat(),
            "open": str(candle.open),
            "high": str(candle.high),
            "low": str(candle.low),
            "close": str(candle.close),
            "volume": str(candle.volume) if candle.volume is not None else None,
            "provider": candle.provider,
        }
        for candle in sorted(candles, key=lambda c: c.open_time)
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _market_data_failure_category(exc: Exception) -> str:
    message = str(exc).lower()
    if "mitros_database_url" in message:
        return "database_configuration"
    if "no market-data provider credentials configured" in message:
        return "provider_credentials"
    if "no active authoritative provider route" in message:
        return "provider_route"
    if "symbol" in message and ("mapping" in message or "mapped" in message):
        return "provider_symbol_mapping"
    if any(token in message for token in ("401", "403", "api key", "apikey", "rate limit", "quota")):
        return "provider_api_rejection"
    if any(token in message for token in ("stale", "incomplete", "future", "continuity gap", "conflict")):
        return "verification_gate"
    if "no authoritative verified market data" in message or "no verified candles" in message:
        return "verified_data_unavailable"
    return "market_data_unavailable"


async def build_verified_service() -> VerifiedMarketDataService:
    settings = get_settings()
    database_url = os.getenv("MITROS_DATABASE_URL", "").strip()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not database_url and not (supabase_url and service_role_key):
        raise RuntimeError("A DB-backed provider configuration is required for verified intelligence")

    symbols = SymbolMapper(DEFAULT_SYMBOL_MAPPINGS)
    providers: list[MarketDataProvider] = []
    if settings.twelvedata_api_key:
        providers.append(TwelveDataProvider(api_key=settings.twelvedata_api_key, symbols=symbols))
    if settings.finnhub_api_key:
        providers.append(FinnhubProvider(api_key=settings.finnhub_api_key, symbols=symbols))
    if settings.alphavantage_api_key:
        providers.append(AlphaVantageProvider(api_key=settings.alphavantage_api_key, symbols=symbols))
    if not providers:
        raise RuntimeError("No market-data provider credentials configured")

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if supabase_url and service_role_key:
        configuration = SupabaseRestProviderConfiguration(supabase_url, service_role_key)
    else:
        configuration = PostgresProviderConfiguration(database_url)
    ingestor = MarketDataIngestor(
        providers,
        freshness_seconds=settings.freshness_seconds,
        configuration=configuration,
    )
    return VerifiedMarketDataService(ingestor, producer_version="0.6.0")


async def build_intelligence(asset: str, venue: str, timeframe: str) -> IntelligenceSnapshotResponse:
    service = await build_verified_service()
    batch = await service.candles(
        MarketDataRequest(asset=asset, venue=venue, timeframe=timeframe, limit=200)
    )
    candles = batch.candles
    snapshot: IntelligenceSnapshot = MarketIntelligenceEngine().snapshot(candles)

    features = FeatureEngine().snapshot(candles)
    context = StrategyContext(candles=candles, features=features)
    smc_strategy = SMCStrategy()
    crt_strategy = CRTStrategy()
    votes = (smc_strategy.evaluate(context), crt_strategy.evaluate(context))
    consensus_engine = StrategyConsensusEngine()
    consensus = consensus_engine.combine_strategies(votes)

    mtf_votes: dict[str, tuple[StrategyVote, ...]] = {}
    for candidate in ("15m", "1h", "4h"):
        try:
            candidate_batch = await service.candles(
                MarketDataRequest(asset=asset, venue=venue, timeframe=candidate, limit=80)
            )
            candidate_candles = candidate_batch.candles
            if len(candidate_candles) >= 7:
                candidate_features = FeatureEngine().snapshot(candidate_candles)
                candidate_context = StrategyContext(
                    candles=candidate_candles, features=candidate_features
                )
                mtf_votes[candidate] = (
                    smc_strategy.evaluate(candidate_context),
                    crt_strategy.evaluate(candidate_context),
                )
        except (RuntimeError, ValueError):
            continue
    if not mtf_votes:
        mtf_votes = {timeframe: votes}
    mtf = consensus_engine.combine_mtf(mtf_votes)

    provenance = IntelligenceProvenanceResponse(
        data_quality=DataQuality.VERIFIED,
        batch_checksum=batch.batch_checksum,
        observation_count=len(candles),
        observations=tuple(
            ObservationProvenanceResponse(
                provider=item.provider,
                provider_version=item.provider_version,
                request_id=str(item.request_id) if item.request_id else None,
                observation_checksum=item.checksum or "",
                observed_at=item.observed_at,
                received_at=item.received_at,
            )
            for item in candles
        ),
    )

    return IntelligenceSnapshotResponse(
        asset=snapshot.asset,
        venue=snapshot.venue,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        as_of=snapshot.as_of,
        observation_window=snapshot.observation_window,
        engine_version=snapshot.engine_version,
        configuration_version=snapshot.configuration_version,
        input_checksums=snapshot.input_checksums,
        snapshot_checksum=snapshot.snapshot_checksum,
        candle_count=len(candles),
        latest_close=str(candles[-1].close),
        feature_set_version=features.feature_set_version,
        features={key: str(value) for key, value in features.values.items()},
        quantitative=snapshot.quantitative,
        structure=snapshot.structure,
        liquidity=snapshot.liquidity,
        smc_context=snapshot.smc,
        crt_analysis=snapshot.crt,
        regime=snapshot.regime,
        context=snapshot.context,
        strategy_votes=votes,
        consensus=consensus,
        mtf=mtf,
        provenance=provenance,
        generated_at=datetime.now(UTC),
    )


async def build_research_report(asset: str, venue: str, timeframe: str) -> ResearchReport:
    candles = await load_candles(asset, venue, timeframe, 200)
    ordered = sorted(candles, key=lambda c: c.open_time)
    statistics = _statistical_snapshot(ordered)
    checksum = _artifact_checksum(ordered)
    artifact = ResearchPlatform().register_artifact(
        artifact_type=ResearchArtifactType.DATASET,
        name=f"{asset} {timeframe} verified candles",
        version="1.0.0",
        checksum=checksum,
        created_at=datetime.now(UTC),
        metadata={"provider": ordered[-1].provider, "candle_count": str(len(ordered))},
    )
    query = ResearchQuery(
        asset=asset,
        venue=venue,
        timeframe=timeframe,
        start=ordered[0].open_time,
        end=ordered[-1].close_time,
    )
    metrics = (
        ResearchMetric(name="mean_return", value=statistics.mean_return, sample_size=statistics.sample_size),
        ResearchMetric(name="volatility", value=statistics.volatility, sample_size=statistics.sample_size),
        ResearchMetric(name="win_rate", value=statistics.win_rate, sample_size=statistics.sample_size),
        ResearchMetric(name="downside_deviation", value=statistics.downside_deviation, sample_size=statistics.sample_size),
        ResearchMetric(name="last_return_z_score", value=statistics.z_score, sample_size=statistics.sample_size),
    )
    return ResearchPlatform().report(
        query,
        artifacts=(artifact,),
        metrics=metrics,
        findings=(
            "Research is computed from verified provider candles.",
            f"Dataset checksum: {checksum}",
        ),
        generated_at=datetime.now(UTC),
    )


def create_app() -> FastAPI:
    app = FastAPI(title="MITROS API", version="0.5.0", docs_url="/docs", redoc_url="/redoc")
    configured_origins = [
        item.strip() for item in os.getenv("MITROS_ALLOWED_ORIGINS", "").split(",") if item.strip()
    ]
    frontend_origin = os.getenv("MITROS_FRONTEND_URL", "").strip()
    production_origins = [origin for origin in (frontend_origin, "https://mitros.vercel.app") if origin]
    origins = list(dict.fromkeys(configured_origins + production_origins))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Authorization", "Content-Type", "X-MITROS-Request-ID"],
    )

    @app.on_event("startup")
    async def startup_market_data_diagnostics() -> None:
        settings = get_settings()
        configured_providers = tuple(
            provider
            for provider, key in (
                ("twelvedata", settings.twelvedata_api_key),
                ("finnhub", settings.finnhub_api_key),
                ("alphavantage", settings.alphavantage_api_key),
            )
            if key
        )
        database_configured = bool(os.getenv("MITROS_DATABASE_URL", "").strip())
        logger.warning(
            "market_data_configuration providers=%s database_configured=%s freshness_seconds=%s",
            ",".join(configured_providers) or "none",
            database_configured,
            settings.freshness_seconds,
        )
        supabase_url = os.getenv("SUPABASE_URL", "").strip()
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        try:
            if supabase_url and service_role_key:
                configuration = SupabaseRestProviderConfiguration(supabase_url, service_role_key)
                configuration_source = "supabase_data_api"
            elif database_configured:
                configuration = PostgresProviderConfiguration(os.environ["MITROS_DATABASE_URL"])
                configuration_source = "postgres"
            else:
                raise RuntimeError("no provider-route database configuration is available")
            route_counts = {}
            for asset in ("BTC/USD", "ETH/USD", "SOL/USD"):
                routes = await configuration.routes(asset=asset, venue="spot", timeframe="1h")
                route_counts[asset] = len(routes)
            logger.warning(
                "market_data_provider_routes source=%s route_counts=%s",
                configuration_source,
                route_counts,
            )
        except Exception as exc:
            logger.error(
                "market_data_route_configuration_unavailable category=%s exception_type=%s sqlstate=%s detail=%s",
                _market_data_failure_category(exc),
                type(exc).__name__,
                getattr(exc, "sqlstate", None),
                str(exc).replace(os.getenv("MITROS_DATABASE_URL", ""), "<database-url>").replace("\\n", " ")[:240],
            )

    @app.get("/health", response_model=ApiHealth)
    async def health() -> ApiHealth:
        return ApiHealth(status="ok", service="mitros-api", timestamp=datetime.now(UTC))

    @app.get("/api/v1/auth/me", response_model=dict[str, object])
    async def auth_me(user: CurrentUser) -> dict[str, object]:
        return {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role,
            "entitlements": list(user.entitlements),
            "assurance_level": user.assurance_level,
        }

    @app.get("/api/v1/operations/readiness", response_model=ReadinessResponse)
    async def readiness(user: CurrentUser) -> ReadinessResponse:

        try:
            config = ProductionConfig.from_env()
        except ValueError:
            return ReadinessResponse(status="NOT_READY", execution_mode="invalid", live_trading_enabled=False,
                checks={"api":"PASS","production_configuration":"FAIL","live_trading":"DISABLED","human_approval":"REQUIRED"})
        return ReadinessResponse(
            status="READY" if config.execution_mode.value == "paper" else "NOT_READY",
            execution_mode=config.execution_mode.value,
            live_trading_enabled=config.live_trading_enabled,
            checks={
                "api":"PASS","production_configuration":"PASS",
                "paper_execution_default":"PASS" if config.execution_mode.value == "paper" else "FAIL",
                "live_trading":"ENABLED" if config.live_trading_enabled else "DISABLED",
                "human_approval":"REQUIRED",
            },
        )

    @app.get("/api/v1/market/quote", response_model=MarketQuoteResponse)
    async def quote(user: CurrentUser, asset: str = Query(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$"), venue: str = Query(default="spot", min_length=1, max_length=32)) -> MarketQuoteResponse:
        try:
            # Quotes are derived from the same verified candle boundary used by Intelligence.
            # This keeps provider authority, symbol mappings, freshness and verification identical.
            batch = await (await build_verified_service()).candles(
                MarketDataRequest(asset=asset, venue=venue, timeframe="1h", limit=2)
            )
        except (RuntimeError, ValueError) as exc:
            logger.error(
                "market_quote_unavailable category=%s asset=%s venue=%s",
                _market_data_failure_category(exc), asset, venue,
            )
            raise HTTPException(status_code=503, detail="Verified market data unavailable") from exc
        latest = batch.candles[-1]
        return MarketQuoteResponse(
            asset=latest.asset,
            venue=latest.venue,
            price=str(latest.close),
            provider=latest.provider,
            provider_version=latest.provider_version,
            observed_at=latest.observed_at,
            received_at=latest.received_at,
            quality=latest.quality.value,
        )

    @app.get("/api/v1/market/health", response_model=list[ProviderHealth])
    async def market_health(user: CurrentUser) -> list[ProviderHealth]:
        try:
            return list(await build_router().health())
        except RuntimeError:
            return []

    @app.get("/api/v1/risk/assessment", response_model=RiskAssessment)
    async def risk_assessment(
        equity: Annotated[Decimal, Query(gt=0)],
        daily_pnl: Annotated[Decimal, Query()],
        peak_equity: Annotated[Decimal, Query(gt=0)],
        requested_size: Annotated[Decimal, Query(gt=0)],
        stop_distance_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_position_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_gross_exposure: Annotated[Decimal, Query(gt=0)],
        max_daily_loss_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_drawdown_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_concentration_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_leverage: Annotated[Decimal, Query(gt=0)],
        max_spread_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_risk_fraction: Annotated[Decimal, Query(gt=0, le=1)],
        max_correlation_exposure: Annotated[Decimal, Query(gt=0)],
        asset: Annotated[str, Query(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$")],
        existing_exposure: Annotated[Decimal, Query(ge=0)] = Decimal("0"),
        spread_fraction: Annotated[Decimal, Query(ge=0, le=1)] = Decimal("0"),
        correlated_exposure: Annotated[Decimal, Query(ge=0)] = Decimal("0"),
        *,
        user: CurrentUser,
    ) -> RiskAssessment:
        if peak_equity < equity:
            raise HTTPException(status_code=422, detail="peak_equity must be at least equity")
        positions: tuple[PositionState, ...] = ()
        if existing_exposure > 0:
            positions = (PositionState(asset=asset, market_value=existing_exposure, unrealized_pnl=Decimal("0"), direction="UNKNOWN"),)
        portfolio = PortfolioState(
            equity=equity,
            balance=equity,
            daily_pnl=daily_pnl,
            peak_equity=peak_equity,
            positions=positions,
        )
        limits = RiskLimits(
            max_position_fraction=max_position_fraction,
            max_gross_exposure=max_gross_exposure,
            max_daily_loss_fraction=max_daily_loss_fraction,
            max_drawdown_fraction=max_drawdown_fraction,
            max_concentration_fraction=max_concentration_fraction,
            max_leverage=max_leverage,
            max_spread_fraction=max_spread_fraction,
            max_risk_fraction=max_risk_fraction,
            max_correlation_exposure=max_correlation_exposure,
        )
        try:
            return AdvancedRiskEngine(limits).assess(
                portfolio,
                asset=asset,
                requested_size=requested_size,
                stop_distance_fraction=stop_distance_fraction,
                spread_fraction=spread_fraction,
                correlated_exposure=correlated_exposure,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/intelligence/snapshot", response_model=IntelligenceSnapshotResponse)
    async def intelligence_snapshot(
        user: CurrentUser,
        asset: str = Query(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$"),
        venue: str = Query(default="spot", min_length=1, max_length=32),
        timeframe: str = Query(default="1h", pattern=r"^(15m|1h|4h)$"),
    ) -> IntelligenceSnapshotResponse:
        try:
            return await build_intelligence(asset, venue, timeframe)
        except (RuntimeError, ValueError) as exc:
            logger.error(
                "intelligence_snapshot_unavailable category=%s asset=%s venue=%s timeframe=%s",
                _market_data_failure_category(exc), asset, venue, timeframe,
            )
            raise HTTPException(status_code=503, detail="Verified intelligence is unavailable") from exc

    @app.get("/api/v1/research/report", response_model=ResearchReport)
    async def research_report(
        user: CurrentUser,
        asset: str = Query(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$"),
        venue: str = Query(default="spot", min_length=1, max_length=32),
        timeframe: str = Query(default="1h", pattern=r"^(15m|1h|4h)$"),
    ) -> ResearchReport:
        try:
            return await build_research_report(asset, venue, timeframe)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Research data is unavailable") from exc

    @app.get("/api/v1/research/copilot", response_model=ResearchAnswer)
    async def research_copilot(
        user: CurrentUser,
        asset: str = Query(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$"),
        venue: str = Query(default="spot", min_length=1, max_length=32),
        timeframe: str = Query(default="1h", pattern=r"^(15m|1h|4h)$"),
    ) -> ResearchAnswer:
        try:
            report = await build_research_report(asset, venue, timeframe)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Grounded research evidence is unavailable") from exc
        artifact = report.artifacts[0]
        evidence = ResearchEvidence(
            kind=EvidenceKind.DATASET,
            artifact_id=artifact.id,
            title=artifact.name,
            checksum=artifact.checksum,
            excerpt="Verified candle dataset used to compute the research report.",
            source_timestamp=artifact.created_at,
        )
        return GroundedResearchCopilot().answer(report.query, (evidence,), generated_at=datetime.now(UTC))

    return app


app = create_app()
