from fastapi.testclient import TestClient

from packages.api.app import app
from packages.api.auth import AuthenticatedUser, require_user


TEST_USER = AuthenticatedUser(
    user_id="00000000-0000-0000-0000-000000000019",
    email="test@example.com",
    role="user",
    entitlements=("free",),
    assurance_level="aal1",
)

INTENT = {
    "proposal_id": "proposal-test-001",
    "asset": "BTC/USDT",
    "direction": "LONG",
    "entry": "100",
    "stop_loss": "95",
    "take_profit": "110",
    "requested_notional": "1000",
    "idempotency_key": "phase4-test-key-0001",
}


def _post(payload: dict):
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        return TestClient(app).post("/api/v1/risk/phase4/evaluate", json=payload)
    finally:
        app.dependency_overrides.pop(require_user, None)


def test_phase4_risk_route_requires_database_storage(monkeypatch) -> None:
    monkeypatch.delenv("MITROS_DATABASE_URL", raising=False)
    response = _post(INTENT)
    assert response.status_code == 503
    assert "database storage" in response.json()["detail"]


def test_phase4_intent_does_not_accept_client_portfolio_as_authority() -> None:
    from packages.api.app import Phase4RiskIntent

    payload = {
        **INTENT,
        "equity": "1",
        "daily_pnl": "-999999",
        "peak_equity": "1",
        "open_positions": [],
        "data_verified": True,
        "data_quality": "1",
        "spread_fraction": "0",
    }
    intent = Phase4RiskIntent.model_validate(payload)
    assert intent.asset == "BTC/USDT"
    assert not hasattr(intent, "equity")
    assert not hasattr(intent, "open_positions")
    assert not hasattr(intent, "data_verified")


