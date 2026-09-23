# MITROS repository structure

apps/web/ — Next.js/Vercel application
apps/api/ — authenticated BFF/API boundary
services/market-data/ — Render ingestion
services/signal-engine/ — Render scanning/consensus
services/risk-engine/ — Render risk worker
services/execution-gateway/ — isolated execution
services/reconciliation/ — durable reconciliation
services/research-engine/ — deterministic research
services/intelligence-worker/ — ML/statistical jobs
services/notification-worker/ — outbound notifications

packages/contracts/ — versioned domain/event schemas
packages/market-data/ — providers and normalization
packages/features/ — feature/indicator calculations
packages/strategies/ — strategy plugin implementations
packages/consensus/ — MTF and strategy consensus
packages/regime/ — regime detection
packages/risk/ — independent risk rules
packages/models/ — model lifecycle
packages/execution/ — gateway contracts/adapters
packages/portfolio/ — exposure/correlation
packages/research/ — research primitives
packages/provenance/ — traceability
packages/observability/ — logging/metrics/tracing

infrastructure/supabase/ — database migrations/policies/functions
infrastructure/render/ — worker deployment configuration
infrastructure/vercel/ — web deployment configuration
tests/ — unit, contract, integration, replay, backtest, paper, sandbox and e2e
docs/ — architecture, ADRs, strategy/risk/execution/research specifications
