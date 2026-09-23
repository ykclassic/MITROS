from abc import ABC,abstractmethod
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class ExecutionOrder:
    client_order_id:str; venue:str; asset:str; side:str; quantity:Decimal; order_type:str; limit_price:Decimal|None=None
@dataclass(frozen=True)
class ExecutionResult:
    client_order_id:str; venue_order_id:str|None; status:str; filled_quantity:Decimal; average_price:Decimal|None
class ExecutionGateway(ABC):
    gateway_id:str; version:str
    @abstractmethod
    def submit(self,order:ExecutionOrder,approval_token:str)->ExecutionResult: raise NotImplementedError
    @abstractmethod
    def reconcile(self,client_order_id:str)->ExecutionResult|None: raise NotImplementedError
