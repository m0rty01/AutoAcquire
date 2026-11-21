from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from db import db
from auth import require_roles
from comms import email_configured, sms_configured

health_router = APIRouter(prefix="/api", tags=["health"])


@health_router.get("/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok"}
    except Exception:
        return {"status": "degraded", "database": "unreachable"}


@health_router.get("/system/health")
async def system_health(user: dict = Depends(require_roles("platform_admin", "platform_support", "dealership_admin"))):
    org = user["organization_id"]
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    comm = {s: await db.communications.count_documents({"organization_id": org, "created_at": {"$gte": since}, "status": s})
            for s in ("sent", "delivered", "failed", "bounced", "undelivered", "not_configured", "blocked")}
    runs = {s: await db.automation_runs.count_documents({"organization_id": org, "status": s}) for s in ("failed", "scheduled")}
    last_run = await db.automation_runs.find_one({"organization_id": org, "executed_at": {"$ne": None}}, sort=[("executed_at", -1)])
    imports = await db.inventory_imports.find({"organization_id": org}).sort("created_at", -1).to_list(5)
    integ = await db.partner_integrations.find({"organization_id": org, "last_errors.0": {"$exists": True}}).to_list(10)
    db_ok = True
    try:
        await db.command("ping")
    except Exception:
        db_ok = False
    checks = [
        {"name": "Database", "ok": db_ok, "detail": "reachable" if db_ok else "unreachable"},
        {"name": "Email provider (Resend)", "ok": email_configured(), "detail": "connected" if email_configured() else "pending credentials"},
        {"name": "SMS provider (Twilio)", "ok": sms_configured(), "detail": "connected" if sms_configured() else "pending credentials"},
        {"name": "Email/SMS delivery (24h)", "ok": comm["failed"] + comm["bounced"] + comm["undelivered"] == 0,
         "detail": f"{comm['failed']} failed · {comm['bounced']} bounced · {comm['undelivered']} undelivered · {comm['not_configured']} not configured"},
        {"name": "Background jobs", "ok": runs["failed"] == 0,
         "detail": f"{runs['failed']} failed runs · {runs['scheduled']} scheduled · last executed {(last_run or {}).get('executed_at', 'never')}"},
        {"name": "Inventory sync", "ok": not any(i.get("status") == "failed" for i in imports) and not integ,
         "detail": f"{len(integ)} partner integration(s) with errors · last import {(imports[0].get('created_at') if imports else 'never')}"},
    ]
    return {"checks": checks, "communications_24h": comm, "automation": runs}
