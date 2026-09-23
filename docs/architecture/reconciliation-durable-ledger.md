# Phase 13 — Reconciliation + Durable Execution Ledger

MITROS now treats execution as a recoverable state machine backed by an append-only execution ledger.

## Flow

Human Approval → Execution Intent → SUBMITTING → Venue Result → Reconciliation

An execution intent is persisted before a venue submission is attempted. The client order ID is the proposal UUID and is the idempotency key across retries.

## Ledger guarantees

- Intent creation is idempotent.
- A client order ID cannot be rebound to another proposal.
- State changes are append-only.
- Submission attempts are counted.
- Request fingerprints make order identity auditable.
- Process interruption can leave an explicit UNKNOWN state rather than falsely assuming failure or success.
- Venue reconciliation is authoritative for determining whether local state matches the venue.
- Missing venue orders are never treated as filled.
- Divergent venue/local state is surfaced instead of silently repaired.

## Safety boundary

The ledger never creates approval authority and never calls a strategy, risk engine, approval manager, or MT5 SDK. Reconciliation reads through the existing ExecutionGateway interface, preserving the gateway as the only venue boundary.

## Durable storage

Supabase/Postgres migration 0002_execution_ledger.sql adds durable intent, append-only entry, and reconciliation tables. Application code may use the same contracts against another durable repository later; the domain does not depend on Supabase.

## Recovery rule

If the process stops after recording SUBMITTING but before receiving a response, recovery must reconcile the client order ID before retrying. It must not blindly submit a second order.

## Live trading status

Phase 13 does not enable live MT5 trading. It provides the durability and recovery primitives required before live execution validation.
