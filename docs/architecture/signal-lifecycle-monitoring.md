# Phase 10 — Signal lifecycle and monitoring

Signals are explicit, versioned state machines. Legal transitions are fail-closed and timestamp-monotonic.

Lifecycle management records every transition with actor, reason and timestamp. Monitoring is read-only operational observability: population counts, mean confidence, stale active signals and alerts.

Monitoring cannot approve, reject, size, submit or execute an order. The MT5 gateway remains the only execution authority.

Phase 10 therefore adds observability without weakening the frozen Strategy -> Risk -> Human Approval -> MT5 Execution boundary.
