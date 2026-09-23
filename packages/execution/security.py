import hashlib
import hmac


def approval_token_digest(token: str) -> str:
    if not token:
        raise ValueError("approval token is required")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_approval_token(token: str, expected_digest: str) -> bool:
    if not token or not expected_digest:
        return False
    return hmac.compare_digest(approval_token_digest(token), expected_digest)
