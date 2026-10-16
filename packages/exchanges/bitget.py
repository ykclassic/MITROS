from __future__ import annotations

import base64
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


class BitgetReadOnlyError(AccountProviderError):
    """Raised when a Bitget read-only account request cannot be trusted."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        reason_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason_code = reason_code or "bitget_request_failed"


class BitgetReadOnlyClient:
    """Bitget Unified Trading Account (UTA) read-only adapter; requests are GET-only."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        passphrase: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("MITROS_BITGET_API_KEY", "")).strip()
        self.api_secret = (
            api_secret if api_secret is not None else os.getenv("MITROS_BITGET_API_SECRET", "")
        ).strip()
        self.passphrase = (
            passphrase if passphrase is not None else os.getenv("MITROS_BITGET_API_PASSPHRASE", "")
        ).strip()
        self.base_url = (base_url or os.getenv("MITROS_BITGET_BASE_URL") or "https://api.bitget.com").rstrip("/")
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    async def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
        *,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        ordered = dict(sorted((params or {}).items()))
        query = urlencode(ordered)
        headers: dict[str, str] = {"Accept": "application/json"}
        if authenticated:
            if not self.configured:
                raise BitgetReadOnlyError(
                    "Bitget API credentials are not configured",
                    reason_code="bitget_credentials_missing",
                )
            timestamp = str(int(time.time() * 1000))
            request_path = f"{path}?{query}" if query else path
            prehash = f"{timestamp}GET{request_path}"
            digest = hmac.new(
                self.api_secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256
            ).digest()
            headers.update(
                {
                    "ACCESS-KEY": self.api_key,
                    "ACCESS-SIGN": base64.b64encode(digest).decode("ascii"),
                    "ACCESS-TIMESTAMP": timestamp,
                    "ACCESS-PASSPHRASE": self.passphrase,
                }
            )
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.get(
                f"{self.base_url}{path}", params=ordered or None, headers=headers
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise BitgetReadOnlyError(
                f"Bitget HTTP request failed with status {status_code}",
                status_code=status_code,
                reason_code=f"bitget_http_{status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise BitgetReadOnlyError(
                "Bitget API request failed", reason_code="bitget_transport_or_json_error"
            ) from exc
        finally:
            if self._client is None:
                await client.aclose()
        if not isinstance(payload, dict) or payload.get("code") != "00000":
            raise BitgetReadOnlyError("Bitget returned an unsuccessful response")
        if not isinstance(payload.get("data"), (dict, list)):
            raise BitgetReadOnlyError("Bitget response is missing the expected data")
        request_time = payload.get("requestTime")
        if request_time is not None:
            payload["_response_time_ms"] = request_time
        return payload

    async def verify_read_only_key(self) -> None:
        if not self.configured:
            raise BitgetReadOnlyError(
                "Bitget API credentials are not configured",
                reason_code="bitget_credentials_missing",
            )
        payload = await self._get("/api/v3/account/info", authenticated=True)
        data = payload["data"]
        if not isinstance(data, dict):
            raise BitgetReadOnlyError("Bitget account information is invalid")
        permission_type = str(data.get("permType", "")).lower().replace("_", "-")
        if permission_type not in {"readonly", "read-only"}:
            raise BitgetReadOnlyError(
                "Bitget API key is not explicitly read-only",
                reason_code="bitget_key_not_read_only",
            )
        permissions = data.get("permissions")
        if not isinstance(permissions, list):
            raise BitgetReadOnlyError(
                "Bitget API permissions could not be verified",
                reason_code="bitget_permissions_unverifiable",
            )
        normalized_permissions = {str(permission).lower() for permission in permissions}
        if "uta_mgt" not in normalized_permissions:
            raise BitgetReadOnlyError(
                "Bitget key lacks unified-account read permission",
                reason_code="bitget_uta_read_permission_missing",
            )
        forbidden = {"uta_trade", "withdraw", "copy_futures_position", "copy_futures_order"}
        if normalized_permissions.intersection(forbidden):
            raise BitgetReadOnlyError(
                "Bitget API key includes non-read-only permissions",
                reason_code="bitget_write_permissions_detected",
            )

    async def market_ticker(self, asset: str) -> dict[str, Decimal | datetime]:
        symbol = asset.replace("/", "").replace("-", "").upper()
        payload = await self._get("/api/v2/spot/market/tickers", {"symbol": symbol})
        rows = payload["data"]
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise BitgetReadOnlyError("Bitget market ticker is missing")
        row = rows[0]
        try:
            bid = Decimal(str(row["bidPr"]))
            ask = Decimal(str(row["askPr"]))
            last = Decimal(str(row["lastPr"]))
            observed_ms = int(payload.get("_response_time_ms", 0))
            if observed_ms <= 0:
                raise ValueError("missing timestamp")
            observed_at = datetime.fromtimestamp(observed_ms / 1000, tz=UTC)
        except (KeyError, InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise BitgetReadOnlyError("Bitget market ticker contains invalid fields") from exc
        if bid <= 0 or ask < bid or last <= 0:
            raise BitgetReadOnlyError("Bitget market ticker prices are invalid")
        return {"bid": bid, "ask": ask, "last": last, "observed_at": observed_at}

    async def btc_usdt_price(self) -> Decimal:
        ticker = await self.market_ticker("BTC/USDT")
        price = ticker["last"]
        if not isinstance(price, Decimal) or price <= 0:
            raise BitgetReadOnlyError("Bitget BTC/USDT price is invalid")
        return price

    async def account_snapshot(self) -> AccountSnapshot:
        await self.verify_read_only_key()
        payload = await self._get("/api/v3/account/assets", authenticated=True)
        data = payload["data"]
        if not isinstance(data, dict):
            raise BitgetReadOnlyError("Bitget UTA assets response is invalid")
        observed_at_ms = int(payload.get("_response_time_ms", 0))
        if observed_at_ms <= 0:
            raise BitgetReadOnlyError("Bitget account observation timestamp is missing")
        try:
            total_btc_value = Decimal(str(data["btcEquity"]))
            rows = data["assets"]
            if not isinstance(rows, list):
                raise TypeError("asset list is invalid")
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise BitgetReadOnlyError("Bitget UTA equity response contains invalid fields") from exc
        btc_price = await self.btc_usdt_price()
        balances: list[AccountBalance] = []
        for row in rows:
            if not isinstance(row, dict):
                raise BitgetReadOnlyError("Bitget UTA asset entry is invalid")
            try:
                currency = str(row["coin"]).upper()
                available = Decimal(str(row.get("available", "0")))
                total = Decimal(str(row["equity"]))
                usd_value = Decimal(str(row["usdValue"]))
                locked = Decimal(str(row.get("locked", "0")))
                btc_value = total if currency == "BTC" else usd_value / btc_price
                if min(available, total, usd_value, locked) < 0:
                    raise ValueError("negative balance")
            except (KeyError, InvalidOperation, TypeError, ValueError, ZeroDivisionError) as exc:
                raise BitgetReadOnlyError("Bitget UTA asset contains invalid balances") from exc
            balances.append(
                AccountBalance(
                    currency=currency,
                    available=available,
                    frozen=locked,
                    total=total,
                    btc_value=btc_value,
                )
            )
        if not balances or total_btc_value <= 0:
            raise BitgetReadOnlyError("Bitget account has no positive valued UTA assets")
        return AccountSnapshot(
            observed_at_ms=observed_at_ms,
            total_btc_value=total_btc_value,
            balances=tuple(balances),
            provider="bitget",
            account_type="unified",
        )
