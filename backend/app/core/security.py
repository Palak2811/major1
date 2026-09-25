import hashlib
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.models.base import utcnow

# Argon2id: memory-hard, random per-hash salt embedded in the encoded hash.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)

ROLE_SCOPES: dict[str, list[str]] = {
    "student": ["me", "content:read"],
    "content_manager": ["me", "content:read", "content:write", "admin:panel"],
    "admin": ["me", "content:read", "content:write", "admin:panel", "users:manage"],
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        return _hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, role: str, scopes: list[str]) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "scopes": scopes,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_ttl_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
