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

## Phase 1 completion hardening

The Phase 1 exit gate is enforced by the verified market-data boundary:

1. **Continuity and incomplete candles** — every adjacent candle must advance exactly one canonical timeframe; a missing interval is classified as `INCOMPLETE`. A candle whose close is in the future is also `INCOMPLETE`.
2. **Operational quality state machine** — `DataQualityStateMachine` defines admissible transitions and deterministic classification for verified, stale, incomplete, conflicted, invalid, degraded and unavailable observations.
3. **Provider authority** — `market_data_provider_routes` stores primary/secondary/emergency roles, priority, supported venues/timeframes, cross-validation and authority conditions. Runtime routing can load this policy directly from Postgres.
4. **Canonical mappings** — production seed data establishes canonical `BTC/USD`, `ETH/USD`, and `SOL/USD` assets on the `spot` venue with explicit provider symbol mappings.
5. **Canonical observation contracts** — Candle/Quote now carry explicit symbols and sequences; Trade, OrderBook, Funding and OpenInterest contracts are defined with provenance fields.
6. **Observation checksums and manifests** — every verified candle receives an observation SHA-256 checksum. A batch manifest and batch checksum are emitted with `MarketDataUpdated`.
7. **Durable persistence** — `PostgresVerifiedMarketDataRepository` persists only `VERIFIED` observations and the manifest, and can reconstruct the source/provider/request/checksum provenance for a stored observation.
8. **Downstream fail-closed gate** — downstream consumers must receive `VERIFIED` observations with checksums; empty, degraded, stale, incomplete or conflicted data is blocked.
9. **Verification workflow** — `.github/workflows/phase1-verification.yml` independently runs the Phase 1 unit/integration suite, strict lint/type checks and migration-contract checks.

### Reconstruction target

For any stored observation, MITROS can reconstruct:

`observation → canonical asset/venue/timeframe → provider/provider version → provider symbol → observed_at/received_at → request_id → observation checksum → batch checksum → data quality`

No intelligence or execution stage should bypass this boundary.
