# MITROS API

FastAPI backend for the browser-facing Vercel application.

## Boundary

The API is read-only in this phase. It exposes health, operational readiness, market quotes and provider health. It does not approve proposals, change risk limits, submit orders, or execute trades.

Run locally with:

`uvicorn packages.api.app:app --reload`

The runtime belongs on Render. Provider credentials are server-side environment variables and are never exposed to the browser.
