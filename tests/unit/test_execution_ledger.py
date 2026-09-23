from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from contracts.ledger import LedgerOrderState, ReconciliationStatus
from packages.execution.interface import ExecutionOrder, ExecutionOrderType, ExecutionResult, ExecutionSide
from packages.execution.ledger import ExecutionLedger
from packages.execution.paper import PaperExecutionGateway
from packages.execution.reconciliation import ExecutionReconciler


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def order(client_id: str = "proposal-1") -> ExecutionOrder:
    return ExecutionOrder(
        client_order_id=client_id,
        venue="paper",
        asset="BTC/USDT",
        side=ExecutionSide.BUY,
        quantity=Decimal("1"),
        order_type=ExecutionOrderType.MARKET,
    )


def test_intent_is_idempotent_and_append_only() -> None:
    ledger = ExecutionLedger()
    proposal_id = uuid4()
    first = ledger.record_intent(proposal_id=proposal_id, order=order(), now=NOW)
    second = ledger.record_intent(proposal_id=proposal_id, order=order(), now=NOW)
    assert first == second
    assert len(ledger.history("proposal-1")) == 1
    assert ledger.latest("proposal-1").state is LedgerOrderState.INTENDED


def test_submission_and_result_survive_unknown_interruption() -> None:
    ledger = ExecutionLedger()
    proposal_id = uuid4()
    ledger.record_intent(proposal_id=proposal_id, order=order(), now=NOW)
    submitting = ledger.begin_submission(order(), now=NOW)
    assert submitting.state is LedgerOrderState.SUBMITTING
    unknown = ledger.mark_unknown("proposal-1", now=NOW, reason="process interrupted")
    assert unknown.state is LedgerOrderState.UNKNOWN
    assert unknown.result is not None
    assert unknown.result.reason == "process interrupted"


def test_reconciliation_matches_paper_gateway() -> None:
    ledger = ExecutionLedger()
    gateway = PaperExecutionGateway()
    proposal_id = uuid4()
    o = order()
    ledger.record_intent(proposal_id=proposal_id, order=o, now=NOW)
    ledger.begin_submission(o, now=NOW)
    result = gateway.submit(o, "approved-token")
    ledger.record_result(o, result, now=NOW)
    reconciliation = ExecutionReconciler(ledger, gateway).reconcile("proposal-1", now=NOW)
    assert reconciliation.status is ReconciliationStatus.MATCHED


def test_reconciliation_detects_divergence() -> None:
    ledger = ExecutionLedger()
    gateway = PaperExecutionGateway()
    proposal_id = uuid4()
    o = order()
    ledger.record_intent(proposal_id=proposal_id, order=o, now=NOW)
    ledger.begin_submission(o, now=NOW)
    local = ExecutionResult(
        client_order_id="proposal-1",
        venue_order_id="paper-proposal-1",
        status="FILLED",
        filled_quantity=Decimal("2"),
        average_price=None,
    )
    ledger.record_result(o, local, now=NOW)
    gateway.submit(o, "approved-token")
    reconciliation = ExecutionReconciler(ledger, gateway).reconcile("proposal-1", now=NOW)
    assert reconciliation.status is ReconciliationStatus.DIVERGENT
    assert "filled quantity differs" in reconciliation.reasons


def test_missing_venue_order_is_not_treated_as_filled() -> None:
    ledger = ExecutionLedger()
    gateway = PaperExecutionGateway()
    proposal_id = uuid4()
    o = order("missing")
    ledger.record_intent(proposal_id=proposal_id, order=o, now=NOW)
    reconciliation = ExecutionReconciler(ledger, gateway).reconcile("missing", now=NOW)
    assert reconciliation.status is ReconciliationStatus.MISSING
    assert ledger.latest("missing").state is LedgerOrderState.INTENDED


def test_conflicting_proposal_id_is_rejected() -> None:
    ledger = ExecutionLedger()
    o = order()
    ledger.record_intent(proposal_id=uuid4(), order=o, now=NOW)
    with pytest.raises(ValueError, match="another proposal"):
        ledger.record_intent(proposal_id=uuid4(), order=o, now=NOW)
