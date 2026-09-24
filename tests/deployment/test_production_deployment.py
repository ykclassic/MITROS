from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal

import pytest


API_URL = os.getenv("MITROS_PRODUCTION_API_URL", "https://mitros.onrender.com").rstrip("/")
WEB_URL = os.getenv("MITROS_PRODUCTION_WEB_URL", "https://mitros.vercel.app").rstrip("/")
VERCEL_ORIGIN = os.getenv("MITROS_PRODUCTION_VERCEL_ORIGIN", WEB_URL)
EXPECTED_PROVIDERS = {"twelvedata", "finnhub", "alphavantage"}


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict | list, dict[str, str]]:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body), dict(response.headers)


def request_text(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, str, dict[str, str]]:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.read().decode("utf-8", errors="replace"), dict(response.headers)


def wait_for_health() -> None:
    deadline = time.monotonic() + 300
    last_error = ""
    while time.monotonic() < deadline:
        try:
            status, body, _ = request_json(f"{API_URL}/health")
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                return
            last_error = f"unexpected health response: {status} {body!r}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = repr(exc)
        time.sleep(10)
    pytest.fail(f"Production API did not become healthy: {last_error}")


def test_production_web_deployment_is_reachable() -> None:
    try:
        status, html, _ = request_text(f"{WEB_URL}/markets")
    except Exception as exc:
        pytest.fail(f"Vercel deployment is unreachable: {exc}")
    assert status == 200
    assert "BTC/USD" in html
    assert "ETH/USD" in html


def test_production_api_cors_and_health() -> None:
    wait_for_health()
    status, body, headers = request_json(
        f"{API_URL}/health",
        headers={"Origin": VERCEL_ORIGIN},
    )
    assert status == 200
    assert body["status"] == "ok"
    assert headers.get("Access-Control-Allow-Origin") == VERCEL_ORIGIN

    preflight_status, _, preflight_headers = request_text(
        f"{API_URL}/api/v1/market/quote?asset=BTC%2FUSD&venue=spot",
        method="OPTIONS",
        headers={
            "Origin": VERCEL_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight_status == 200
    assert preflight_headers.get("Access-Control-Allow-Origin") == VERCEL_ORIGIN


def test_all_three_provider_credentials_are_runtime_usable() -> None:
    status, body, _ = request_json(f"{API_URL}/api/v1/market/health")
    assert status == 200
    assert isinstance(body, list)
    providers = {item["provider"]: item for item in body}
    assert set(providers) == EXPECTED_PROVIDERS
    unavailable = {
        name: item.get("error") or "unavailable"
        for name, item in providers.items()
        if item.get("available") is not True
    }
    assert not unavailable, f"Provider runtime health failures: {unavailable}"


@pytest.mark.parametrize("asset", ["BTC/USD", "ETH/USD"])
def test_production_quote(asset: str) -> None:
    status, body, _ = request_json(
        f"{API_URL}/api/v1/market/quote?asset={asset.replace('/', '%2F')}&venue=spot"
    )
    assert status == 200
    assert body["asset"] == asset
    assert body["provider"] in EXPECTED_PROVIDERS
    assert Decimal(body["price"]) > 0
    assert body["quality"] == "VERIFIED"
    datetime.fromisoformat(body["observed_at"])
    datetime.fromisoformat(body["received_at"])


def test_production_web_does_not_expose_provider_credentials() -> None:
    _, html, _ = request_text(f"{WEB_URL}/markets")
    assert "MITROS_MARKET_TWELVEDATA_API_KEY" not in html
    assert "MITROS_MARKET_FINNHUB_API_KEY" not in html
    assert "MITROS_MARKET_ALPHAVANTAGE_API_KEY" not in html
    assert not re.search(r"(sk-|ghp_|AKIA[0-9A-Z]{16})", html)


def test_frontend_api_url_contract_matches_render() -> None:
    assert API_URL == "https://mitros.onrender.com"
    assert WEB_URL == "https://mitros.vercel.app"
    assert VERCEL_ORIGIN == WEB_URL
