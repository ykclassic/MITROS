# MITROS

Market Intelligence and Trading Operating System.

Phase 0 establishes the canonical architecture, contracts, data model, event model, execution boundaries, provenance requirements, testing gates, and deployment boundaries. Legacy production code is intentionally not imported in Phase 0.

Phase 1 establishes authoritative market-data ingestion, normalization, validation, freshness, deterministic provider failover, and provenance-bearing MarketDataUpdated events.

Phase 2 establishes the deterministic feature / indicator engine. It consumes only completed, VERIFIED Phase 1 candles and emits versioned FeatureSnapshot records plus FeaturesComputed events. The canonical technical feature set is versioned independently so strategies can consume stable feature contracts without embedding indicator calculations.
