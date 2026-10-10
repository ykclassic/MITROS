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

BODY = {
    "idempotency_key": "phase4-test-key-0001",
    "request": {
        "proposal_id": "proposal-test-001",
        "asset": "BTC/USD",
        "correlated_group": "BTC-beta",
        "direction": "LONG",
        "as_of": "2026-10-10T12:00:00Z",
        "quote_observed_at": "2026-10-10T11:59:55Z",
        "data_verified": True,
        "data_quality": "0.99",
        "equity": "10000",
        "daily_pnl": "0",
        "peak_equity": "10000",
        "open_positions": [],
        "requested_notional": "1000",
        "entry": "100",
        "stop_loss": "95",
        "take_profit": "110",
        "spread_fraction": "0.001",
        "expected_slippage_fraction": "0.0005",
    },
}


def test_phase4_risk_route_is_disabled_in_live_mode(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_EXECUTION_MODE", "live")
    monkeypatch.delenv("MITROS_DATABASE_URL", raising=False)
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        response = TestClient(app).post("/api/v1/risk/phase4/scenario", json=BODY)
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 503
    assert "authoritative account-state integration" in response.json()["detail"]


def test_phase4_risk_route_requires_durable_audit_storage(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_EXECUTION_MODE", "paper")
    monkeypatch.delenv("MITROS_DATABASE_URL", raising=False)
    app.dependency_overrides[require_user] = lambda: TEST_USER
    try:
        response = TestClient(app).post("/api/v1/risk/phase4/scenario", json=BODY)
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 503
    assert "audit storage" in response.json()["detail"]
