from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db import db, new_id, now_iso, clean, audit
from auth import get_current_user

crm_router = APIRouter(prefix="/api", tags=["crm"])

PIPELINE_STAGES = ["new_lead", "contact_required", "contacted", "qualified", "vehicle_matched",
                   "appointment_requested", "appointment_confirmed", "test_drive_scheduled",
                   "test_drive_completed", "negotiation", "sale_reported", "sale_verified", "lost"]

_STATUS_TO_STAGE = {
    "new": "new_lead", "needs_review": "contact_required", "qualified": "qualified",
    "partially_qualified": "qualified", "sent_to_dealership": "vehicle_matched",
    "appointment_requested": "appointment_requested", "appointment_confirmed": "appointment_confirmed",
    "appointment_declined": "contacted", "lost": "lost",
}

FINANCE_ROLES = ("platform_admin", "dealership_admin", "dealership_manager", "platform_support")
COMM_PERMISSION_KEYS = ("operational", "appointment", "promotional")


def stage_of(lead: dict) -> str:
    return lead.get("pipeline_stage") or _STATUS_TO_STAGE.get(lead.get("status"), "new_lead")


async def log_activity(org_id, lead_id, activity_type, actor="system", details="", dealer_group_id=None):
    await db.activities.insert_one({"id": new_id(), "organization_id": org_id, "lead_id": lead_id,
        "activity_type": activity_type, "actor": actor, "details": details,
        "dealer_group_id": dealer_group_id, "created_at": now_iso()})


async def scoped_lead(lead_id: str, user: dict) -> dict:
    """Load a lead within the user's org; representatives only see leads assigned to them."""
    lead = await db.leads.find_one({"id": lead_id, "organization_id": user["organization_id"]})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if user["role"] == "dealership_representative" and lead.get("assigned_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your lead")
    return clean(lead)


def _actor(user):
    return user.get("email", user["id"])


def _user_out(u):
    if not u:
        return None
    return {"id": u["id"], "name": f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip(),
            "email": u.get("email"), "role": u.get("role")}


