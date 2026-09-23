from contracts.domain import ApprovalStatus, Direction, ExecutionStatus, TradeProposal
from packages.execution.interface import (
    ExecutionGateway,
    ExecutionOrder,
    ExecutionOrderType,
    ExecutionResult,
    ExecutionSide,
)
from packages.execution.security import verify_approval_token


class ProposalExecutionGateway:
    """The sole application boundary that turns an approved proposal into an order."""

    version = "1.0.0"

    def __init__(self, venue_gateway: ExecutionGateway, *, approval_digest: str) -> None:
        if not approval_digest:
            raise ValueError("approval digest is required")
        self._venue_gateway = venue_gateway
        self._approval_digest = approval_digest

    def submit(self, proposal: TradeProposal, approval_token: str) -> ExecutionResult:
        if proposal.approval_status is not ApprovalStatus.APPROVED:
            raise ValueError("proposal is not human-approved")
        if proposal.execution_status not in {
            ExecutionStatus.NOT_AUTHORIZED,
            ExecutionStatus.AUTHORIZED,
        }:
            raise ValueError("proposal is already executing or terminal")
        if not verify_approval_token(approval_token, self._approval_digest):
            raise ValueError("invalid approval token")
        side = ExecutionSide.BUY if proposal.direction is Direction.LONG else ExecutionSide.SELL
        order = ExecutionOrder(
            client_order_id=str(proposal.id),
            venue=proposal.venue,
            asset=proposal.asset,
            side=side,
            quantity=proposal.position_size,
            order_type=ExecutionOrderType.MARKET,
        )
        return self._venue_gateway.submit(order, approval_token)
