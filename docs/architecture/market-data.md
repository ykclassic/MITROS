# Phase 1 — Market Data Foundation

## Authority
Market data is the authoritative upstream state for MITROS. Provider responses are external observations; MITROS normalizes and records them without silently inventing values.

## Provider boundary
Adapters implement MarketDataProvider. Current foundation adapters cover Twelve Data, Finnhub and Alpha Vantage. API keys are server-side configuration only.

## Canonical rules
1. Provider timestamps are preserved as observed_at; received_at is separate.
2. Symbol mappings are explicit per provider; missing mappings fail closed.
3. Only completed candles enter the authoritative candle stream.
4. OHLC relationships and non-negative volume are validated.
5. Freshness is evaluated against a configurable age threshold.
6. Provider failover is deterministic by configured priority.
7. Every persisted observation carries provider/version and provenance.
8. No downstream strategy may fetch a provider directly; all access goes through the market-data package/service.
9. Provider outages or malformed data produce an explicit unavailable/stale state, never a fabricated fallback.
10. Duplicate observations must be idempotently persisted using canonical asset/venue/timeframe/open-time identity.

## Initial supported provider roles
- Twelve Data: general time-series/quote adapter
- Finnhub: quote/candle adapter
- Alpha Vantage: quote/intraday/crypto-intraday adapter

Provider availability and supported symbols are configuration facts, not assumptions; integration tests must exercise each configured mapping against a controlled response fixture, while production verification uses provider credentials.
