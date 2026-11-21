from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db import db, new_id, now_iso, clean, audit
from auth import get_current_user
from crm import scoped_lead, log_activity
from automation import fire

td_router = APIRouter(prefix="/api", tags=["test-drives"])

STATUSES = ["requested", "pending_confirmation", "confirmed", "completed", "cancelled", "no_show", "dealership_declined"]
_ALLOWED = {
    "confirm": ("requested", "pending_confirmation"),
    "decline": ("requested", "pending_confirmation"),
    "reschedule": ("requested", "pending_confirmation", "confirmed"),
    "cancel": ("requested", "pending_confirmation", "confirmed"),
    "complete": ("confirmed",),
    "no-show": ("confirmed",),
}


def _iso(v: str) -> str:
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid date/time")


async def _scoped_td(td_id: str, user: dict) -> dict:
    td = await db.test_drives.find_one({"id": td_id, "organization_id": user["organization_id"]})
    if not td:
        raise HTTPException(status_code=404, detail="Test drive not found")
    if user["role"] == "dealership_representative" and td.get("assigned_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your test drive")
    return clean(td)


def _writer(user):
    if user["role"] == "platform_support":
        raise HTTPException(status_code=403, detail="Read-only role")


def _query(user, dealer_group_id, assigned_user_id, status, date_from, date_to):
    q = {"organization_id": user["organization_id"]}
    if user["role"] == "dealership_representative":
        q["assigned_user_id"] = user["id"]
    elif assigned_user_id:
        q["assigned_user_id"] = assigned_user_id
    if dealer_group_id:
        q["dealer_group_id"] = dealer_group_id
    if status:
        q["status"] = status
    if date_from or date_to:
        q["scheduled_at"] = {**({"$gte": date_from} if date_from else {}), **({"$lte": date_to + "T23:59:59" if len(date_to) == 10 else date_to} if date_to else {})}
    return q


@td_router.get("/test-drives")
async def list_test_drives(user: dict = Depends(get_current_user), dealer_group_id: Optional[str] = None,
                           assigned_user_id: Optional[str] = None, status: Optional[str] = None,
                           date_from: Optional[str] = None, date_to: Optional[str] = None):
    rows = await db.test_drives.find(_query(user, dealer_group_id, assigned_user_id, status, date_from, date_to)).sort("scheduled_at", 1).to_list(2000)
    sellers = {s["id"]: s for s in await db.sellers.find({"id": {"$in": [r["seller_id"] for r in rows]}}).to_list(None)}
    users = {u["id"]: u for u in await db.users.find({"organization_id": user["organization_id"]}).to_list(500)}
    groups = {g["id"]: g for g in await db.dealer_groups.find({"organization_id": user["organization_id"]}).to_list(500)}
    out = []
    for r in rows:
        clean(r)
        s, u = sellers.get(r["seller_id"]) or {}, users.get(r.get("assigned_user_id")) or {}
        r["customer_name"] = (f"{s.get('first_name') or ''} {s.get('last_name') or ''}").strip() or "Anonymous customer"
        r["representative"] = (f"{u.get('first_name', '')} {u.get('last_name', '')}").strip() or None
        r["dealer_group_name"] = (groups.get(r.get("dealer_group_id")) or {}).get("name")
        out.append(r)
    return out


