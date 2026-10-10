from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from contracts.phase4_risk import RiskDecisionResult, RiskEvaluationRequest, RiskPolicy


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


class RiskDecisionPersistenceError(RuntimeError):
    """Raised when a risk decision cannot be durably audited."""


class PostgresPhase4RiskDecisionRepository:
    """Atomically stores a Phase 4 decision and its system audit event."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url

    async def record(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        request: RiskEvaluationRequest,
        policy: RiskPolicy,
        decision: RiskDecisionResult,
        correlation_id: UUID,
    ) -> dict[str, Any]:
        if not user_id or not idempotency_key.strip():
            raise ValueError("user_id and idempotency_key are required")
        if decision.proposal_id != request.proposal_id:
            raise ValueError("decision/request proposal identity mismatch")

        request_json = request.model_dump(mode="json")
        policy_json = policy.model_dump(mode="json")
        decision_json = decision.model_dump(mode="json")
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict_row
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    insert into phase4_risk_decisions (
                        user_id, proposal_id, idempotency_key, disposition,
                        engine_version, request_snapshot, policy_snapshot,
                        decision_snapshot
                    )
                    values (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                    on conflict (user_id, idempotency_key) do nothing
                    returning id, proposal_id, disposition, engine_version,
                              request_snapshot, policy_snapshot,
                              decision_snapshot, created_at
                    """,
                    (
                        user_id,
                        request.proposal_id,
                        idempotency_key,
                        decision.disposition.value,
                        decision.risk_engine_version,
                        json.dumps(request_json),
                        json.dumps(policy_json),
                        json.dumps(decision_json),
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    await cursor.execute(
                        """
                        select id, proposal_id, disposition, engine_version,
                               request_snapshot, policy_snapshot,
                               decision_snapshot, created_at
                        from phase4_risk_decisions
                        where user_id = %s and idempotency_key = %s
                        """,
                        (user_id, idempotency_key),
                    )
                    row = await cursor.fetchone()
                    if row is None:
                        raise RiskDecisionPersistenceError(
                            "idempotent risk decision could not be retrieved"
                        )
                    if (
                        row["proposal_id"] != request.proposal_id
                        or row["request_snapshot"] != request_json
                        or row["policy_snapshot"] != policy_json
                    ):
                        raise RiskDecisionPersistenceError(
                            "idempotency key reused with different risk inputs"
                        )
                    return dict(row)

                await cursor.execute(
                    """
                    insert into system_events (
                        event_type, aggregate_id, occurred_at, recorded_at,
                        producer, producer_version, correlation_id,
                        schema_version, payload, provenance
                    )
                    values (
                        'RiskEvaluated', %s, %s, now(),
                        'phase4-independent-risk', %s, %s,
                        1, %s::jsonb, %s::jsonb
                    )
                    """,
                    (
                        UUID(request.proposal_id) if _is_uuid(request.proposal_id) else uuid5(NAMESPACE_URL, request.proposal_id),
                        decision.evaluated_at,
                        decision.risk_engine_version,
                        correlation_id,
                        json.dumps(decision_json),
                        json.dumps([{
                            "source": "phase4-risk-decision-repository",
                            "engine_version": decision.risk_engine_version,
                        }]),
                    ),
                )
                return dict(row)
            except RiskDecisionPersistenceError:
            raise
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise RiskDecisionPersistenceError(
                "risk decision audit persistence failed"
            ) from exc
