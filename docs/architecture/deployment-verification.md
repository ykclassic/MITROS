# Production deployment verification

MITROS production has two public boundaries:

- Vercel: `https://mitros.vercel.app`
- Render API: `https://mitros.onrender.com`

The browser-facing `NEXT_PUBLIC_MITROS_API_URL` must resolve to the Render API. Provider credentials are never valid browser configuration; the only public frontend environment value required for this integration is the API URL.

## Verification contract

The production E2E suite in `tests/deployment/test_production_deployment.py` verifies:

1. Vercel is reachable.
2. Render health is reachable.
3. Render CORS explicitly permits the production Vercel origin.
4. CORS preflight for the quote endpoint succeeds.
5. All three configured providers (Twelve Data, Finnhub, Alpha Vantage) are present at runtime without exposing whether the credential value itself is secret. Provider availability is recorded by the same endpoint; transient provider-side rate limits do not make credential configuration appear missing.
6. BTC/USD and ETH/USD return a positive price, provider provenance, provider quote timestamp, receipt timestamp, and `VERIFIED` quality.
7. The Vercel HTML does not expose provider credential variable names or common credential material.
8. The production URL contract remains explicit, so a deployment URL change forces a test update.

The market UI fetches BTC/USD and ETH/USD independently. One asset failure no longer suppresses the other asset's result, and each failed row reports its own sanitized HTTP/API failure state.

## Environment boundaries

- Vercel: `NEXT_PUBLIC_MITROS_API_URL=https://mitros.onrender.com`
- Render: `MITROS_ALLOWED_ORIGINS=https://mitros.vercel.app,...`
- Render only: `MITROS_MARKET_TWELVEDATA_API_KEY`, `MITROS_MARKET_FINNHUB_API_KEY`, `MITROS_MARKET_ALPHAVANTAGE_API_KEY`

Do not copy provider credentials into Vercel `NEXT_PUBLIC_*` variables or the repository.
