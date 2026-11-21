import os
import re
import hmac
import base64
import hashlib
import logging
import time
from html import escape
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from db import db, new_id, now_iso, clean, audit
from auth import get_current_user
from crm import scoped_lead, log_activity
from templates import TEMPLATES, STAFF_SENDABLE

logger = logging.getLogger("comms")
comms_router = APIRouter(prefix="/api", tags=["communications"])

FINAL = ("delivered", "bounced", "failed", "undelivered", "blocked")
_RANK = {"not_configured": 0, "queued": 1, "accepted": 1, "sending": 2, "sent": 3, "delivered": 4,
         "bounced": 5, "failed": 5, "undelivered": 5}


def email_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY") and os.environ.get("EMAIL_FROM"))


def sms_configured() -> bool:
    return all(os.environ.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"))


def _base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")


def render(template: str, language: str, vars: dict, link: Optional[str] = None):
    t = TEMPLATES[template]
    loc = t.get(language) or t["en"]
    safe = {k: escape(str(v if v is not None else "")) for k, v in vars.items()}

    def fill(s):
        return re.sub(r"\{(\w+)\}", lambda m: safe.get(m.group(1), ""), s)
    subject = re.sub(r"\{(\w+)\}", lambda m: str(vars.get(m.group(1)) or ""), loc["subject"])
    text = fill(loc["body"])
    btn = ""
    if link and link.startswith("https://"):
        btn = (f'<p style="margin:24px 0"><a href="{escape(link)}" style="background:#3b82f6;color:#fff;'
               f'padding:12px 20px;border-radius:4px;text-decoration:none;font-weight:600">{escape(loc.get("link_label", "Open"))}</a></p>')
    footer = ("Sent by AutoNova AI. We never ask for your password or payment details by email."
              if language != "fr" else "Envoyé par AutoNova AI. Nous ne demandons jamais votre mot de passe ni vos informations de paiement par courriel.")
    html = (f'<table role="presentation" width="100%" style="font-family:Arial,sans-serif;color:#111"><tr><td style="padding:24px">'
            f'<p style="font-size:15px;line-height:1.5">{text}</p>{btn}'
            f'<p style="font-size:12px;color:#888;margin-top:32px">{footer}</p></td></tr></table>')
    sms = re.sub(r"\{(\w+)\}", lambda m: str(vars.get(m.group(1)) or ""), loc.get("sms", loc["body"]))
    return subject, html, sms


async def _send_resend(to: str, subject: str, html: str, idem: str):
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post("https://api.resend.com/emails",
                         headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Idempotency-Key": idem[:256]},
                         json={"from": os.environ["EMAIL_FROM"], "to": [to], "subject": subject, "html": html,
                               **({"reply_to": os.environ["EMAIL_REPLY_TO"]} if os.environ.get("EMAIL_REPLY_TO") else {})})
    if r.status_code >= 400:
        raise RuntimeError(f"Resend {r.status_code}: {r.text[:300]}")
    return r.json().get("id"), "sent"


async def _send_twilio(to: str, body: str):
    sid = os.environ["TWILIO_ACCOUNT_SID"]
    data = {"To": to, "From": os.environ["TWILIO_FROM_NUMBER"], "Body": body}
    if _base_url().startswith("https://"):
        data["StatusCallback"] = f"{_base_url()}/api/webhooks/twilio/status"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                         auth=(sid, os.environ["TWILIO_AUTH_TOKEN"]), data=data)
    if r.status_code >= 400:
        raise RuntimeError(f"Twilio {r.status_code}: {r.text[:300]}")
    j = r.json()
    return j.get("sid"), j.get("status", "queued")


def _permission_block(seller: dict, channel: str, category: str) -> Optional[str]:
    if category == "system":
        return None
    if channel == "sms" and seller.get("sms_opted_out"):
        return "Customer opted out of SMS (STOP)"
    if channel == "email" and seller.get("email_opted_out"):
        return "Customer unsubscribed from email"
    if not (seller.get("communication_permissions") or {}).get(category):
        return f"No recorded {category} communication permission"
    return None


