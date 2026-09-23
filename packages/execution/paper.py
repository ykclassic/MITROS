from packages.execution.interface import ExecutionGateway, ExecutionOrder, ExecutionResult


class PaperExecutionGateway(ExecutionGateway):
    """Deterministic gateway for paper/demo execution tests."""

    gateway_id = "paper"
    version = "1.0.0"

    def __init__(self) -> None:
        self._orders: dict[str, ExecutionResult] = {}

    def submit(self, order: ExecutionOrder, approval_token: str) -> ExecutionResult:
        if not approval_token:
            raise ValueError("approval token is required")
        existing = self._orders.get(order.client_order_id)
        if existing is not None:
            return existing
        result = ExecutionResult(
            client_order_id=order.client_order_id,
            venue_order_id=f"paper-{order.client_order_id}",
            status="FILLED",
            filled_quantity=order.quantity,
            average_price=order.limit_price,
        )
        self._orders[order.client_order_id] = result
        return result

    def reconcile(self, client_order_id: str) -> ExecutionResult | None:
        return self._orders.get(client_order_id)
