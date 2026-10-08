import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.security import decode_access_token
from backend.app.db.database import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Resolve the bearer token to a user dict: {id, username, email, created_at}."""
    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _unauthorized("Invalid or expired token")

    subject = payload.get("sub")
    user = get_user_by_id(int(subject)) if subject and str(subject).isdigit() else None
    if user is None:
        raise _unauthorized("Invalid or expired token")
    return user
