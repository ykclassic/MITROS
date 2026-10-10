import pytest
import httpx

from packages.execution.factory import build_venue_gateway
from packages.execution.paper import PaperExecutionGateway
from packages.execution.xt import XTExecutionError, XTSpotExecutionGateway
from packages.operations.config import ProductionConfig


def test_paper_gateway_is_default() -> None:
    gateway = build_venue_gateway(ProductionConfig.from_env({}))
    assert isinstance(gateway, PaperExecutionGateway)


def test_xt_gateway_cannot_submit_when_live_toggles_are_off(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_EXECUTION_MODE", "paper")
    monkeypatch.setenv("MITROS_LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv("MITROS_XT_LIVE_ORDERS_ENABLED", "false")
    gateway = XTSpotExecutionGateway(api_key="test", api_secret="test")
    from packages.execution.interface import ExecutionOrder, ExecutionOrderType, ExecutionSide
    from decimal import Decimal
    order = ExecutionOrder(
        client_order_id="test-order",
        venue="xt.com",
        asset="BTC/USDT",
        side=ExecutionSide.BUY,
        quantity=Decimal("0.001"),
        order_type=ExecutionOrderType.MARKET,
    )
    with pytest.raises(XTExecutionError, match="disabled"):
        gateway.submit(order, "approval-token")


def test_xt_live_requires_all_environment_toggles(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_EXECUTION_MODE", "live")
    monkeypatch.setenv("MITROS_LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("MITROS_LIVE_TRADING_ACK", "I_UNDERSTAND_LIVE_TRADING")
    monkeypatch.setenv("MITROS_XT_LIVE_ORDERS_ENABLED", "false")
    gateway = XTSpotExecutionGateway(api_key="test", api_secret="test")
    with pytest.raises(XTExecutionError, match="MITROS_XT_LIVE_ORDERS_ENABLED"):
        gateway._require_live_enabled()



def test_xt_limit_order_submission_and_reconciliation(monkeypatch) -> None:
    from decimal import Decimal
    from packages.execution.interface import ExecutionOrder, ExecutionOrderType, ExecutionSide

    monkeypatch.setenv("MITROS_EXECUTION_MODE", "live")
    monkeypatch.setenv("MITROS_LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("MITROS_LIVE_TRADING_ACK", "I_UNDERSTAND_LIVE_TRADING")
    monkeypatch.setenv("MITROS_XT_LIVE_ORDERS_ENABLED", "true")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "POST":
            body = request.read().decode()
            assert '"timeInForce":"GTC"' in body
            assert '"clientOrderId":"mitros_' in body
            assert request.headers.get("validate-signature")
            return httpx.Response(200, json={"rc": 0, "result": {"orderId": "xt-order-123"}})
        return httpx.Response(200, json={
            "rc": 0,
            "result": {
                "orderId": "xt-order-123", "state": "FILLED",
                "executedQty": "0.01", "avgPrice": "100",
            },
        })

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        gateway = XTSpotExecutionGateway(
            api_key="test-key", api_secret="test-secret",
            base_url="https://xt.test", client=client,
        )
        order = ExecutionOrder(
            client_order_id="proposal-uuid",
            venue="xt.com",
            asset="BTC/USDT",
            side=ExecutionSide.BUY,
            quantity=Decimal("0.01"),
            order_type=ExecutionOrderType.LIMIT,
            limit_price=Decimal("100"),
        )
        submitted = gateway.submit(order, "human-approval-token")
        reconciled = gateway.reconcile("proposal-uuid")

    assert submitted.venue_order_id == "xt-order-123"
    assert submitted.status == "SUBMITTED"
    assert reconciled is not None
    assert reconciled.status == "FILLED"
    assert reconciled.filled_quantity == Decimal("0.01")
    assert reconciled.average_price == Decimal("100")
    assert len(calls) == 2
