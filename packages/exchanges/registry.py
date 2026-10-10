from __future__ import annotations

import os

from packages.exchanges.xt import XTSpotClient


SUPPORTED_ACCOUNT_EXCHANGES = ("xt.com",)


def build_account_client(exchange: str | None = None) -> XTSpotClient:
    """Resolve the authoritative account adapter through a future-selectable registry."""
    selected_value = exchange if exchange is not None else os.getenv("MITROS_ACCOUNT_EXCHANGE")
    if not selected_value:
        selected_value = "xt.com"
    selected = selected_value.strip().lower()
    if selected != "xt.com":
        raise ValueError(f"Unsupported account exchange: {selected}")
    return XTSpotClient()
