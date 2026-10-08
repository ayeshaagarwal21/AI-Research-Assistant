"""Private API used only by the standalone admin dashboard."""
import os
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.app.core import config
from backend.app.core.admin_auth import authenticate_admin, require_admin
from backend.app.db.database import get_admin_stats, get_all_users, get_recent_conversations


router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminLogin(BaseModel):
    email: str
    password: str


@router.post("/login")
def admin_login(credentials: AdminLogin):
    token = authenticate_admin(credentials.email, credentials.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return {"access_token": token, "token_type": "bearer"}


def _admin(authorization: str | None):
    return require_admin(authorization)


@router.get("/stats")
def admin_stats(authorization: str | None = Header(default=None)):
    _admin(authorization)
    return get_admin_stats()


@router.get("/users")
def admin_users(authorization: str | None = Header(default=None)):
    _admin(authorization)
    return get_all_users()


@router.get("/conversations")
def admin_conversations(authorization: str | None = Header(default=None)):
    _admin(authorization)
    return get_recent_conversations(limit=100)
