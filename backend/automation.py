import os
import hmac
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from db import db, new_id, now_iso, clean, audit, notify
from auth import require_roles
from crm import log_activity
from comms import send_communication, lead_context

logger = logging.getLogger("automation")
automation_router = APIRouter(prefix="/api", tags=["automation"])
MANAGE = ("platform_admin", "dealership_admin", "dealership_manager")

DEFAULT_RULES = [
    {"key": "new_lead", "name": "A · New consented lead", "trigger": "referral_consented", "delay_minutes": 0,
     "channels": ["email"], "template": "lead_referred_dealer", "language": "customer",
     "params": {"follow_up_hours": 24}},
    {"key": "uncontacted_lead", "name": "B · Uncontacted lead", "trigger": "lead_uncontacted", "delay_minutes": 0,
     "channels": ["email"], "template": "rep_task_alert", "language": "en",
     "params": {"idle_hours": 24, "escalate_after_hours": 48}},
    {"key": "appointment_confirmation", "name": "C · Appointment confirmation", "trigger": "appointment_confirmed",
     "delay_minutes": 0, "channels": ["email", "sms"], "template": "appointment_confirmation", "language": "customer",
     "params": {"reminder_hours_before": 24, "reminder_template": "appointment_reminder"}},
    {"key": "test_drive_confirmation", "name": "D · Test drive confirmation", "trigger": "test_drive_confirmed",
     "delay_minutes": 0, "channels": ["email", "sms"], "template": "test_drive_confirmation", "language": "customer",
     "params": {"reminder_hours_before": 24, "reminder_template": "test_drive_reminder"}},
    {"key": "inactive_customer", "name": "E · Inactive customer", "trigger": "customer_inactive", "delay_minutes": 0,
     "channels": ["email"], "template": "follow_up", "language": "customer",
     "params": {"inactive_days": 7, "send_message": False}},
]


class SkipRun(Exception):
    pass


async def cancel_reminders(source_id: str):
    await db.automation_runs.update_many({"kind": "reminder", "status": "scheduled", "payload.source_id": source_id},
                                         {"$set": {"status": "cancelled", "error": "Source cancelled or rescheduled", "executed_at": now_iso()}})


def _now():
    return datetime.now(timezone.utc)


def _parse(ts):
    try:
        return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except ValueError:
        return None


async def ensure_rules(org_id: str):
    for r in DEFAULT_RULES:
        if not await db.automation_rules.find_one({"organization_id": org_id, "key": r["key"]}):
            await db.automation_rules.insert_one({"id": new_id(), "organization_id": org_id, **r, "enabled": True,
                "assign_to_user_id": None, "created_at": now_iso(), "updated_at": now_iso()})


async def _pick_rep(org_id: str, rule: dict) -> Optional[dict]:
    if rule.get("assign_to_user_id"):
        u = await db.users.find_one({"id": rule["assign_to_user_id"], "organization_id": org_id, "status": "active"})
        if u:
            return u
    reps = await db.users.find({"organization_id": org_id, "role": "dealership_representative", "status": {"$in": ["active", None]}}).to_list(200)
    if not reps:
        return None
    loads = {r["id"]: await db.leads.count_documents({"assigned_user_id": r["id"], "pipeline_stage": {"$nin": ["sale_verified", "lost"]}}) for r in reps}
    return min(reps, key=lambda r: loads[r["id"]])


async def _follow_up(lead, hours, note, actions, assignee=None):
    due = (_now() + timedelta(hours=hours)).isoformat()
    await db.follow_ups.insert_one({"id": new_id(), "organization_id": lead["organization_id"], "lead_id": lead["id"],
        "due_at": due, "note": note, "assigned_user_id": assignee or lead.get("assigned_user_id"), "status": "open",
        "created_by": "automation", "completed_at": None, "created_at": now_iso()})
    actions.append(f"follow-up task due {due[:16]}")


