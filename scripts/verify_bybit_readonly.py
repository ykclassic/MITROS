"""Run sanitized, authenticated, read-only Bybit connectivity verification."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from time import time

from packages.exchanges.bybit import BybitReadOnlyClient, BybitReadOnlyError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("mitros.bybit_readonly_verification")


async def run_verification() -> None:
    api_key = os.getenv("MITROS_BYBIT_API_KEY", "").strip()
    api_secret = os.getenv("MITROS_BYBIT_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError("required_credentials_missing")

    max_age_seconds = int(os.getenv("MITROS_BYBIT_MAX_TICKER_AGE_SECONDS", "60"))
    if max_age_seconds < 1 or max_age_seconds > 300:
        raise RuntimeError("invalid_freshness_policy")

    client = BybitReadOnlyClient()
    if not client.configured:
        raise RuntimeError("client_not_configured")

    # The native method returns None on success and raises on any non-read-only key.
    await client.verify_read_only_key()
    logger.info("check=read_only_key result=passed")

    account = await client.account_snapshot()
    if account.provider != "bybit" or account.total_btc_value <= Decimal("0"):
        raise RuntimeError("account_snapshot_invalid")
    account_age_seconds = time() - (account.observed_at_ms / 1000)
    if account_age_seconds < 0 or account_age_seconds > max_age_seconds:
        raise RuntimeError("account_snapshot_stale")
    logger.info("check=account_snapshot result=passed account_age_seconds=%.3f", account_age_seconds)

    ticker = await client.market_ticker("BTC/USDT")
    last = ticker.get("last")
    observed_at = ticker.get("observed_at")
    if not isinstance(last, Decimal) or last <= 0:
        raise RuntimeError("ticker_price_invalid")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise RuntimeError("ticker_timestamp_invalid")
    age_seconds = (datetime.now(UTC) - observed_at.astimezone(UTC)).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_seconds:
        raise RuntimeError("ticker_stale")
    logger.info(
        "check=btc_usdt_ticker result=passed ticker_age_seconds=%.3f",
        age_seconds,
    )
    logger.info("result=passed live_orders=disabled")


async def main() -> int:
    try:
        await run_verification()
    except BybitReadOnlyError as exc:
        # Native adapter messages are sanitized; log only the exception category anyway.
        logger.error("result=failed category=%s", type(exc).__name__)
        return 1
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.error("result=failed reason_code=%s", str(exc))
        return 1
    except Exception as exc:
        logger.error("result=failed category=%s", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
