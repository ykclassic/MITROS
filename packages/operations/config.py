import os
from dataclasses import dataclass
from enum import StrEnum


class ExecutionMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class ProductionConfig:
    execution_mode: ExecutionMode
    live_trading_enabled: bool
    live_trading_acknowledged: bool

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ProductionConfig":
        source = os.environ if env is None else env
        mode = ExecutionMode(source.get("MITROS_EXECUTION_MODE", "paper").lower())
        enabled = source.get("MITROS_LIVE_TRADING_ENABLED", "false").lower() == "true"
        acknowledged = source.get("MITROS_LIVE_TRADING_ACK", "") == "I_UNDERSTAND_LIVE_TRADING"
        config = cls(mode, enabled, acknowledged)
        config.validate()
        return config

    def validate(self) -> None:
        if self.execution_mode is ExecutionMode.PAPER and self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled in paper mode")
        if self.execution_mode is ExecutionMode.LIVE:
            if not self.live_trading_enabled:
                raise ValueError("live mode requires explicit live trading enablement")
            if not self.live_trading_acknowledged:
                raise ValueError("live mode requires explicit operator acknowledgement")
