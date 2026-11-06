from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from ..db import db, utcnow
from ..security import (clear_failed_logins, create_access_token, create_refresh_token,
                        get_current_user, hash_password, is_locked_out, register_failed_login,
                        set_auth_cookies, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def public_user(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id") or doc.get("id")),
        "email": doc["email"],
        "name": doc.get("name"),
        "role": doc.get("role", "user"),
        "plan": doc.get("plan", "free"),
        "reports_used": doc.get("reports_used", 0),
        "credits": doc.get("credits", 0),
        "profile": doc.get("profile") or {},
        "persona_key": doc.get("persona_key"),
        "created_at": doc.get("created_at"),
    }


@router.post("/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    doc = {
        "email": email, "password_hash": hash_password(payload.password), "name": payload.name.strip(),
        "role": "user", "plan": "free", "reports_used": 0, "credits": 0, "profile": {},
        "persona_key": None, "created_at": utcnow().isoformat(),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    user_id = str(result.inserted_id)
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    return {**public_user(doc), "access_token": create_access_token(user_id, email)}


@router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    identifier = f"{request.client.host if request.client else 'unknown'}:{email}"
    if await is_locked_out(identifier):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await register_failed_login(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await clear_failed_logins(identifier)
    user_id = str(user["_id"])
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    return {**public_user(user), "access_token": create_access_token(user_id, email)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    doc = await db.users.find_one({"email": user["email"]})
    return public_user(doc)


class ProfileIn(BaseModel):
    stage: str | None = None
    household: str | None = None
    work_locality: str | None = None
    work_mode: str | None = None
    budget_band: str | None = None
    commute_tolerance: str | None = None
    free_text: str | None = None
    persona_key: str | None = None


@router.put("/profile")
async def update_profile(payload: ProfileIn, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    profile = payload.model_dump(exclude_none=True)
    persona_key = profile.pop("persona_key", None)
    update = {"profile": profile}
    if persona_key:
        update["persona_key"] = persona_key
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": update})
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    return public_user(doc)
