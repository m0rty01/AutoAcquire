import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from db import db, new_id, now_iso, clean, audit
from comms import send_communication
from auth import get_current_user

users_router = APIRouter(prefix="/api", tags=["users"])

ROLE_LABELS = {
    "platform_admin": "Super Admin",
    "platform_support": "Platform Support / Operations",
    "dealership_admin": "Dealership Admin",
    "dealership_manager": "Dealership Manager",
    "dealership_representative": "Sales Representative",
}
_CAN_MANAGE = {
    "platform_admin": set(ROLE_LABELS),
    "dealership_admin": {"dealership_admin", "dealership_manager", "dealership_representative"},
    "dealership_manager": {"dealership_representative"},
}
_VIEW_ROLES = ("platform_admin", "platform_support", "dealership_admin", "dealership_manager")


def _manageable(actor: dict) -> set:
    return _CAN_MANAGE.get(actor["role"], set())


def _out(u: dict, orgs: dict = None, groups: dict = None) -> dict:
    clean(u)
    u.pop("password_hash", None)
    u.pop("google_sub", None)
    u["role_label"] = ROLE_LABELS.get(u.get("role"), u.get("role"))
    u["status"] = u.get("status") or "active"
    if orgs is not None:
        u["organization_name"] = (orgs.get(u.get("organization_id")) or {}).get("name")
    if groups is not None:
        u["dealer_group_name"] = (groups.get(u.get("dealer_group_id")) or {}).get("name")
    return u


async def _target(user_id: str, actor: dict) -> dict:
    q = {"id": user_id}
    if actor["role"] != "platform_admin":
        q["organization_id"] = actor["organization_id"]
    t = await db.users.find_one(q)
    if not t:
        raise HTTPException(status_code=404, detail="User not found")
    if t.get("role") not in _manageable(actor):
        raise HTTPException(status_code=403, detail="You cannot manage this user")
    return clean(t)


async def _check_dealer_group(dg_id: Optional[str], org_id: str):
    if dg_id and not await db.dealer_groups.find_one({"id": dg_id, "organization_id": org_id}):
        raise HTTPException(status_code=400, detail="Dealer group does not belong to this dealership")


