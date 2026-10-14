# Phase 4 Account Providers and Verification Runbook

## Safety invariants

- PR #74 must remain open and unmerged until every required CI job and the controlled authenticated verification are explicitly successful.
- The existing Render service and production Supabase project are outside the scope of these checks and must not be changed.
- Keep `MITROS_XT_LIVE_ORDERS_ENABLED=false`. The Bybit adapter is GET-only and cannot submit orders.
- Do not expose credentials, authorization headers, signatures, response bodies, or secret-bearing exception text in logs.

## Provider selection

Set `MITROS_ACCOUNT_EXCHANGE` to one of:

- `xt.com`: the existing XT account adapter and current execution venue.
- `bybit`: the Bybit V5 read-only account adapter.
- `simulated`: deterministic fixtures only on an explicitly permitted non-production verification/development environment.

Bybit requires `MITROS_BYBIT_API_KEY` and `MITROS_BYBIT_API_SECRET`. The optional `MITROS_BYBIT_BASE_URL` defaults to `https://api.bybit.com`. Use an exchange key with read-only permissions and no order, transfer, or withdrawal permissions. The native adapter calls the API-key information endpoint and requires `readOnly=1`.

## Isolated PostgreSQL integration tests

The CI job provisions an ephemeral PostgreSQL service with a database named `mitros_test_db`. It applies the repository's real foundation and Phase 4 migration files to that database before tests run:

- `20261007222136_0001_mitros_foundation.sql`
- `20261010174746_0010_phase4_risk_decision_audit.sql`
- `20261010174748_0011_phase4_xt_portfolio_snapshots.sql`
- `20261010174751_0012_phase4_proposal_lifecycle.sql`
- `20261010200000_0013_phase4_xt_protection_monitor.sql`

The integration test guard refuses non-local hosts and database names without `mitros_test`. The tests verify snapshot persistence/read-back and durable rejected-risk audit persistence without creating a trade proposal. They do not connect to production.

## Authenticated Bybit smoke test

The `Authenticated Bybit Read-Only Smoke Test` workflow is manually dispatched with the exact current head SHA of PR #74. Before checking out or running the candidate, it confirms that PR #74 is still open/unmerged, originates from `phase/phase4-bybit-reconciled` in `ykclassic/MITROS`, and has the requested SHA as its current head. A protected `production-verification` environment must contain the Bybit read-only credentials. The verification checks:

1. Native adapter confirms the API key's `readOnly=1` status.
2. An authenticated account snapshot is positive and fresh.
3. The BTC/USDT ticker price is positive and its exchange observation timestamp is fresh.

A successful smoke test proves Bybit read-only connectivity only. It does not prove full Phase 4 readiness or authorize approval/execution; verified market data, risk audit, proposal lifecycle and all other release gates remain independent.

## Release posture

**HOLD.** No merge or production deployment is authorized by these verification steps. The existing production Render service and Supabase database must remain untouched, and live trading must remain disabled until the separate release approval.
