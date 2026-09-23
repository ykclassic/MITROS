from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from contracts.signal import SignalMonitoringSnapshot, SignalRecord, SignalState

class SignalMonitor:
    """Read-only signal health metrics; never changes lifecycle or execution state."""
    def snapshot(self,signals: Iterable[SignalRecord],states: dict[str,SignalState],*,observed_at: datetime|None=None,
                 stale_after_seconds:int=300,alert_threshold:int=1)->SignalMonitoringSnapshot:
        if stale_after_seconds<=0 or alert_threshold<=0:
            raise ValueError("monitoring thresholds must be positive")
        now=observed_at or datetime.now(timezone.utc)
        items=tuple(signals); confidences=[s.confidence for s in items]
        counts={state:0 for state in SignalState}; stale=0
        for signal in items:
            state=states.get(str(signal.id))
            if state is None: raise ValueError("missing lifecycle state for signal")
            counts[state]+=1
            if state is SignalState.ACTIVE and (now-signal.created_at).total_seconds()>stale_after_seconds:
                stale+=1
        alerts=("stale active signals detected",) if stale>=alert_threshold else ()
        return SignalMonitoringSnapshot(observed_at=now,total_signals=len(items),
            active_signals=counts[SignalState.ACTIVE],expired_signals=counts[SignalState.EXPIRED],
            invalidated_signals=counts[SignalState.INVALIDATED],approved_signals=counts[SignalState.APPROVED],
            rejected_signals=counts[SignalState.REJECTED],completed_signals=counts[SignalState.COMPLETED],
            mean_confidence=sum(confidences,Decimal("0"))/Decimal(len(confidences)) if confidences else Decimal("0"),
            stale_signal_count=stale,alerts=alerts)
