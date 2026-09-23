# Phase 4 — CRT Strategy

MITROS Phase 4 adds a deterministic Candle Range Theory (CRT) strategy plugin.

## Signal definition

The immediately preceding verified candle is the reference range.

- Bullish CRT: the latest candle trades below the reference low and closes back above the reference low. The reference high is the analytical opposing-range target.
- Bearish CRT: the latest candle trades above the reference high and closes back below the reference high. The reference low is the analytical opposing-range target.
- Neutral: neither sweep-and-reclaim condition is confirmed.

## Safety boundary

CRT produces a StrategyVote only. It does not calculate position size, approve risk, create a TradeProposal, approve a trade, or submit an order.

## Data integrity

The strategy fails closed unless all candles are VERIFIED, timestamps are strictly increasing, and asset, venue, and timeframe are consistent.

## Versioning

The canonical plugin identifier is crt@1.0.0.
