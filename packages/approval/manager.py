from datetime import datetime, timezone
from uuid import uuid4

from contracts.approval import ApprovalDecision, ApprovalOutcome, ApprovalRecord
from contracts.domain import ApprovalStatus, ExecutionStatus, TradeProposal


class HumanApprovalManager:
    """Explicit human gate. Approval is recorded but never submits an order."""

    version = "1.0.0"

    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalOutcome] = {}

    def approve(
        self,
        proposal: TradeProposal,
        *,
        actor: str,
        reason: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ApprovalOutcome:
        return self._decide(
            proposal,
            decision=ApprovalDecision.APPROVED,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            now=now,
        )

    def reject(
        self,
        proposal: TradeProposal,
        *,
        actor: str,
        reason: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ApprovalOutcome:
        return self._decide(
            proposal,
            decision=ApprovalDecision.REJECTED,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            now=now,
        )

    def _decide(
        self,
        proposal: TradeProposal,
        *,
        decision: ApprovalDecision,
        actor: str,
        reason: str,
        idempotency_key: str,
        now: datetime | None,
    ) -> ApprovalOutcome:
        if not actor.strip() or not reason.strip() or not idempotency_key.strip():
            raise ValueError("actor, reason, and idempotency_key are required")
        existing = self._decisions.get(idempotency_key)
        if existing is not None:
            if existing.proposal_id != proposal.id:
                raise ValueError("idempotency key already belongs to another proposal")
            return existing
        if proposal.approval_status is not ApprovalStatus.PENDING:
            raise ValueError("proposal is no longer pending human approval")
        decided_at = now or datetime.now(timezone.utc)
        if decided_at >= proposal.expires_at:
            raise ValueError("proposal has expired")
        if proposal.risk.decision.value != "APPROVED":
            raise ValueError("human approval requires an approved risk decision")

        token = str(uuid4()) if decision is ApprovalDecision.APPROVED else None
        record = ApprovalRecord(
            proposal_id=proposal.id,
            actor=actor.strip(),
            decision=decision,
            reason=reason.strip(),
            idempotency_key=idempotency_key,
            decided_at=decided_at,
            approval_token=token,
        )
        outcome = ApprovalOutcome(
            proposal_id=proposal.id,
            decision=decision,
            approval=record,
            execution_authorized=decision is ApprovalDecision.APPROVED,
        )
        self._decisions[idempotency_key] = outcome
        return outcome

    @staticmethod
    def apply(
        proposal: TradeProposal,
        outcome: ApprovalOutcome,
    ) -> TradeProposal:
        if outcome.proposal_id != proposal.id:
            raise ValueError("approval does not belong to proposal")
        status = (
            ApprovalStatus.APPROVED
            if outcome.decision is ApprovalDecision.APPROVED
            else ApprovalStatus.REJECTED
        )
        return proposal.model_copy(
            update={
                "approval_status": status,
                "approval_actor": outcome.approval.actor,
                "approval_at": outcome.approval.decided_at,
                "execution_status": ExecutionStatus.NOT_AUTHORIZED,
            }
        )
