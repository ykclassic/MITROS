from datetime import datetime

from contracts.ledger import ReconciliationResult, ReconciliationStatus
from packages.execution.interface import ExecutionGateway
from packages.execution.ledger import ExecutionLedger


class ExecutionReconciler:
    """Reconciles local execution state with the authoritative venue gateway."""

    def __init__(self, ledger: ExecutionLedger, gateway: ExecutionGateway) -> None:
        self._ledger = ledger
        self._gateway = gateway

    def reconcile(self, client_order_id: str, *, now: datetime) -> ReconciliationResult:
        local = self._ledger.latest(client_order_id)
        if local is None:
            raise ValueError("client order is not in the ledger")
        remote = self._gateway.reconcile(client_order_id)
        if remote is None:
            return ReconciliationResult(
                client_order_id=client_order_id,
                status=ReconciliationStatus.MISSING,
                local=local,
                remote=None,
                reasons=("venue has no matching order",),
                reconciled_at=now,
            )

        reasons: list[str] = []
        if local.result is not None and local.result.venue_order_id != remote.venue_order_id:
            reasons.append("venue order id differs")
        if local.result is not None and local.result.filled_quantity != remote.filled_quantity:
            reasons.append("filled quantity differs")
        if local.result is not None and local.result.average_price != remote.average_price:
            reasons.append("average price differs")
        if local.result is not None and local.result.status != remote.status:
            reasons.append("execution status differs")

        status = ReconciliationStatus.DIVERGENT if reasons else ReconciliationStatus.MATCHED
        return ReconciliationResult(
            client_order_id=client_order_id,
            status=status,
            local=local,
            remote=remote,
            reasons=tuple(reasons),
            reconciled_at=now,
        )