def test_phase4_requires_xt_credentials_before_any_risk_decision(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_DATABASE_URL", "postgresql://unreachable/test")
    monkeypatch.delenv("MITROS_XT_API_KEY", raising=False)
    monkeypatch.delenv("MITROS_XT_API_SECRET", raising=False)
    for key, value in {
        "MITROS_RISK_MAX_RISK_PER_TRADE": "0.01",
        "MITROS_RISK_MAX_POSITION_FRACTION": "0.20",
        "MITROS_RISK_MAX_GROSS_EXPOSURE_FRACTION": "1.0",
        "MITROS_RISK_MAX_DAILY_LOSS_FRACTION": "0.03",
        "MITROS_RISK_MAX_DRAWDOWN_FRACTION": "0.10",
        "MITROS_RISK_MAX_ASSET_CONCENTRATION_FRACTION": "0.30",
        "MITROS_RISK_MAX_CORRELATED_POSITIONS": "2",
        "MITROS_RISK_MAX_CORRELATED_EXPOSURE_FRACTION": "0.40",
        "MITROS_RISK_MAX_OPEN_POSITIONS": "5",
        "MITROS_RISK_MIN_RISK_REWARD": "2",
        "MITROS_RISK_MAX_SPREAD_FRACTION": "0.002",
        "MITROS_RISK_MAX_SLIPPAGE_FRACTION": "0.001",
        "MITROS_RISK_MIN_DATA_QUALITY": "0.90",
        "MITROS_RISK_MAX_QUOTE_AGE_SECONDS": "60",
        "MITROS_RISK_EXPECTED_SLIPPAGE_FRACTION": "0.001",
    }.items():
        monkeypatch.setenv(key, value)
    response = _post(INTENT)
    assert response.status_code == 503
    assert "XT account state" in response.json()["detail"]



def _phase4_proposal_fixture():
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal
    from uuid import uuid4

    from contracts.domain import Direction, StrategyVote
    from contracts.phase4_risk import RiskEvaluationRequest, RiskPolicy
    from contracts.signal import SignalRecord
    from packages.proposals.phase4_builder import Phase4TradeProposalBuilder
    from packages.risk.phase4 import IndependentRiskGate

    now = datetime.now(UTC)
    signal = SignalRecord(
        id=uuid4(), asset="BTC/USDT", venue="spot", direction=Direction.LONG,
        created_at=now, expires_at=now + timedelta(minutes=15),
        strategy_votes=(StrategyVote(
            strategy_id="smc", strategy_version="1.0.0", direction=Direction.LONG,
            confidence=Decimal("0.9"),
        ),),
        confidence=Decimal("0.9"),
    )
    policy = RiskPolicy(
        max_risk_per_trade=Decimal("0.01"), max_position_fraction=Decimal("0.20"),
        max_gross_exposure_fraction=Decimal("1"), max_daily_loss_fraction=Decimal("0.03"),
        max_drawdown_fraction=Decimal("0.10"), max_asset_concentration_fraction=Decimal("0.30"),
        max_correlated_positions=2, max_correlated_exposure_fraction=Decimal("0.40"),
        max_open_positions=5, min_risk_reward=Decimal("2"),
        max_spread_fraction=Decimal("0.002"), max_slippage_fraction=Decimal("0.001"),
        min_data_quality=Decimal("0.90"), max_quote_age_seconds=60,
    )
    request = RiskEvaluationRequest(
        proposal_id=str(signal.id), asset="BTC/USDT", correlated_group="BTC-beta",
        direction=Direction.LONG, as_of=now, quote_observed_at=now - timedelta(seconds=2),
        data_verified=True, data_quality=Decimal("1"), equity=Decimal("10000"),
        daily_pnl=Decimal("0"), peak_equity=Decimal("10000"), open_positions=(),
        requested_notional=Decimal("1000"), entry=Decimal("100"), stop_loss=Decimal("95"),
        take_profit=Decimal("110"), spread_fraction=Decimal("0.001"),
        expected_slippage_fraction=Decimal("0.001"),
    )
    decision = IndependentRiskGate(policy).evaluate(request)
    proposal = Phase4TradeProposalBuilder().build(
        signal, request, decision, venue="xt.com", regime="TREND_UP",
        mtf_alignment=Decimal("0.9"), now=now,
    )
    return signal, policy, request, decision, proposal


def test_rejected_fresh_risk_cannot_advance_proposal_to_human_approval(monkeypatch) -> None:
    from decimal import Decimal
    from packages.api import app as api_module
    from contracts.phase4_risk import RiskDisposition
    from packages.risk.phase4 import IndependentRiskGate

    _, policy, request, _, proposal = _phase4_proposal_fixture()
    rejected_request = request.model_copy(update={"daily_pnl": Decimal("-500")})
    rejected_decision = IndependentRiskGate(policy).evaluate(rejected_request)
    assert rejected_decision.disposition is RiskDisposition.REJECTED
    response = api_module.Phase4RiskEvaluationResponse(
        scope="XT_ACCOUNT", audit_id="00000000-0000-0000-0000-000000000055",
        account_snapshot_id="snapshot-test", market_evidence={}, decision=rejected_decision,
    )

    class FakeRepository:
        def __init__(self, database_url: str) -> None:
            self.approvals = []

        async def get(self, *, user_id: str, proposal_id):
            return proposal

        async def record_approval(self, **kwargs) -> None:
            self.approvals.append(kwargs)

    fake = FakeRepository("unused")

    async def evaluate(*args, **kwargs):
        return response, rejected_request, policy

    monkeypatch.setenv("MITROS_DATABASE_URL", "postgresql://unused/test")
    monkeypatch.setattr(api_module, "PostgresPhase4ProposalRepository", lambda database_url: fake)
    monkeypatch.setattr(api_module, "_evaluate_phase4_intent", evaluate)
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        result = TestClient(app).post(
            f"/api/v1/proposals/{proposal.id}/approve",
            json={"reason": "reviewed", "idempotency_key": "approve-test-key"},
        )
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert result.status_code == 409
    assert fake.approvals == []


def test_approved_proposal_revalidates_risk_before_issuing_human_approval(monkeypatch) -> None:
    from packages.api import app as api_module

    _, policy, request, decision, proposal = _phase4_proposal_fixture()
    response = api_module.Phase4RiskEvaluationResponse(
        scope="XT_ACCOUNT", audit_id="00000000-0000-0000-0000-000000000056",
        account_snapshot_id="snapshot-fresh", market_evidence={}, decision=decision,
    )

    class FakeRepository:
        def __init__(self, database_url: str) -> None:
            self.approval_record = None

        async def get(self, *, user_id: str, proposal_id):
            return proposal

        async def record_approval(self, **kwargs) -> None:
            self.approval_record = kwargs

    fake = FakeRepository("unused")

    async def evaluate(*args, **kwargs):
        return response, request, policy

    monkeypatch.setenv("MITROS_DATABASE_URL", "postgresql://unused/test")
    monkeypatch.setattr(api_module, "PostgresPhase4ProposalRepository", lambda database_url: fake)
    monkeypatch.setattr(api_module, "_evaluate_phase4_intent", evaluate)
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        result = TestClient(app).post(
            f"/api/v1/proposals/{proposal.id}/approve",
            json={"reason": "fresh risk revalidated", "idempotency_key": "approve-test-key-2"},
        )
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert result.status_code == 200
    assert result.json()["status"] == "APPROVED"
    assert result.json()["approval_token"]
    assert fake.approval_record is not None
    assert str(fake.approval_record["risk_audit_id"]) == response.audit_id



def test_rejected_phase4_decision_never_persists_a_trade_proposal(monkeypatch) -> None:
    from packages.api import app as api_module
    from contracts.phase4_risk import RiskDisposition
    from packages.risk.phase4 import IndependentRiskGate

    signal, policy, request, _, _ = _phase4_proposal_fixture()
    rejected_request = request.model_copy(update={"data_verified": False})
    rejected_decision = IndependentRiskGate(policy).evaluate(rejected_request)
    assert rejected_decision.disposition is RiskDisposition.REJECTED
    response = api_module.Phase4RiskEvaluationResponse(
        scope="XT_ACCOUNT", audit_id="00000000-0000-0000-0000-000000000057",
        account_snapshot_id="snapshot-test", market_evidence={}, decision=rejected_decision,
    )

    class FakeRepository:
        def __init__(self, database_url: str) -> None:
            self.created = False

        async def create_approved(self, **kwargs) -> None:
            self.created = True

    fake = FakeRepository("unused")

    async def evaluate(*args, **kwargs):
        return response, rejected_request, policy

    monkeypatch.setenv("MITROS_DATABASE_URL", "postgresql://unused/test")
    monkeypatch.setattr(api_module, "PostgresPhase4ProposalRepository", lambda database_url: fake)
    monkeypatch.setattr(api_module, "_evaluate_phase4_intent", evaluate)
    body = {
        "intent": {
            "proposal_id": str(signal.id),
            "asset": "BTC/USDT",
            "direction": "LONG",
            "entry": "100",
            "stop_loss": "95",
            "take_profit": "110",
            "requested_notional": "1000",
            "idempotency_key": "rejected-proposal-test",
        },
        "signal": signal.model_dump(mode="json"),
        "regime": "TREND_UP",
        "mtf_alignment": "0.9",
        "model_versions": [],
    }
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        result = TestClient(app).post("/api/v1/proposals/phase4", json=body)
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert result.status_code == 409
    assert not fake.created
    assert result.json()["detail"]["audit_id"] == response.audit_id



def test_rejected_execution_revalidation_cannot_reserve_or_submit_order(monkeypatch) -> None:
    from decimal import Decimal
    from contracts.domain import ApprovalStatus, ExecutionStatus
    from contracts.phase4_risk import RiskDisposition
    from packages.api import app as api_module
    from packages.execution.security import approval_token_digest
    from packages.risk.phase4 import IndependentRiskGate

    _, policy, request, _, pending = _phase4_proposal_fixture()
    proposal = pending.model_copy(update={
        "approval_status": ApprovalStatus.APPROVED,
        "approval_actor": TEST_USER.user_id,
        "approval_at": request.as_of,
        "execution_status": ExecutionStatus.NOT_AUTHORIZED,
    })
    rejected_request = request.model_copy(update={"daily_pnl": Decimal("-500")})
    rejected_decision = IndependentRiskGate(policy).evaluate(rejected_request)
    assert rejected_decision.disposition is RiskDisposition.REJECTED
    response = api_module.Phase4RiskEvaluationResponse(
        scope="XT_ACCOUNT", audit_id="00000000-0000-0000-0000-000000000058",
        account_snapshot_id="snapshot-latest", market_evidence={}, decision=rejected_decision,
    )
    token = "phase4-human-approval-token"

    class FakeRepository:
        def __init__(self, database_url: str) -> None:
            self.reserved = False

        async def get(self, *, user_id: str, proposal_id):
            return proposal

        async def approval_digest(self, *, user_id: str, proposal_id):
            return approval_token_digest(token)

        async def reserve_execution(self, **kwargs) -> None:
            self.reserved = True

    fake = FakeRepository("unused")

    async def evaluate(*args, **kwargs):
        return response, rejected_request, policy

    monkeypatch.setenv("MITROS_DATABASE_URL", "postgresql://unused/test")
    monkeypatch.setattr(api_module, "PostgresPhase4ProposalRepository", lambda database_url: fake)
    monkeypatch.setattr(api_module, "_evaluate_phase4_intent", evaluate)
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        result = TestClient(app).post(
            f"/api/v1/proposals/{proposal.id}/execute",
            json={"approval_token": token},
        )
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert result.status_code == 409
    assert not fake.reserved



def test_phase4_readiness_reports_missing_xt_and_database_without_exposing_secrets(monkeypatch) -> None:
    monkeypatch.delenv("MITROS_DATABASE_URL", raising=False)
    monkeypatch.delenv("MITROS_XT_API_KEY", raising=False)
    monkeypatch.delenv("MITROS_XT_API_SECRET", raising=False)
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        response = TestClient(app).get("/api/v1/risk/phase4/readiness")
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["checks"]["database_configured"] is False
    assert payload["checks"]["xt_credentials_configured"] is False
    assert payload["checks"]["live_trading_disabled"] is True
    assert "MITROS_XT_API_SECRET" not in response.text
