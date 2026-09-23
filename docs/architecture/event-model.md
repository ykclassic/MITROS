# Event model

MarketDataUpdated → FeaturesComputed → RegimeDetected → StrategySignalGenerated → ConsensusEvaluated → RiskEvaluated → TradeProposalCreated → ApprovalGranted → OrderSubmitted → OrderFilled → PositionUpdated → TradeClosed → OutcomeRecorded → StrategyPerformanceUpdated.

Events are immutable facts. Commands request actions. Every event has aggregate_id, correlation_id, optional causation_id, producer/version, schema_version, timestamps, payload and provenance. Consumers must be idempotent.