async def _staff_alert(lead, rule, users, details, actions, run_id):
    for u in users:
        await notify(lead["organization_id"], "user", u["id"], "in_app", "automation_alert", {"lead_id": lead["id"], "details": details})
        if "email" in rule["channels"]:
            c = await send_communication(org_id=lead["organization_id"], channel="email", template="rep_task_alert", to=u.get("email"),
                vars={"name": details.split(":")[0], "details": details}, recipient_type="staff",
                idempotency_key=f"{run_id}:{u['id']}", triggered_by="automation")
            actions.append(f"email {u.get('email')} ({c['status']})")
        else:
            actions.append(f"in-app alert {u.get('email')}")


async def _customer_send(lead, rule, template, vars, actions, key_prefix):
    seller, lang, base = await lead_context(lead)
    lang = lang if rule.get("language") == "customer" else rule.get("language", "en")
    for ch in rule["channels"]:
        to = seller.get("email") if ch == "email" else seller.get("phone")
        c = await send_communication(org_id=lead["organization_id"], channel=ch, template=template, to=to, language=lang,
            vars={**base, **vars}, lead_id=lead["id"], seller=seller, idempotency_key=f"{key_prefix}:{ch}", triggered_by="automation")
        actions.append(f"{ch} {template} ({c['status']}{': ' + c['error'] if c.get('error') else ''})")


async def _schedule_reminder(lead, rule, start_time, vars, entity_id, actions, src):
    st = _parse(start_time)
    hrs = rule["params"].get("reminder_hours_before", 24)
    if not st:
        return
    run_at = st - timedelta(hours=hrs)
    if run_at <= _now():
        actions.append("reminder skipped (too close to start)")
        return
    key = f"reminder:{rule['key']}:{entity_id}"
    if await db.automation_runs.find_one({"idempotency_key": key}):
        return
    await db.automation_runs.insert_one({"id": new_id(), "organization_id": lead["organization_id"], "rule_key": rule["key"],
        "kind": "reminder", "lead_id": lead["id"], "entity_id": entity_id, "idempotency_key": key, "status": "scheduled",
        "run_at": run_at.isoformat(), "payload": {"template": rule["params"].get("reminder_template"), "vars": vars,
                                                  "source": src.get("source"), "source_id": src.get("source_id"),
                                                  "start_time": start_time},
        "actions": [], "attempts": 0, "created_at": now_iso()})
    actions.append(f"reminder scheduled {run_at.isoformat()[:16]}")


