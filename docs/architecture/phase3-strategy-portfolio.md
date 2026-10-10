# Phase 3 — Strategy Portfolio and Signal Consensus

## Scope

Phase 3 combines Phase 2's verified, completed-candle intelligence into a deterministic strategy portfolio evaluation. It produces a **decision assessment**, not an executable order. It does not bypass the risk engine, human approval, paper-mode restrictions, or any future execution authorization.

Core implementation: `packages/intelligence/portfolio.py`; immutable Pydantic contracts: `contracts/strategy_portfolio.py`.

## Evaluation pipeline

1. **Hard gates:** unverified data, stale data, and active news/event blocks return `NO_TRADE`. Unknown or low-confidence regimes return `WAIT`.
2. **Eligibility:** a candidate must be marked eligible by its strategy adapter, provide a direction, pass all of its evidence checks, and explicitly support the detected regime.
3. **Regime-aware weights:** a strategy unsupported in the active regime receives zero effective weight. Eligible strategy votes are scored as `base_weight × confidence`.
4. **Weighted consensus:** long and short scores are aggregated independently. A tied score is a conflict and cannot produce a directional decision.
5. **Multi-timeframe alignment:** alignment is the confidence-weighted fraction of supplied timeframe votes agreeing with the selected direction.
6. **Quality score:** deterministic weighted score: 40% directional strength, 25% mean confidence of winning-side votes, 20% MTF alignment, and 15% evidence quality. The score is a **setup-quality score, not a calibrated probability of profit**.
7. **Completion gates:** at least the configured number of measurable evidence checks must be supplied; every supplied check must pass; MTF alignment and quality score must meet configured floors. Otherwise return `WAIT` and clear the selected direction.

## Decision semantics

- `QUALIFIED`: candidate passes the portfolio-level strategy, regime, evidence, consensus, and MTF checks. It is still not risk-approved, user-approved, or executable.
- `WAIT`: inputs may be usable, but there is insufficient agreement, regime confidence, evidence, or setup quality. The output explains why.
- `NO_TRADE`: a hard market-data or event gate blocks evaluation.

Every result includes engine version, timestamp, regime and confidence, strategy contributions, numeric evidence checks, supporting/opposing counts, MTF alignment, quality score, and human-readable reasons.

## Strategy adapter contract

Strategy adapters should supply immutable `StrategyCandidate` objects with a version, direction, confidence, configured base weight, eligibility result, explicitly supported regimes, timeframe, reasons, and numeric `EvidenceCheck` records. Timeframe adapters supply `TimeframeBias` values from verified Phase 2 snapshots only.

The portfolio engine does not invent missing inputs, fetch candles, infer a regime from numeric state IDs, optimize weights online, or silently replace failed evidence. Empty evidence never qualifies. Keep allocations configuration-versioned and reviewed; no adaptive process may increase risk limits.

## Validation and limitations

Unit tests cover qualification, stale/unverified data, event blocks, unknown/low-confidence regimes, regime mismatch, strategy ineligibility, failed evidence, directional conflict, and low MTF alignment.

Before exposing this as a production signal endpoint, the next integration work must connect the engine to authenticated, persisted Phase 2 snapshots, apply API authorization and request validation, persist the versioned evaluation and its evidence, add deployment E2E coverage, and render WAIT/NO TRADE/QUALIFIED plus reasons in the frontend. No production endpoint or frontend capability should be considered delivered until those integration tests pass.
