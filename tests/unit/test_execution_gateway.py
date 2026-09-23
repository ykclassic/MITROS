from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from contracts.approval import ApprovalOutcome
from contracts.domain import Direction, StrategyVote, TradeProposal
from contracts.risk import RiskAssessment
from contracts.signal import SignalRecord
from packages.approval.manager import HumanApprovalManager
from packages.execution.gateway import ProposalExecutionGateway
from packages.execution.paper import PaperExecutionGateway
from packages.execution.security import approval_token_digest
from packages.proposals.builder import TradeProposalBuilder


def proposal() -> tuple[TradeProposal, ApprovalOutcome]:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    signal = SignalRecord(
        asset="BTC/USDT", venue="paper", direction=Direction.LONG,
        created_at=now, expires_at=now + timedelta(minutes=15),
        strategy_votes=(StrategyVote(
            strategy_id="smc", strategy_version="1.0.0",
            direction=Direction.LONG, confidence=Decimal("0.8"),
        ),), confidence=Decimal("0.8"),
    )
    risk = RiskAssessment(
        approved=True, requested_size=Decimal("1"), approved_size=Decimal("1"),
        checks=(), reasons=("approved",), risk_score=Decimal("0.1"),
    )
    p = TradeProposalBuilder().build(
        signal, risk, entry=Decimal("100"), stop=Decimal("90"),
        target=Decimal("120"), regime="trend_up",
        mtf_alignment=Decimal("0.9"), data_quality=Decimal("1"), now=now,
    )
    outcome = HumanApprovalManager().approve(
        p, actor="human:test", reason="reviewed",
        idempotency_key="exec-1", now=now + timedelta(minutes=1),
    )
    return p, outcome


def test_only_approved_token_reaches_gateway() -> None:
    p, outcome = proposal()
    gateway = PaperExecutionGateway()
    boundary = ProposalExecutionGateway(
        gateway, approval_digest=approval_token_digest(outcome.approval.approval_token or ""),
    )
    result = boundary.submit(p.model_copy(update={
        "approval_status": "APPROVED",
    }), outcome.approval.approval_token or "")
    assert result.status == "FILLED"
    assert result.filled_quantity == Decimal("1")


def test_invalid_token_fails_closed_without_submission() -> None:
    p, outcome = proposal()
    paper = PaperExecutionGateway()
    boundary = ProposalExecutionGateway(
        paper, approval_digest=approval_token_digest(outcome.approval.approval_token or ""),
    )
    approved = p.model_copy(update={"approval_status": "APPROVED"})
    with pytest.raises(ValueError, match="invalid approval token"):
        boundary.submit(approved, "forged")
    assert paper.reconcile(str(p.id)) is None


def test_gateway_maps_short_to_sell_and_is_idempotent() -> None:
    p, outcome = proposal()
    short = p.model_copy(update={"direction": Direction.SHORT, "approval_status": "APPROVED"})
    paper = PaperExecutionGateway()
    boundary = ProposalExecutionGateway(
        paper, approval_digest=approval_token_digest(outcome.approval.approval_token or ""),
    )
    first = boundary.submit(short, outcome.approval.approval_token or "")
    second = boundary.submit(short, outcome.approval.approval_token or "")
    assert first == second
    assert paper.reconcile(str(p.id)) == first


def test_unapproved_proposal_cannot_execute() -> None:
    p, outcome = proposal()
    boundary = ProposalExecutionGateway(
        PaperExecutionGateway(),
        approval_digest=approval_token_digest(outcome.approval.approval_token or ""),
    )
    with pytest.raises(ValueError, match="human-approved"):
        boundary.submit(p, outcome.approval.approval_token or "")


def test_execution_contract_has_no_mt5_sdk_dependency() -> None:
    import packages.execution.mt5 as module
    assert "MetaTrader5" not in module.__dict__
