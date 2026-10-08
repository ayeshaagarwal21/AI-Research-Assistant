"""Authentication helpers for the separate admin portal.

Admin credentials are intentionally separate from normal user authentication.
They are read from environment variables and never appear in the Streamlit user UI.
"""
import hmac
import time
from typing import Optional

import jwt
from fastapi import HTTPException, status

from backend.app.core import config

ADMIN_EMAIL = config.ADMIN_EMAIL
ADMIN_PASSWORD = config.ADMIN_PASSWORD
ADMIN_SECRET_KEY = config.ADMIN_SECRET_KEY


def create_admin_token(email: str) -> str:
    now = int(time.time())
    payload = {
        "sub": email,
        "scope": "admin",
        "iat": now,
        "exp": now + config.ADMIN_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, ADMIN_SECRET_KEY, algorithm=config.ALGORITHM)


def authenticate_admin(email: str, password: str) -> Optional[str]:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return None
    if not hmac.compare_digest(email.strip().lower(), ADMIN_EMAIL.strip().lower()):
        return None
    if not hmac.compare_digest(password, ADMIN_PASSWORD):
        return None
    return create_admin_token(ADMIN_EMAIL.strip().lower())


def require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, ADMIN_SECRET_KEY, algorithms=[config.ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired admin session")

    if payload.get("scope") != "admin" or payload.get("sub") != ADMIN_EMAIL.strip().lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    return payload["sub"]
