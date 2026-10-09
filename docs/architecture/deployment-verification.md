# Production deployment verification

MITROS production has two public boundaries:

- Vercel frontend: `https://mitros.vercel.app`
- Render API: `https://mitros.onrender.com`

The browser-facing `NEXT_PUBLIC_MITROS_API_URL` must resolve to the Render API. Provider credentials and the Supabase service-role key must remain server-side.

## Required end-to-end verification

The production E2E suite in `tests/deployment/test_production_deployment.py` verifies:

1. Vercel's public login page is reachable and protected product pages do not bypass authentication.
2. Render health is reachable and returns `200`.
3. Render CORS explicitly permits the production Vercel origin and quote-route preflight succeeds.
4. Unauthenticated backend product routes return `401`.
5. Public Coinbase Advanced and Kraken OHLC endpoints return non-empty candles for BTC/USD and ETH/USD across 15m, 1h and 4h.
6. The authenticated Phase 2 matrix returns BTC/USD and ETH/USD snapshots across 15m, 1h and 4h. Every case must return `200`, `VERIFIED` quality, allowed provider provenance, a batch checksum, observation checksums, snapshot checksum, input checksums, engine/configuration versions and an observation window.
7. Trade probability is not exposed until statistically calibrated resolved outcomes exist.
8. Browser HTML does not expose provider credential names or common credential material.

The authenticated matrix requires the `MITROS_PRODUCTION_ACCESS_TOKEN` GitHub Actions secret. The test fails if that secret is absent; it must never silently skip the authenticated production gate.

## Persistence contract

A successful verified Phase 1 batch must be durably persisted before the API reports success. A successful Phase 2 snapshot must persist:

- canonical candles and market-data observations;
- observation manifests with checksums and provider provenance;
- versioned feature and regime snapshots;
- strategy signals and multi-timeframe evidence;
- a versioned intelligence snapshot with input checksums, engine/configuration versions, observation window and provenance.

Persistence failures remain fail-closed and return an unavailable response rather than an unpersisted success.

## Environment boundaries

- Vercel: `NEXT_PUBLIC_MITROS_API_URL=https://mitros.onrender.com`
- Render: `MITROS_ALLOWED_ORIGINS=https://mitros.vercel.app,...`
- Render only: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, database URL and provider credentials.

Do not copy provider credentials or the service-role key into Vercel `NEXT_PUBLIC_*` variables or the repository. Production diagnostics must redact credentials and sensitive response bodies.
