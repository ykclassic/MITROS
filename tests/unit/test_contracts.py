from datetime import datetime,timezone
from decimal import Decimal
from contracts.domain import Direction,Provenance,RiskDecision,RiskDecisionRecord,StrategyVote,TradeProposal
def test_trade_proposal_is_immutable():
    now=datetime.now(timezone.utc)
    p=TradeProposal(asset="BTC/USDT",venue="test",direction=Direction.LONG,created_at=now,expires_at=now,entry=Decimal("100"),stop=Decimal("90"),target=Decimal("120"),risk_reward=Decimal("2"),position_size=Decimal("1"),strategy_votes=(StrategyVote(strategy_id="smc",strategy_version="1",direction=Direction.LONG,confidence=Decimal("0.8")),),mtf_alignment=Decimal("0.8"),regime="trend",data_quality=Decimal("1"),evidence=(),risk=RiskDecisionRecord(decision=RiskDecision.APPROVED,reasons=(),evaluated_at=now,risk_engine_version="1"),provenance=(Provenance(source="test",observed_at=now,received_at=now),))
    try: p.asset="ETH/USDT"; assert False
    except Exception: assert p.asset=="BTC/USDT"
