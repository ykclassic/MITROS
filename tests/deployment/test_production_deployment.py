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


def request_text_no_redirect(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, str, dict[str, str]]:
    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(url, method=method, headers=headers or {})
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", errors="replace"), {
                key.lower(): value for key, value in response.headers.items()
            }
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), {
            key.lower(): value for key, value in exc.headers.items()
        }


def wait_for_web_login() -> None:
    deadline = time.monotonic() + 300
    last_error = ""
    while time.monotonic() < deadline:
        try:
            status, html, _ = request_text(f"{WEB_URL}/login")
            if status == 200 and "MITROS secure access" in html:
                return
            last_error = f"unexpected login response: {status}"
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = repr(exc)
        time.sleep(10)
    pytest.fail(f"Vercel auth deployment did not become reachable: {last_error}")


def wait_for_backend_auth_boundary() -> None:
    deadline = time.monotonic() + 300
    last_error = ""
    while time.monotonic() < deadline:
        try:
            status, body, _ = request_json(f"{API_URL}/api/v1/operations/readiness")
            if status == 401 and body.get("detail") == "Authentication required":
                return
            last_error = f"unexpected auth boundary response: {status} {body!r}"
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return
            last_error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = repr(exc)
        time.sleep(10)
    pytest.fail(f"Render auth boundary did not become active: {last_error}")


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
    wait_for_web_login()
    try:
        status, body, _ = request_json(f"{WEB_URL}/api/v1/market/quote?asset=BTC%2FUSD&venue=spot")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = {}
    assert status in (401, 503)
    assert body.get("detail") in (None, "Authentication required", "Authentication configuration is unavailable")


def test_production_web_deployment_is_reachable() -> None:
    wait_for_web_login()
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
    wait_for_backend_auth_boundary()
    for route in (
        "/api/v1/market/health",
        "/api/v1/market/quote?asset=BTC%2FUSD&venue=spot",
        "/api/v1/operations/readiness",
    ):
        try:
            status, _, _ = request_json(f"{API_URL}{route}")
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status == 401


def test_production_web_does_not_expose_provider_credentials() -> None:
    try:
        _, html, _ = request_text(f"{WEB_URL}/markets")
    except urllib.error.HTTPError as exc:
        assert exc.code == 503
        return
    assert "MITROS_MARKET_TWELVEDATA_API_KEY" not in html
    assert "MITROS_MARKET_FINNHUB_API_KEY" not in html
    assert "MITROS_MARKET_ALPHAVANTAGE_API_KEY" not in html
    assert not re.search(r"(sk-|ghp_|AKIA[0-9A-Z]{16})", html)


def test_frontend_api_url_contract_matches_render() -> None:
    assert API_URL == "https://mitros.onrender.com"
    assert WEB_URL == "https://mitros.vercel.app"
    assert VERCEL_ORIGIN == WEB_URL


def test_production_web_login_is_public_and_product_routes_are_protected() -> None:
    wait_for_web_login()
    status, login_html, _ = request_text(f"{WEB_URL}/login")
    assert status == 200
    assert "MITROS secure access" in login_html
    # Auth pages must not render the authenticated application navigation.
    assert '<nav class="nav">' not in login_html

    for route in (
        "/markets",
        "/intelligence",
        "/strategies",
        "/signals",
        "/risk",
        "/research",
        "/trading",
        "/operations",
    ):
        status, html, headers = request_text_no_redirect(f"{WEB_URL}{route}")
        assert status in (307, 503)
        if status == 307:
            assert headers.get("location", "").startswith("/login?next=")
            assert "MITROS secure access" not in html
        else:
            assert "Authentication configuration is unavailable" in html


