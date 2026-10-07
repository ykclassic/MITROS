# MITROS Phase 1 — Institutional Market Data

Phase 1 establishes the trust boundary for all downstream MITROS intelligence.

## Invariants

A candle can enter the verified pipeline only when:

1. asset, venue and timeframe are canonical;
2. all timestamps are timezone-aware;
3. close_time is after open_time;
4. candle duration exactly matches the canonical timeframe;
5. OHLC values are positive and internally consistent;
6. volume is non-negative when present;
7. the candle is completed;
8. the candle is not stale;
9. the provider is explicitly mapped to the requested canonical symbol;
10. source, source version, observation time, receipt time, request ID and checksum are retained.

If verification fails, MITROS fails closed. No feature, regime, strategy signal or trade proposal should be produced from the failed batch.

## Provider routing

Provider order is deterministic. A provider is accepted only when its response produces at least one verified candle. Empty, invalid, future or stale provider data is not an implicit source of truth.

Failover is deterministic and observable. The accepted batch emits a MarketDataUpdated event containing the accepted provider provenance.

## Canonical checksum

The accepted candle batch receives a SHA-256 checksum over normalized OHLCV values and timestamps. This supports deterministic research and incident reconstruction.

## Current boundary

Phase 1 owns ingestion, normalization, validation, freshness, provider routing and provenance-bearing events. Persistence adapters and production provider configuration can be layered over this boundary without allowing providers to bypass verification.

## Exit criteria

- invalid OHLCV is rejected;
- future candles are rejected;
- incomplete candles are rejected;
- stale candles are rejected;
- duplicate candles are deterministically removed;
- provider fallback is deterministic;
- canonical symbol mappings are mandatory;
- every accepted candle carries provenance;
- accepted batches emit MarketDataUpdated;
- downstream layers receive only VERIFIED candles.
