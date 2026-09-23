from datetime import datetime, timezone
from contracts.signal import SignalLifecycle, SignalRecord, SignalState, SignalTransition

_ALLOWED={
 SignalState.GENERATED:frozenset({SignalState.ACTIVE,SignalState.EXPIRED,SignalState.INVALIDATED}),
 SignalState.ACTIVE:frozenset({SignalState.INVALIDATED,SignalState.EXPIRED,SignalState.APPROVED,SignalState.REJECTED}),
 SignalState.APPROVED:frozenset({SignalState.EXECUTING,SignalState.EXPIRED,SignalState.REJECTED}),
 SignalState.REJECTED:frozenset(), SignalState.INVALIDATED:frozenset(), SignalState.EXPIRED:frozenset(),
 SignalState.EXECUTING:frozenset({SignalState.COMPLETED}), SignalState.COMPLETED:frozenset(),
}
class SignalLifecycleManager:
    """Fail-closed lifecycle; observation never grants execution authority."""
    def create(self, signal: SignalRecord, now: datetime|None=None)->SignalLifecycle:
        observed=now or datetime.now(timezone.utc)
        transition=SignalTransition(from_state=SignalState.GENERATED,to_state=SignalState.GENERATED,
            occurred_at=observed,reason="signal generated",actor="signal-lifecycle")
        return SignalLifecycle(signal_id=signal.id,state=SignalState.GENERATED,version=1,
            updated_at=observed,transitions=(transition,))
    def transition(self,lifecycle: SignalLifecycle,to_state: SignalState,*,reason: str,actor: str,occurred_at: datetime)->SignalLifecycle:
        if to_state not in _ALLOWED[lifecycle.state]:
            raise ValueError(f"invalid signal transition: {lifecycle.state} -> {to_state}")
        if occurred_at<lifecycle.updated_at:
            raise ValueError("signal transition time cannot move backwards")
        transition=SignalTransition(from_state=lifecycle.state,to_state=to_state,occurred_at=occurred_at,reason=reason,actor=actor)
        return lifecycle.model_copy(update={"state":to_state,"version":lifecycle.version+1,
            "updated_at":occurred_at,"transitions":(*lifecycle.transitions,transition)})
    @staticmethod
    def signal_expired(signal: SignalRecord,now: datetime)->bool:
        return now>=signal.expires_at
