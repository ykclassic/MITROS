# MITROS Architecture — Frozen Phase 0

MITROS is a modular market-intelligence and trading operating system, not a merge of twelve legacy applications.

Authoritative flow:
Market Data → Features → Regime → Strategy Plugins → MTF/Strategy Consensus → Risk Engine → Trade Proposal → Human Approval → Execution Gateway → Reconciliation/Ledger → Outcome/Learning.

Vercel: web application, research/copilot UX, proposal review/approval UX and authenticated BFF.
Render: long-running ingestion, scanners, signal/ML workers, backtests, reconciliation, notifications and isolated execution workers.
Supabase: PostgreSQL, Auth, RLS, durable state, intelligence records, trade ledger, audit/event storage and realtime subscriptions.

AI is generative intelligence only and cannot silently mutate verified market state.
