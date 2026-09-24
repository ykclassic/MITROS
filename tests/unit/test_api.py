from fastapi.testclient import TestClient

from packages.api.app import app, create_app, get_settings
from packages.api.auth import AuthenticatedUser, require_user


TEST_USER = AuthenticatedUser(
    user_id="00000000-0000-0000-0000-000000000019",
    email="test@example.com",
    role="user",
    entitlements=("free",),
    assurance_level="aal1",
)


def authenticated_client() -> TestClient:
    app.dependency_overrides[require_user] = lambda: TEST_USER
    return TestClient(app)


def clear_auth_override() -> None:
    app.dependency_overrides.pop(require_user, None)



def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_is_paper_and_human_approval_required() -> None:
    client = authenticated_client()
    response = client.get("/api/v1/operations/readiness")
    clear_auth_override()
    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "paper"
    assert body["live_trading_enabled"] is False
    assert body["checks"]["human_approval"] == "REQUIRED"


def test_quote_fails_closed_without_provider_credentials(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("MITROS_MARKET_TWELVEDATA_API_KEY", raising=False)
    monkeypatch.delenv("MITROS_MARKET_FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("MITROS_MARKET_ALPHAVANTAGE_API_KEY", raising=False)
    client = authenticated_client()
    response = client.get("/api/v1/market/quote?asset=BTC%2FUSD&venue=spot")
    clear_auth_override()
    assert response.status_code == 503
    get_settings.cache_clear()


def test_production_vcs_origin_is_allowed(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_ALLOWED_ORIGINS", "https://mitros.vercel.app")
    response = TestClient(create_app()).get(
        "/health",
        headers={"Origin": "https://mitros.vercel.app"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://mitros.vercel.app"


def test_risk_assessment_is_independent_and_fail_closed() -> None:
    client = authenticated_client()
    params = {
        "asset": "BTC/USD", "equity": "10000", "daily_pnl": "0", "peak_equity": "10000",
        "existing_exposure": "0", "requested_size": "100", "stop_distance_fraction": "0.01",
        "spread_fraction": "0.001", "correlated_exposure": "0", "max_position_fraction": "0.02",
        "max_gross_exposure": "1", "max_daily_loss_fraction": "0.03", "max_drawdown_fraction": "0.10",
        "max_concentration_fraction": "0.25", "max_leverage": "2", "max_spread_fraction": "0.005",
        "max_risk_fraction": "0.01", "max_correlation_exposure": "0.50",
    }
    response = client.get("/api/v1/risk/assessment", params=params)
    assert response.status_code == 200
    body = response.json()
    assert body["approved"] is True
    assert body["approved_size"] == "100"
    clear_auth_override()


def test_product_api_requires_authentication() -> None:
    clear_auth_override()
    response = TestClient(app).get("/api/v1/operations/readiness")
    assert response.status_code == 401


def test_authenticated_identity_is_returned_from_verified_dependency() -> None:
    client = authenticated_client()
    response = client.get("/api/v1/auth/me")
    clear_auth_override()
    assert response.status_code == 200
    assert response.json() == {
        "user_id": TEST_USER.user_id,
        "email": TEST_USER.email,
        "role": "user",
        "entitlements": ["free"],
        "assurance_level": "aal1",
    }
