from collections.abc import Sequence
from datetime import datetime

from contracts.copilot import ResearchAnswer, ResearchEvidence, ResearchEvidence as Evidence, EvidenceKind
from contracts.research import ResearchQuery


class GroundedResearchCopilot:
    """Citation-first research answer composer; it does not invent research facts."""

    def answer(
        self,
        query: ResearchQuery,
        evidence: Sequence[ResearchEvidence],
        *,
        generated_at: datetime,
    ) -> ResearchAnswer:
        ordered = tuple(sorted(evidence, key=lambda item: (item.kind.value, str(item.artifact_id))))
        if not ordered:
            return ResearchAnswer(
                query_id=query.query_id,
                answer="No verified research evidence is available for this query.",
                evidence=(),
                grounded=False,
                generated_at=generated_at,
            )

        references = "\n".join(
            f"[{index}] {item.title} ({item.kind.value}, {item.checksum[:12]})"
            for index, item in enumerate(ordered, start=1)
        )
        answer = (
            f"Research query: {query.asset} {query.timeframe} "
            f"from {query.start.isoformat()} to {query.end.isoformat()}.\n"
            f"Verified evidence available: {len(ordered)} artifact(s).\n\n"
            f"Evidence:\n{references}"
        )
        return ResearchAnswer(
            query_id=query.query_id,
            answer=answer,
            evidence=ordered,
            grounded=True,
            generated_at=generated_at,
        )
