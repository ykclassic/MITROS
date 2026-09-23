# Phase 16 — Production Hardening

Phase 16 hardens MITROS operational boundaries without changing trading authority.

## Runtime safety

Production configuration is fail-closed:
- paper mode is the default
- live mode requires explicit enablement
- live mode additionally requires explicit operator acknowledgement
- invalid combinations are rejected before runtime use

## Readiness

Readiness is separate from liveness. A readiness report evaluates registered dependency probes and is NOT_READY if any probe fails or raises. Probe exceptions are sanitized so operational secrets are not returned through health surfaces.

## Failure containment

The circuit breaker opens after a configured number of operational failures and blocks further work until explicitly reset. It is intentionally fail-closed and does not grant or revoke trade approval.

## Secret hygiene

Operational mappings can be recursively redacted before logging or diagnostics. Sensitive values are never returned as probe exception details.

## Authority boundary

Production hardening cannot:
- create or approve trade proposals
- change risk limits
- bypass human approval
- submit orders
- reconcile venue state as authoritative
- mutate the execution ledger

The existing execution gateway and durable ledger remain the only path toward venue interaction.
