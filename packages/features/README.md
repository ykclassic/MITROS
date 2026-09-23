# Feature / Indicator Engine

Phase 2 provides deterministic, look-ahead-safe technical features from the Phase 1 canonical Candle contract.

The engine:
- requires completed, VERIFIED candles;
- sorts candles by open_time and rejects duplicate timestamps;
- requires at least 50 candles for the canonical set;
- uses only data at or before the latest completed candle;
- emits a versioned, immutable FeatureSnapshot;
- carries provider provenance into the FeaturesComputed event.

Canonical v1.0.0 features:
return_1, sma_20, ema_20, ema_50, rsi_14, macd_12_26, macd_signal_9, macd_histogram_12_26_9, atr_14, bb_mid_20, bb_upper_20, bb_lower_20, bb_width_20.
