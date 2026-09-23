from abc import ABC,abstractmethod
from contracts.domain import RiskDecisionRecord,TradeProposal
class RiskEngine(ABC):
    version:str
    @abstractmethod
    def evaluate(self,proposal:TradeProposal)->RiskDecisionRecord: raise NotImplementedError
