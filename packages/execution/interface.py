from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ExecutionOrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class ExecutionSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class ExecutionOrder:
    client_order_id: str
    venue: str
    asset: str
    side: ExecutionSide
    quantity: Decimal
    order_type: ExecutionOrderType
    limit_price: Decimal | None = None


@dataclass(frozen=True)
class ExecutionResult:
    client_order_id: str
    venue_order_id: str | None
    status: str
    filled_quantity: Decimal
    average_price: Decimal | None
    reason: str | None = None


class ExecutionGateway(ABC):
    """The only boundary permitted to submit an order to a trading venue."""

    gateway_id: str
    version: str

    @abstractmethod
    def submit(self, order: ExecutionOrder, approval_token: str) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def reconcile(self, client_order_id: str) -> ExecutionResult | None:
        raise NotImplementedError
