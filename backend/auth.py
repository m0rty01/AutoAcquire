import os
import jwt
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from db import db, new_id, now_iso, clean, audit

JWT_ALGORITHM = "HS256"
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        clean(user)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


# ---- Schemas ----
class RegisterBody(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    organization_name: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    password: str


def _slugify(name: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base or "dealership"


@auth_router.post("/register")
async def register(body: RegisterBody):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    org_id = new_id()
    slug = _slugify(body.organization_name)
    if await db.organizations.find_one({"slug": slug}):
        slug = f"{slug}-{org_id[:6]}"
    await db.organizations.insert_one({
        "id": org_id, "name": body.organization_name, "slug": slug,
        "status": "active", "country": "CA", "time_zone": "America/Toronto",
        "plan": "pilot", "onboarding_complete": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    })

    user_id = new_id()
    await db.users.insert_one({
        "id": user_id, "organization_id": org_id, "first_name": body.first_name,
        "last_name": body.last_name, "email": email, "phone": None,
        "role": "dealership_admin", "status": "active", "auth_provider": "password",
        "password_hash": hash_password(body.password), "last_login_at": now_iso(),
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    await audit(org_id, "user", user_id, "user", user_id, "register")
    token = create_access_token(user_id, email)
    user = await db.users.find_one({"id": user_id})
    clean(user); user.pop("password_hash", None)
    return {"token": token, "user": user}


@auth_router.post("/login")
async def login(body: LoginBody):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_iso()}})
    await audit(user["organization_id"], "user", user["id"], "user", user["id"], "login")
    token = create_access_token(user["id"], email)
    clean(user); user.pop("password_hash", None)
    return {"token": token, "user": user}


@auth_router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"success": True}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"id": user["organization_id"]})
    return {"user": user, "organization": clean(org) if org else None}


@auth_router.post("/forgot-password")
async def forgot_password(body: ForgotBody):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "id": new_id(), "user_id": user["id"], "token": token, "used": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "created_at": now_iso(),
        })
        print(f"[PASSWORD RESET] {email} token={token}")
    return {"success": True, "message": "If the email exists, a reset link was sent."}


@auth_router.post("/reset-password")
async def reset_password(body: ResetBody):
    rec = await db.password_reset_tokens.find_one({"token": body.token, "used": False})
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid or used reset token")
    if datetime.fromisoformat(rec["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token expired")
    await db.users.update_one({"id": rec["user_id"]},
                              {"$set": {"password_hash": hash_password(body.password)}})
    await db.password_reset_tokens.update_one({"id": rec["id"]}, {"$set": {"used": True}})
    return {"success": True}
