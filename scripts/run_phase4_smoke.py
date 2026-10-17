from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import psycopg


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Phase 4 smoke is not configured: missing {name}")
    return value


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP request failed with status {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError("HTTP request failed due to transport or invalid JSON") from None
    if not isinstance(decoded, dict):
        raise RuntimeError("HTTP request returned an unexpected JSON shape")
    return decoded


def obtain_access_token() -> str:
    """Authenticate the dedicated E2E user without logging credentials or tokens."""
    supabase_url = _required_env("MITROS_E2E_SUPABASE_URL").rstrip("/")
    publishable_key = _required_env("MITROS_E2E_SUPABASE_PUBLISHABLE_KEY")
    email = _required_env("MITROS_E2E_USER_EMAIL")
    password = _required_env("MITROS_E2E_USER_PASSWORD")
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        data=payload,
        method="POST",
        headers={
            "apikey": publishable_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Supabase E2E authentication failed with status {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError("Supabase E2E authentication failed due to transport or invalid JSON") from None
    token = result.get("access_token") if isinstance(result, dict) else None
    token_type = result.get("token_type") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token.strip() or token_type != "bearer":
        raise RuntimeError("Supabase E2E authentication returned no valid bearer token")
    return token.strip()


def _verify_persistence(
    *,
    database_url: str,
    expected_database: str,
    correlation_id: str,
    proposal_id: str,
    idempotency_key: str,
    audit_id: str,
    snapshot_id: str,
) -> tuple[str, str]:
    # The connection is server-enforced read-only. This module contains only fixed
    # SELECT statements; all user/request values are bound parameters, never SQL text.
    with psycopg.connect(
        database_url,
        autocommit=True,
        options="-c default_transaction_read_only=on",
    ) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database_name, database_user = cursor.fetchone()
        if database_name != expected_database:
            raise RuntimeError("Connected database does not match MITROS_EXPECTED_DB_NAME")

        cursor.execute(
            """
            SELECT count(*)
            FROM phase4_risk_decisions
            WHERE id = %s::uuid AND proposal_id = %s AND idempotency_key = %s
            """,
            (audit_id, proposal_id, idempotency_key),
        )
        decision_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT count(*) FROM phase4_portfolio_snapshots WHERE id = %s::uuid",
            (snapshot_id,),
        )
        snapshot_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT count(*)
            FROM system_events
            WHERE event_type = 'RiskEvaluated'
              AND correlation_id = %s::uuid
              AND aggregate_id = %s::uuid
            """,
            (correlation_id, proposal_id),
        )
        event_count = cursor.fetchone()[0]

    counts = {
        "decision": decision_count,
        "snapshot": snapshot_count,
        "risk_evaluated_event": event_count,
    }
    if any(count != 1 for count in counts.values()):
        raise RuntimeError(
            "Persistence cardinality mismatch: "
            + ",".join(f"{name}={count}" for name, count in counts.items())
        )
    return str(database_name), str(database_user)


def main() -> int:
    backend_url = _required_env("MITROS_BACKEND_URL").rstrip("/")
    expected_sha = _required_env("MITROS_EXPECTED_DEPLOYED_SHA").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise SystemExit("MITROS_EXPECTED_DEPLOYED_SHA must be a full 40-character commit SHA")

    health = _json_request(f"{backend_url}/health")
    deployed_sha = str(health.get("build_sha", "")).lower() or "missing"
    if deployed_sha != expected_sha:
        raise SystemExit(
            "Deployed backend SHA mismatch: "
            f"requested_sha={expected_sha} deployed_sha={deployed_sha}"
        )

    token = obtain_access_token()
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Use a fresh verified quote to construct internally consistent stop/target levels.
    quote_query = urllib.parse.urlencode({"asset": "BTC/USDT", "venue": "spot"})
    quote = _json_request(f"{backend_url}/api/v1/market/quote?{quote_query}", headers=auth_headers)
    try:
        price = Decimal(str(quote["price"]))
    except (KeyError, TypeError, InvalidOperation):
        raise SystemExit("Authenticated verified quote returned no valid price") from None
    if not price.is_finite() or price <= 0:
        raise SystemExit("Authenticated verified quote returned a non-positive price")

    correlation_id = str(uuid4())
    proposal_id = str(uuid4())
    idempotency_key = f"phase4-smoke-{uuid4()}"
    intent = {
        "proposal_id": proposal_id,
        "asset": "BTC/USDT",
        "direction": "LONG",
        "entry": str(price),
        "stop_loss": str(price * Decimal("0.99")),
        "take_profit": str(price * Decimal("1.02")),
        "requested_notional": "1",
        "idempotency_key": idempotency_key,
    }
    request_url = (
        f"{backend_url}/api/v1/risk/phase4/evaluate?"
        + urllib.parse.urlencode({"request_id": correlation_id})
    )
    try:
        response = _json_request(
            request_url,
            method="POST",
            payload=intent,
            headers=auth_headers,
        )
    except RuntimeError as exc:
        raise SystemExit(f"Phase 4 evaluation request failed: {exc}") from None

    audit_id = response.get("audit_id")
    snapshot_id = response.get("account_snapshot_id")
    if not isinstance(audit_id, str) or not isinstance(snapshot_id, str):
        raise SystemExit("Phase 4 evaluation response omitted required persistence identifiers")

    database_url = _required_env("MITROS_DATABASE_URL")
    expected_database = _required_env("MITROS_EXPECTED_DB_NAME")
    try:
        database_name, database_user = _verify_persistence(
            database_url=database_url,
            expected_database=expected_database,
            correlation_id=correlation_id,
            proposal_id=proposal_id,
            idempotency_key=idempotency_key,
            audit_id=audit_id,
            snapshot_id=snapshot_id,
        )
    except RuntimeError as exc:
        raise SystemExit(f"Phase 4 persistence verification failed: {exc}") from None
    except (psycopg.Error, TypeError) as exc:
        # Do not serialize database exceptions; drivers can include connection details.
        category = "database_error" if isinstance(exc, psycopg.Error) else "verification_failed"
        raise SystemExit(f"Phase 4 persistence verification failed ({category})") from None

    print(
        f"result=passed db={database_name} db_user={database_user} "
        f"correlation_id={correlation_id} audit_id={audit_id} deployed_sha={deployed_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