@td_router.get("/test-drives/dashboard")
async def td_dashboard(user: dict = Depends(get_current_user), dealer_group_id: Optional[str] = None,
                       assigned_user_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    rows = await db.test_drives.find(_query(user, dealer_group_id, assigned_user_id, None, date_from, date_to)).to_list(5000)
    now = now_iso()
    by = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    completed = [r for r in rows if r["status"] == "completed"]
    lead_ids = [r["lead_id"] for r in completed]
    sold = {s["lead_id"] for s in await db.sales.find({"lead_id": {"$in": lead_ids}, "status": "verified"}).to_list(None)}
    converted = sum(1 for r in completed if r.get("sale_id") or r["lead_id"] in sold)
    return {"total": len(rows), "upcoming": sum(1 for r in rows if r["status"] in ("confirmed", "pending_confirmation", "requested") and (r.get("scheduled_at") or "") >= now),
            "completed": by["completed"], "cancelled": by["cancelled"] + by["dealership_declined"], "no_shows": by["no_show"],
            "by_status": by, "converted_to_sale": converted,
            "conversion_rate": round(converted / len(completed) * 100, 1) if completed else 0}


class TDCreate(BaseModel):
    lead_id: str
    requested_time: str
    inventory_vehicle_id: Optional[str] = None
    notes: Optional[str] = None


@td_router.post("/test-drives")
async def create_test_drive(body: TDCreate, user: dict = Depends(get_current_user)):
    _writer(user)
    lead = await scoped_lead(body.lead_id, user)
    when = _iso(body.requested_time)
    ref = await db.referrals.find_one({"lead_id": lead["id"]}) or {}
    veh_id = body.inventory_vehicle_id or ref.get("inventory_vehicle_id")
    if not veh_id:
        top = await db.inventory_matches.find_one({"lead_id": lead["id"]}, sort=[("ranking", 1)])
        veh_id = (top or {}).get("inventory_vehicle_id")
    v = await db.inventory_vehicles.find_one({"id": veh_id, "organization_id": lead["organization_id"]}) if veh_id else None
    if body.inventory_vehicle_id and not v:
        raise HTTPException(status_code=400, detail="Vehicle not found")
    td = {"id": new_id(), "organization_id": lead["organization_id"], "lead_id": lead["id"], "seller_id": lead["seller_id"],
          "referral_id": ref.get("id"), "dealer_group_id": (v or {}).get("dealer_group_id") or ref.get("dealer_group_id"),
          "inventory_vehicle_id": (v or {}).get("id"),
          "vehicle_label": " ".join(str(x) for x in [(v or {}).get("year"), (v or {}).get("make"), (v or {}).get("model")] if x) or ref.get("vehicle_label"),
          "assigned_user_id": lead.get("assigned_user_id"), "requested_at": when, "confirmed_at": None, "scheduled_at": when,
          "status": "requested", "notes": [{"content": body.notes, "by": user.get("email"), "at": now_iso()}] if body.notes else [],
          "customer_feedback": None, "completed_at": None, "sale_id": None,
          "status_history": [{"status": "requested", "at": now_iso(), "by": user.get("email")}],
          "created_by": user["id"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.test_drives.insert_one(dict(td))
    await log_activity(lead["organization_id"], lead["id"], "test_drive_requested", user.get("email"),
                       f"{td['vehicle_label'] or 'Vehicle'} · {when[:16].replace('T', ' ')}")
    await audit(lead["organization_id"], "user", user["id"], "test_drive", td["id"], "requested")
    return td


class TDAction(BaseModel):
    time: Optional[str] = None
    reason: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None


async def _transition(td: dict, action: str, status: str, user: dict, extra: dict = None, detail: str = ""):
    if td["status"] not in _ALLOWED[action]:
        raise HTTPException(status_code=400, detail=f"Cannot {action.replace('-', ' ')} a test drive that is {td['status'].replace('_', ' ')}")
    upd = {"status": status, "updated_at": now_iso(), **(extra or {})}
    await db.test_drives.update_one({"id": td["id"]}, {"$set": upd,
        "$push": {"status_history": {"status": status, "at": now_iso(), "by": user.get("email"), "detail": detail}}})
    await log_activity(td["organization_id"], td["lead_id"], f"test_drive_{status}", user.get("email"),
                       f"{td.get('vehicle_label') or 'Test drive'}{' · ' + detail if detail else ''}")
    await audit(td["organization_id"], "user", user["id"], "test_drive", td["id"], status)
    return {**td, **upd}


class TDNote(BaseModel):
    content: str


@td_router.post("/test-drives/{td_id}/notes")
async def td_note(td_id: str, body: TDNote, user: dict = Depends(get_current_user)):
    _writer(user)
    td = await _scoped_td(td_id, user)
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")
    await db.test_drives.update_one({"id": td_id}, {"$push": {"notes": {"content": body.content.strip(), "by": user.get("email"), "at": now_iso()}},
                                                    "$set": {"updated_at": now_iso()}})
    await log_activity(td["organization_id"], td["lead_id"], "test_drive_note", user.get("email"), body.content.strip())
    return {"success": True}


class TDSale(BaseModel):
    sale_id: str


@td_router.post("/test-drives/{td_id}/link-sale")
async def td_link_sale(td_id: str, body: TDSale, user: dict = Depends(get_current_user)):
    _writer(user)
    td = await _scoped_td(td_id, user)
    if td["status"] != "completed":
        raise HTTPException(status_code=400, detail="Only completed test drives can be linked to a sale")
    sale = await db.sales.find_one({"id": body.sale_id, "organization_id": td["organization_id"], "lead_id": td["lead_id"]})
    if not sale:
        raise HTTPException(status_code=400, detail="Sale not found for this customer")
    await db.test_drives.update_one({"id": td_id}, {"$set": {"sale_id": sale["id"], "updated_at": now_iso()}})
    await log_activity(td["organization_id"], td["lead_id"], "test_drive_linked_to_sale", user.get("email"), sale.get("vehicle_label") or "")
    return {"success": True}


@td_router.post("/test-drives/{td_id}/{action}")
async def td_action(td_id: str, action: str, body: TDAction = TDAction(), user: dict = Depends(get_current_user)):
    _writer(user)
    if action not in _ALLOWED:
        raise HTTPException(status_code=404, detail="Unknown action")
    td = await _scoped_td(td_id, user)
    if action == "confirm":
        when = _iso(body.time) if body.time else td["requested_at"]
        out = await _transition(td, action, "confirmed", user, {"confirmed_at": when, "scheduled_at": when}, when[:16].replace("T", " "))
        await db.leads.update_one({"id": td["lead_id"]}, {"$set": {"pipeline_stage": "test_drive_scheduled", "last_activity_at": now_iso()}})
        seller = await db.sellers.find_one({"id": td["seller_id"]}) or {}
        await fire(td["organization_id"], "test_drive_confirmed", td["lead_id"], f"{td_id}:{when}",
                   {"start_time": when, "vehicle": td.get("vehicle_label"),
                    "customer_name": (f"{seller.get('first_name') or ''} {seller.get('last_name') or ''}").strip() or "Customer"})
        return out
    if action == "decline":
        return await _transition(td, action, "dealership_declined", user, {"decline_reason": body.reason}, body.reason or "")
    if action == "reschedule":
        if not body.time:
            raise HTTPException(status_code=400, detail="New time is required")
        when = _iso(body.time)
        return await _transition(td, action, "pending_confirmation", user,
                                 {"requested_at": when, "scheduled_at": when, "confirmed_at": None}, f"rescheduled to {when[:16].replace('T', ' ')}")
    if action == "cancel":
        return await _transition(td, action, "cancelled", user, {"cancel_reason": body.reason}, body.reason or "")
    if action == "no-show":
        return await _transition(td, action, "no_show", user)
    if body.rating is not None and not 1 <= body.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    out = await _transition(td, action, "completed", user, {"completed_at": now_iso(),
        "customer_feedback": body.feedback, "customer_rating": body.rating}, body.feedback or "")
    await db.leads.update_one({"id": td["lead_id"]}, {"$set": {"pipeline_stage": "test_drive_completed", "last_activity_at": now_iso()}})
    return out
