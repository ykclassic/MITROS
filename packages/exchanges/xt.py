from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

import httpx


class XTSpotError(RuntimeError):
    """Raised when XT account or public market data cannot be trusted."""


@dataclass(frozen=True)
class XTBalance:
    currency: str
    available: Decimal
    frozen: Decimal
    total: Decimal
    btc_value: Decimal


@dataclass(frozen=True)
class XTSpotAccount:
    observed_at_ms: int
    total_btc_value: Decimal
    balances: tuple[XTBalance, ...]
    provider: str = "xt.com"
    account_type: str = "spot"


class XTSpotClient:
    """XT.com spot API client; account reads are signed and never include secrets in logs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("MITROS_XT_API_KEY", "")).strip()
        self.api_secret = (api_secret if api_secret is not None else os.getenv("MITROS_XT_API_SECRET", "")).strip()
        resolved_base_url = base_url if base_url is not None else os.getenv("MITROS_XT_BASE_URL")
        if not resolved_base_url:
            resolved_base_url = "https://sapi.xt.com"
        self.base_url = resolved_base_url.rstrip("/")
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _headers(self, method: str, path: str, timestamp: str, query: str, body: str) -> dict[str, str]:
        if not self.configured:
            raise XTSpotError("XT account API credentials are not configured")
        recvwindow = "5000"
        algorithm = "HmacSHA256"
        prefix = (
            f"xt-validate-algorithms={algorithm}&xt-validate-appkey={self.api_key}"
            f"&xt-validate-recvwindow={recvwindow}&xt-validate-timestamp={timestamp}"
        )
        material = f"{prefix}#{method.upper()}#{path}"
        if query or body:
            material += f"#{query or body}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"), material.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return {
            "validate-appkey": self.api_key,
            "validate-timestamp": timestamp,
            "validate-signature": signature,
            "validate-recvwindow": recvwindow,
            "validate-algorithms": algorithm,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        signed: bool = False,
    ) -> dict[str, Any]:
        ordered_params = dict(sorted((params or {}).items()))
        query = urlencode(ordered_params)
        timestamp = str(int(time.time() * 1000))
        headers = (
            self._headers(method, path, timestamp, query, "")
            if signed else {"Accept": "application/json"}
        )
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.request(
                method.upper(),
                f"{self.base_url}{path}",
                params=ordered_params or None,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise XTSpotError("XT API request failed") from exc
        finally:
            if self._client is None:
                await client.aclose()
        if not isinstance(payload, dict):
            raise XTSpotError("XT returned a non-object response")
        if payload.get("rc") not in (None, 0, "0"):
            raise XTSpotError(f"XT rejected the request (rc={payload.get('rc')})")
        return payload

    async def account_snapshot(self) -> XTSpotAccount:
        if not self.configured:
            raise XTSpotError("XT account API credentials are not configured")
        payload = await self._request("GET", "/spot/v4/balances", signed=True)
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("assets"), list):
            raise XTSpotError("XT balance response is missing the expected assets payload")
        try:
            total_btc = Decimal(str(result["totalBtcAmount"]))
            balances = tuple(
                XTBalance(
                    currency=str(item["currency"]).upper(),
                    available=Decimal(str(item.get("availableAmount", "0"))),
                    frozen=Decimal(str(item.get("frozenAmount", "0"))),
                    total=Decimal(str(item.get("totalAmount", "0"))),
                    btc_value=Decimal(str(item.get("convertBtcAmount", "0"))),
                )
                for item in result["assets"]
                if isinstance(item, dict) and Decimal(str(item.get("totalAmount", "0"))) > 0
            )
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise XTSpotError("XT balance response contains invalid numeric fields") from exc
        if total_btc <= 0:
            raise XTSpotError("XT reported non-positive total account value")
        return XTSpotAccount(
            observed_at_ms=int(time.time() * 1000),
            total_btc_value=total_btc,
            balances=balances,
        )

    async def market_ticker(self, asset: str) -> dict[str, Decimal | datetime]:
        """Read XT's public ticker and require bid/ask evidence for spread checks."""
        symbol = asset.replace("/", "_").lower()
        payload = await self._request(
            "GET", "/v4/public/ticker", params={"symbol": symbol}
        )
        result = payload.get("result")
        item: dict[str, Any] | None = None
        if isinstance(result, dict):
            item = result
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            item = result[0]
        if item is None:
            raise XTSpotError("XT ticker response is missing the expected result")
        try:
            bid_value = item.get("bidPrice") or item.get("bp") or item.get("bid")
            ask_value = item.get("askPrice") or item.get("ap") or item.get("ask")
            last_value = item.get("lastPrice") or item.get("c") or item.get("last") or item.get("price")
            bid = Decimal(str(bid_value))
            ask = Decimal(str(ask_value))
            last = Decimal(str(last_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise XTSpotError("XT ticker response has invalid bid/ask/last values") from exc
        if bid <= 0 or ask < bid or last <= 0:
            raise XTSpotError("XT ticker bid/ask/last values are invalid")
        observed_at = datetime.now(UTC)
        try:
            exchange_timestamp = int(item.get("t", 0))
            if exchange_timestamp > 0:
                observed_at = datetime.fromtimestamp(exchange_timestamp / 1000, tz=UTC)
        except (TypeError, ValueError, OverflowError):
            pass
        return {
            "bid": bid,
            "ask": ask,
            "last": last,
            "observed_at": observed_at,
        }

    async def btc_usdt_price(self) -> Decimal:
        payload = await self._request(
            "GET", "/v4/public/ticker/price", params={"symbol": "btc_usdt"}
        )
        result = payload.get("result")
        candidates: list[Any] = []
        if isinstance(result, dict):
            candidates.extend(result.get(key) for key in ("price", "last", "c", "p"))
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            candidates.extend(result[0].get(key) for key in ("price", "last", "c", "p"))
        candidates.extend(payload.get(key) for key in ("price", "last"))
        for candidate in candidates:
            try:
                price = Decimal(str(candidate))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if price > 0:
                return price
        raise XTSpotError("XT BTC/USDT ticker response has no valid price")
