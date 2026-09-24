from fastapi.testclient import TestClient

from packages.api.app import app, get_settings


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_is_paper_and_human_approval_required() -> None:
    response = TestClient(app).get("/api/v1/operations/readiness")
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
    response = TestClient(app).get("/api/v1/market/quote?asset=BTC%2FUSD&venue=spot")
    assert response.status_code == 503
    get_settings.cache_clear()
