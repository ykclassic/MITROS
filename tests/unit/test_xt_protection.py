from decimal import Decimal

from packages.execution.protection import protection_trigger_reason


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
