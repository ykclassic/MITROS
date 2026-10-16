"""Run sanitized, authenticated, read-only Bitget connectivity verification."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from time import time

from packages.exchanges.bitget import BitgetReadOnlyClient, BitgetReadOnlyError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("mitros.bitget_readonly_verification")


async def run_verification() -> None:
    key = os.getenv("MITROS_BITGET_API_KEY", "").strip()
    secret = os.getenv("MITROS_BITGET_API_SECRET", "").strip()
    passphrase = os.getenv("MITROS_BITGET_API_PASSPHRASE", "").strip()
    if not key or not secret or not passphrase:
        raise RuntimeError("required_credentials_missing")

    max_age_seconds = int(os.getenv("MITROS_BITGET_MAX_SNAPSHOT_AGE_SECONDS", "60"))
    if max_age_seconds < 1 or max_age_seconds > 300:
        raise RuntimeError("invalid_freshness_policy")

    client = BitgetReadOnlyClient()
    await client.verify_read_only_key()
    logger.info("check=read_only_permissions result=passed")

    account = await client.account_snapshot()
    if account.provider != "bitget" or account.total_btc_value <= Decimal("0"):
        raise RuntimeError("account_snapshot_invalid")
    account_age = time() - account.observed_at_ms / 1000
    if account_age < 0 or account_age > max_age_seconds:
        raise RuntimeError("account_snapshot_stale")
    logger.info("check=account_snapshot result=passed age_seconds=%.3f", account_age)

    ticker = await client.market_ticker("BTC/USDT")
    observed_at = ticker.get("observed_at")
    last = ticker.get("last")
    if not isinstance(last, Decimal) or last <= 0:
        raise RuntimeError("ticker_price_invalid")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise RuntimeError("ticker_timestamp_invalid")
    age = (datetime.now(UTC) - observed_at.astimezone(UTC)).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise RuntimeError("ticker_stale")
    logger.info("check=btc_usdt_ticker result=passed age_seconds=%.3f", age)
    logger.info("result=passed live_orders=disabled")


async def main() -> int:
    try:
        await run_verification()
    except BitgetReadOnlyError as exc:
        logger.error(
            "result=failed category=%s reason_code=%s http_status=%s",
            type(exc).__name__,
            exc.reason_code,
            exc.status_code if exc.status_code is not None else "not_available",
        )
        return 1
    except (RuntimeError, ValueError, TypeError):
        logger.error("result=failed reason_code=verification_input_or_data_invalid")
        return 1
    except Exception as exc:
        logger.error("result=failed category=%s", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
