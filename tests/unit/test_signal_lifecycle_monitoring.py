from datetime import datetime,timedelta,timezone
from decimal import Decimal
from contracts.domain import Direction,StrategyVote
from contracts.signal import SignalRecord,SignalState
from packages.monitoring.signals import SignalMonitor
from packages.signals.lifecycle import SignalLifecycleManager
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def signal():
 return SignalRecord(asset="BTCUSD",venue="TEST",direction=Direction.LONG,created_at=NOW,expires_at=NOW+timedelta(minutes=10),
  strategy_votes=(StrategyVote(strategy_id="crt",strategy_version="1.0.0",direction=Direction.LONG,confidence=Decimal("0.8")),),
  confidence=Decimal("0.8"),provenance=("fixture",))
def test_lifecycle_is_deterministic_and_versioned():
 m=SignalLifecycleManager(); created=m.create(signal(),NOW)
 active=m.transition(created,SignalState.ACTIVE,reason="validated",actor="test",occurred_at=NOW)
 approved=m.transition(active,SignalState.APPROVED,reason="approval recorded",actor="test",occurred_at=NOW)
 assert approved.version==3 and approved.state is SignalState.APPROVED and len(approved.transitions)==3
def test_invalid_transition_fails_closed():
 l=SignalLifecycleManager().create(signal(),NOW)
 try: SignalLifecycleManager().transition(l,SignalState.COMPLETED,reason="skip",actor="test",occurred_at=NOW)
 except ValueError as exc: assert "invalid signal transition" in str(exc)
 else: raise AssertionError("invalid transition was accepted")
def test_monitoring_is_read_only_and_deterministic():
 s=signal(); m=SignalLifecycleManager(); l=m.create(s,NOW)
 active=m.transition(l,SignalState.ACTIVE,reason="validated",actor="test",occurred_at=NOW)
 snapshot=SignalMonitor().snapshot((s,),{str(s.id):active.state},observed_at=NOW+timedelta(minutes=6),stale_after_seconds=300)
 assert snapshot.active_signals==1 and snapshot.stale_signal_count==1
 assert snapshot.alerts==("stale active signals detected",)