async def dispatch(comm: dict) -> dict:
    """Attempt provider delivery for a stored communication record and persist the outcome."""
    upd = {"updated_at": now_iso(), "attempts": comm.get("attempts", 0) + 1, "last_attempt_at": now_iso()}
    configured = email_configured() if comm["channel"] == "email" else sms_configured()
    if not configured:
        upd.update(status="not_configured", error=f"{'Email (Resend)' if comm['channel'] == 'email' else 'SMS (Twilio)'} provider credentials are not configured")
    else:
        try:
            if comm["channel"] == "email":
                pid, st = await _send_resend(comm["to"], comm["subject"], comm["html"], comm["id"])
            else:
                pid, st = await _send_twilio(comm["to"], comm["body"])
            upd.update(status=st, provider_message_id=pid, sent_at=now_iso(), error=None)
        except Exception as e:  # provider/network failure is recorded, never silently dropped
            logger.warning(f"send failed {comm['id']}: {e}")
            upd.update(status="failed", error=str(e)[:500])
    await db.communications.update_one({"id": comm["id"]}, {"$set": upd,
        "$push": {"events": {"status": upd["status"], "at": now_iso(), "source": "dispatch", "error": upd.get("error")}}})
    return {**comm, **upd}


async def send_communication(*, org_id: str, channel: str, template: str, to: Optional[str], language: str = "en",
                             vars: dict = None, lead_id: Optional[str] = None, seller: Optional[dict] = None,
                             idempotency_key: Optional[str] = None, triggered_by: str = "system",
                             link: Optional[str] = None, recipient_type: str = "customer") -> dict:
    if channel not in ("email", "sms") or template not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown channel or template")
    if idempotency_key:
        dup = await db.communications.find_one({"idempotency_key": idempotency_key,
                                                "status": {"$nin": ["failed", "not_configured"]}})
        if dup:
            return {**clean(dup), "duplicate": True}
    language = language if language in ("en", "fr") else "en"
    category = TEMPLATES[template]["category"]
    subject, html, sms = render(template, language, vars or {}, link)
    comm = {"id": new_id(), "organization_id": org_id, "lead_id": lead_id, "direction": "outbound", "channel": channel,
            "template": template, "category": category, "language": language, "recipient_type": recipient_type,
            "to": to, "subject": subject if channel == "email" else None, "html": html if channel == "email" else None,
            "body": sms if channel == "sms" else None, "status": "queued", "provider_message_id": None,
            "idempotency_key": idempotency_key, "triggered_by": triggered_by, "attempts": 0, "events": [],
            "created_at": now_iso(), "updated_at": now_iso()}
    block = None if to else f"Recipient has no {'email address' if channel == 'email' else 'phone number'}"
    if not block and seller is not None:
        block = _permission_block(seller, channel, category)
    if block:
        comm.update(status="blocked", error=block)
        comm["events"] = [{"status": "blocked", "at": now_iso(), "source": "policy", "error": block}]
        await db.communications.insert_one(dict(comm))
        return comm
    await db.communications.insert_one(dict(comm))
    out = await dispatch(comm)
    if lead_id:
        await log_activity(org_id, lead_id, f"{channel}_{'sent' if out['status'] not in ('failed', 'not_configured') else out['status']}",
                           triggered_by, f"{template.replace('_', ' ')} → {to} ({out['status']})")
    return out


async def lead_context(lead: dict) -> tuple:
    seller = await db.sellers.find_one({"id": lead["seller_id"]}) or {}
    conv = await db.conversations.find_one({"lead_id": lead["id"]}) or {}
    org = await db.organizations.find_one({"id": lead["organization_id"]}) or {}
    ref = await db.referrals.find_one({"lead_id": lead["id"]}) or {}
    dg = await db.dealer_groups.find_one({"id": ref.get("dealer_group_id")}) if ref.get("dealer_group_id") else None
    lang = seller.get("preferred_language") or conv.get("language") or "en"
    vars = {"name": seller.get("first_name") or ("client" if lang == "fr" else "there"),
            "dealer": (dg or {}).get("name") or org.get("name", "the dealership"), "vehicle": ref.get("vehicle_label") or ""}
    return clean(seller), lang, vars


# ---------------- staff API ----------------
@comms_router.get("/communications/config")
async def comms_config(user: dict = Depends(get_current_user)):
    b = _base_url()
    return {"email": {"provider": "Resend", "configured": email_configured(), "from": os.environ.get("EMAIL_FROM"),
                      "webhook_url": f"{b}/api/webhooks/resend", "webhook_signing": bool(os.environ.get("RESEND_WEBHOOK_SECRET"))},
            "sms": {"provider": "Twilio", "configured": sms_configured(), "from": os.environ.get("TWILIO_FROM_NUMBER"),
                    "status_webhook_url": f"{b}/api/webhooks/twilio/status", "inbound_webhook_url": f"{b}/api/webhooks/twilio/inbound"},
            "templates": [{"key": k, "category": v["category"], "audience": v["audience"]} for k, v in TEMPLATES.items()],
            "staff_sendable": STAFF_SENDABLE}