@crm_router.get("/leads/{lead_id}/profile")
async def customer_profile(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await scoped_lead(lead_id, user)
    finance = user["role"] in FINANCE_ROLES
    seller = clean(await db.sellers.find_one({"id": lead["seller_id"]})) or {}
    trade_in = clean(await db.seller_vehicles.find_one({"lead_id": lead_id}))
    pref = clean(await db.inventory_preferences.find_one({"lead_id": lead_id}))
    conv = clean(await db.conversations.find_one({"lead_id": lead_id}))
    messages = [clean(m) for m in await db.messages.find(
        {"conversation_id": conv["id"]}).sort("created_at", 1).to_list(1000)] if conv else []
    matches = []
    for m in await db.inventory_matches.find({"lead_id": lead_id}).sort("ranking", 1).to_list(20):
        clean(m)
        v = await db.inventory_vehicles.find_one({"id": m["inventory_vehicle_id"]})
        m["vehicle"] = clean(v) if v else None
        matches.append(m)
    groups = {g["id"]: g for g in await db.dealer_groups.find({"organization_id": lead["organization_id"]}).to_list(500)}
    gname = lambda gid: (groups.get(gid) or {}).get("name")  # noqa: E731
    users = {u["id"]: u for u in await db.users.find({"organization_id": lead["organization_id"]}).to_list(500)}

    consents = [clean(c) for c in await db.consent_records.find({"lead_id": lead_id}).sort("created_at", 1).to_list(200)]
    for c in consents:
        c["recipient_names"] = [gname(g) or g for g in c.get("recipient_dealer_group_ids", [])]
    referrals = []
    for r in await db.referrals.find({"lead_id": lead_id}).sort("created_at", -1).to_list(50):
        clean(r)
        r["dealer_group_name"] = gname(r.get("dealer_group_id"))
        r["consent_status"] = lead.get("consent_status")
        referrals.append(r)
    sales = []
    for s in await db.sales.find({"lead_id": lead_id}).sort("created_at", -1).to_list(50):
        clean(s)
        s["dealer_group_name"] = gname(s.get("dealer_group_id"))
        if finance:
            s["commission"] = clean(await db.commission_transactions.find_one({"sale_id": s["id"]}))
        else:
            s.pop("sale_amount", None)
        sales.append(s)
    appts = []
    for a in await db.appointments.find({"lead_id": lead_id}).sort("start_time", -1).to_list(100):
        clean(a)
        a["assigned_user"] = _user_out(users.get(a.get("assigned_user_id")))
        appts.append(a)
    test_drives = [clean(t) for t in await db.test_drives.find({"lead_id": lead_id}).sort("created_at", -1).to_list(100)]
    comms = [clean(c) for c in await db.communications.find({"lead_id": lead_id}).sort("created_at", -1).to_list(500)]
    recips = [x for x in [seller.get("email"), seller.get("phone")] if x]
    legacy = [clean(n) for n in await db.notifications.find(
        {"recipient_type": "seller", "recipient_id": {"$in": recips}}).sort("created_at", -1).to_list(200)] if recips else []
    acts = [clean(a) for a in await db.activities.find({"lead_id": lead_id}).sort("created_at", -1).to_list(1000)]
    follow_ups = [clean(f) for f in await db.follow_ups.find({"lead_id": lead_id}).sort("due_at", 1).to_list(200)]
    nxt = next((f for f in follow_ups if f["status"] == "open"), None)
    last_msg = messages[-1]["created_at"] if messages else None
    last_interaction = max(filter(None, [lead.get("last_activity_at"), last_msg, acts[0]["created_at"] if acts else None]), default=None)
    primary_ref = referrals[0] if referrals else None
    return {
        "lead": lead, "customer": seller, "stage": stage_of(lead), "stages": PIPELINE_STAGES,
        "overview": {"preferred_language": seller.get("preferred_language") or (conv or {}).get("language", "en"),
                     "lead_source": lead.get("source"), "assigned_user": _user_out(users.get(lead.get("assigned_user_id"))),
                     "dealer_group": {"id": primary_ref["dealer_group_id"], "name": primary_ref["dealer_group_name"]} if primary_ref else None,
                     "last_interaction": last_interaction, "next_follow_up": nxt},
        "preferences": pref, "trade_in": trade_in, "matches": matches,
        "conversation": conv, "messages": messages, "activities": acts, "appointments": appts,
        "test_drives": test_drives, "referrals": referrals, "sales": sales, "can_view_financials": finance,
        "communications": comms, "legacy_notifications": legacy,
        "communication_permissions": seller.get("communication_permissions") or {k: False for k in COMM_PERMISSION_KEYS},
        "communication_permission_history": seller.get("communication_permission_history", []),
        "consents": consents, "follow_ups": follow_ups,
    }


class CustomerPatch(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_contact_method: Optional[str] = None
    city: Optional[str] = None
    province_state: Optional[str] = None


@crm_router.patch("/leads/{lead_id}/customer")
async def update_customer(lead_id: str, body: CustomerPatch, user: dict = Depends(get_current_user)):
    lead = await scoped_lead(lead_id, user)
    if user["role"] == "platform_support":
        raise HTTPException(status_code=403, detail="Read-only role")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates.get("preferred_language") and updates["preferred_language"] not in ("en", "fr"):
        raise HTTPException(status_code=400, detail="Language must be en or fr")
    if not updates:
        return {"success": True}
    prev = await db.sellers.find_one({"id": lead["seller_id"]}) or {}
    await db.sellers.update_one({"id": lead["seller_id"]}, {"$set": {**updates, "updated_at": now_iso()}})
    await db.leads.update_one({"id": lead_id}, {"$set": {"last_activity_at": now_iso()}})
    await audit(lead["organization_id"], "user", user["id"], "customer", lead["seller_id"], "update",
                {k: prev.get(k) for k in updates}, updates)
    await log_activity(lead["organization_id"], lead_id, "customer_updated", _actor(user),
                       "Updated " + ", ".join(updates.keys()))
    return {"success": True}


class FollowUpBody(BaseModel):
    due_at: str
    note: Optional[str] = ""
    assigned_user_id: Optional[str] = None


@crm_router.post("/leads/{lead_id}/follow-ups")
async def create_follow_up(lead_id: str, body: FollowUpBody, user: dict = Depends(get_current_user)):
    lead = await scoped_lead(lead_id, user)
    try:
        datetime.fromisoformat(body.due_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid due date")
    fu = {"id": new_id(), "organization_id": lead["organization_id"], "lead_id": lead_id, "due_at": body.due_at,
          "note": body.note or "", "assigned_user_id": body.assigned_user_id or lead.get("assigned_user_id") or user["id"],
          "status": "open", "created_by": user["id"], "completed_at": None, "created_at": now_iso()}
    await db.follow_ups.insert_one(dict(fu))
    await log_activity(lead["organization_id"], lead_id, "follow_up_scheduled", _actor(user),
                       f"Follow-up due {body.due_at[:16].replace('T', ' ')}" + (f" · {body.note}" if body.note else ""))
    return fu


@crm_router.post("/follow-ups/{fu_id}/complete")
async def complete_follow_up(fu_id: str, user: dict = Depends(get_current_user)):
    fu = await db.follow_ups.find_one({"id": fu_id, "organization_id": user["organization_id"]})
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    await scoped_lead(fu["lead_id"], user)
    if fu["status"] != "open":
        raise HTTPException(status_code=400, detail="Follow-up already closed")
    await db.follow_ups.update_one({"id": fu_id}, {"$set": {"status": "done", "completed_at": now_iso()}})
    await db.leads.update_one({"id": fu["lead_id"]}, {"$set": {"last_activity_at": now_iso()}})
    await log_activity(fu["organization_id"], fu["lead_id"], "follow_up_completed", _actor(user), fu.get("note") or "")
    return {"success": True}


@crm_router.get("/follow-ups")
async def list_follow_ups(user: dict = Depends(get_current_user), status: str = "open"):
    q = {"organization_id": user["organization_id"], "status": status}
    if user["role"] == "dealership_representative":
        q["assigned_user_id"] = user["id"]
    rows = await db.follow_ups.find(q).sort("due_at", 1).to_list(500)
    now = datetime.now(timezone.utc).isoformat()
    return [{**clean(r), "overdue": r["status"] == "open" and r["due_at"] < now} for r in rows]


class CommPermBody(BaseModel):
    operational: bool
    appointment: bool
    promotional: bool
    source: str = "staff_recorded"


@crm_router.put("/leads/{lead_id}/communication-permissions")
async def set_comm_permissions(lead_id: str, body: CommPermBody, user: dict = Depends(get_current_user)):
    lead = await scoped_lead(lead_id, user)
    if user["role"] == "platform_support":
        raise HTTPException(status_code=403, detail="Read-only role")
    perms = {k: getattr(body, k) for k in COMM_PERMISSION_KEYS}
    entry = {**perms, "source": body.source, "recorded_by": user["id"], "at": now_iso()}
    await db.sellers.update_one({"id": lead["seller_id"]}, {"$set": {"communication_permissions": perms,
        "marketing_consent": body.promotional, "updated_at": now_iso()},
        "$push": {"communication_permission_history": entry}})
    await audit(lead["organization_id"], "user", user["id"], "communication_permissions", lead["seller_id"], "update", None, perms)
    await log_activity(lead["organization_id"], lead_id, "communication_permissions_updated", _actor(user),
                       ", ".join(f"{k}: {'yes' if v else 'no'}" for k, v in perms.items()))
    return {"success": True, "permissions": perms}


class WithdrawBody(BaseModel):
    reason: Optional[str] = None


@crm_router.post("/leads/{lead_id}/consent/withdraw")
async def withdraw_consent(lead_id: str, body: WithdrawBody, user: dict = Depends(get_current_user)):
    """Records a NEW withdrawal entry; historical consent records are never modified."""
    lead = await scoped_lead(lead_id, user)
    if user["role"] == "platform_support":
        raise HTTPException(status_code=403, detail="Read-only role")
    last = await db.consent_records.find_one({"lead_id": lead_id, "status": "accepted"}, sort=[("created_at", -1)])
    if not last or lead.get("consent_status") == "withdrawn":
        raise HTTPException(status_code=400, detail="No active consent to withdraw")
    rec = {"id": new_id(), "organization_id": lead["organization_id"], "lead_id": lead_id, "seller_id": lead["seller_id"],
           "agreement_version_id": last.get("agreement_version_id"), "agreement_version": last.get("agreement_version"),
           "language": last.get("language"), "recipient_dealer_group_ids": last.get("recipient_dealer_group_ids", []),
           "categories": last.get("categories", []), "status": "withdrawn", "method": "staff_recorded",
           "withdraws_record_id": last["id"], "reason": body.reason, "recorded_by": user["id"],
           "accepted_at": None, "withdrawn_at": now_iso(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.consent_records.insert_one(dict(rec))
    await db.leads.update_one({"id": lead_id}, {"$set": {"consent_status": "withdrawn", "last_activity_at": now_iso()}})
    await audit(lead["organization_id"], "user", user["id"], "consent", rec["id"], "withdrawn")
    await log_activity(lead["organization_id"], lead_id, "consent_withdrawn", _actor(user), body.reason or "Consent withdrawn")
    return {"success": True}
