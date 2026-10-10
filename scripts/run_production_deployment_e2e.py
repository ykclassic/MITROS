from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Production E2E authentication is not configured: missing {name}")
    return value


def obtain_access_token() -> str:
    """Authenticate the dedicated E2E user without printing credentials or tokens."""
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
        # Do not print the response body: authentication providers may return
        # account metadata, and logs must never contain credential material.
        raise SystemExit(
            f"Supabase E2E authentication failed (HTTP {exc.code}); "
            "check the project URL, publishable key, and dedicated test account."
        ) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise SystemExit(
            "Supabase E2E authentication failed due to a transport or response error."
        ) from None

    token = result.get("access_token") if isinstance(result, dict) else None
    token_type = result.get("token_type") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token.strip() or token_type != "bearer":
        raise SystemExit(
            "Supabase E2E authentication returned no valid bearer access token."
        )
    return token.strip()


def main() -> int:
    token = obtain_access_token()
    environment = os.environ.copy()
    environment["MITROS_PRODUCTION_ACCESS_TOKEN"] = token
    # Run the existing production verification suite with the fresh token held
    # only in process memory/environment; never echo it to the CI log.
    return subprocess.call(
        [sys.executable, "-m", "pytest", "-q", "tests/deployment/test_production_deployment.py"],
        env=environment,
    )


if __name__ == "__main__":
    raise SystemExit(main())
