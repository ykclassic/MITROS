# Phase 8 — Advanced Risk / Portfolio Engine

Phase 8 introduces an independent portfolio risk gate.

## Controls
The engine evaluates proposed position size, gross exposure, daily loss, asset concentration, leverage, drawdown, and spread.

## Fail-closed behavior
Invalid risk inputs raise errors. Any breached limit produces zero approved size.

## Architecture boundary
The risk engine is independent from strategy consensus and AI/ML. It consumes their outputs only as evidence. It does not approve human authorization and has no execution capability.
