from datetime import timedelta
from typing import Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request

from .config import settings
from .db import db, utcnow

JWT_ALGORITHM = "HS256"
MAX_FAILED = 5
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": utcnow() + timedelta(hours=12),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh", "exp": utcnow() + timedelta(days=7)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token:
        return token
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


async def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["id"] = str(user.pop("_id"))
    user.pop("password_hash", None)
    return user


async def get_optional_user(request: Request) -> Optional[dict]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


async def register_failed_login(identifier: str):
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"last_at": utcnow().isoformat()}},
        upsert=True,
    )


async def is_locked_out(identifier: str) -> bool:
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if not doc or doc.get("count", 0) < MAX_FAILED:
        return False
    from datetime import datetime

    last = datetime.fromisoformat(doc["last_at"])
    if (utcnow() - last).total_seconds() > LOCKOUT_MINUTES * 60:
        await db.login_attempts.delete_one({"identifier": identifier})
        return False
    return True


async def clear_failed_logins(identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})


def set_auth_cookies(response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True,
                        samesite="none", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")


CurrentUser = Depends(get_current_user)
