from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
from threading import RLock
from uuid import UUID

from contracts.ledger import ExecutionIntent, LedgerEntry, LedgerOrderState
from packages.execution.interface import ExecutionOrder, ExecutionResult


class ExecutionLedger:
    """Append-only execution journal with idempotent intent creation and state recovery."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[LedgerEntry, ...]] = {}
        self._intents: dict[str, ExecutionIntent] = {}
        self._lock = RLock()

    @staticmethod
    def fingerprint(order: ExecutionOrder) -> str:
        material = "|".join(
            (
                order.client_order_id,
                order.venue,
                order.asset,
                order.side.value,
                str(order.quantity),
                order.order_type.value,
                str(order.limit_price),
            )
        )
        return sha256(material.encode("utf-8")).hexdigest()

    def record_intent(
        self,
        *,
        proposal_id: UUID,
        order: ExecutionOrder,
        now: datetime,
    ) -> ExecutionIntent:
        with self._lock:
            existing = self._intents.get(order.client_order_id)
            if existing is not None:
                if existing.proposal_id != proposal_id:
                    raise ValueError("client order id is bound to another proposal")
                return existing
            intent = ExecutionIntent(
                proposal_id=proposal_id,
                client_order_id=order.client_order_id,
                venue=order.venue,
                asset=order.asset,
                quantity=order.quantity,
                created_at=now,
            )
            self._intents[order.client_order_id] = intent
            self._append(
                LedgerEntry(
                    client_order_id=order.client_order_id,
                    proposal_id=proposal_id,
                    state=LedgerOrderState.INTENDED,
                    recorded_at=now,
                    attempt=0,
                    request_fingerprint=self.fingerprint(order),
                )
            )
            return intent

    def begin_submission(self, order: ExecutionOrder, *, now: datetime) -> LedgerEntry:
        with self._lock:
            latest = self.latest(order.client_order_id)
            if latest is None:
                raise ValueError("execution intent must be recorded before submission")
            if latest.state in {
                LedgerOrderState.SUBMITTED,
                LedgerOrderState.PARTIALLY_FILLED,
                LedgerOrderState.FILLED,
                LedgerOrderState.CANCELLED,
                LedgerOrderState.REJECTED,
                LedgerOrderState.RECONCILED,
            }:
                return latest
            entry = LedgerEntry(
                client_order_id=order.client_order_id,
                proposal_id=latest.proposal_id,
                state=LedgerOrderState.SUBMITTING,
                recorded_at=now,
                attempt=latest.attempt + 1,
                request_fingerprint=self.fingerprint(order),
            )
            self._append(entry)
            return entry

    def record_result(
        self,
        order: ExecutionOrder,
        result: ExecutionResult,
        *,
        now: datetime,
    ) -> LedgerEntry:
        with self._lock:
            latest = self.latest(order.client_order_id)
            if latest is None:
                raise ValueError("execution intent must be recorded before result")
            state = self._state_for_result(result)
            entry = LedgerEntry(
                client_order_id=order.client_order_id,
                proposal_id=latest.proposal_id,
                state=state,
                result=result,
                recorded_at=now,
                attempt=latest.attempt,
                request_fingerprint=self.fingerprint(order),
            )
            self._append(entry)
            return entry

    def mark_unknown(self, client_order_id: str, *, now: datetime, reason: str) -> LedgerEntry:
        with self._lock:
            latest = self.latest(client_order_id)
            if latest is None:
                raise ValueError("unknown order is not in the ledger")
            entry = latest.model_copy(
                update={
                    "state": LedgerOrderState.UNKNOWN,
                    "recorded_at": now,
                    "result": ExecutionResult(
                        client_order_id=client_order_id,
                        venue_order_id=latest.result.venue_order_id if latest.result else None,
                        status="UNKNOWN",
                        filled_quantity=latest.result.filled_quantity if latest.result else Decimal("0"),
                        average_price=latest.result.average_price if latest.result else None,
                        reason=reason,
                    ),
                }
            )
            self._append(entry)
            return entry

    def latest(self, client_order_id: str) -> LedgerEntry | None:
        entries = self._entries.get(client_order_id, ())
        return entries[-1] if entries else None

    def history(self, client_order_id: str) -> tuple[LedgerEntry, ...]:
        return self._entries.get(client_order_id, ())

    def intents(self) -> tuple[ExecutionIntent, ...]:
        return tuple(self._intents.values())

    @staticmethod
    def _state_for_result(result: ExecutionResult) -> LedgerOrderState:
        mapping: Mapping[str, LedgerOrderState] = {
            "SUBMITTED": LedgerOrderState.SUBMITTED,
            "PARTIALLY_FILLED": LedgerOrderState.PARTIALLY_FILLED,
            "FILLED": LedgerOrderState.FILLED,
            "CANCELLED": LedgerOrderState.CANCELLED,
            "REJECTED": LedgerOrderState.REJECTED,
            "UNKNOWN": LedgerOrderState.UNKNOWN,
        }
        return mapping.get(result.status, LedgerOrderState.UNKNOWN)

    def _append(self, entry: LedgerEntry) -> None:
        history = self._entries.setdefault(entry.client_order_id, ())
        if history and entry.recorded_at < history[-1].recorded_at:
            raise ValueError("ledger timestamps must be monotonic")
        self._entries[entry.client_order_id] = history + (entry,)
