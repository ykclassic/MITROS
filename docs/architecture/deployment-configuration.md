# MITROS Deployment & Configuration Foundation

## Deployment boundary

MITROS uses four explicit operational boundaries:

- **GitHub Actions** — source control, CI gates, branch governance and deployment automation metadata. It must not become the runtime secret store.
- **Vercel** — browser-facing web/API boundary. Only browser-safe configuration may use `NEXT_PUBLIC_*` names.
- **Render** — long-running backend/workers and the isolated execution boundary. Provider credentials and server-only secrets belong here.
- **Supabase/Postgres** — authentication, RLS, durable persistence, execution ledger and audit data.

A secret is stored only in the platform/service that requires it. Production credentials are never committed to Git, CI logs, browser bundles or public configuration.

## GitHub Actions

Required repository/org secrets for future deployment automation:

- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_DB_PASSWORD`
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `RENDER_API_KEY`
- `RENDER_OWNER_ID`

Optional:

- `CODECOV_TOKEN`

GitHub Actions variables may contain non-secret build metadata such as `PYTHON_VERSION=3.12` and `MITROS_ENVIRONMENT=ci`.

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
- `MITROS_MARKET_TWELVEDATA_API_KEY`
- `MITROS_MARKET_FINNHUB_API_KEY`
- `MITROS_MARKET_ALPHAVANTAGE_API_KEY`
- `MITROS_MARKET_FRESHNESS_SECONDS=120`
- `MITROS_APP_SECRET`
- `MITROS_APPROVAL_SECRET`
- `MITROS_INTERNAL_API_SECRET` when Vercel-to-Render service authentication is enabled
- `MITROS_FRONTEND_URL`
- `MITROS_ALLOWED_ORIGINS`
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
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Server-only Vercel configuration, if needed:

- `MITROS_API_INTERNAL_URL`
- `MITROS_INTERNAL_API_SECRET`

Never expose `SUPABASE_SERVICE_ROLE_KEY`, provider API keys, approval secrets, application secrets, database credentials or MT5 credentials through `NEXT_PUBLIC_*`.

## Naming rules

- Backend/runtime configuration uses the `MITROS_*` namespace.
- Market-data credentials use the existing `MITROS_MARKET_*` namespace.
- Browser-exposed configuration must use `NEXT_PUBLIC_*` and contain no secrets.
- Empty/absent secrets are preferable to placeholder credentials in production.
- Secrets must be injected by the deployment platform, not committed to the repository.

## CI safety checks

CI validates the configuration contract and rejects accidental credential material in tracked example/configuration files. CI does not require production credentials to run unit tests.

## Provisioning order

1. Create/configure Supabase project and obtain the project URL and server-side credentials.
2. Configure GitHub deployment secrets only for actions that actually need them.
3. Configure Render server-side runtime variables and provider credentials.
4. Configure Vercel public variables and any required server-only integration secret.
5. Keep execution in paper mode until the isolated execution service and all later production-readiness gates are complete.
