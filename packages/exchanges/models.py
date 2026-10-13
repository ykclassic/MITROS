from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AccountBalance:
    currency: str
    available: Decimal
    frozen: Decimal
    total: Decimal
    btc_value: Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    observed_at_ms: int
    total_btc_value: Decimal
    balances: tuple[AccountBalance, ...]
    provider: str
    account_type: str = "spot"
