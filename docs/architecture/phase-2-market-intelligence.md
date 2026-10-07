# MITROS Phase 2 — Institutional Market Intelligence

## Objective

Transform only VERIFIED, checksummed market observations into a reproducible intelligence snapshot.

Pipeline:

`verified candles → quantitative features → market structure → liquidity → volatility → regime → context`

## Domains

- Quantitative: returns, ATR, realized volatility, momentum, volume statistics, skew, kurtosis, autocorrelation, optional cross-series correlation.
- Market structure: deterministic swing highs/lows, BOS, CHOCH, trend/range classification.
- Liquidity: EQH/EQL, prior-day high/low proxies from the supplied observation window, session highs/lows, liquidity pools and sweeps.
- SMC: FVG, order blocks, premium/discount, displacement and mitigation.
- CRT: explicit reference-range, sweep/reclaim, confirmation, opposite-range target and measurable score.
- Regime: TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, LOW_VOLATILITY, BREAKOUT, TRANSITION, NEWS, UNKNOWN.

## Determinism

`MarketIntelligenceEngine` is pure with respect to its supplied observations and configuration.

A snapshot records:

- asset / venue / symbol / timeframe
- observation window and as-of timestamp
- engine/configuration versions
- every input observation checksum
- quantitative metrics
- structure/liquidity/SMC/CRT context
- regime snapshot
- context
- SHA-256 snapshot checksum

No wall-clock time, randomness, provider re-query, ML inference or mutable global state participates in snapshot generation.

## Regime confidence

Regime confidence is a **regime-fit measure**. It is not a trade probability and must never be interpreted as one.

Trade probability belongs to a later, separately calibrated outcome model.

## CRT measurement

CRT is treated as an observable market-pattern analysis:

1. Select the immediately preceding completed candle as the reference range.
2. Detect a sweep beyond one reference boundary.
3. Require reclaim back through that boundary.
4. Record direction and opposite-range target.
5. Score sweep/reclaim, displacement and target availability independently.

This separates market observation from strategy execution.

## Fail-closed behavior

The engine rejects:

- unverified observations
- missing observation checksums
- mixed asset/venue/timeframe series
- duplicate/non-increasing timestamps
- insufficient history

The engine does not create a degraded intelligence snapshot from invalid input.

## Exit gate

Given identical historical observations and identical configuration, two executions must produce identical `IntelligenceSnapshot` values and identical `snapshot_checksum` values.
