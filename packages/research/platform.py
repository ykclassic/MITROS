from collections.abc import Sequence
from typing import Final
from datetime import datetime

from contracts.research import ResearchArtifact, ResearchArtifactType, ResearchMetric, ResearchQuery, ResearchReport


class ResearchPlatform:
    _EMPTY_METADATA: Final[dict[str, str]] = {}
    """Deterministic research orchestration over verified MITROS research engines."""

    def register_artifact(
        self,
        *,
        artifact_type: ResearchArtifactType,
        name: str,
        version: str,
        checksum: str,
        created_at: datetime,
        metadata: dict[str, str] | None = None,
    ) -> ResearchArtifact:
        return ResearchArtifact(
            artifact_type=artifact_type,
            name=name,
            version=version,
            checksum=checksum,
            created_at=created_at,
            metadata=metadata if metadata is not None else self._EMPTY_METADATA,
        )

    def report(
        self,
        query: ResearchQuery,
        *,
        artifacts: Sequence[ResearchArtifact] = (),
        metrics: Sequence[ResearchMetric] = (),
        findings: Sequence[str] = (),
        generated_at: datetime,
    ) -> ResearchReport:
        if query.start >= query.end:
            raise ValueError("research query start must precede end")
        return ResearchReport(
            query=query,
            artifacts=tuple(artifacts),
            metrics=tuple(metrics),
            findings=tuple(findings),
            generated_at=generated_at,
        )

    @staticmethod
    def compare_metrics(left: ResearchReport, right: ResearchReport) -> tuple[ResearchMetric, ...]:
        left_by_name = {metric.name: metric for metric in left.metrics}
        right_by_name = {metric.name: metric for metric in right.metrics}
        names = sorted(left_by_name.keys() & right_by_name.keys())
        return tuple(
            ResearchMetric(
                name=name,
                value=right_by_name[name].value - left_by_name[name].value,
                sample_size=min(left_by_name[name].sample_size, right_by_name[name].sample_size),
            )
            for name in names
        )
