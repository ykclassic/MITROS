# Phase 4 — Independent Risk Management and Trade Proposals

## Implemented safety boundary

Phase 4 provides an immutable risk-policy contract, deterministic independent hard gate, proposal builder, per-check evidence, invalidation conditions, and an audit event. It does not submit orders, grant human approval, or authorize execution.

A failed hard check returns `REJECTED` with `approved_notional=0`. Strategy confidence cannot alter policy. Requested notional above any applicable limit is rejected rather than silently resized.

## Risk checks

- Mandatory stop-loss/take-profit levels with directionally correct orientation.
- Minimum reward-to-risk and stop-based risk budget.
- Position-size, gross-exposure, asset-concentration, correlated-position count and correlated-exposure limits.
- Daily-loss and peak-to-current drawdown hard stops.
- Verified-data assertion, quote freshness, minimum data quality, spread and expected slippage.
- Measured observed values, thresholds, per-check reasons, and explicit invalidation conditions.

## API and audit

- `POST /api/v1/risk/phase4/scenario` runs the Phase 4 gate in paper/non-live mode.
- Risk policy values are server-owned and must be configured using the `MITROS_RISK_*` environment variables listed in `.env.example`. The API does not silently choose defaults.
- `MITROS_DATABASE_URL` is required. A decision and its `RiskEvaluated` system event are stored in one PostgreSQL transaction.
- The idempotency key is scoped to the authenticated user. Reusing a key with different proposal inputs or policy is rejected.
- The endpoint returns a durable audit ID, each hard check, rejection reasons, and invalidation conditions.
- CORS permits POST for the API route. Authentication is required.

## Position sizing

The gate computes the risk-budget notional as equity multiplied by maximum risk per trade divided by stop-distance fraction. The reported size cap is the minimum of risk budget and per-position, gross-exposure, asset-concentration, and correlated-exposure headroom. Position-count caps can reduce the size cap to zero.

## Explicit production limitations — do not enable live use based on this phase alone

The current endpoint is intentionally labelled `SCENARIO_ONLY`: its request includes caller-supplied account and quote observations, so those values are not authoritative live account state. The route returns HTTP 503 when `MITROS_EXECUTION_MODE=live`. This is deliberate fail-closed behavior, not a temporary validation bypass.

Before Phase 4 can be called production-ready for real trading, all of the following remain required:

1. Implement an authenticated, server-side account-state adapter that obtains equity, daily P&L, peak equity, open positions, notional exposure, and correlation-group exposure from a verified account/ledger source. The client must not supply these fields.
2. Obtain quote freshness, verified-data status, spread and slippage from trusted server-side market-data/execution adapters rather than trusting client assertions.
3. Persist a proposal only after the independent risk decision and link it to the audit decision in a transaction.
4. Integrate the resulting proposal into the existing human approval workflow; approval must revalidate expiry and risk, and risk approval must never imply execution approval.
5. Add production E2E tests proving missing/stale account snapshots, missing policy, audit-store outage, idempotency conflict, and any failed hard gate cannot create an approvable or executable proposal.
6. Apply the new migration to the production database, configure and validate all risk-policy environment variables, and verify the deployed backend/frontend build and authenticated endpoints.

Until these gates pass, the Phase 4 endpoint is a durable, audited scenario evaluator only. No claim is made that it is live-account-aware or safe to authorize real orders.
