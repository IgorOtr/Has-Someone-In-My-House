"""Password hashing and JWT access tokens for the web dashboard.

Password hashing uses only the standard library (PBKDF2-HMAC-SHA256) to
avoid adding a compiled dependency (e.g. bcrypt) for a local single-user
tool.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

_HASH_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 600_000  # OWASP-recommended minimum for PBKDF2-HMAC-SHA256
_JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash encoded as ``algorithm$iterations$salt$hash``."""
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return f"{_HASH_ALGORITHM}${_PBKDF2_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Return True if ``password`` matches a hash produced by :func:`hash_password`."""
    try:
        algorithm, iterations_str, salt, hash_hex = encoded_hash.split("$")
    except ValueError:
        return False
    if algorithm != _HASH_ALGORITHM:
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations_str)
    )
    return hmac.compare_digest(derived.hex(), hash_hex)


def create_access_token(subject: str, secret_key: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> str:
    """Return the token's subject (the user's email).

    Raises:
        jwt.PyJWTError: If the token is malformed, tampered with, or expired.
    """
    payload = jwt.decode(token, secret_key, algorithms=[_JWT_ALGORITHM])
    return payload["sub"]