@comms_router.get("/communications")
async def list_comms(user: dict = Depends(get_current_user), channel: Optional[str] = None, status: Optional[str] = None,
                     direction: Optional[str] = None, lead_id: Optional[str] = None, limit: int = 300):
    q = {"organization_id": user["organization_id"]}
    for k, v in (("channel", channel), ("status", status), ("direction", direction), ("lead_id", lead_id)):
        if v:
            q[k] = v
    if user["role"] == "dealership_representative":
        mine = [l["id"] for l in await db.leads.find({"organization_id": user["organization_id"], "assigned_user_id": user["id"]}, {"id": 1}).to_list(5000)]
        q["lead_id"] = {"$in": [x for x in mine if not lead_id or x == lead_id]}
    rows = await db.communications.find(q, {"html": 0}).sort("created_at", -1).to_list(min(limit, 1000))
    leads = {l["id"]: l for l in await db.leads.find({"id": {"$in": list({r.get("lead_id") for r in rows if r.get("lead_id")})}}).to_list(None)}
    sellers = {s["id"]: s for s in await db.sellers.find({"id": {"$in": [l["seller_id"] for l in leads.values()]}}).to_list(None)}
    users = {u["id"]: u for u in await db.users.find({"organization_id": user["organization_id"]}).to_list(500)}
    out = []
    for r in rows:
        clean(r)
        lead = leads.get(r.get("lead_id")) or {}
        s = sellers.get(lead.get("seller_id")) or {}
        rep = users.get(lead.get("assigned_user_id")) or {}
        r["customer_name"] = (f"{s.get('first_name') or ''} {s.get('last_name') or ''}").strip() or None
        r["representative"] = (f"{rep.get('first_name', '')} {rep.get('last_name', '')}").strip() or None
        out.append(r)
    summary = {}
    for r in out:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"items": out, "summary": summary}


class StaffSendBody(BaseModel):
    channel: str
    template: str
    language: Optional[str] = None


@comms_router.post("/leads/{lead_id}/communications")
async def staff_send(lead_id: str, body: StaffSendBody, user: dict = Depends(get_current_user)):
    lead = await scoped_lead(lead_id, user)
    if user["role"] == "platform_support":
        raise HTTPException(status_code=403, detail="Read-only role")
    if body.template not in STAFF_SENDABLE:
        raise HTTPException(status_code=400, detail="This template cannot be sent manually")
    seller, lang, vars = await lead_context(lead)
    appt = await db.appointments.find_one({"lead_id": lead_id, "status": {"$in": ["confirmed", "requested"]}}, sort=[("start_time", -1)])
    if appt:
        vars["when"] = appt["start_time"][:16].replace("T", " ")
        vars["appointment_type"] = appt.get("appointment_type", "").replace("_", " ")
    to = seller.get("email") if body.channel == "email" else seller.get("phone")
    out = await send_communication(org_id=lead["organization_id"], channel=body.channel, template=body.template, to=to,
                                   language=body.language or lang, vars=vars, lead_id=lead_id, seller=seller,
                                   triggered_by=user.get("email", user["id"]))
    await audit(lead["organization_id"], "user", user["id"], "communication", out["id"], "staff_send", None,
                {"channel": body.channel, "template": body.template, "status": out["status"]})
    out.pop("html", None)
    return out


@comms_router.post("/communications/{comm_id}/retry")
async def retry_comm(comm_id: str, user: dict = Depends(get_current_user)):
    comm = await db.communications.find_one({"id": comm_id, "organization_id": user["organization_id"]})
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    if comm.get("lead_id"):
        await scoped_lead(comm["lead_id"], user)
    if comm["status"] not in ("failed", "not_configured"):
        raise HTTPException(status_code=400, detail=f"Cannot retry a message that is {comm['status']}")
    out = await dispatch(clean(comm))
    out.pop("html", None)
    return out


