# Frontend and Backend API

## Phase 18A production boundary

MITROS uses a single browser-facing API contract. Production browser requests are same-origin (/api/...) and are rewritten by the Next.js deployment to the Render API origin.

The frontend is observational and does not hold provider credentials, approval tokens, database service-role credentials or broker credentials.

### Rules

- Browser code never embeds the Render URL in production requests.
- Market and Operations use the same centralized API client.
- The Next.js rewrite is the production browser-to-Render routing mechanism.
- FastAPI remains read-only at this boundary.
- Provider failures remain fail-closed.
- CORS is restricted to configured frontend origins; local development falls back to localhost only.

### Read-only API contract

- GET /health
- GET /api/v1/operations/readiness
- GET /api/v1/market/quote?asset=...&venue=spot
- GET /api/v1/market/health

Production deployment verification must exercise both the direct Render API and the Vercel same-origin proxy path.


## Phase 19 authentication boundary

All product APIs under `/api/v1/*` require an authenticated Supabase access token.

The browser never calls Render directly. Next.js `/api/[...path]` authenticates the cookie session, obtains the current access token, and forwards it to FastAPI. FastAPI independently verifies the token signature, issuer, audience, expiry and subject before serving product data.

Unauthenticated requests fail with HTTP 401. Authentication configuration failures fail closed rather than downgrading to anonymous access.

The public health endpoint remains `/health` only. It reports service liveness and does not expose market data, provider health, intelligence, research or trading state.
