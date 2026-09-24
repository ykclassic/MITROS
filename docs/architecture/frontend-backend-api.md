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
