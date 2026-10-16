# Phase 4 Account Providers and Verification Runbook

## Safety invariants

- PR #74 must remain open and unmerged until every required CI job and the controlled authenticated verification are explicitly successful.
- The existing Render service and production Supabase project are outside the scope of these checks and must not be changed.
- Keep `MITROS_XT_LIVE_ORDERS_ENABLED=false` and `MITROS_LIVE_TRADING_ENABLED=false`. The Bitget adapter is GET-only and cannot submit orders.
- Do not expose credentials, authorization headers, signatures, response bodies, or secret-bearing exception text in logs.

## Provider selection

Set `MITROS_ACCOUNT_EXCHANGE` to one of:

- `xt.com`: the existing XT account adapter and current execution venue.
- `bybit`: the Bybit V5 read-only account adapter.
- `bitget`: the Bitget Unified Trading Account (UTA) read-only account adapter.
- `simulated`: deterministic fixtures only on an explicitly permitted non-production verification/development environment.

Bitget verification requires `MITROS_BITGET_API_KEY`, `MITROS_BITGET_API_SECRET`, and `MITROS_BITGET_API_PASSPHRASE`. The optional `MITROS_BITGET_BASE_URL` defaults to `https://api.bitget.com`. Create a dedicated API key with read-only permissions and no trade, transfer, or withdrawal permissions. Bitget recommends IP binding; GitHub-hosted runner egress IPs may change, so use a stable, controlled runner or carefully managed allowlist if IP binding is enabled.

The adapter signs GET requests using Bitget's documented HMAC-SHA256/Base64 scheme, checks the API key's explicit read-only permission type, rejects non-read-only keys, fetches unified-account assets and BTC equity, and uses a public BTC/USDT ticker to validate freshness and value per-asset balances in BTC. API failures expose only sanitized reason codes and HTTP status, never response bodies or credential material.

Bitget API access is not guaranteed from every server or region. The protected authenticated smoke test is the evidence required for the actual runner environment; public market-data access alone does not establish authenticated account access.

## Authenticated Bitget smoke test

The `Authenticated Bitget Read-Only Smoke Test` workflow verifies the exact current head SHA of PR #74, checks the presence of credentials in the protected `production-verification` environment without logging values, records the runner's public egress IP, and runs `scripts/verify_bitget_readonly.py`.

The verification checks:

1. The authenticated account-info endpoint responds and does not report known write authorities.
2. The account snapshot is positive and fresh.
3. The BTC/USDT ticker price is positive and its exchange observation timestamp is fresh.

A successful smoke test proves Bitget read-only connectivity only. It does not prove full Phase 4 readiness or authorize approval/execution; verified market data, risk audit, proposal lifecycle and all other release gates remain independent.

## Isolated PostgreSQL integration tests

The CI job provisions an ephemeral PostgreSQL service with a database named `mitros_test_db`. It applies the repository's real foundation and Phase 4 migration files to that database before tests run:

- `20261007222136_0001_mitros_foundation.sql`
- `20261010174746_0010_phase4_risk_decision_audit.sql`
- `20261010174748_0011_phase4_xt_portfolio_snapshots.sql`
- `20261010174751_0012_phase4_proposal_lifecycle.sql`
- `20261010200000_0013_phase4_xt_protection_monitor.sql`

The integration test guard refuses non-local hosts and database names without `mitros_test`. The tests verify snapshot persistence/read-back and durable rejected-risk audit persistence without creating a trade proposal. They do not connect to production.

## Release posture

**HOLD.** No merge or production deployment is authorized by these verification steps. The existing production Render service and Supabase database must remain untouched, and live trading must remain disabled until the separate release approval.
