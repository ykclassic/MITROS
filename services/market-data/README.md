# Market Data Ingestor

Responsibilities:
- retrieve provider market data through canonical adapters
- normalize symbols and timestamps
- reject malformed OHLCV
- exclude incomplete candles
- assess freshness
- fail over across configured providers
- emit MarketDataUpdated only for authoritative completed observations

This worker never computes trading signals, risk, approvals or orders.
