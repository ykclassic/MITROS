from datetime import UTC, datetime
from decimal import Decimal
import pytest

from contracts.ml import DriftStatus, ModelLifecycleStage, ModelVersion, ValidationResult
from packages.ml.drift import DriftDetector
from packages.ml.inference import DeterministicModel
from packages.ml.lifecycle import ModelLifecycle


NOW = datetime(2026, 9, 23, tzinfo=UTC)
CHECKSUM = "a" * 64


def model(stage=ModelLifecycleStage.DEVELOPED):
    return ModelVersion(
        model_id="baseline", version="1.0.0", stage=stage,
        feature_set_version="features@1.0.0", artifact_checksum=CHECKSUM,
        training_data_checksum="b" * 64, created_at=NOW,
    )


def validation(passed=True):
    return ValidationResult(
        model_id="baseline", model_version="1.0.0", sample_size=100,
        walk_forward_folds=5, purged_observations=10, mean_score=Decimal("0.72"),
        minimum_score=Decimal("0.60"), passed=passed, evaluated_at=NOW,
    )


def test_lifecycle_requires_validation():
    result = ModelLifecycle().validate_for_stage(model(), validation())
    assert result.stage is ModelLifecycleStage.VALIDATED


def test_lifecycle_rejects_failed_validation():
    with pytest.raises(ValueError, match="not passed"):
        ModelLifecycle().validate_for_stage(model(), validation(False))


def test_lifecycle_rejects_invalid_promotion():
    with pytest.raises(ValueError, match="invalid model lifecycle"):
        ModelLifecycle().transition(model(), ModelLifecycleStage.PRODUCTION)


def test_deterministic_inference_and_schema_guard():
    engine = DeterministicModel("baseline", "1.0.0", {"x": Decimal("1")}, "features@1.0.0")
    a = engine.predict({"x": Decimal("0.2")}, NOW)
    b = engine.predict({"x": Decimal("0.2")}, NOW)
    assert a.probability == b.probability
    assert a.feature_checksum == b.feature_checksum
    with pytest.raises(ValueError, match="schema"):
        engine.predict({"y": Decimal("0.2")}, NOW)


def test_drift_thresholds():
    detector = DriftDetector()
    stable = detector.compare("baseline", "1.0.0", "x", [Decimal("10"), Decimal("10")], [Decimal("10.5"), Decimal("9.5")], NOW)
    breached = detector.compare("baseline", "1.0.0", "x", [Decimal("10"), Decimal("10")], [Decimal("14"), Decimal("16")], NOW)
    assert stable.status is DriftStatus.STABLE
    assert breached.status is DriftStatus.BREACHED


def test_lifecycle_can_progress_only_in_order():
    lifecycle = ModelLifecycle()
    validated = lifecycle.validate_for_stage(model(), validation())
    staged = lifecycle.transition(validated, ModelLifecycleStage.STAGED)
    production = lifecycle.transition(staged, ModelLifecycleStage.PRODUCTION)
    assert production.stage is ModelLifecycleStage.PRODUCTION
    assert lifecycle.transition(production, ModelLifecycleStage.RETIRED).stage is ModelLifecycleStage.RETIRED


def test_prediction_has_unique_identity():
    engine = DeterministicModel("baseline", "1.0.0", {"x": Decimal("1")}, "features@1.0.0")
    a = engine.predict({"x": Decimal("0")}, NOW)
    b = engine.predict({"x": Decimal("0")}, NOW)
    assert a.prediction_id != b.prediction_id