async def _issue_reset(u: dict, actor: dict, kind: str) -> str:
    token = secrets.token_urlsafe(32)
    hours = 72 if kind == "invite" else 1
    await db.password_reset_tokens.update_many({"user_id": u["id"], "used": False}, {"$set": {"used": True}})
    await db.password_reset_tokens.insert_one({"id": new_id(), "user_id": u["id"], "token": token, "used": False,
        "kind": kind, "issued_by": actor["id"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(), "created_at": now_iso()})
    url = f"{os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')}/reset-password?token={token}"
    comm = await send_communication(org_id=u["organization_id"], channel="email",
        template="user_invitation" if kind == "invite" else "password_reset", to=u["email"],
        vars={"name": u.get("first_name") or ""}, link=url, recipient_type="staff", triggered_by=actor.get("email", "system"))
    # The link is only revealed to the admin when the email could not be delivered by the provider
    return url if comm["status"] in ("not_configured", "failed", "blocked") else None, comm["status"]


@users_router.get("/users/roles")
async def roles(user: dict = Depends(get_current_user)):
    return {"roles": [{"value": k, "label": v} for k, v in ROLE_LABELS.items()],
            "manageable": sorted(_manageable(user))}


@users_router.get("/users")
async def list_users(user: dict = Depends(get_current_user), search: Optional[str] = None,
                     role: Optional[str] = None, status: Optional[str] = None,
                     organization_id: Optional[str] = None, dealer_group_id: Optional[str] = None):
    q = {}
    if user["role"] == "platform_admin":
        if organization_id:
            q["organization_id"] = organization_id
    else:
        q["organization_id"] = user["organization_id"]
    if role:
        q["role"] = role
    if status:
        q["status"] = status
    if dealer_group_id:
        q["dealer_group_id"] = dealer_group_id
    rows = await db.users.find(q).sort("created_at", 1).to_list(2000)
    if search:
        s = search.lower()
        rows = [u for u in rows if s in f"{u.get('first_name') or ''} {u.get('last_name') or ''} {u.get('email')}".lower()]
    orgs = {o["id"]: o for o in await db.organizations.find({"id": {"$in": list({u["organization_id"] for u in rows})}}).to_list(None)}
    groups = {g["id"]: g for g in await db.dealer_groups.find({"id": {"$in": [u.get("dealer_group_id") for u in rows if u.get("dealer_group_id")]}}).to_list(None)}
    full = user["role"] in _VIEW_ROLES
    out = []
    for u in rows:
        u = _out(u, orgs, groups)
        if not full:
            u = {k: u.get(k) for k in ("id", "first_name", "last_name", "email", "role", "role_label", "status")}
        out.append(u)
    return out


class CreateUserBody(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    phone: Optional[str] = None
    organization_id: Optional[str] = None
    dealer_group_id: Optional[str] = None


async def _create(body: CreateUserBody, actor: dict) -> dict:
    if body.role not in _manageable(actor):
        raise HTTPException(status_code=403, detail="You are not allowed to create users with this role")
    org_id = actor["organization_id"]
    if body.organization_id and body.organization_id != org_id:
        if actor["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="Cannot create users in another dealership")
        if not await db.organizations.find_one({"id": body.organization_id}):
            raise HTTPException(status_code=400, detail="Dealership not found")
        org_id = body.organization_id
    await _check_dealer_group(body.dealer_group_id, org_id)
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    u = {"id": new_id(), "organization_id": org_id, "first_name": body.first_name.strip(),
         "last_name": body.last_name.strip(), "email": email, "phone": body.phone, "role": body.role,
         "dealer_group_id": body.dealer_group_id, "status": "invited", "auth_provider": "password",
         "password_hash": None, "last_login_at": None, "created_by": actor["id"],
         "created_at": now_iso(), "updated_at": now_iso()}
    await db.users.insert_one(dict(u))
    await audit(org_id, "user", actor["id"], "user", u["id"], "created", None, {"role": body.role})
    url, email_status = await _issue_reset(u, actor, "invite")
    return {"user": _out(u), "setup_url": url, "email_status": email_status}


@users_router.post("/users")
async def create_user(body: CreateUserBody, user: dict = Depends(get_current_user)):
    return await _create(body, user)


@users_router.post("/users/invite")
async def invite_user(body: CreateUserBody, user: dict = Depends(get_current_user)):
    return await _create(body, user)


class UpdateUserBody(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[str] = None
    dealer_group_id: Optional[str] = None


@users_router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserBody, user: dict = Depends(get_current_user)):
    t = await _target(user_id, user)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if "role" in updates:
        if updates["role"] not in _manageable(user):
            raise HTTPException(status_code=403, detail="You are not allowed to assign this role")
        if t["id"] == user["id"] and updates["role"] != t["role"]:
            raise HTTPException(status_code=400, detail="You cannot change your own role")
    if "organization_id" in updates:
        if user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="Only Super Admin can move users between dealerships")
        if not await db.organizations.find_one({"id": updates["organization_id"]}):
            raise HTTPException(status_code=400, detail="Dealership not found")
    org_id = updates.get("organization_id", t["organization_id"])
    if updates.get("dealer_group_id") == "":
        updates["dealer_group_id"] = None
    await _check_dealer_group(updates.get("dealer_group_id"), org_id)
    if not updates:
        return _out(t)
    updates["updated_at"] = now_iso()
    await db.users.update_one({"id": user_id}, {"$set": updates})
    await audit(t["organization_id"], "user", user["id"], "user", user_id, "updated",
                {k: t.get(k) for k in updates if k != "updated_at"}, updates)
    return _out(await db.users.find_one({"id": user_id}))


async def _set_status(user_id: str, actor: dict, status: str):
    t = await _target(user_id, actor)
    if t["id"] == actor["id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own account status")
    if status == "inactive" and t.get("status") == "inactive":
        raise HTTPException(status_code=400, detail="User already deactivated")
    if status == "active" and t.get("status") != "inactive":
        raise HTTPException(status_code=400, detail="User is not deactivated")
    new_status = status if status == "inactive" or t.get("password_hash") else "invited"
    await db.users.update_one({"id": user_id}, {"$set": {"status": new_status, "updated_at": now_iso(),
        "deactivated_at": now_iso() if status == "inactive" else None}})
    if status == "inactive":
        await db.password_reset_tokens.update_many({"user_id": user_id, "used": False}, {"$set": {"used": True}})
    await audit(t["organization_id"], "user", actor["id"], "user", user_id,
                "deactivated" if status == "inactive" else "reactivated")
    return {"success": True, "status": new_status}


@users_router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, user: dict = Depends(get_current_user)):
    return await _set_status(user_id, user, "inactive")


@users_router.post("/users/{user_id}/reactivate")
async def reactivate_user(user_id: str, user: dict = Depends(get_current_user)):
    return await _set_status(user_id, user, "active")


@users_router.post("/users/{user_id}/password-reset")
async def admin_password_reset(user_id: str, user: dict = Depends(get_current_user)):
    t = await _target(user_id, user)
    if t.get("status") == "inactive":
        raise HTTPException(status_code=400, detail="Reactivate the account before resetting its password")
    if t.get("auth_provider") == "google" and not t.get("password_hash"):
        raise HTTPException(status_code=400, detail="This user signs in with Google")
    url, email_status = await _issue_reset(t, user, "invite" if t.get("status") == "invited" else "reset")
    await audit(t["organization_id"], "user", user["id"], "user", user_id, "password_reset_initiated")
    return {"success": True, "reset_url": url, "email_status": email_status, "expires_in_hours": 72 if t.get("status") == "invited" else 1}


class PrefsBody(BaseModel):
    language: str


@users_router.patch("/me/preferences")
async def my_preferences(body: PrefsBody, user: dict = Depends(get_current_user)):
    if body.language not in ("en", "fr"):
        raise HTTPException(status_code=400, detail="Language must be en or fr")
    await db.users.update_one({"id": user["id"]}, {"$set": {"preferred_language": body.language, "updated_at": now_iso()}})
    return {"success": True, "language": body.language}
