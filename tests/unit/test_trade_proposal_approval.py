from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.approval import ApprovalDecision
from contracts.domain import Direction, StrategyVote
from contracts.risk import RiskAssessment
from contracts.signal import SignalRecord
from packages.approval.manager import HumanApprovalManager
from packages.proposals.builder import TradeProposalBuilder


def _signal(now: datetime) -> SignalRecord:
    return SignalRecord(
        asset="BTC/USDT",
        venue="paper",
        direction=Direction.LONG,
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        strategy_votes=(
            StrategyVote(
                strategy_id="smc",
                strategy_version="1.0.0",
                direction=Direction.LONG,
                confidence=Decimal("0.8"),
            ),
        ),
        confidence=Decimal("0.8"),
    )


def _risk() -> RiskAssessment:
    return RiskAssessment(
        approved=True,
        requested_size=Decimal("1"),
        approved_size=Decimal("1"),
        checks=(),
        reasons=("all risk checks passed",),
        risk_score=Decimal("0.1"),
    )


def _proposal(now: datetime):
    return TradeProposalBuilder().build(
        _signal(now),
        _risk(),
        entry=Decimal("100"),
        stop=Decimal("90"),
        target=Decimal("120"),
        regime="trend_up",
        mtf_alignment=Decimal("0.9"),
        data_quality=Decimal("1"),
        now=now,
    )


def test_proposal_requires_approved_risk_and_calculates_rr() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    proposal = _proposal(now)
    assert proposal.position_size == Decimal("1")
    assert proposal.risk_reward == Decimal("2")


def test_proposal_fails_closed_on_rejected_risk() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    rejected = _risk().model_copy(update={"approved": False, "approved_size": Decimal("0")})
    with pytest.raises(ValueError, match="approved risk"):
        TradeProposalBuilder().build(
            _signal(now), rejected,
            entry=Decimal("100"), stop=Decimal("90"), target=Decimal("120"),
            regime="trend_up", mtf_alignment=Decimal("0.9"),
            data_quality=Decimal("1"), now=now,
        )


def test_directional_price_levels_fail_closed() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="price levels"):
        TradeProposalBuilder().build(
            _signal(now), _risk(),
            entry=Decimal("100"), stop=Decimal("110"), target=Decimal("120"),
            regime="trend_up", mtf_alignment=Decimal("0.9"),
            data_quality=Decimal("1"), now=now,
        )


def test_human_approval_is_explicit_idempotent_and_does_not_execute() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    proposal = _proposal(now)
    manager = HumanApprovalManager()
    outcome = manager.approve(
        proposal,
        actor="human:alice",
        reason="Reviewed setup and risk",
        idempotency_key="approval-1",
        now=now + timedelta(minutes=1),
    )
    approved = manager.apply(proposal, outcome)
    assert outcome.decision is ApprovalDecision.APPROVED
    assert outcome.execution_authorized is True
    assert outcome.approval.approval_token
    assert approved.approval_status.value == "APPROVED"
    assert approved.execution_status.value == "NOT_AUTHORIZED"

    replay = manager.approve(
        proposal,
        actor="human:alice",
        reason="Reviewed setup and risk",
        idempotency_key="approval-1",
        now=now + timedelta(minutes=2),
    )
    assert replay.approval.id == outcome.approval.id

    with pytest.raises(ValueError, match="no longer pending"):
        manager.approve(
            approved,
            actor="human:alice",
            reason="second decision",
            idempotency_key="approval-2",
            now=now + timedelta(minutes=2),
        )


def test_rejection_records_reason_and_never_authorizes() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    outcome = HumanApprovalManager().reject(
        _proposal(now),
        actor="human:bob",
        reason="Setup invalidated",
        idempotency_key="reject-1",
        now=now + timedelta(minutes=1),
    )
    assert outcome.decision is ApprovalDecision.REJECTED
    assert outcome.execution_authorized is False
    assert outcome.approval.approval_token is None


def test_expired_proposal_cannot_be_approved() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    signal = _signal(now).model_copy(update={"expires_at": now + timedelta(minutes=1)})
    proposal = TradeProposalBuilder().build(
        signal,
        _risk(),
        entry=Decimal("100"),
        stop=Decimal("90"),
        target=Decimal("120"),
        regime="trend_up",
        mtf_alignment=Decimal("0.9"),
        data_quality=Decimal("1"),
        now=now,
    )
    with pytest.raises(ValueError, match="expired"):
        HumanApprovalManager().approve(
            proposal,
            actor="human:alice",
            reason="late",
            idempotency_key="late-1",
            now=signal.expires_at,
        )
