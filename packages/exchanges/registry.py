from __future__ import annotations

import os
from typing import Any

from packages.exchanges.bybit import BybitReadOnlyClient
from packages.exchanges.simulated import SimulatedAccountClient
from packages.exchanges.xt import XTSpotClient


SUPPORTED_ACCOUNT_EXCHANGES = ("xt.com", "bybit", "simulated")


def build_account_client(exchange: str | None = None) -> Any:
    """Build the selected read-only account adapter; simulation is verification-gated."""
    selected_value = exchange if exchange is not None else os.getenv("MITROS_ACCOUNT_EXCHANGE")
    selected = (selected_value or "xt.com").strip().lower()
    if selected == "xt.com":
        return XTSpotClient()
    if selected == "bybit":
        return BybitReadOnlyClient()
    if selected == "simulated":
        client = SimulatedAccountClient()
        if not client.configured:
            raise ValueError("Simulated account provider is disabled outside verification environments")
        return client
    raise ValueError(f"Unsupported account exchange: {selected}")
