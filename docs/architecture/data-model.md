# Canonical data model

Core entities: assets, venues, market_data, candles, market_events, features, regimes, strategies, strategy_versions, strategy_signals, strategy_votes, strategy_performance, models, model_versions, model_predictions, model_validation, model_drift, trade_proposals, risk_decisions, approvals, orders, executions, fills, positions, portfolio_snapshots, risk_snapshots, trade_outcomes, signal_outcomes, strategy_attribution, research_queries, research_answers, research_evidence, system_events and audit_events.

Postgres is authoritative durable state. JSONB is permitted for versioned payloads/evidence; high-value query fields remain typed.
