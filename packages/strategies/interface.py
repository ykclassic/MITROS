from abc import ABC,abstractmethod
from contracts.context import SignalContext
from contracts.domain import StrategyVote
class StrategyPlugin(ABC):
    id:str; version:str
    @abstractmethod
    def evaluate(self,context:SignalContext)->StrategyVote: raise NotImplementedError
