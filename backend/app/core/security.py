"""Password hashing (scrypt) and JWT helpers.

scrypt ships with Python's standard library, so there is no passlib/bcrypt
version conflict to fight with.
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from backend.app.core import config

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = hashed_password.split("$")
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.scrypt(
        plain_password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=len(expected)
    )
    return hmac.compare_digest(actual, expected)


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    minutes = config.ACCESS_TOKEN_EXPIRE_MINUTES if expires_minutes is None else expires_minutes
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError if the token is invalid or expired."""
    return jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
