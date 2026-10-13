# Phase 4 Account Providers

Phase 4 obtains authoritative portfolio state through the account-provider registry. The provider supplies a read-only account snapshot, a BTC/USDT valuation price, and a current bid/ask/last quote. Verified candle data remains a separate required input.

## Provider selection

Set `MITROS_ACCOUNT_EXCHANGE` to one of:

- `xt.com` — existing XT.com account adapter and current execution venue.
- `bybit` — Bybit V5 read-only account adapter. This adapter implements GET requests only and validates that the API key reports `readOnly=1`.
- `simulated` — deterministic account fixture for controlled verification only.

### Simulated verification

Set all of the following only on a non-production verification target:

```dotenv
MITROS_ENVIRONMENT=verification
MITROS_ACCOUNT_EXCHANGE=simulated
MITROS_PHASE4_SIMULATED_ACCOUNT_ENABLED=true
MITROS_EXECUTION_MODE=paper
MITROS_LIVE_TRADING_ENABLED=false
MITROS_XT_LIVE_ORDERS_ENABLED=false
```

The simulated adapter is rejected unless the explicit enable flag is true and `MITROS_ENVIRONMENT` is one of `test`, `verification`, `staging`, `development`, or `local`. It uses deterministic fixture balances and prices; these are not exchange data and must never be represented as production account state.

The database and complete Phase 4 risk-policy configuration are still required for persisted risk-decision tests. The market-data readiness check also remains independent and must pass with verified candles. A simulated account does not suppress or bypass market-data, freshness, risk, audit, or schema gates.

### Bybit read-only account access

Configure `MITROS_ACCOUNT_EXCHANGE=bybit` and set:

- `MITROS_BYBIT_API_KEY`
- `MITROS_BYBIT_API_SECRET`
- Optional `MITROS_BYBIT_BASE_URL` (defaults to `https://api.bybit.com`)

Create a dedicated Bybit API key with read-only permissions and no order, transfer, or withdrawal permissions. The adapter checks Bybit's API-key information endpoint and rejects the account if `readOnly` is not `1`. The adapter reads Unified Trading Account balances and spot tickers only; it does not place orders or mutate account settings.

## Approval and execution boundary

The current execution gateway remains XT-specific. Human approval and execution endpoints therefore return HTTP 409 when the selected account provider is not `xt.com`. This prevents a simulated or Bybit account snapshot from authorizing an order on a different venue. A future Bybit execution integration would require a separate implementation and venue-bound approval/revalidation tests.

## Verification

Run the focused suite:

```bash
python -m pytest \
  tests/unit/test_account_providers.py \
  tests/unit/test_xt_account.py \
  tests/unit/test_phase4_api_guard.py -q
```

Do not merge until required CI is green and authenticated end-to-end verification has passed on a separate controlled target. Keep production configuration unchanged and live trading disabled during this work.
