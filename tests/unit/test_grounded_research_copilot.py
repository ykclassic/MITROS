from datetime import UTC, datetime
from uuid import uuid4

from contracts.copilot import EvidenceKind, ResearchEvidence
from contracts.research import ResearchQuery
from packages.research.copilot import GroundedResearchCopilot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def query() -> ResearchQuery:
    return ResearchQuery(
        asset="BTC/USDT", venue="paper", timeframe="1h",
        start=datetime(2025, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 1, tzinfo=UTC),
    )


def evidence(kind: EvidenceKind, title: str) -> ResearchEvidence:
    return ResearchEvidence(kind=kind, artifact_id=uuid4(), title=title, checksum="a" * 64)


def test_no_evidence_fails_closed() -> None:
    result = GroundedResearchCopilot().answer(query(), (), generated_at=NOW)
    assert result.grounded is False
    assert "No verified research evidence" in result.answer


def test_answer_contains_only_supplied_evidence() -> None:
    supplied = (
        evidence(EvidenceKind.BACKTEST, "BTC baseline"),
        evidence(EvidenceKind.DATASET, "BTC verified dataset"),
    )
    result = GroundedResearchCopilot().answer(query(), supplied, generated_at=NOW)
    assert result.grounded is True
    assert result.evidence == tuple(sorted(supplied, key=lambda x: (x.kind.value, str(x.artifact_id))))
    assert "BTC baseline" in result.answer
    assert "BTC verified dataset" in result.answer
