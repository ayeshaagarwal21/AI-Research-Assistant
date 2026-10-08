from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.dependencies import get_current_user
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.db.database import create_user, get_user_by_email, record_login
from backend.app.schemas.auth import Token, UserLogin, UserOut, UserSignup

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _token_for(user_id: int, username: str) -> dict:
    return {
        "access_token": create_access_token({"sub": str(user_id)}),
        "token_type": "bearer",
        "username": username,
    }


@router.post("/signup", response_model=Token, status_code=201)
def signup(user: UserSignup):
    try:
        user_id = create_user(user.username, user.email, hash_password(user.password))
    except ValueError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    record_login(user_id)
    return _token_for(user_id, user.username.strip())


@router.post("/login", response_model=Token)
def login(credentials: UserLogin):
    record = get_user_by_email(credentials.email)
    if record is None or not verify_password(credentials.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    record_login(record["id"])
    return _token_for(record["id"], record["username"])


@router.get("/me", response_model=UserOut)
def me(current_user: dict = Depends(get_current_user)):
    return current_user
