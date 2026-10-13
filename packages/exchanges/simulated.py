from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from decimal import Decimal

from packages.exchanges.base import AccountProviderError
from packages.exchanges.xt import XTBalance, XTSpotAccount


class SimulatedAccountClient:
    """Deterministic, explicitly gated account fixture for verification environments only."""

    equity_usdt = Decimal("10000")
    btc_usdt_price_value = Decimal("65000")

    def __init__(self) -> None:
        environment = os.getenv("MITROS_ENVIRONMENT", "").strip().lower()
        enabled = os.getenv("MITROS_PHASE4_SIMULATED_ACCOUNT_ENABLED", "false").strip().lower() == "true"
        self._allowed = enabled and environment in {"test", "verification", "staging", "development", "local"}

    @property
    def configured(self) -> bool:
        return self._allowed

    async def verify_read_only_key(self) -> None:
        if not self._allowed:
            raise AccountProviderError("Simulated account provider is disabled outside verification environments")

    async def btc_usdt_price(self) -> Decimal:
        if not self._allowed:
            raise AccountProviderError("Simulated account provider is disabled outside verification environments")
        return self.btc_usdt_price_value

    async def account_snapshot(self) -> XTSpotAccount:
        if not self._allowed:
            raise AccountProviderError("Simulated account provider is disabled outside verification environments")
        btc_value = self.equity_usdt / self.btc_usdt_price_value
        balance = XTBalance(
            currency="BTC",
            available=btc_value,
            frozen=Decimal("0"),
            total=btc_value,
            btc_value=btc_value,
        )
        return XTSpotAccount(
            observed_at_ms=int(time.time() * 1000),
            total_btc_value=btc_value,
            balances=(balance,),
            provider="simulated",
            account_type="verification",
        )

    async def market_ticker(self, asset: str) -> dict[str, Decimal | datetime]:
        if not self._allowed:
            raise AccountProviderError("Simulated account provider is disabled outside verification environments")
        return {
            "bid": Decimal("64999"),
            "ask": Decimal("65001"),
            "last": self.btc_usdt_price_value,
            "observed_at": datetime.now(UTC),
        }
