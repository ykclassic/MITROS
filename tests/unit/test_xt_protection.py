from decimal import Decimal

import pytest

from packages.execution.protection import XTSpotProtectionMonitor, protection_trigger_reason
from packages.exchanges.xt import XTSpotClient
from packages.execution.xt import XTSpotExecutionGateway


def test_long_position_stop_and_target_triggers() -> None:
    assert protection_trigger_reason(
        direction="LONG", price=Decimal("94"), stop_loss=Decimal("95"), take_profit=Decimal("110")
    ) == "STOP_LOSS_TRIGGERED"
    assert protection_trigger_reason(
        direction="LONG", price=Decimal("111"), stop_loss=Decimal("95"), take_profit=Decimal("110")
    ) == "TAKE_PROFIT_TRIGGERED"
    assert protection_trigger_reason(
        direction="LONG", price=Decimal("100"), stop_loss=Decimal("95"), take_profit=Decimal("110")
    ) is None


def test_short_position_trigger_logic_is_defined_for_future_derivative_adapters() -> None:
    assert protection_trigger_reason(
        direction="SHORT", price=Decimal("111"), stop_loss=Decimal("110"), take_profit=Decimal("90")
    ) == "STOP_LOSS_TRIGGERED"
    assert protection_trigger_reason(
        direction="SHORT", price=Decimal("89"), stop_loss=Decimal("110"), take_profit=Decimal("90")
    ) == "TAKE_PROFIT_TRIGGERED"



@pytest.mark.asyncio
async def test_protection_monitor_is_idle_when_live_feature_flags_are_off(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_EXECUTION_MODE", "paper")
    monkeypatch.setenv("MITROS_LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv("MITROS_XT_LIVE_ORDERS_ENABLED", "false")
    monkeypatch.setenv("MITROS_XT_PROTECTION_MONITOR_ENABLED", "false")
    monitor = XTSpotProtectionMonitor(
        "postgresql://unused/test",
        xt=XTSpotClient(api_key="", api_secret=""),
        gateway=XTSpotExecutionGateway(api_key="", api_secret=""),
    )
    assert await monitor.run_once() == 0
