from typing import Protocol

from packages.execution.interface import ExecutionGateway, ExecutionOrder, ExecutionResult


class MT5Client(Protocol):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult: ...

    def reconcile_order(self, client_order_id: str) -> ExecutionResult | None: ...


class MT5ExecutionGateway(ExecutionGateway):
    """Isolated MT5 boundary; no MT5 SDK import is permitted in the core."""

    gateway_id = "mt5"
    version = "1.0.0"

    def __init__(self, client: MT5Client) -> None:
        self._client = client

    def submit(self, order: ExecutionOrder, approval_token: str) -> ExecutionResult:
        if not approval_token:
            raise ValueError("approval token is required")
        return self._client.submit_order(order)

    def reconcile(self, client_order_id: str) -> ExecutionResult | None:
        return self._client.reconcile_order(client_order_id)
