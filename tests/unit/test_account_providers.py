from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from packages.exchanges.bybit import BybitReadOnlyClient, BybitReadOnlyError
from packages.exchanges.registry import build_account_client
from packages.exchanges.simulated import SimulatedAccountClient


@pytest.mark.asyncio
async def test_bybit_adapter_verifies_read_only_key_and_parses_account_snapshot() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        if request.url.path == "/v5/user/query-api":
            assert request.headers.get("X-BAPI-API-KEY") == "bybit-test-key"
            assert request.headers.get("X-BAPI-SIGN")
            return httpx.Response(200, json={"retCode": 0, "time": 1791840000000, "result": {"readOnly": 1}})
        if request.url.path == "/v5/account/wallet-balance":
            return httpx.Response(200, json={"retCode": 0, "time": 1791840000000, "result": {"list": [{
                "totalEquity": "10000",
                "accountType": "UNIFIED",
                "coin": [
                    {"coin": "USDT", "walletBalance": "10000", "locked": "0", "usdValue": "10000"},
                    {"coin": "BTC", "walletBalance": "0.01", "locked": "0", "usdValue": "650"},
                ],
            }]}})
        if request.url.path == "/v5/market/tickers":
            return httpx.Response(200, json={"retCode": 0, "time": 1791840000000, "result": {"list": [{
                "symbol": "BTCUSDT", "lastPrice": "65000", "bid1Price": "64999", "ask1Price": "65001",
            }]}})
        return httpx.Response(404, json={"retCode": 10001, "result": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        bybit = BybitReadOnlyClient(
            api_key="bybit-test-key", api_secret="bybit-test-secret",
            base_url="https://bybit.test", client=client,
        )
        await bybit.verify_read_only_key()
        account = await bybit.account_snapshot()
        ticker = await bybit.market_ticker("BTC/USDT")

    assert account.provider == "bybit"
    assert account.account_type == "unified"
    assert account.observed_at_ms == 1791840000000
    assert ticker["observed_at"].timestamp() == pytest.approx(1791840000.0)
    assert account.total_btc_value == Decimal("10000") / Decimal("65000")
    assert len(account.balances) == 2
    assert ticker["bid"] == Decimal("64999")
    assert ticker["ask"] == Decimal("65001")
    assert all(call.method == "GET" for call in calls)


@pytest.mark.asyncio
async def test_bybit_adapter_rejects_api_key_that_is_not_read_only() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"retCode": 0, "result": {"readOnly": 0}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        bybit = BybitReadOnlyClient(
            api_key="key", api_secret="secret", base_url="https://bybit.test", client=client
        )
        with pytest.raises(BybitReadOnlyError, match="not configured as read-only"):
            await bybit.verify_read_only_key()


def test_simulated_provider_requires_explicit_verification_environment(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_ACCOUNT_EXCHANGE", "simulated")
    monkeypatch.setenv("MITROS_PHASE4_SIMULATED_ACCOUNT_ENABLED", "true")
    monkeypatch.setenv("MITROS_ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="disabled outside verification environments"):
        build_account_client()


@pytest.mark.asyncio
async def test_simulated_provider_is_deterministic_and_verification_gated(monkeypatch) -> None:
    monkeypatch.setenv("MITROS_PHASE4_SIMULATED_ACCOUNT_ENABLED", "true")
    monkeypatch.setenv("MITROS_ENVIRONMENT", "verification")
    client = SimulatedAccountClient()
    await client.verify_read_only_key()
    first = await client.account_snapshot()
    second = await client.account_snapshot()
    assert first.provider == "simulated"
    assert first.account_type == "verification"
    assert first.total_btc_value == second.total_btc_value
    assert await client.btc_usdt_price() == Decimal("65000")



@pytest.mark.asyncio
async def test_bybit_http_error_exposes_only_sanitized_status_and_reason_code() -> None:
    secret_marker = "SENSITIVE_RESPONSE_BODY_MARKER"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=secret_marker)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        bybit = BybitReadOnlyClient(
            api_key="key", api_secret="secret", base_url="https://bybit.test", client=client
        )
        with pytest.raises(BybitReadOnlyError) as caught:
            await bybit.verify_read_only_key()

    assert caught.value.status_code == 403
    assert caught.value.reason_code == "bybit_http_403"
    assert secret_marker not in str(caught.value)




@pytest.mark.asyncio
async def test_bitget_adapter_signs_read_only_requests_and_parses_classic_spot_assets() -> None:
    from packages.exchanges.bitget import BitgetReadOnlyClient

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        if request.url.path == "/api/v2/spot/account/info":
            assert request.headers.get("ACCESS-KEY") == "bitget-test-key"
            assert request.headers.get("ACCESS-SIGN")
            assert request.headers.get("ACCESS-TIMESTAMP")
            assert request.headers.get("ACCESS-PASSPHRASE") == "bitget-test-passphrase"
            assert request.headers.get("Content-Type") == "application/json"
            assert request.headers.get("locale") == "en-US"
            return httpx.Response(200, json={
                "code": "00000", "requestTime": 1791840000000,
                "data": {"authorities": ["stor", "cpor"]},
            })
        if request.url.path == "/api/v2/spot/account/assets":
            return httpx.Response(200, json={
                "code": "00000", "requestTime": 1791840000000,
                "data": [
                    {"coin": "BTC", "available": "0.01", "frozen": "0", "locked": "0"},
                    {"coin": "USDT", "available": "640", "frozen": "0", "locked": "10"},
                ],
            })
        if request.url.path == "/api/v2/spot/market/tickers":
            return httpx.Response(200, json={
                "code": "00000", "requestTime": 1791840000000,
                "data": [{"symbol": "BTCUSDT", "bidPr": "64999", "askPr": "65001", "lastPr": "65000"}],
            })
        return httpx.Response(404, text="SENSITIVE_RESPONSE_BODY_MARKER")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        bitget = BitgetReadOnlyClient(
            api_key="bitget-test-key",
            api_secret="bitget-test-secret",
            passphrase="bitget-test-passphrase",
            base_url="https://bitget.test",
            client=http_client,
        )
        await bitget.verify_read_only_key()
        account = await bitget.account_snapshot()
        ticker = await bitget.market_ticker("BTC/USDT")

    assert account.provider == "bitget"
    assert account.account_type == "spot"
    assert account.observed_at_ms == 1791840000000
    assert account.total_btc_value == Decimal("0.02")
    assert len(account.balances) == 2
    assert account.balances[1].frozen == Decimal("10")
    assert account.balances[1].btc_value == Decimal("650") / Decimal("65000")
    assert ticker["last"] == Decimal("65000")
    assert all(request.method == "GET" for request in calls)
    assert {request.url.path for request in calls}.issubset({
        "/api/v2/spot/account/info",
        "/api/v2/spot/account/assets",
        "/api/v2/spot/market/tickers",
    })


@pytest.mark.asyncio
async def test_bitget_adapter_rejects_write_permissions() -> None:
    from packages.exchanges.bitget import BitgetReadOnlyClient, BitgetReadOnlyError

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "code": "00000", "requestTime": 1791840000000,
            "data": {"authorities": ["stor", "stow"]},
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        bitget = BitgetReadOnlyClient(
            api_key="key", api_secret="secret", passphrase="passphrase",
            base_url="https://bitget.test", client=http_client,
        )
        with pytest.raises(BitgetReadOnlyError) as caught:
            await bitget.verify_read_only_key()

    assert caught.value.reason_code == "bitget_write_permissions_detected"


@pytest.mark.asyncio
async def test_bitget_http_error_exposes_only_sanitized_status_and_reason_code() -> None:
    from packages.exchanges.bitget import BitgetReadOnlyClient, BitgetReadOnlyError

    secret_marker = "SENSITIVE_RESPONSE_BODY_MARKER"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=secret_marker)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        bitget = BitgetReadOnlyClient(
            api_key="key", api_secret="secret", passphrase="passphrase",
            base_url="https://bitget.test", client=http_client,
        )
        with pytest.raises(BitgetReadOnlyError) as caught:
            await bitget.verify_read_only_key()

    assert caught.value.status_code == 403
    assert caught.value.reason_code == "bitget_http_403"
    assert secret_marker not in str(caught.value)


def test_registry_supports_bitget_read_only_provider() -> None:
    from packages.exchanges.bitget import BitgetReadOnlyClient

    assert isinstance(build_account_client("bitget"), BitgetReadOnlyClient)

@pytest.mark.asyncio
async def test_bitget_http_400_maps_documented_error_code_without_exposing_response_body() -> None:
    from packages.exchanges.bitget import BitgetReadOnlyClient, BitgetReadOnlyError

    secret_marker = "SENSITIVE_RESPONSE_BODY_MARKER"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": "40009", "msg": secret_marker})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        bitget = BitgetReadOnlyClient(
            api_key="key", api_secret="secret", passphrase="passphrase",
            base_url="https://bitget.test", client=http_client,
        )
        with pytest.raises(BitgetReadOnlyError) as caught:
            await bitget.verify_read_only_key()

    assert caught.value.status_code == 400
    assert caught.value.reason_code == "bitget_signature_invalid"
    assert secret_marker not in str(caught.value)

