from datetime import datetime

from contracts.ml import ModelLifecycleStage, ModelVersion, ValidationResult


class ModelLifecycle:
    """Fail-closed model registry transition rules."""

    _allowed = {
        ModelLifecycleStage.DEVELOPED: {ModelLifecycleStage.VALIDATED, ModelLifecycleStage.RETIRED},
        ModelLifecycleStage.VALIDATED: {ModelLifecycleStage.STAGED, ModelLifecycleStage.RETIRED},
        ModelLifecycleStage.STAGED: {ModelLifecycleStage.PRODUCTION, ModelLifecycleStage.RETIRED},
        ModelLifecycleStage.PRODUCTION: {ModelLifecycleStage.RETIRED},
        ModelLifecycleStage.RETIRED: set(),
    }

    def validate_for_stage(self, model: ModelVersion, validation: ValidationResult) -> ModelVersion:
        if validation.model_id != model.model_id or validation.model_version != model.version:
            raise ValueError("model and validation identity mismatch")
        if not validation.passed:
            raise ValueError("model validation has not passed")
        if model.stage is not ModelLifecycleStage.DEVELOPED:
            raise ValueError("only DEVELOPED models can be promoted by this operation")
        return model.model_copy(update={"stage": ModelLifecycleStage.VALIDATED})

    def transition(self, model: ModelVersion, target: ModelLifecycleStage) -> ModelVersion:
        if target not in self._allowed[model.stage]:
            raise ValueError(f"invalid model lifecycle transition: {model.stage} -> {target}")
        return model.model_copy(update={"stage": target, "created_at": datetime.now(model.created_at.tzinfo)})
