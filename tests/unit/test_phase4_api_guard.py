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