# ---------------- provider webhooks ----------------
def _verify_svix(secret: str, msg_id: str, ts: str, body: bytes, sig_header: str) -> bool:
    try:
        if abs(time.time() - int(ts)) > 300:
            return False
        key = base64.b64decode(secret.split("_", 1)[1] if secret.startswith("whsec_") else secret)
        expected = base64.b64encode(hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
        return any(hmac.compare_digest(expected, s.split(",", 1)[1]) for s in sig_header.split() if "," in s)
    except Exception:
        return False


async def _apply_status(provider_id: str, status: str, source: str, detail=None):
    comm = await db.communications.find_one({"provider_message_id": provider_id})
    if not comm:
        return False
    if (comm.get("status") in FINAL and status not in ("bounced", "failed")) or _RANK.get(status, 0) < _RANK.get(comm.get("status"), 0):
        status = comm["status"]  # never regress (out-of-order webhooks)
    await db.communications.update_one({"id": comm["id"]}, {"$set": {"status": status, "updated_at": now_iso(),
        **({"delivered_at": now_iso()} if status == "delivered" else {})},
        "$push": {"events": {"status": status, "at": now_iso(), "source": source, "detail": detail}}})
    return True


@comms_router.post("/webhooks/resend")
async def resend_webhook(request: Request, svix_id: str = Header(default=""), svix_timestamp: str = Header(default=""),
                         svix_signature: str = Header(default="")):
    body = await request.body()
    secret = os.environ.get("RESEND_WEBHOOK_SECRET")
    if not secret or not _verify_svix(secret, svix_id, svix_timestamp, body, svix_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if await db.webhook_events.find_one({"provider": "resend", "event_id": svix_id}):
        return {"ok": True, "duplicate": True}
    await db.webhook_events.insert_one({"id": new_id(), "provider": "resend", "event_id": svix_id, "created_at": now_iso()})
    evt = await request.json()
    mapping = {"email.sent": "sent", "email.delivered": "delivered", "email.bounced": "bounced",
               "email.failed": "failed", "email.complained": "failed", "email.delivery_delayed": "sent"}
    st = mapping.get(evt.get("type"))
    if st:
        await _apply_status((evt.get("data") or {}).get("email_id"), st, "resend_webhook", evt.get("type"))
    return {"ok": True}


def _verify_twilio(url: str, params: dict, signature: str) -> bool:
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not token or not signature:
        return False
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    expected = base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)


async def _twilio_form(request: Request, path: str, signature: str) -> dict:
    form = dict(await request.form())
    if not _verify_twilio(f"{_base_url()}{path}", form, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    return form


@comms_router.post("/webhooks/twilio/status")
async def twilio_status(request: Request, x_twilio_signature: str = Header(default="")):
    form = await _twilio_form(request, "/api/webhooks/twilio/status", x_twilio_signature)
    st = form.get("MessageStatus")
    if st in ("queued", "accepted", "sending", "sent", "delivered", "failed", "undelivered"):
        await _apply_status(form.get("MessageSid"), st, "twilio_webhook", form.get("ErrorCode"))
    return {"ok": True}


_STOP = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit", "arret", "arrêt"}
_START = {"start", "unstop", "yes"}


@comms_router.post("/webhooks/twilio/inbound")
async def twilio_inbound(request: Request, x_twilio_signature: str = Header(default="")):
    form = await _twilio_form(request, "/api/webhooks/twilio/inbound", x_twilio_signature)
    if await db.communications.find_one({"provider_message_id": form.get("MessageSid")}):
        return PlainTextResponse("<Response/>", media_type="application/xml")
    frm, text = form.get("From", ""), (form.get("Body") or "").strip()
    seller = await db.sellers.find_one({"phone": frm})
    lead = await db.leads.find_one({"seller_id": seller["id"]}, sort=[("created_at", -1)]) if seller else None
    kw = text.lower()
    if seller and kw in _STOP:
        await db.sellers.update_one({"id": seller["id"]}, {"$set": {"sms_opted_out": True, "sms_opted_out_at": now_iso()}})
    elif seller and kw in _START:
        await db.sellers.update_one({"id": seller["id"]}, {"$set": {"sms_opted_out": False}})
    org_id = (lead or seller or {}).get("organization_id")
    await db.communications.insert_one({"id": new_id(), "organization_id": org_id, "lead_id": (lead or {}).get("id"),
        "direction": "inbound", "channel": "sms", "template": None, "category": "reply", "to": form.get("To"),
        "from": frm, "body": text, "status": "received", "provider_message_id": form.get("MessageSid"),
        "events": [], "created_at": now_iso(), "updated_at": now_iso()})
    if lead:
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"last_activity_at": now_iso(), "last_customer_reply_at": now_iso()}})
        await log_activity(org_id, lead["id"], "sms_received", "customer", text[:200])
    return PlainTextResponse("<Response/>", media_type="application/xml")
