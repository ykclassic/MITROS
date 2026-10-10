from __future__ import annotations

import os

from packages.exchanges.xt import XTSpotClient


SUPPORTED_ACCOUNT_EXCHANGES = ("xt.com",)


def build_account_client(exchange: str | None = None) -> XTSpotClient:
    """Resolve the authoritative account adapter through a future-selectable registry."""
    selected = (exchange or os.getenv("MITROS_ACCOUNT_EXCHANGE", "xt.com")).strip().lower()
    if selected != "xt.com":
        raise ValueError(f"Unsupported account exchange: {selected}")
    return XTSpotClient()