async def _execute(rule: dict, run: dict):
    lead = await db.leads.find_one({"id": run["lead_id"]})
    if not lead:
        raise RuntimeError("Lead no longer exists")
    clean(lead)
    actions, ctx = [], run.get("payload") or {}
    if run.get("kind") == "reminder":
        src = ctx.get("source")
        coll = db.test_drives if src == "test_drive" else db.appointments
        doc = await coll.find_one({"id": ctx.get("source_id")}) if src else None
        when = (doc or {}).get("scheduled_at" if src == "test_drive" else "start_time")
        if src and (not doc or doc.get("status") != "confirmed" or when != ctx.get("start_time")):
            raise SkipRun(f"{src.replace('_', ' ')} is no longer confirmed for this time")
        await _customer_send(lead, rule, ctx["template"], ctx.get("vars", {}), actions, run["id"])
        return actions
    trig = rule["trigger"]
    if trig == "referral_consented":
        upd = {"last_activity_at": now_iso()}
        if not lead.get("pipeline_stage") or lead["pipeline_stage"] in ("new_lead", "contact_required", "qualified"):
            upd["pipeline_stage"] = "vehicle_matched"
            actions.append("CRM stage → vehicle_matched")
        rep = None
        if not lead.get("assigned_user_id"):
            rep = await _pick_rep(lead["organization_id"], rule)
            if rep:
                upd["assigned_user_id"] = rep["id"]
                actions.append(f"assigned to {rep['email']}")
                await log_activity(lead["organization_id"], lead["id"], "lead_assigned", "automation", f"Auto-assigned to {rep['email']}")
        await db.leads.update_one({"id": lead["id"]}, {"$set": upd})
        lead.update(upd)
        ref = await db.referrals.find_one({"lead_id": lead["id"]})
        _, _, vars = await lead_context(lead)
        dg = await db.dealer_groups.find_one({"id": (ref or {}).get("dealer_group_id")}) if ref and ref.get("dealer_group_id") else None
        await notify(lead["organization_id"], "dealership", lead["organization_id"], "in_app", "lead_referred", {"lead_id": lead["id"]})
        if dg and dg.get("notification_email") and "email" in rule["channels"]:
            c = await send_communication(org_id=lead["organization_id"], channel="email", template="lead_referred_dealer",
                to=dg["notification_email"], vars=vars, lead_id=lead["id"], recipient_type="dealership",
                idempotency_key=f"{run['id']}:dealer", triggered_by="automation")
            actions.append(f"dealership email ({c['status']})")
        else:
            actions.append("dealership notified in-app (no dealer notification email configured)")
        if ref:
            await db.referrals.update_one({"id": ref["id"]}, {"$set": {"delivered_at": now_iso()},
                "$push": {"status_history": {"status": "delivered", "at": now_iso()}}})
            actions.append("referral delivery recorded")
        await _follow_up(lead, rule["params"].get("follow_up_hours", 24), "Contact newly referred customer", actions, (rep or {}).get("id"))
    elif trig == "lead_uncontacted":
        name = ctx.get("customer_name", "Customer")
        idle = ctx.get("idle_hours", 0)
        users = [u for u in [await db.users.find_one({"id": lead.get("assigned_user_id")})] if u]
        if idle >= rule["params"].get("escalate_after_hours", 48) or not users:
            users += await db.users.find({"organization_id": lead["organization_id"], "role": "dealership_manager", "status": {"$ne": "inactive"}}).to_list(20)
            actions.append("escalated to managers")
        await _staff_alert(lead, rule, users, f"{name}: not contacted for {idle}h", actions, run["id"])
        await _follow_up(lead, 0, "Overdue: contact this lead", actions)
    elif trig in ("appointment_confirmed", "test_drive_confirmed"):
        vars = {"when": (ctx.get("start_time") or "")[:16].replace("T", " "), "appointment_type": ctx.get("appointment_type", ""),
                "vehicle": ctx.get("vehicle") or ""}
        vars = {k: v for k, v in vars.items() if v}
        await _customer_send(lead, rule, rule["template"], vars, actions, run["id"])
        await _schedule_reminder(lead, rule, ctx.get("start_time"), vars, run["entity_id"], actions, ctx)
        if trig == "test_drive_confirmed" and lead.get("assigned_user_id"):
            rep = await db.users.find_one({"id": lead["assigned_user_id"]})
            if rep:
                await _staff_alert(lead, rule, [rep], f"{ctx.get('customer_name', 'Customer')}: test drive confirmed for {vars.get('when', '')}", actions, run["id"])
    elif trig == "customer_inactive":
        await _follow_up(lead, 0, f"Re-engage inactive customer ({ctx.get('idle_days')} days)", actions)
        if rule["params"].get("send_message"):
            await _customer_send(lead, rule, rule["template"], {}, actions, run["id"])
    return actions


async def _run(run: dict):
    rule = await db.automation_rules.find_one({"organization_id": run["organization_id"], "key": run["rule_key"]})
    if not rule or not rule.get("enabled"):
        await db.automation_runs.update_one({"id": run["id"]}, {"$set": {"status": "skipped", "error": "Rule disabled", "executed_at": now_iso()}})
        return
    await db.automation_runs.update_one({"id": run["id"]}, {"$set": {"status": "running"}, "$inc": {"attempts": 1}})
    try:
        actions = await _execute(clean(rule), run)
        await db.automation_runs.update_one({"id": run["id"]}, {"$set": {"status": "success", "actions": actions, "error": None, "executed_at": now_iso()}})
    except SkipRun as e:
        await db.automation_runs.update_one({"id": run["id"]}, {"$set": {"status": "skipped", "error": str(e), "executed_at": now_iso()}})
    except Exception as e:
        logger.exception("automation run failed")
        await db.automation_runs.update_one({"id": run["id"]}, {"$set": {"status": "failed", "error": str(e)[:500], "executed_at": now_iso()}})


