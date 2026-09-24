from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("MITROS_RUN_DEPLOYMENT_E2E") != "true",
    reason="production deployment E2E runs only in the deployment-e2e CI job",
)


API_URL = os.getenv("MITROS_PRODUCTION_API_URL", "https://mitros.onrender.com").rstrip("/")
WEB_URL = os.getenv("MITROS_PRODUCTION_WEB_URL", "https://mitros.vercel.app").rstrip("/")
VERCEL_ORIGIN = os.getenv("MITROS_PRODUCTION_VERCEL_ORIGIN", WEB_URL)

def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict | list, dict[str, str]]:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body), {key.lower(): value for key, value in response.headers.items()}


def request_text(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, str, dict[str, str]]:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.read().decode("utf-8", errors="replace"), {key.lower(): value for key, value in response.headers.items()}


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


def test_production_web_market_api_requires_authentication() -> None:
    try:
        status, body, _ = request_json(f"{WEB_URL}/api/v1/market/quote?asset=BTC%2FUSD&venue=spot")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = {}
    assert status == 401
    assert body.get("detail") == "Authentication required"


def test_production_web_deployment_is_reachable() -> None:
    try:
        status, html, _ = request_text(f"{WEB_URL}/login")
    except Exception as exc:
        pytest.fail(f"Vercel deployment is unreachable: {exc}")
    assert status == 200
    assert "MITROS secure access" in html


def test_production_api_cors_and_health() -> None:
    wait_for_health()
    status, body, headers = request_json(
        f"{API_URL}/health",
        headers={"Origin": VERCEL_ORIGIN},
    )
    assert status == 200
    assert body["status"] == "ok"
    assert headers.get("access-control-allow-origin") == VERCEL_ORIGIN

    preflight_status, _, preflight_headers = request_text(
        f"{API_URL}/api/v1/market/quote?asset=BTC%2FUSD&venue=spot",
        method="OPTIONS",
        headers={
            "Origin": VERCEL_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight_status == 200
    assert preflight_headers.get("access-control-allow-origin") == VERCEL_ORIGIN


def test_production_api_product_routes_require_authentication() -> None:
    for route in (
        "/api/v1/market/health",
        "/api/v1/market/quote?asset=BTC%2FUSD&venue=spot",
        "/api/v1/operations/readiness",
    ):
        try:
            status, body, _ = request_json(f"{API_URL}{route}")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = {}
        assert status == 401
        assert body.get("detail") == "Authentication required"


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


def test_production_web_login_is_public_and_product_routes_are_protected() -> None:
    status, login_html, _ = request_text(f"{WEB_URL}/login")
    assert status == 200
    assert "MITROS secure access" in login_html

    for route, marker in (
        ("/markets", "Markets"),
        ("/intelligence", "Intelligence"),
        ("/strategies", "Strategies"),
        ("/signals", "Signals"),
        ("/risk", "Risk"),
        ("/research", "Research"),
        ("/trading", "Trading"),
        ("/operations", "Operations"),
    ):
        status, html, _ = request_text(f"{WEB_URL}{route}")
        assert status == 200
        assert "MITROS secure access" in html
        assert marker not in html


def test_production_web_protected_api_routes_require_authentication() -> None:
    for route in (
        "/api/v1/operations/readiness",
        "/api/v1/intelligence/snapshot?asset=BTC%2FUSD&venue=spot&timeframe=1h",
        "/api/v1/research/copilot?asset=BTC%2FUSD&venue=spot&timeframe=1h",
    ):
        try:
            status, body, _ = request_json(f"{WEB_URL}{route}")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = {}
        assert status == 401
        assert body.get("detail") == "Authentication required"


def test_production_web_has_no_browser_execution_or_approval_mutation_routes() -> None:
    for route in (
        "/api/v1/approval/approve",
        "/api/v1/approval/reject",
        "/api/v1/execution/order",
        "/api/v1/execution/submit",
    ):
        try:
            status, _, _ = request_text(f"{WEB_URL}{route}", method="POST")
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status == 404
