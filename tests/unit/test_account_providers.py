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
            return httpx.Response(200, json={"retCode": 0, "result": {"list": [{
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
