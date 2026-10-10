from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest

from packages.exchanges.xt import XTSpotClient, XTSpotError


@pytest.mark.asyncio
async def test_xt_account_snapshot_parses_signed_spot_balances() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/spot/v4/balances":
            assert request.headers.get("validate-appkey") == "test-key"
            assert request.headers.get("validate-signature")
            return httpx.Response(200, json={
                "rc": 0,
                "result": {
                    "totalBtcAmount": "0.05",
                    "assets": [
                        {"currency": "BTC", "availableAmount": "0.04", "frozenAmount": "0.01",
                         "totalAmount": "0.05", "convertBtcAmount": "0.05"},
                        {"currency": "USDT", "availableAmount": "100", "frozenAmount": "0",
                         "totalAmount": "100", "convertBtcAmount": "0.0015"},
                    ],
                },
            })
        if request.url.path == "/v4/public/ticker/price":
            return httpx.Response(200, json={"rc": 0, "result": [{"s": "btc_usdt", "p": "65000", "t": 1791652800000}]})
        if request.url.path == "/v4/public/ticker":
            return httpx.Response(200, json={
                "rc": 0, "result": [{"s": "btc_usdt", "bp": "64999", "ap": "65001", "c": "65000", "t": 1791652800000}]
            })
        return httpx.Response(404, json={"rc": 404})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        xt = XTSpotClient(
            api_key="test-key", api_secret="test-secret",
            base_url="https://xt.test", client=client,
        )
        account = await xt.account_snapshot()
        price = await xt.btc_usdt_price()
        ticker = await xt.market_ticker("BTC/USDT")

    assert account.total_btc_value.as_tuple().digits == (5,)
    assert len(account.balances) == 2
    assert price == 65000
    assert ticker["bid"] == 64999
    assert ticker["ask"] == 65001
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_xt_ticker_without_exchange_timestamp_fails_closed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "rc": 0,
            "result": [{"s": "btc_usdt", "bp": "64999", "ap": "65001", "c": "65000"}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        xt = XTSpotClient(base_url="https://xt.test", client=client)
        with pytest.raises(XTSpotError, match="missing a valid exchange timestamp"):
            await xt.market_ticker("BTC/USDT")


def test_xt_signature_matches_documented_canonical_material() -> None:
    xt = XTSpotClient(api_key="app-key", api_secret="secret", base_url="https://xt.test")
    import time

    timestamp = str(int(time.time() * 1000))
    headers = xt._headers("GET", "/spot/v4/balances", timestamp, "currencies=btc", "")
    material = (
        f"xt-validate-algorithms=HmacSHA256&xt-validate-appkey=app-key"
        f"&xt-validate-recvwindow=5000&xt-validate-timestamp={timestamp}"
        "#GET#/spot/v4/balances#currencies=btc"
    )
    expected = hmac.new(b"secret", material.encode(), hashlib.sha256).hexdigest()
    assert headers["validate-signature"] == expected


@pytest.mark.asyncio
async def test_xt_balance_response_missing_assets_fails_closed() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"rc": 0, "result": {}}))
    ) as client:
        xt = XTSpotClient(
            api_key="test-key", api_secret="test-secret",
            base_url="https://xt.test", client=client,
        )
        with pytest.raises(XTSpotError, match="missing the expected assets"):
            await xt.account_snapshot()
