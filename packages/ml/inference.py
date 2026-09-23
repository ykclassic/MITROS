from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from contracts.ml import ModelPrediction


class DeterministicModel:
    """A transparent baseline model: weighted feature sum mapped to [0, 1]."""

    def __init__(self, model_id: str, version: str, weights: Mapping[str, Decimal], feature_set_version: str) -> None:
        if not weights:
            raise ValueError("model requires at least one feature weight")
        self.model_id = model_id
        self.version = version
        self.weights = dict(weights)
        self.feature_set_version = feature_set_version

    def predict(self, features: Mapping[str, Decimal], as_of: datetime, provenance: tuple[str, ...] = ()) -> ModelPrediction:
        if set(features) != set(self.weights):
            raise ValueError("feature schema mismatch")
        score = sum((features[name] * self.weights[name] for name in self.weights), Decimal("0"))
        probability = max(Decimal("0"), min(Decimal("1"), (score + Decimal("1")) / Decimal("2")))
        direction = "LONG" if probability > Decimal("0.5") else "SHORT" if probability < Decimal("0.5") else "NEUTRAL"
        canonical = "|".join(f"{name}={features[name]}" for name in sorted(features))
        checksum = sha256(canonical.encode()).hexdigest()
        return ModelPrediction(
            model_id=self.model_id, model_version=self.version, prediction_id=uuid4(),
            as_of=as_of, probability=probability, direction=direction,
            feature_set_version=self.feature_set_version, feature_checksum=checksum,
            provenance=provenance,
        )
