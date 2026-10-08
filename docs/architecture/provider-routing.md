# MITROS Provider Routing

## Production authority

1. Kraken — PRIMARY, priority 1
2. Coinbase Exchange — SECONDARY, priority 2
3. CoinGecko — EMERGENCY / independent validation, priority 3 for 1h and 4h

Legacy TwelveData, Finnhub, and AlphaVantage routes are inactive for canonical crypto authority.

## Canonical timeframes

Kraken and Coinbase are authoritative for 15m, 1h, and 4h. CoinGecko is deliberately limited to 1h and 4h. Its market-chart price series is deterministically reconstructed into hourly OHLC buckets and then 4h buckets; it is not used for 15m authority.

## Verification

Every provider response still passes completed-candle filtering, future timestamp rejection, freshness, continuity, observation checksum, provenance, and the downstream verified-data gate.

Primary cross-validation uses a configurable price tolerance of 0.01 (1%) by default. A material disagreement raises CONFLICTED and blocks downstream intelligence.

## Secrets

Coinbase and Kraken public market-data adapters require no API credential. CoinGecko uses the optional server-side MITROS_MARKET_COINGECKO_API_KEY when configured.
