from packages.execution.interface import ExecutionGateway, ExecutionOrder, ExecutionResult


class MT5ExecutionGateway(ExecutionGateway):
    """Isolated MT5 boundary; no MT5 SDK import is permitted in the core."""

    gateway_id = "mt5"
    version = "1.0.0"

    def __init__(self, client: object) -> None:
        self._client = client

    def submit(self, order: ExecutionOrder, approval_token: str) -> ExecutionResult:
        if not approval_token:
            raise ValueError("approval token is required")
        submit = getattr(self._client, "submit_order", None)
        if not callable(submit):
            raise TypeError("MT5 client does not implement submit_order")
        return submit(order)

    def reconcile(self, client_order_id: str) -> ExecutionResult | None:
        reconcile = getattr(self._client, "reconcile_order", None)
        if not callable(reconcile):
            raise TypeError("MT5 client does not implement reconcile_order")
        return reconcile(client_order_id)