async def fire(org_id: str, trigger: str, lead_id: str, entity_id: str, payload: dict = None):
    """Entry point for domain events. Idempotent per rule+entity; automation actions never re-fire triggers (no loops)."""
    await ensure_rules(org_id)
    for rule in await db.automation_rules.find({"organization_id": org_id, "trigger": trigger, "enabled": True}).to_list(20):
        key = f"{rule['key']}:{entity_id}"
        if await db.automation_runs.find_one({"idempotency_key": key}):
            continue
        delay = rule.get("delay_minutes") or 0
        run = {"id": new_id(), "organization_id": org_id, "rule_key": rule["key"], "kind": "trigger", "lead_id": lead_id,
               "entity_id": entity_id, "idempotency_key": key, "status": "scheduled" if delay else "pending",
               "run_at": (_now() + timedelta(minutes=delay)).isoformat(), "payload": payload or {}, "actions": [],
               "attempts": 0, "created_at": now_iso()}
        try:
            await db.automation_runs.insert_one(dict(run))
        except Exception:
            continue
        if not delay:
            await _run(run)


async def scan_conditions(org_id: str):
    await ensure_rules(org_id)
    rules = {r["key"]: r for r in await db.automation_rules.find({"organization_id": org_id, "enabled": True}).to_list(20)}
    now = _now()
    leads = await db.leads.find({"organization_id": org_id, "is_test": {"$ne": True},
                                 "pipeline_stage": {"$nin": ["sale_verified", "lost"]}}).to_list(5000)
    sellers = {s["id"]: s for s in await db.sellers.find({"id": {"$in": [l.get("seller_id") for l in leads]}},
                                                         {"id": 1, "first_name": 1, "last_name": 1}).to_list(None)}
    for lead in leads:
        last = _parse(lead.get("last_activity_at") or lead.get("created_at"))
        if not last:
            continue
        idle_h = int((now - last).total_seconds() // 3600)
        seller = sellers.get(lead.get("seller_id")) or {}
        name = (f"{seller.get('first_name') or ''} {seller.get('last_name') or ''}").strip() or "Customer"
        b = rules.get("uncontacted_lead")
        if b and lead.get("consent_status") == "granted" and idle_h >= b["params"].get("idle_hours", 24):
            stamp = lead.get("last_activity_at") or lead.get("created_at")
            esc = idle_h >= b["params"].get("escalate_after_hours", 48)
            await fire(org_id, "lead_uncontacted", lead["id"], f"{lead['id']}:{stamp}:{'esc' if esc else 'rep'}",
                       {"idle_hours": idle_h, "customer_name": name})
        e = rules.get("inactive_customer")
        if e and idle_h >= 24 * e["params"].get("inactive_days", 7):
            await fire(org_id, "customer_inactive", lead["id"], f"{lead['id']}:{lead.get('last_activity_at')}",
                       {"idle_days": idle_h // 24, "customer_name": name})


async def process_due(org_id: Optional[str] = None):
    q = {"status": "scheduled", "run_at": {"$lte": now_iso()}}
    if org_id:
        q["organization_id"] = org_id
    due = await db.automation_runs.find(q).to_list(500)
    for run in due:
        res = await db.automation_runs.update_one({"id": run["id"], "status": "scheduled"}, {"$set": {"status": "pending"}})
        if res.modified_count:
            await _run(clean(run))
    orgs = [org_id] if org_id else [o["id"] for o in await db.organizations.find({}, {"id": 1}).to_list(1000)]
    for o in orgs:
        await scan_conditions(o)
    return len(due)


# ---------------- admin API ----------------
VIEW = MANAGE + ("platform_support",)


@automation_router.get("/automations")
async def list_rules(user: dict = Depends(require_roles(*VIEW))):
    await ensure_rules(user["organization_id"])
    rules = [clean(r) for r in await db.automation_rules.find({"organization_id": user["organization_id"]}).sort("name", 1).to_list(20)]
    for r in rules:
        r["stats"] = {s: await db.automation_runs.count_documents({"organization_id": user["organization_id"], "rule_key": r["key"], "status": s})
                      for s in ("success", "failed", "scheduled")}
    return rules


class RulePatch(BaseModel):
    enabled: Optional[bool] = None
    delay_minutes: Optional[int] = None
    channels: Optional[list] = None
    template: Optional[str] = None
    language: Optional[str] = None
    assign_to_user_id: Optional[str] = None
    params: Optional[dict] = None


@automation_router.patch("/automations/{key}")
async def update_rule(key: str, body: RulePatch, user: dict = Depends(require_roles(*MANAGE))):
    rule = await db.automation_rules.find_one({"organization_id": user["organization_id"], "key": key})
    if not rule:
        raise HTTPException(status_code=404, detail="Automation not found")
    upd = body.model_dump(exclude_unset=True)
    if "channels" in upd and (not upd["channels"] or any(c not in ("email", "sms") for c in upd["channels"])):
        raise HTTPException(status_code=400, detail="Channels must be email and/or sms")
    if "language" in upd and upd["language"] not in ("customer", "en", "fr"):
        raise HTTPException(status_code=400, detail="Invalid language")
    if "delay_minutes" in upd and not (0 <= upd["delay_minutes"] <= 60 * 24 * 30):
        raise HTTPException(status_code=400, detail="Delay must be between 0 and 43200 minutes")
    if "template" in upd:
        from templates import TEMPLATES
        if upd["template"] not in TEMPLATES:
            raise HTTPException(status_code=400, detail="Unknown template")
    if upd.get("assign_to_user_id") and not await db.users.find_one({"id": upd["assign_to_user_id"], "organization_id": user["organization_id"]}):
        raise HTTPException(status_code=400, detail="Assignee not found")
    if "params" in upd:
        upd["params"] = {**rule.get("params", {}), **{k: v for k, v in upd["params"].items() if k in rule.get("params", {})}}
    upd["updated_at"] = now_iso()
    await db.automation_rules.update_one({"id": rule["id"]}, {"$set": upd})
    await audit(user["organization_id"], "user", user["id"], "automation_rule", rule["id"], "updated", None, upd)
    return clean(await db.automation_rules.find_one({"id": rule["id"]}))


@automation_router.get("/automations/runs")
async def list_runs(user: dict = Depends(require_roles(*VIEW)), status: Optional[str] = None, rule_key: Optional[str] = None):
    q = {"organization_id": user["organization_id"]}
    if status:
        q["status"] = status
    if rule_key:
        q["rule_key"] = rule_key
    return [clean(r) for r in await db.automation_runs.find(q).sort("created_at", -1).to_list(300)]


@automation_router.post("/automations/runs/{run_id}/retry")
async def retry_run(run_id: str, user: dict = Depends(require_roles(*MANAGE))):
    run = await db.automation_runs.find_one({"id": run_id, "organization_id": user["organization_id"]})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["status"] != "failed":
        raise HTTPException(status_code=400, detail="Only failed runs can be retried")
    await _run(clean(run))
    return clean(await db.automation_runs.find_one({"id": run_id}))


@automation_router.post("/automations/process")
async def process_now(user: dict = Depends(require_roles(*MANAGE))):
    n = await process_due(user["organization_id"])
    return {"success": True, "due_processed": n}


@automation_router.post("/cron/automations")
async def cron_automations(authorization: Optional[str] = Header(default=None)):
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not secret or not token or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    asyncio.create_task(process_due())
    return {"accepted": True}
