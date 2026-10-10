# Phase 4 — XT-Backed Risk Management, Proposals, Approval, and Execution

## Scope

“Production-ready” in this build phase means the intended features are implemented and integrated for development and controlled testing. It does not mean MITROS is ready for public distribution. A full feature, security, deployment, and operational audit remains a separate pre-distribution milestone.

XT.com is the authoritative account/portfolio source for this building phase. Exchange connectivity is behind provider boundaries so a future exchange selector can supply other account and execution adapters without changing the risk engine contracts.

## Account state and market evidence

- `XTSpotClient` signs XT private requests using HMAC-SHA256 and retrieves the XT spot balance snapshot.
- XT BTC-valued account totals are converted to USDT using XT's public BTC/USDT price.
- Asset balances, observed equity, peak observed equity, intraday snapshot-based equity movement, and derived spot holdings are persisted in `phase4_portfolio_snapshots`.
- The daily P&L currently means change from the first persisted account-equity snapshot for the UTC day; deposit/withdrawal adjustments and a full exchange-ledger reconciliation are still future refinement items.
- Trade-market candles must pass the existing verified market-data pipeline. The API records provider/version, timestamps, checksum, XT bid/ask/last, spread, and account snapshot identity with each risk input.
- Client input cannot supply or override equity, positions, daily P&L, peak equity, quote freshness, or verified-data status.

## Risk policy and decision audit

The independent Phase 4 gate evaluates stop/target orientation, reward-to-risk, stop-based risk budget, position size, gross exposure, asset concentration, correlated exposure and count, open-position count, daily loss, drawdown, data quality, quote freshness, spread, expected slippage, and deviation between the latest verified candle close and XT's current ticker. The maximum permitted market-price deviation is configured through `MITROS_RISK_MAX_MARKET_PRICE_DEVIATION_FRACTION`.

A failed hard check returns `REJECTED`, `approved_notional=0`, and explicit reasons. Risk decisions and their `RiskEvaluated` event are written in one database transaction with request, policy, decision, evidence, and engine-version snapshots. Idempotency is scoped to the authenticated user.

## API lifecycle

- `GET /api/v1/risk/phase4/readiness` — reports whether risk policy, XT credentials/read-only access, Phase 4 schema, verified market data, and live-off toggles are configured; it never returns credentials or account values.
- `POST /api/v1/risk/phase4/evaluate` — evaluates a trade intent against fresh XT account state and verified market evidence; returns risk evidence and audit IDs.
- `POST /api/v1/proposals/phase4` — creates a durable proposal only after an approved Phase 4 decision. Rejected decisions remain in the risk audit and cannot create a proposal.
- `POST /api/v1/proposals/{proposal_id}/approve` — refreshes account state and market evidence, reruns the risk policy, verifies the requested size still passes, then records human approval. It returns a one-time approval token; only the token digest is persisted.
- `POST /api/v1/proposals/{proposal_id}/execute` — requires the persisted human approval and token, checks Phase 4 provenance, writes an execution intent before submission, then persists the result or marks an uncertain outcome for reconciliation.
- The old `GET /api/v1/risk/assessment` endpoint, which accepted caller-supplied risk limits and portfolio numbers, returns HTTP 410 and cannot approve a trade.
- The legacy proposal builder remains available for isolated legacy tests, but XT execution requires `phase4-independent-risk-*` provenance and cannot submit a legacy proposal.

## XT spot execution limitation for this build

The XT adapter submits approved IOC limit entries and reconciles XT order state. Because the XT spot order interface does not provide a single native bracket order for both stop-loss and take-profit, MITROS runs a database-backed protective monitor in the API process. It watches filled XT spot longs and submits one idempotent market sell when stop-loss or take-profit is crossed. It claims the exit state before submission and reconciles uncertain outcomes rather than blindly retrying. XT spot short entries are rejected because spot trading cannot open a short position. The monitor requires `MITROS_XT_PROTECTION_MONITOR_ENABLED=true`; all live flags remain false by default. The full pre-distribution audit must still test monitor uptime/restarts, partial fills, exchange rate limits, and close-order reconciliation.

## Live execution configuration

Paper mode is the default. XT live order submission is implemented behind an execution-gateway factory and is disabled by deployment environment variables; no code edit is needed to switch modes.

Required controls:
- `MITROS_EXECUTION_MODE=paper`
- `MITROS_LIVE_TRADING_ENABLED=false`
- `MITROS_LIVE_TRADING_ACK=` (empty in paper mode)
- `MITROS_XT_LIVE_ORDERS_ENABLED=false`
- `MITROS_XT_PROTECTION_MONITOR_ENABLED=false`
- `MITROS_XT_PROTECTION_POLL_SECONDS=5`

XT account access uses server-only `MITROS_XT_API_KEY` and `MITROS_XT_API_SECRET`. Use least-privilege keys; never enable withdrawals. The API key/secret must be configured in Render secrets, never in GitHub, browser code, or `.env.example`.

To switch modes later, set `MITROS_EXECUTION_MODE=live`, `MITROS_LIVE_TRADING_ENABLED=true`, `MITROS_LIVE_TRADING_ACK=I_UNDERSTAND_LIVE_TRADING`, `MITROS_XT_LIVE_ORDERS_ENABLED=true`, and `MITROS_XT_PROTECTION_MONITOR_ENABLED=true` in the backend environment. These flags are intentionally separate; changing any one flag alone does not enable live orders. Do not enable them until XT account, market evidence, database migrations, approval revalidation, order reconciliation, and the full pre-distribution audit are complete.

## Configuration

Risk policy values are server-side `MITROS_RISK_*` variables listed in `.env.example`. The API refuses risk evaluation when the policy is incomplete or invalid. Example starting values are not financial advice and must be tuned to the selected market and account.

Required database migrations:
- `0010_phase4_risk_decision_audit`
- `0011_phase4_xt_portfolio_snapshots`
- `0012_phase4_proposal_lifecycle`

## Validation requirements

CI tests cover:
- deterministic independent risk checks and rejected-notional behavior;
- XT signature construction and balance/ticker parsing;
- audit and portfolio persistence schema presence;
- client-supplied portfolio fields being ignored;
- legacy risk API cannot bypass Phase 4;
- proposal builder refuses rejected decisions;
- rejected fresh risk cannot advance a pending proposal to approval;
- approval requires a fresh passing risk result;
- XT execution requires Phase 4 provenance and all environment toggles;
- execution intent/result persistence and reconciliation state transitions.

Before public distribution, perform a full feature and security audit, apply and verify production migrations, configure real XT credentials in Render, run authenticated production E2E against the intended account, reconcile all portfolio and order state, and verify the frontend's proposal/approval/execute flows end to end.
