# Phase 7 — AI/ML Lifecycle

Phase 7 establishes the governance and runtime boundary for machine-learning components.

## Lifecycle
Models progress monotonically through DEVELOPED → VALIDATED → STAGED → PRODUCTION → RETIRED. Promotion requires an explicit validation record. Failed validation and illegal transitions fail closed.

## Validation
The validation contract records sample size, walk-forward fold count, purged observations, score thresholds, and evaluation time. The platform does not treat an unvalidated model as production-capable.

## Inference
Inference is version-pinned and feature-schema-pinned. Predictions carry a deterministic feature checksum and model identity.

## Drift
Feature-level baseline/current mean shifts are monitored with explicit warning and breach thresholds.

## Safety boundary
AI/ML outputs are evidence only. They cannot become authoritative market truth, modify risk limits, authorize approval, submit orders, or mutate ledger state.

## Reproducibility
Artifacts, training-data checksums, feature-set versions, model versions, validation records, and prediction provenance are explicit contracts.
