# Render worker boundaries
market-data-ingestor: provider ingestion, completed candles, freshness/failover.
signal-scanner: features, regime, strategy plugins and consensus.
risk-worker: independent risk evaluation and circuit breakers.
research-worker: deterministic research and evidence assembly.
ml-worker: training, validation, inference artifacts and drift.
backtest-worker: replay, walk-forward, purged validation, stress tests.
execution-gateway: isolated venue submission and reconciliation; no strategy logic.
reconciliation-worker: external state vs ledger recovery.
notification-worker: Discord/email/webhooks only.
scheduler: emits jobs/events; no business logic.
Workers must be idempotent, observable, restart-safe and timeout-bounded.