def test_live_exchange_provider_matrix() -> None:
    """Verify the public exchange candle sources used by production adapters."""
    import time

    cases = (
        ("coinbase", "BTC/USD", "15m", "BTC-USD", "FIFTEEN_MINUTE"),
        ("coinbase", "BTC/USD", "1h", "BTC-USD", "ONE_HOUR"),
        ("coinbase", "BTC/USD", "4h", "BTC-USD", "ONE_HOUR"),
        ("coinbase", "ETH/USD", "15m", "ETH-USD", "FIFTEEN_MINUTE"),
        ("coinbase", "ETH/USD", "1h", "ETH-USD", "ONE_HOUR"),
        ("coinbase", "ETH/USD", "4h", "ETH-USD", "ONE_HOUR"),
        ("kraken", "BTC/USD", "15m", "BTC/USD", "15"),
        ("kraken", "BTC/USD", "1h", "BTC/USD", "60"),
        ("kraken", "BTC/USD", "4h", "BTC/USD", "240"),
        ("kraken", "ETH/USD", "15m", "ETH/USD", "15"),
        ("kraken", "ETH/USD", "1h", "ETH/USD", "60"),
        ("kraken", "ETH/USD", "4h", "ETH/USD", "240"),
    )
    end_time = int(time.time())
    for provider, asset, timeframe, symbol, interval in cases:
        if provider == "coinbase":
            span = 900 * (16 if timeframe == "4h" else 10)
            url = (
                "https://api.coinbase.com/api/v3/brokerage/market/products/"
                f"{symbol}/candles?start={end_time - span}&end={end_time}"
                f"&granularity={interval}&limit=350"
            )
            status, body, _ = request_json(url)
            assert status == 200
            assert isinstance(body, dict)
            rows = body.get("candles", [])
            assert rows, (provider, asset, timeframe, body)
        else:
            url = (
                "https://api.kraken.com/0/public/OHLC"
                f"?pair={symbol.replace('/', '%2F')}&interval={interval}"
            )
            status, body, _ = request_json(url)
            assert status == 200
            assert isinstance(body, dict)
            assert body.get("error") == [], (provider, asset, timeframe, body.get("error"))
            result = body.get("result", {})
            rows = [value for key, value in result.items() if key != "last" and isinstance(value, list)]
            assert rows and rows[0], (provider, asset, timeframe, "empty candles")


def test_authenticated_production_phase2_snapshots() -> None:
    access_token = os.getenv("MITROS_PRODUCTION_ACCESS_TOKEN", "").strip()
    if not access_token:
        pytest.skip("MITROS_PRODUCTION_ACCESS_TOKEN is not configured for authenticated production E2E")

    headers = {"Authorization": f"Bearer {access_token}"}
    for asset in ("BTC/USD", "ETH/USD"):
        for timeframe in ("15m", "1h", "4h"):
            encoded_asset = asset.replace("/", "%2F")
            status, body, _ = request_json(
                f"{API_URL}/api/v1/intelligence/snapshot"
                f"?asset={encoded_asset}&venue=spot&timeframe={timeframe}",
                headers=headers,
            )
            assert status == 200
            assert body["asset"] == asset
            assert body["venue"] == "spot"
            assert body["timeframe"] == timeframe
            assert body["provenance"]["data_quality"] == "VERIFIED"
            providers = {item["provider"] for item in body["provenance"]["observations"]}
            assert providers
            assert providers <= {"kraken", "coinbase", "coingecko"}
            assert body["snapshot_checksum"]
            assert body["input_checksums"]
            assert body["engine_version"]
            assert body["configuration_version"]
            assert body["observation_window"]
            assert body["generated_at"]
            assert body["provenance"]["batch_checksum"]
            assert body["provenance"]["observations"]
            assert "trade_probability" not in body


def test_production_web_protected_api_routes_require_authentication() -> None:
    wait_for_web_login()
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
        assert status in (401, 503)
        if status == 200:
            raise AssertionError(f"protected API unexpectedly returned 200: {body!r}")


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
        assert status in (404, 405, 503)


def test_authenticated_production_market_data_and_intelligence_matrix() -> None:
    access_token = os.getenv("MITROS_PRODUCTION_ACCESS_TOKEN", "").strip()
    if not access_token:
        pytest.fail("MITROS_PRODUCTION_ACCESS_TOKEN is required for the production matrix gate")

    headers = {"Authorization": f"Bearer {access_token}"}
    for asset in ("BTC/USD", "ETH/USD"):
        quote_status, quote_body, _ = request_json(
            f"{API_URL}/api/v1/market/quote?asset={asset.replace('/', '%2F')}&venue=spot",
            headers=headers,
        )
        assert quote_status == 200
        assert quote_body["asset"] == asset
        assert quote_body["venue"] == "spot"
        assert quote_body["quality"] == "VERIFIED"
        assert quote_body["provider"] in {"kraken", "coinbase", "coingecko"}
        assert quote_body["price"]

        for timeframe in ("15m", "1h", "4h"):
            status, body, _ = request_json(
                f"{API_URL}/api/v1/intelligence/snapshot"
                f"?asset={asset.replace('/', '%2F')}&venue=spot&timeframe={timeframe}",
                headers=headers,
            )
            assert status == 200
            assert body["asset"] == asset
            assert body["venue"] == "spot"
            assert body["timeframe"] == timeframe
            assert body["provenance"]["data_quality"] == "VERIFIED"
            assert body["provenance"]["observations"]
            assert {item["provider"] for item in body["provenance"]["observations"]} <= {
                "kraken", "coinbase", "coingecko"
            }
            assert body["snapshot_checksum"]
            assert body["provenance"]["batch_checksum"]
