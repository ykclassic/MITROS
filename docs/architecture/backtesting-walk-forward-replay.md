# Phase 9 — Backtesting, Walk-forward and Replay

Phase 9 is research-only. It evaluates historical evidence without authorizing, approving, submitting, or mutating live orders.

## Causal backtesting
A strategy observes only completed candles through decision time. A signal is filled using the next candle open and evaluated through that next candle close, preventing same-bar close leakage.

Every run records dataset and configuration SHA-256 checksums, strategy identity/version, feature-set version, fill model and provenance.

## Replay
Replay feeds the exact historical prefix into the existing feature and strategy engines one completed candle at a time. Feature-vector checksums make frames reproducible and auditable.

## Walk-forward
The evaluator uses expanding training windows, an explicit purge gap, and out-of-sample test windows. OOS windows are never used to create the preceding training prefix.

## Safety boundary
Backtest, replay and walk-forward components have no execution dependency and cannot reach the MT5 gateway, human approval state, or live ledger.
