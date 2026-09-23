# Phase 11 — Trade Proposal + Human Approval

MITROS now materializes a risk-approved signal as an immutable TradeProposal and places an explicit human decision between risk and execution.

## Flow

Strategy and intelligence evidence -> Risk Engine -> Trade Proposal -> Human Approval -> Execution Gateway.

## Trade proposal

TradeProposalBuilder requires:
- a non-expired directional signal;
- an independently approved RiskAssessment with a positive approved size;
- directionally consistent entry, stop and target;
- bounded MTF alignment and data quality.

Risk sizing is copied from the approved risk result; the proposal cannot increase it.

## Human approval

HumanApprovalManager requires:
- a non-empty human actor;
- a reason;
- an idempotency key;
- an unexpired proposal still in PENDING;
- an approved risk decision.

Approval creates an immutable ApprovalRecord and an opaque approval token. Replaying the same idempotency key is idempotent. A different decision cannot be applied after the proposal has left PENDING.

Rejection creates an immutable audit record and no token.

## Execution boundary

Approval does not call or import the execution gateway. The approved proposal remains NOT_AUTHORIZED in ExecutionStatus; the token is the explicit capability passed later to the isolated execution gateway.

No order is submitted in Phase 11.

## Safety properties

- Risk remains independent of human approval.
- Human approval cannot alter risk sizing.
- Expired or risk-rejected proposals cannot be approved.
- No implicit, automatic, or AI-generated approval path exists.
- No execution capability is imported by the approval package.
