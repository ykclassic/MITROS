from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

import httpx

from packages.exchanges.base import AccountProviderError
from packages.exchanges.models import AccountBalance, AccountSnapshot


class BybitReadOnlyError(AccountProviderError):
    """Raised when a Bybit read-only account request cannot be trusted."""


class BybitReadOnlyClient:
    """Minimal Bybit V5 read-only adapter. It exposes GET requests only."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("MITROS_BYBIT_API_KEY", "")).strip()
        self.api_secret = (api_secret if api_secret is not None else os.getenv("MITROS_BYBIT_API_SECRET", "")).strip()
        self.base_url = (base_url or os.getenv("MITROS_BYBIT_BASE_URL", "https://api.bybit.com")).rstrip("/")
        self.recv_window = "5000"
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    async def _get(self, path: str, params: dict[str, str] | None = None, *, authenticated: bool = False) -> dict[str, Any]:
        ordered = dict(sorted((params or {}).items()))
        query = urlencode(ordered)
        headers: dict[str, str] = {"Accept": "application/json"}
        if authenticated:
            if not self.configured:
                raise BybitReadOnlyError("Bybit API credentials are not configured")
            timestamp = str(int(time.time() * 1000))
            material = f"{timestamp}{self.api_key}{self.recv_window}{query}"
            signature = hmac.new(
                self.api_secret.encode("utf-8"), material.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            headers.update({
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": self.recv_window,
                "X-BAPI-SIGN": signature,
            })
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.get(
                f"{self.base_url}{path}", params=ordered or None, headers=headers
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BybitReadOnlyError("Bybit API request failed") from exc
        finally:
            if self._client is None:
                await client.aclose()
        if not isinstance(payload, dict) or payload.get("retCode") != 0:
            raise BybitReadOnlyError("Bybit returned an unsuccessful response")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitReadOnlyError("Bybit response is missing the expected result")
        if payload.get("time") is not None:
            result["_response_time_ms"] = payload["time"]
        return result

    async def verify_read_only_key(self) -> None:
        result = await self._get("/v5/user/query-api", authenticated=True)
        if result.get("readOnly") != 1:
            raise BybitReadOnlyError("Bybit API key is not configured as read-only")

    async def btc_usdt_price(self) -> Decimal:
        result = await self._get(
            "/v5/market/tickers", {"category": "spot", "symbol": "BTCUSDT"}
        )
        rows = result.get("list")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise BybitReadOnlyError("Bybit BTC/USDT ticker is missing")
        try:
            price = Decimal(str(rows[0]["lastPrice"]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise BybitReadOnlyError("Bybit BTC/USDT ticker is invalid") from exc
        if price <= 0:
            raise BybitReadOnlyError("Bybit BTC/USDT price is non-positive")
        return price

    async def market_ticker(self, asset: str) -> dict[str, Decimal | datetime]:
        symbol = asset.replace("/", "").upper()
        result = await self._get(
            "/v5/market/tickers", {"category": "spot", "symbol": symbol}
        )
        rows = result.get("list")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise BybitReadOnlyError("Bybit market ticker is missing")
        row = rows[0]
        try:
            bid = Decimal(str(row["bid1Price"]))
            ask = Decimal(str(row["ask1Price"]))
            last = Decimal(str(row["lastPrice"]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise BybitReadOnlyError("Bybit market ticker contains invalid prices") from exc
        if bid <= 0 or ask < bid or last <= 0:
            raise BybitReadOnlyError("Bybit market ticker prices are invalid")
        try:
            response_time_ms = int(result.get("_response_time_ms", 0))
            if response_time_ms <= 0:
                raise ValueError("missing exchange timestamp")
            observed_at = datetime.fromtimestamp(response_time_ms / 1000, tz=UTC)
        except (TypeError, ValueError, OverflowError) as exc:
            raise BybitReadOnlyError("Bybit ticker observation timestamp is missing or invalid") from exc
        return {"bid": bid, "ask": ask, "last": last, "observed_at": observed_at}

    async def account_snapshot(self) -> AccountSnapshot:
        if not self.configured:
            raise BybitReadOnlyError("Bybit API credentials are not configured")
        await self.verify_read_only_key()
        result = await self._get(
            "/v5/account/wallet-balance",
            {"accountType": "UNIFIED"},
            authenticated=True,
        )
        rows = result.get("list")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise BybitReadOnlyError("Bybit wallet balance is missing")
        wallet = rows[0]
        try:
            total_equity = Decimal(str(wallet["totalEquity"]))
            coin_rows = wallet.get("coin", [])
            if not isinstance(coin_rows, list):
                raise TypeError("coin list is invalid")
            btc_price = await self.btc_usdt_price()
            balances = tuple(
                AccountBalance(
                    currency=str(item["coin"]).upper(),
                    available=max(Decimal("0"), Decimal(str(item.get("walletBalance", "0"))) - Decimal(str(item.get("locked", "0")))),
                    frozen=Decimal(str(item.get("locked", "0"))),
                    total=Decimal(str(item.get("walletBalance", "0"))),
                    btc_value=Decimal(str(item.get("usdValue", "0"))) / btc_price,
                )
                for item in coin_rows
                if isinstance(item, dict) and Decimal(str(item.get("walletBalance", "0"))) > 0
            )
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise BybitReadOnlyError("Bybit wallet balance contains invalid numeric fields") from exc
        if total_equity <= 0:
            raise BybitReadOnlyError("Bybit reported non-positive account equity")
        try:
            observed_at_ms = int(result.get("_response_time_ms", 0))
            if observed_at_ms <= 0:
                raise ValueError("missing exchange timestamp")
        except (TypeError, ValueError, OverflowError) as exc:
            raise BybitReadOnlyError("Bybit account observation timestamp is missing or invalid") from exc
        return AccountSnapshot(
            observed_at_ms=observed_at_ms,
            total_btc_value=total_equity / btc_price,
            balances=balances,
            provider="bybit",
            account_type="unified",
        )
