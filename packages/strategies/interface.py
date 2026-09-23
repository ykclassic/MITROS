from abc import ABC,abstractmethod
from contracts.domain import StrategyVote,SignalContext
class StrategyPlugin(ABC):
    id:str; version:str
    @abstractmethod
    def evaluate(self,context:SignalContext)->StrategyVote: raise NotImplementedError
