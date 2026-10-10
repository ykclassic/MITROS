# MITROS Deployment & Configuration Foundation

## Deployment boundary
MITROS uses four explicit operational boundaries:

- **GitHub Actions** — source control, CI gates, branch governance and deployment automation metadata. It must not become the runtime secret store.
- **Vercel** — browser-facing web/API boundary. Only browser-safe configuration may use `NEXT_PUBLIC_*` names.
- **Render** — long-running backend/workers and the isolated execution boundary. Provider credentials and server-only secrets belong here.
- **Supabase/Postgres** — authentication, RLS, durable persistence, execution ledger and audit data.

A secret is stored only in the platform/service that requires it. Production credentials are never committed to Git, CI logs, browser bundles or public configuration.

## GitHub Actions

Required repository/org secrets for deployment automation:

- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_DB_PASSWORD`
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `RENDER_API_KEY`
- `RENDER_OWNER_ID`

Production E2E authentication uses a dedicated, least-privilege Supabase test user. Configure these repository secrets for the `deployment-e2e` job:

- `MITROS_E2E_SUPABASE_URL` — URL of the same Supabase project configured in the Render API.
- `MITROS_E2E_SUPABASE_PUBLISHABLE_KEY` — that project's publishable/anon key; never use a service-role key here.
- `MITROS_E2E_USER_EMAIL` — email of the dedicated E2E test user.
- `MITROS_E2E_USER_PASSWORD` — password for that dedicated test user.

The workflow signs in through Supabase Auth at runtime, keeps the returned access token in process memory, and passes it only to the production test process. The token and authentication response body are not printed. Do not use a personal account; keep the E2E account unprivileged and do not grant it trading/execution permissions. If any required secret is absent or authentication fails, production E2E fails closed.

Optional:

- `CODECOV_TOKEN`

Do **not** place market-data API keys, Supabase service-role keys, application secrets, approval secrets, broker credentials or MT5 credentials in GitHub unless a narrowly scoped deployment action explicitly requires them. Runtime secrets remain in the target runtime.

## Render

The Render backend/worker environment is the server-side runtime secret boundary.

### Required foundation configuration

- `MITROS_ENVIRONMENT=production`
- `MITROS_EXECUTION_MODE=paper`
- `MITROS_LIVE_TRADING_ENABLED=false`
- `MITROS_LIVE_TRADING_ACK` unset/empty while paper mode is active
- `MITROS_DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `MITROS_MARKET_TWELVEDATA_API_KEY`
- `MITROS_MARKET_FINNHUB_API_KEY`
- `MITROS_MARKET_ALPHAVANTAGE_API_KEY`
- `MITROS_MARKET_FRESHNESS_SECONDS=120`
- `MITROS_APP_SECRET`
- `MITROS_APPROVAL_SECRET`
- `MITROS_INTERNAL_API_SECRET` when Vercel-to-Render service authentication is enabled
- `MITROS_FRONTEND_URL`
- `MITROS_ALLOWED_ORIGINS`

### XT.com and Phase 4 risk configuration

For the current building phase, XT.com is the authoritative spot-account source. Keep the API key and secret in Render only:
- `MITROS_XT_API_KEY`
- `MITROS_XT_API_SECRET`
- `MITROS_XT_BASE_URL=https://sapi.xt.com`
- `MITROS_ACCOUNT_EXCHANGE=xt.com`
- `MITROS_XT_ACCOUNT_SCOPE_ID=xt.com:primary`
- `MITROS_XT_ACCOUNT_TYPE=spot`

Set the Phase 4 risk policy values from `.env.example`. These are runtime configuration, not secrets. Account snapshots and risk decisions require `MITROS_DATABASE_URL`.

Live order submission must remain disabled during this build phase:
- `MITROS_EXECUTION_MODE=paper`
- `MITROS_LIVE_TRADING_ENABLED=false`
- `MITROS_LIVE_TRADING_ACK` empty
- `MITROS_XT_LIVE_ORDERS_ENABLED=false`
- `MITROS_XT_PROTECTION_MONITOR_ENABLED=false`
- `MITROS_XT_PROTECTION_POLL_SECONDS=5`

No XT credentials are stored in this repository or GitHub Actions. Do not enable live orders by changing code; use the backend environment flags after the required testing and audit milestone.

- `MITROS_LOG_LEVEL=INFO`
- `MITROS_LOG_FORMAT=json`

The market-data worker may use the same server-side provider credentials, but credentials must never be returned to the browser.

### Live execution is intentionally reserved

The MT5 credentials are not required for the current paper-mode foundation. When the isolated MT5 execution service is introduced, credentials will be added only to that execution runtime:

- `MITROS_MT5_LOGIN`
- `MITROS_MT5_SERVER`
- `MITROS_MT5_PASSWORD`
- `MITROS_MT5_TERMINAL_PATH`

Live mode remains fail-closed and requires both `MITROS_LIVE_TRADING_ENABLED=true` and `MITROS_LIVE_TRADING_ACK=I_UNDERSTAND_LIVE_TRADING`.

## Vercel

Only public/browser-safe configuration may use `NEXT_PUBLIC_*`:

- `NEXT_PUBLIC_MITROS_API_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Server-only Vercel configuration, if needed:

- `MITROS_API_INTERNAL_URL`
- `MITROS_INTERNAL_API_SECRET`

Never expose `SUPABASE_SERVICE_ROLE_KEY`, provider API keys, approval secrets, application secrets, database credentials or MT5 credentials through `NEXT_PUBLIC_*`.

## Naming rules

- Backend/runtime configuration uses the `MITROS_*` namespace.
- Market-data credentials use the existing `MITROS_MARKET_*` namespace.
- Browser-exposed configuration must use `NEXT_PUBLIC_*` and contain no secrets.
- Empty/absent secrets are preferable to placeholder credentials in production.
- Secrets must be injected by the deployment platform, not committed to Git.

## CI safety checks

CI validates the configuration contract and rejects accidental credential material in tracked example/configuration files. CI does not require production credentials to run unit tests.

## Provisioning order

1. Create/configure Supabase project and obtain the project URL and server-side credentials.
2. Configure GitHub deployment secrets only for actions that actually need them.
3. Configure Render server-side runtime variables and provider credentials.
4. Configure Vercel public variables and any required server-only integration secret.
5. Keep execution in paper mode until the isolated execution service and all later production-readiness gates are complete.
