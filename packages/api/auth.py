from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    role: str
    entitlements: tuple[str, ...]
    assurance_level: str


def _jwt_failure_reason(exc: Exception) -> str:
    """Return a safe, stable reason code without serializing exception data."""
    if isinstance(exc, jwt.ExpiredSignatureError):
        return "token_expired"
    if isinstance(exc, jwt.ImmatureSignatureError):
        return "token_not_yet_valid"
    if isinstance(exc, jwt.InvalidAudienceError):
        return "audience_mismatch"
    if isinstance(exc, jwt.InvalidIssuerError):
        return "issuer_mismatch"
    if isinstance(exc, jwt.InvalidSignatureError):
        return "signature_invalid"
    if isinstance(exc, jwt.MissingRequiredClaimError):
        return "required_claim_missing"
    if isinstance(exc, jwt.InvalidAlgorithmError):
        return "algorithm_not_allowed"
    if isinstance(exc, jwt.PyJWKClientError):
        return "jwks_lookup_failed"
    if isinstance(exc, RuntimeError):
        return "auth_configuration_error"
    if isinstance(exc, ValueError):
        return "claims_invalid"
    if isinstance(exc, jwt.PyJWTError):
        return "jwt_invalid"
    return "local_verification_failed"


class SupabaseTokenVerifier:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
        self._jwks: PyJWKClient | None = None

    def _jwks_client(self) -> PyJWKClient:
        if not self.url:
            raise RuntimeError("SUPABASE_URL is required for API authentication")
        if self._jwks is None:
            self._jwks = PyJWKClient(
                f"{self.url}/auth/v1/.well-known/jwks.json",
                lifespan=600,
            )
        return self._jwks

    @staticmethod
    def _claims_to_user(claims: dict[str, Any]) -> AuthenticatedUser:
        user_id = claims.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("token subject is missing")

        metadata = claims.get("app_metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        raw_entitlements = metadata.get("entitlements", ["free"])
        if isinstance(raw_entitlements, str):
            raw_entitlements = [raw_entitlements]
        entitlements = (
            tuple(item for item in raw_entitlements if isinstance(item, str))
            if isinstance(raw_entitlements, list)
            else ("free",)
        )

        role = metadata.get("role")
        role = role if isinstance(role, str) else "user"
        assurance_level = claims.get("aal")
        assurance_level = assurance_level if isinstance(assurance_level, str) else "aal1"
        return AuthenticatedUser(
            user_id=user_id,
            email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            role=role,
            entitlements=entitlements or ("free",),
            assurance_level=assurance_level,
        )

    def verify(self, token: str) -> AuthenticatedUser:
        if not self.url:
            raise RuntimeError("SUPABASE_URL is required for API authentication")
        signing_key = self._jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256", "EdDSA"],
            audience="authenticated",
            issuer=f"{self.url}/auth/v1",
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        return self._claims_to_user(claims)

    async def verify_async(self, token: str) -> AuthenticatedUser:
        try:
            return self.verify(token)
        except (jwt.PyJWTError, RuntimeError, ValueError) as exc:
            reason_code = _jwt_failure_reason(exc)
            # Do not log the token, exception text, key material, claims, or response body.
            logger.warning(
                "auth_local_verification_failed reason_code=%s fallback=configured",
                reason_code,
            )
            if not self.publishable_key or not self.url:
                logger.error(
                    "auth_fallback_unavailable reason_code=provider_configuration_missing"
                )
                raise HTTPException(
                    status_code=503,
                    detail="Authentication provider is not configured",
                ) from None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.url}/auth/v1/user",
                    headers={
                        "apikey": self.publishable_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.TimeoutException:
            logger.warning("auth_fallback_unavailable reason_code=provider_timeout")
            raise HTTPException(
                status_code=503,
                detail="Authentication provider unavailable",
            ) from None
        except httpx.HTTPError:
            logger.warning("auth_fallback_unavailable reason_code=provider_transport_error")
            raise HTTPException(
                status_code=503,
                detail="Authentication provider unavailable",
            ) from None

        if response.status_code != 200:
            # Only log the status code; never log request headers or response content.
            logger.warning(
                "auth_fallback_rejected reason_code=supabase_user_endpoint_rejected "
                "http_status=%s",
                response.status_code,
            )
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        try:
            user = response.json()
        except ValueError:
            logger.warning("auth_fallback_rejected reason_code=invalid_user_payload")
            raise HTTPException(status_code=401, detail="Invalid authenticated user") from None

        user_id = user.get("id") if isinstance(user, dict) else None
        if not isinstance(user_id, str) or not user_id:
            logger.warning("auth_fallback_rejected reason_code=user_id_missing")
            raise HTTPException(status_code=401, detail="Invalid authenticated user")

        metadata = user.get("app_metadata") if isinstance(user.get("app_metadata"), dict) else {}
        raw_entitlements = metadata.get("entitlements", ["free"])
        if isinstance(raw_entitlements, str):
            raw_entitlements = [raw_entitlements]
        entitlements = (
            tuple(item for item in raw_entitlements if isinstance(item, str))
            if isinstance(raw_entitlements, list)
            else ("free",)
        )

        role = metadata.get("role")
        role = role if isinstance(role, str) else "user"
        logger.info("auth_fallback_succeeded provider=supabase_user_endpoint")
        return AuthenticatedUser(
            user_id=user_id,
            email=user.get("email") if isinstance(user.get("email"), str) else None,
            role=role,
            entitlements=entitlements or ("free",),
            assurance_level="aal1",
        )


verifier = SupabaseTokenVerifier()


async def require_user(request: Request) -> AuthenticatedUser:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        logger.info("auth_request_rejected reason_code=bearer_header_missing")
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization[7:].strip()
    if not token:
        logger.info("auth_request_rejected reason_code=bearer_token_empty")
        raise HTTPException(status_code=401, detail="Authentication required")

    return await verifier.verify_async(token)
