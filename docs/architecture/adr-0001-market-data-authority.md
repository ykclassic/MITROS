# ADR-0001: Canonical Market Data Authority

Status: Accepted

MITROS will expose one market-data abstraction to all downstream components. Provider adapters remain replaceable, but normalized completed candles and provider provenance are the only inputs eligible for deterministic strategy calculations.

Reason: the twelve source repositories contain duplicated exchange/data clients and differing timestamp/freshness assumptions. A single boundary prevents divergence and makes failover auditable.
