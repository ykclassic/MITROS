from collections.abc import Sequence
from decimal import Decimal

from contracts.ml import DriftReport, DriftStatus


class DriftDetector:
    def __init__(self, warning_threshold: Decimal = Decimal("0.10"), breach_threshold: Decimal = Decimal("0.25")) -> None:
        if not Decimal("0") < warning_threshold < breach_threshold:
            raise ValueError("drift thresholds are invalid")
        self.warning_threshold = warning_threshold
        self.breach_threshold = breach_threshold

    def compare(self, model_id: str, model_version: str, feature_name: str,
                baseline: Sequence[Decimal], current: Sequence[Decimal], evaluated_at) -> DriftReport:
        if not baseline or not current:
            raise ValueError("drift comparison requires non-empty samples")
        baseline_mean = sum(baseline, Decimal("0")) / Decimal(len(baseline))
        current_mean = sum(current, Decimal("0")) / Decimal(len(current))
        if baseline_mean == 0:
            relative_shift = abs(current_mean) if current_mean else Decimal("0")
        else:
            relative_shift = abs(current_mean - baseline_mean) / abs(baseline_mean)
        status = (
            DriftStatus.BREACHED if relative_shift >= self.breach_threshold
            else DriftStatus.WARNING if relative_shift >= self.warning_threshold
            else DriftStatus.STABLE
        )
        return DriftReport(
            model_id=model_id, model_version=model_version, feature_name=feature_name,
            baseline_mean=baseline_mean, current_mean=current_mean,
            relative_shift=relative_shift, status=status, sample_size=len(current),
            evaluated_at=evaluated_at,
            reasons=(f"baseline_mean={baseline_mean}", f"current_mean={current_mean}"),
        )
