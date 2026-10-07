from collections.abc import Sequence
from decimal import Decimal
from hashlib import sha256
import json

from contracts.intelligence import IntelligenceContext, IntelligenceSnapshot
from packages.market_data.contracts import Candle, DataQuality
from .crt import analyze_crt
from .liquidity import analyze_liquidity
from .quantitative import analyze_quantitative
from .regime import RegimeDetector
from .smc import analyze_smc
from .structure import analyze_structure

ENGINE_VERSION = "2.0.0"
CONFIGURATION_VERSION = "deterministic-rules-2.0.0"


class MarketIntelligenceEngine:
    """Deterministic composition of verified market observations into one snapshot."""

    def __init__(self, regime_detector: RegimeDetector | None = None) -> None:
        self.regime_detector = regime_detector or RegimeDetector()

    def snapshot(
        self,
        candles: Sequence[Candle],
        *,
        context: IntelligenceContext | None = None,
        peer_closes: Sequence[Decimal] | None = None,
    ) -> IntelligenceSnapshot:
        ordered = self._validate(candles)
        latest = ordered[-1]
        regime = self.regime_detector.classify(ordered)
        quantitative = analyze_quantitative(ordered, peer_closes)
        structure = analyze_structure(ordered)
        liquidity = analyze_liquidity(ordered)
        smc = analyze_smc(ordered)
        crt = analyze_crt(ordered)
        intelligence_context = context or IntelligenceContext(
            session=liquidity.session, news_active=False)
        if intelligence_context.news_active:
            regime = regime.model_copy(update={
                "regime": "NEWS",
                "confidence": Decimal("1"),
                "reasons": regime.reasons + ("external_news_context_active",),
            })
        payload = {
            "asset": latest.asset, "venue": latest.venue, "symbol": latest.symbol,
            "timeframe": latest.timeframe, "as_of": latest.close_time.isoformat(),
            "observation_window": [ordered[0].open_time.isoformat(), latest.close_time.isoformat()],
            "engine_version": ENGINE_VERSION, "configuration_version": CONFIGURATION_VERSION,
            "input_checksums": sorted(c.checksum or "" for c in ordered),
            "quantitative": quantitative.model_dump(mode="json"),
            "structure": structure.model_dump(mode="json"),
            "liquidity": liquidity.model_dump(mode="json"),
            "smc": smc.model_dump(mode="json"), "crt": crt.model_dump(mode="json"),
            "regime": regime.model_dump(mode="json"), "context": intelligence_context.model_dump(mode="json"),
        }
        checksum = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return IntelligenceSnapshot(**payload, snapshot_checksum=checksum)

    @staticmethod
    def _validate(candles: Sequence[Candle]) -> list[Candle]:
        ordered = sorted(candles, key=lambda c: c.open_time)
        if len(ordered) < 20:
            raise ValueError("market intelligence requires at least 20 candles")
        if any(c.quality is not DataQuality.VERIFIED for c in ordered):
            raise ValueError("market intelligence requires VERIFIED candles")
        if any(c.checksum is None for c in ordered):
            raise ValueError("market intelligence requires checksummed observations")
        first = ordered[0]
        if any(c.asset != first.asset or c.venue != first.venue or c.timeframe != first.timeframe for c in ordered):
            raise ValueError("all candles must share asset, venue and timeframe")
        for previous, current in pairwise(ordered):
            if current.open_time <= previous.open_time:
                raise ValueError("market intelligence requires strictly increasing timestamps")
        return ordered
