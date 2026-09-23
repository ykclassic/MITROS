# Phase 5 — MTF + Strategy Consensus

Phase 5 adds a deterministic consensus layer above the Phase 3 SMC and Phase 4 CRT strategy plugins.

## Responsibilities

- Aggregate multiple strategy votes on one timeframe using confidence-weighted direction scores.
- Aggregate timeframe-level consensus using explicit positive weights.
- Produce bounded confidence and alignment scores.
- Fail closed to NEUTRAL when votes conflict, confidence is below threshold, or no usable votes exist.

## Safety boundary

Consensus is analytical only. It does not calculate position size, perform risk approval, create executable orders, perform human approval, or submit trades.

## Determinism

Timeframes are processed in sorted order. Decimal arithmetic is used for all scores and weights. No wall-clock state or randomness is introduced.

## Data contract

The MTF consensus retains the complete timeframe-level vote set and underlying strategy consensus so downstream audit layers can reconstruct why the consensus was reached.
