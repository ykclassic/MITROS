# Frontend and Backend API

## Phase 18 boundary

MITROS now has a Vercel-oriented Next.js frontend and a Render-oriented FastAPI backend.

The frontend is observational: it displays verified backend state and never holds provider credentials, approval tokens, database service-role credentials or broker credentials.

The backend API is read-only in this phase:
- GET /health
- GET /api/v1/operations/readiness
- GET /api/v1/market/quote?asset=...
- GET /api/v1/market/health

Market quotes are obtained only through the canonical provider router from Phase 1. Provider failures remain fail-closed.

This phase does not add proposal approval, risk mutation, order submission or broker execution endpoints.
