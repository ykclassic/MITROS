import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from packages.api.app import app
from packages.api.auth import AuthenticatedUser, SupabaseTokenVerifier


def test_claims_map_identity_role_and_entitlements() -> None:
    user = SupabaseTokenVerifier._claims_to_user(
        {
            "sub": "user-19",
            "email": "user@example.com",
            "aal": "aal2",
            "app_metadata": {"role": "researcher", "entitlements": ["free", "research"]},
        }
    )
    assert user == AuthenticatedUser(
        user_id="user-19",
        email="user@example.com",
        role="researcher",
        entitlements=("free", "research"),
        assurance_level="aal2",
    )


def test_missing_bearer_token_is_rejected() -> None:
    response = TestClient(app).get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_supabase_configuration_is_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    verifier = SupabaseTokenVerifier()
    with pytest.raises(HTTPException) as exc_info:
        await verifier.verify_async("not-a-token")
    assert exc_info.value.status_code == 503
