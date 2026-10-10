from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from contracts.domain import ApprovalStatus, ExecutionStatus, RiskDecision, TradeProposal
from contracts.phase4_risk import RiskDecisionResult, RiskDisposition, RiskEvaluationRequest
from packages.execution.interface import ExecutionResult


class Phase4ProposalPersistenceError(RuntimeError):
    """Raised when Phase 4 lifecycle state cannot be persisted."""


class PostgresPhase4ProposalRepository:
    """Persists owner-scoped Phase 4 proposals and their approval/execution lifecycle."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url

    async def create_approved(
        self, *, user_id: str, proposal: TradeProposal, request: RiskEvaluationRequest,
        decision: RiskDecisionResult, audit_id: UUID,
    ) -> dict[str, Any]:
        if decision.disposition is not RiskDisposition.APPROVED or decision.approved_notional <= 0:
            raise ValueError("only approved Phase 4 decisions can create proposals")
        if decision.proposal_id != request.proposal_id or request.proposal_id != str(proposal.id):
            raise ValueError("proposal/request/risk decision identity mismatch")
        if proposal.risk.decision is not RiskDecision.APPROVED:
            raise ValueError("proposal must carry an approved Phase 4 risk record")
        if proposal.position_size != decision.approved_notional:
            raise ValueError("proposal notional must match the independent risk decision")
        payload = proposal.model_dump(mode="json")
        provenance = [{
            "source": request.account_source,
            "account_snapshot_id": request.account_snapshot_id,
            "account_snapshot_at": request.account_snapshot_at.isoformat() if request.account_snapshot_at else None,
            "market_evidence": list(request.market_evidence),
            "risk_audit_id": str(audit_id),
            "risk_engine_version": decision.risk_engine_version,
        }]
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict_row
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    insert into assets (symbol, asset_class, canonical_symbol, active)
                    values (%s, 'crypto', %s, true)
                    on conflict (asset_class, canonical_symbol) do update set active=true
                    returning id
                    """, (proposal.asset, proposal.asset),
                )
                asset = await cursor.fetchone()
                await cursor.execute("select id from venues where name='xt.com' and active=true")
                venue = await cursor.fetchone()
                if not asset or not venue:
                    raise Phase4ProposalPersistenceError("XT venue or canonical asset is not configured")
                await cursor.execute(
                    """
                    insert into trade_proposals (
                        id, owner_user_id, asset_id, venue_id, direction, entry, stop, target,
                        risk_reward, position_size, risk_decision, risk_reasons,
                        approval_status, execution_status, expires_at, payload, provenance,
                        risk_decision_audit_id
                    ) values (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'APPROVED',%s::jsonb,
                        'PENDING','NOT_AUTHORIZED',%s,%s::jsonb,%s::jsonb,%s
                    )
                    returning id, approval_status, execution_status, created_at
                    """,
                    (
                        proposal.id, user_id, asset["id"], venue["id"], proposal.direction.value,
                        proposal.entry, proposal.stop, proposal.target, proposal.risk_reward,
                        proposal.position_size, json.dumps(list(decision.rejection_reasons) or ["All Phase 4 hard checks passed."]),
                        proposal.expires_at, json.dumps(payload), json.dumps(provenance), audit_id,
                    ),
                )
                row = await cursor.fetchone()
                await cursor.execute(
                    """
                    insert into risk_decisions (trade_proposal_id, decision, reasons, engine_version, evaluated_at)
                    values (%s,'APPROVED',%s::jsonb,%s,%s)
                    """,
                    (proposal.id, json.dumps(["All independent Phase 4 hard checks passed."]),
                     decision.risk_engine_version, decision.evaluated_at),
                )
        except Phase4ProposalPersistenceError:
            raise
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise Phase4ProposalPersistenceError("Phase 4 proposal persistence failed") from exc
        if row is None:
            raise Phase4ProposalPersistenceError("Phase 4 proposal insert returned no row")
        return dict(row)

    async def get(self, *, user_id: str, proposal_id: UUID) -> TradeProposal | None:
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                select payload, approval_status, approval_actor, approval_at, execution_status
                from trade_proposals where id=%s and owner_user_id=%s
                """, (proposal_id, user_id),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        proposal = TradeProposal.model_validate(row["payload"])
        return proposal.model_copy(update={
            "approval_status": ApprovalStatus(row["approval_status"]),
            "approval_actor": row["approval_actor"],
            "approval_at": row["approval_at"],
            "execution_status": ExecutionStatus(row["execution_status"]),
        })

    async def record_approval(
        self, *, user_id: str, proposal: TradeProposal, actor: str, reason: str,
        idempotency_key: str, token_digest: str, decided_at: datetime, risk_audit_id: UUID,
    ) -> None:
        if proposal.approval_status is not ApprovalStatus.PENDING:
            raise ValueError("proposal is no longer pending")
        metadata = json.dumps({
            "reason": reason, "approval_token_digest": token_digest,
            "phase4_revalidated": True, "risk_revalidation_audit_id": str(risk_audit_id),
        })
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict_row
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    insert into approvals (trade_proposal_id, actor, decision, idempotency_key, decided_at, metadata)
                    values (%s,%s,'APPROVED',%s,%s,%s::jsonb)
                    returning id
                    """, (proposal.id, actor, idempotency_key, decided_at, metadata),
                )
                await cursor.execute(
                    """
                    update trade_proposals set approval_status='APPROVED', approval_actor=%s,
                        approval_at=%s, execution_status='NOT_AUTHORIZED'
                    where id=%s and owner_user_id=%s and approval_status='PENDING'
                    """, (actor, decided_at, proposal.id, user_id),
                )
                if cursor.rowcount != 1:
                    raise Phase4ProposalPersistenceError("proposal approval state changed concurrently")
        except Phase4ProposalPersistenceError:
            raise
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise Phase4ProposalPersistenceError("Phase 4 approval persistence failed") from exc

    async def approval_digest(self, *, user_id: str, proposal_id: UUID) -> str | None:
        async with await psycopg.AsyncConnection.connect(
            self.database_url, row_factory=dict_row
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                select a.metadata->>'approval_token_digest' as token_digest
                from approvals a join trade_proposals p on p.id=a.trade_proposal_id
                where p.id=%s and p.owner_user_id=%s and a.decision='APPROVED'
                order by a.decided_at desc limit 1
                """, (proposal_id, user_id),
            )
            row = await cursor.fetchone()
        return str(row["token_digest"]) if row and row["token_digest"] else None

    async def reserve_execution(self, *, user_id: str, proposal: TradeProposal) -> None:
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict_row
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    insert into orders (trade_proposal_id, client_order_id, venue, status, submitted_at, updated_at, payload)
                    select id, %s, (select name from venues where id=venue_id),
                        'SUBMITTING', now(), now(), %s::jsonb
                    from trade_proposals
                    where id=%s and owner_user_id=%s and approval_status='APPROVED'
                    on conflict (client_order_id) do nothing
                    """,
                    (str(proposal.id), json.dumps({"intent_recorded": True}), proposal.id, user_id),
                )
                if cursor.rowcount != 1:
                    raise Phase4ProposalPersistenceError("execution intent exists or proposal is not approved")
                await cursor.execute(
                    "update trade_proposals set execution_status='SUBMITTING' where id=%s and owner_user_id=%s",
                    (proposal.id, user_id),
                )
        except Phase4ProposalPersistenceError:
            raise
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise Phase4ProposalPersistenceError("execution intent could not be persisted") from exc

    async def record_execution(self, *, user_id: str, proposal_id: UUID, result: ExecutionResult) -> None:
        payload = {
            "client_order_id": result.client_order_id, "venue_order_id": result.venue_order_id,
            "status": result.status, "filled_quantity": str(result.filled_quantity),
            "average_price": str(result.average_price) if result.average_price is not None else None,
            "reason": result.reason,
        }
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict_row
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    update orders set venue_order_id=%s, status=%s, updated_at=now(), payload=%s::jsonb
                    where client_order_id=%s and trade_proposal_id=%s
                    """, (result.venue_order_id, result.status, json.dumps(payload), str(proposal_id), proposal_id),
                )
                if cursor.rowcount != 1:
                    raise Phase4ProposalPersistenceError("execution order intent not found")
                await cursor.execute(
                    "update trade_proposals set execution_status=%s where id=%s and owner_user_id=%s",
                    (result.status, proposal_id, user_id),
                )
        except Phase4ProposalPersistenceError:
            raise
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise Phase4ProposalPersistenceError("execution reconciliation persistence failed") from exc

    async def mark_execution_unknown(self, *, user_id: str, proposal_id: UUID, reason: str) -> None:
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, row_factory=dict
            ) as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    """
                    update orders set status='UNKNOWN', updated_at=now(), payload=%s::jsonb
                    where client_order_id=%s and trade_proposal_id=%s
                    """, (json.dumps({"reason": reason, "reconciliation_required": True}), str(proposal_id), proposal_id),
                )
                await cursor.execute(
                    "update trade_proposals set execution_status='UNKNOWN' where id=%s and owner_user_id=%s",
                    (proposal_id, user_id),
                )
        except (psycopg.Error, ValueError, TypeError) as exc:
            raise Phase4ProposalPersistenceError("execution unknown state could not be persisted") from exc
