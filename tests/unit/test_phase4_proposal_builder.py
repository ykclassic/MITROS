from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from contracts.domain import Direction, StrategyVote
from contracts.phase4_risk import RiskDisposition
from contracts.signal import SignalRecord
from packages.proposals.phase4_builder import Phase4TradeProposalBuilder
from packages.risk.phase4 import IndependentRiskGate
from tests.unit.test_phase4_risk import policy, request


def signal(now: datetime) -> SignalRecord:
    return SignalRecord(
        id=uuid4(),
        asset="BTC/USD",
        venue="spot",
        direction=Direction.LONG,
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        strategy_votes=(StrategyVote(
            strategy_id="smc", strategy_version="1.0.0",
            direction=Direction.LONG, confidence=Decimal("0.9"),
        ),),
        confidence=Decimal("0.9"),
    )


def test_phase4_builder_requires_passing_independent_decision() -> None:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    candidate = signal(now)
    inputs = request(proposal_id=str(candidate.id))
    decision = IndependentRiskGate(policy()).evaluate(inputs)
    proposal = Phase4TradeProposalBuilder().build(
        candidate, inputs, decision, venue="spot", regime="TREND_UP",
        mtf_alignment=Decimal("0.9"), now=now,
    )
    assert proposal.id == candidate.id
    assert proposal.position_size == decision.approved_notional
    assert proposal.invalidation_conditions == decision.invalidation_conditions
    assert proposal.execution_status.value == "NOT_AUTHORIZED"


def test_phase4_builder_cannot_bypass_rejected_risk_check() -> None:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    candidate = signal(now)
    inputs = request(proposal_id=str(candidate.id), data_verified=False)
    decision = IndependentRiskGate(policy()).evaluate(inputs)
    assert decision.disposition is RiskDisposition.REJECTED
    with pytest.raises(ValueError, match="risk decision rejected"):
        Phase4TradeProposalBuilder().build(
            candidate, inputs, decision, venue="spot", regime="TREND_UP",
            mtf_alignment=Decimal("0.9"), now=now,
        )


def test_phase4_builder_rejects_mismatched_signal_identity() -> None:
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    candidate = signal(now)
    inputs = request(proposal_id="not-the-signal-id")
    decision = IndependentRiskGate(policy()).evaluate(inputs)
    with pytest.raises(ValueError, match="identifiers must match"):
        Phase4TradeProposalBuilder().build(
            candidate, inputs, decision, venue="spot", regime="TREND_UP",
            mtf_alignment=Decimal("0.9"), now=now,
        )
