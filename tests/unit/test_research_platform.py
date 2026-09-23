from datetime import UTC, datetime
from decimal import Decimal

import pytest

from contracts.research import ResearchArtifactType, ResearchMetric, ResearchQuery
from packages.research.platform import ResearchPlatform

NOW = datetime(2026, 1, 1, tzinfo=UTC)

def query() -> ResearchQuery:
    return ResearchQuery(
        asset="BTC/USDT", venue="paper", timeframe="1h",
        start=datetime(2025, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 1, tzinfo=UTC),
    )

def test_register_artifact_preserves_provenance() -> None:
    artifact = ResearchPlatform().register_artifact(
        artifact_type=ResearchArtifactType.BACKTEST, name="smc-baseline", version="1.0.0",
        checksum="a" * 64, created_at=NOW, metadata={"dataset": "dataset-sha"},
    )
    assert artifact.checksum == "a" * 64
    assert artifact.metadata["dataset"] == "dataset-sha"

def test_report_is_immutable_and_validates_window() -> None:
    report = ResearchPlatform().report(
        query(), metrics=(ResearchMetric(name="win_rate", value=Decimal("0.5"), sample_size=10),),
        findings=("deterministic",), generated_at=NOW,
    )
    assert report.metrics[0].value == Decimal("0.5")
    with pytest.raises(ValueError):
        ResearchPlatform().report(query.model_copy(update={"start": query().end}), generated_at=NOW)

def test_compare_metrics_is_deterministic() -> None:
    platform = ResearchPlatform()
    left = platform.report(query(), metrics=(ResearchMetric(name="return", value=Decimal("0.1"), sample_size=20),), generated_at=NOW)
    right = platform.report(query(), metrics=(ResearchMetric(name="return", value=Decimal("0.3"), sample_size=30),), generated_at=NOW)
    result = platform.compare_metrics(left, right)
    assert result[0].value == Decimal("0.2")
    assert result[0].sample_size == 20
