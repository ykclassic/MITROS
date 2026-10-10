from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from packages.execution.interface import ExecutionGateway, ExecutionOrder, ExecutionResult
from packages.operations.config import ExecutionMode, ProductionConfig


class XTExecutionError(RuntimeError):
    """Raised when XT order submission or reconciliation fails."""


class XTSpotExecutionGateway(ExecutionGateway):
    """XT spot execution adapter. Live submission is controlled entirely by deployment env vars."""

    gateway_id = "xt.com"
    version = "1.0.0"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("MITROS_XT_API_KEY", "")).strip()
        self.api_secret = (api_secret if api_secret is not None else os.getenv("MITROS_XT_API_SECRET", "")).strip()
        self.base_url = (base_url or os.getenv("MITROS_XT_BASE_URL", "https://sapi.xt.com")).rstrip("/")
        self._client = client
        self._venue_ids: dict[str, str] = {}

    def _require_live_enabled(self) -> None:
        config = ProductionConfig.from_env()
        if config.execution_mode is not ExecutionMode.LIVE or not config.live_trading_enabled:
            raise XTExecutionError("XT live trading is disabled by MITROS execution configuration")
        if not config.live_trading_acknowledged:
            raise XTExecutionError("XT live trading requires explicit operator acknowledgement")
        if os.getenv("MITROS_XT_LIVE_ORDERS_ENABLED", "false").strip().lower() != "true":
            raise XTExecutionError("XT live order submission is disabled by MITROS_XT_LIVE_ORDERS_ENABLED")
        if not self.api_key or not self.api_secret:
            raise XTExecutionError("XT trading credentials are not configured")

    def _headers(self, method: str, path: str, query: str, body: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        recvwindow = "5000"
        algorithm = "HmacSHA256"
        prefix = (
            f"xt-validate-algorithms={algorithm}&xt-validate-appkey={self.api_key}"
            f"&xt-validate-recvwindow={recvwindow}&xt-validate-timestamp={timestamp}"
        )
        material = f"{prefix}#{method.upper()}#{path}#{query or body}"
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

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = urlencode(sorted((params or {}).items()))
        body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
        headers = self._headers(method, path, query, body_text)
        client = self._client or httpx.Client(timeout=10.0)
        try:
            response = client.request(
                method.upper(),
                f"{self.base_url}{path}",
                params=params,
                content=body_text if body is not None else None,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise XTExecutionError("XT order API request failed") from exc
        finally:
            if self._client is None:
                client.close()
        if not isinstance(payload, dict) or payload.get("rc") not in (None, 0, "0"):
            raise XTExecutionError("XT rejected the order request")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise XTExecutionError("XT order response is missing order result data")
        return result

    def submit(self, order: ExecutionOrder, approval_token: str) -> ExecutionResult:
        self._require_live_enabled()
        if not approval_token:
            raise XTExecutionError("a valid human approval token is required")
        if order.venue.lower() not in {"xt", "xt.com", "xt-spot"}:
            raise XTExecutionError("XT execution gateway received an unsupported venue")
        if order.quantity <= 0:
            raise XTExecutionError("order quantity must be positive")
        body: dict[str, Any] = {
            "symbol": order.asset.replace("/", "_").lower(),
            "side": order.side.value,
            "bizType": "SPOT",
            "quantity": str(order.quantity),
            "type": order.order_type.value,
            "clientOrderId": order.client_order_id,
        }
        if order.limit_price is not None:
            body["price"] = str(order.limit_price)
            body["timeInForce"] = "GTC"
        result = self._request("POST", "/v4/order", body=body)
        venue_id = result.get("orderId", result.get("id"))
        if venue_id is None:
            # Do not retry: the exchange may have accepted an order with an incomplete response.
            return ExecutionResult(
                client_order_id=order.client_order_id,
                venue_order_id=None,
                status="UNKNOWN",
                filled_quantity=Decimal("0"),
                average_price=None,
                reason="XT response omitted order ID; reconciliation required before retry",
            )
        self._venue_ids[order.client_order_id] = str(venue_id)
        status = _normalize_status(str(result.get("status", "SUBMITTED")))
        filled = Decimal(str(result.get("dealQuantity", result.get("filledQuantity", "0"))))
        price_value = result.get("avgPrice", result.get("price"))
        price = Decimal(str(price_value)) if price_value not in (None, "") else None
        return ExecutionResult(
            client_order_id=order.client_order_id,
            venue_order_id=str(venue_id),
            status=status,
            filled_quantity=filled,
            average_price=price,
        )

    def reconcile(self, client_order_id: str) -> ExecutionResult | None:
        self._require_live_enabled()
        venue_id = self._venue_ids.get(client_order_id)
        path = f"/v4/order/{venue_id}" if venue_id else "/v4/order"
        params = None if venue_id else {"clientOrderId": client_order_id, "bizType": "SPOT"}
        result = self._request("GET", path, params=params)
        resolved_id = result.get("orderId", result.get("id", venue_id))
        if resolved_id is None:
            return None
        filled = Decimal(str(result.get("dealQuantity", result.get("filledQuantity", "0"))))
        price_value = result.get("avgPrice", result.get("price"))
        price = Decimal(str(price_value)) if price_value not in (None, "") else None
        return ExecutionResult(
            client_order_id=client_order_id,
            venue_order_id=str(resolved_id),
            status=_normalize_status(str(result.get("status", "UNKNOWN"))),
            filled_quantity=filled,
            average_price=price,
        )



def _normalize_status(value: str) -> str:
    normalized = value.upper()
    mapping = {
        "NEW": "SUBMITTED", "OPEN": "SUBMITTED", "ACCEPTED": "SUBMITTED",
        "PARTIALLY_FILLED": "PARTIALLY_FILLED", "PARTIAL_FILLED": "PARTIALLY_FILLED",
        "FILLED": "FILLED", "CANCELED": "CANCELLED", "CANCELLED": "CANCELLED",
        "REJECTED": "REJECTED", "FAILED": "REJECTED", "UNKNOWN": "UNKNOWN",
    }
    return mapping.get(normalized, "UNKNOWN")
