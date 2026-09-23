from datetime import datetime, timezone
from uuid import UUID

from contracts.domain import TradeProposal
from contracts.events import EventEnvelope, EventType


def trade_proposal_created_event(
    proposal: TradeProposal,
    *,
    correlation_id: UUID,
    recorded_at: datetime | None = None,
) -> EventEnvelope:
    recorded = recorded_at or datetime.now(timezone.utc)
    return EventEnvelope(
        event_type=EventType.TRADE_PROPOSAL_CREATED,
        aggregate_id=proposal.id,
        occurred_at=proposal.created_at,
        recorded_at=recorded,
        producer="trade-proposal",
        producer_version="1.0.0",
        correlation_id=correlation_id,
        payload={
            "asset": proposal.asset,
            "venue": proposal.venue,
            "direction": proposal.direction.value,
            "entry": str(proposal.entry),
            "stop": str(proposal.stop),
            "target": str(proposal.target),
            "position_size": str(proposal.position_size),
            "risk_reward": str(proposal.risk_reward),
            "expires_at": proposal.expires_at.isoformat(),
        },
        provenance=[{"source": "trade-proposal-builder", "version": "1.0.0"}],
    )
