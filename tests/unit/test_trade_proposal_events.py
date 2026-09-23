from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from contracts.domain import Direction, StrategyVote
from contracts.risk import RiskAssessment
from contracts.signal import SignalRecord
from packages.approval.events import approval_granted_event
from packages.approval.manager import HumanApprovalManager
from packages.proposals.builder import TradeProposalBuilder
from packages.proposals.events import trade_proposal_created_event


def test_trade_proposal_and_approval_events_are_canonical() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    signal = SignalRecord(
        asset="BTC/USDT",
        venue="paper",
        direction=Direction.LONG,
        created_at=now,
        expires_at=now.replace(hour=1),
        strategy_votes=(
            StrategyVote(
                strategy_id="crt",
                strategy_version="1.0.0",
                direction=Direction.LONG,
                confidence=Decimal("0.7"),
            ),
        ),
        confidence=Decimal("0.7"),
    )
    risk = RiskAssessment(
        approved=True,
        requested_size=Decimal("1"),
        approved_size=Decimal("1"),
        checks=(),
        reasons=("all risk checks passed",),
        risk_score=Decimal("0.1"),
    )
    proposal = TradeProposalBuilder().build(
        signal,
        risk,
        entry=Decimal("100"),
        stop=Decimal("90"),
        target=Decimal("110"),
        regime="trend_up",
        mtf_alignment=Decimal("0.8"),
        data_quality=Decimal("1"),
        now=now,
    )
    correlation_id = uuid4()
    created = trade_proposal_created_event(
        proposal, correlation_id=correlation_id, recorded_at=now
    )
    outcome = HumanApprovalManager().approve(
        proposal,
        actor="human:test",
        reason="reviewed",
        idempotency_key="event-1",
        now=now,
    )
    granted = approval_granted_event(
        outcome, correlation_id=correlation_id, recorded_at=now
    )
    assert created.event_type.value == "TradeProposalCreated"
    assert created.aggregate_id == proposal.id
    assert granted.event_type.value == "ApprovalGranted"
    assert granted.aggregate_id == proposal.id
    assert granted.payload["actor"] == "human:test"
