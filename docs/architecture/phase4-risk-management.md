# Phase 4 — Independent Risk Management and Trade Proposals

## Status and boundary
Phase 4 adds a deterministic, versioned risk decision contract and independent hard gate. It evaluates proposals; it does not fetch data, submit orders, authorize execution, or mutate risk policy. Human approval and execution remain separate capabilities.

## Evaluation inputs
The caller supplies a timestamped portfolio snapshot, verified-data flag and quality score, quote observation time, requested notional, entry/stop/target, spread, expected slippage, open positions, and an immutable risk policy. The engine rejects timezone-naive timestamps and inconsistent equity snapshots.

## Hard gates
- Stop-loss and take-profit are mandatory, positive, and correctly oriented for LONG/SHORT.
- Reward/risk ratio meets the configured minimum.
- Stop-based loss at requested notional stays within the per-trade risk budget.
- Position size, gross exposure, asset concentration, correlated group exposure and position counts remain within limits.
- Daily-loss and peak-to-current drawdown hard stops block new risk at the threshold.
- Verified data, quote freshness, minimum data quality, spread and expected slippage must pass.
- All checks return measured values, thresholds and rejection reasons. Any failed check means REJECTED and approved notional is exactly zero.

## Position sizing
The engine computes stop-based risk fraction from requested_notional multiplied by abs(entry - stop) / entry, then divides by equity. It calculates the risk-budget notional as equity multiplied by max_risk_per_trade divided by the stop-distance fraction. The reported size_cap_notional is the minimum of that risk budget and per-position, gross-exposure, asset-concentration, and correlated-exposure headroom. If the requested notional exceeds any applicable hard limit, the request is rejected with approved notional zero rather than silently resized.

## Proposal invalidation
Each decision includes explicit stop-crossing, expiry/stale-data, and pre-approval risk-breach invalidation conditions. The proposal is not a live order and the result always sets execution_authorized=false.

## Fail-closed contract
Strategy output cannot alter the risk policy. A failed risk check cannot be overridden by strategy confidence or proposal construction. This gate is intentionally separate from strategy scoring and does not provide an execution API.

## Operational limitations
Portfolio positions, quote quality, spread, and slippage are caller-supplied evidence; they are not claimed to be live account data by this pure engine. Production account-state wiring, persisted risk-decision audit events, UI integration, and exchange execution remain separate work and must be verified before live use.
