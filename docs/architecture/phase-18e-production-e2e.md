# Phase 18E — Production E2E

Production E2E validates the complete read-only product surface across the deployed Vercel and Render boundary.

## Required checks

- Vercel deployment and all product routes are reachable.
- Vercel same-origin market, readiness, risk, intelligence and research proxies reach Render.
- BTC/USD and ETH/USD quote contracts retain provider, positive price, observed_at, received_at and VERIFIED quality.
- CORS and preflight continue to allow the actual Vercel origin.
- Provider credentials are not exposed to browser HTML.
- Intelligence is computed from at least the feature engine's required history and exposes regime/consensus state.
- Grounded research exposes evidence checksums.
- Risk assessment remains read-only and grants no execution authority.
- Approval and execution mutation endpoints are absent from the browser API boundary.

The deployment suite intentionally exercises the production URLs rather than mocks.
