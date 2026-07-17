import logging
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import io, csv, os

from db import db, new_id, now_iso, clean, audit, emit_event, notify
from auth import auth_router, get_current_user, require_roles
from ai_engine import run_orchestrator, FALLBACK_MESSAGE, MODEL_PROVIDER, MODEL_NAME, PROMPT_VERSION
from engine import run_qualification, compute_score, match_inventory, generate_slots, estimate_financing, SCORE_VERSION
from seed import seed_demo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autoacquire")

app = FastAPI(title="AutoAcquire AI")
api = APIRouter(prefix="/api")

REQUIRED_FOR_APPOINTMENT = ["vehicle.make", "vehicle.model", "vehicle.year", "vehicle.mileage", "seller.phone"]


def _org(user):
    return user["organization_id"]


async def build_state(lead: dict) -> dict:
    seller = await db.sellers.find_one({"id": lead["seller_id"]}) or {}
    vehicle = await db.seller_vehicles.find_one({"lead_id": lead["id"]}) or {}
    pref = await db.inventory_preferences.find_one({"lead_id": lead["id"]}) or {}
    return {
        "seller": {k: seller.get(k) for k in ["first_name", "last_name", "phone", "email",
                    "postal_zip_code", "city", "province_state", "preferred_contact_method"]},
        "vehicle": {k: vehicle.get(k) for k in ["vin", "year", "make", "model", "trim", "mileage",
                    "mileage_unit", "exterior_colour", "body_type", "fuel_type", "transmission",
                    "drivetrain", "condition", "ownership_status", "lien_status",
                    "estimated_loan_balance", "asking_price", "accident_history"]},
        "intent": {"primary_intent": lead.get("primary_intent"), "timeline": lead.get("timeline"),
                   "appointment_ready": lead.get("appointment_ready", False)},
        "preference": {k: pref.get(k) for k in ["min_price", "max_price", "preferred_makes",
                       "preferred_models", "preferred_body_types", "preferred_drivetrains",
                       "minimum_seating", "maximum_mileage"]},
    }


def _missing_fields(state: dict) -> list:
    out = []
    for path in REQUIRED_FOR_APPOINTMENT:
        section, field = path.split(".")
        if not state.get(section, {}).get(field):
            out.append(path)
    return out


async def apply_extracted(lead: dict, extracted: list, message_id: str):
    for item in extracted or []:
        field = item.get("field", "")
        value = item.get("value")
        conf = item.get("confidence", 0.5)
        if "." not in field or value in (None, ""):
            continue
        section, name = field.split(".", 1)
        await db.extracted_fields.insert_one({"id": new_id(), "organization_id": lead["organization_id"],
            "lead_id": lead["id"], "message_id": message_id, "field_name": field,
            "extracted_value": value, "confidence": conf, "source": "ai", "confirmed": False,
            "overridden": False, "created_at": now_iso()})
        if section == "seller":
            await db.sellers.update_one({"id": lead["seller_id"]},
                                        {"$set": {name: value, "updated_at": now_iso()}})
        elif section == "vehicle":
            await db.seller_vehicles.update_one({"lead_id": lead["id"]},
                {"$set": {name: value, "updated_at": now_iso()},
                 "$setOnInsert": {"id": new_id(), "organization_id": lead["organization_id"],
                                  "lead_id": lead["id"], "seller_id": lead["seller_id"], "created_at": now_iso()}},
                upsert=True)
        elif section == "preference":
            await db.inventory_preferences.update_one({"lead_id": lead["id"]},
                {"$set": {name: value, "updated_at": now_iso()},
                 "$setOnInsert": {"id": new_id(), "organization_id": lead["organization_id"],
                                  "lead_id": lead["id"], "created_at": now_iso()}}, upsert=True)


async def recalc_and_store_score(lead: dict):
    state = await build_state(lead)
    rules = await db.qualification_rules.find({"organization_id": lead["organization_id"], "active": True}).to_list(200)
    for r in rules:
        clean(r)
    qual = run_qualification(state, rules)
    score = compute_score(state, qual["rule_adjustment"])
    await db.lead_scores.insert_one({"id": new_id(), "organization_id": lead["organization_id"],
        "lead_id": lead["id"], **score, "applied_rules": qual["applied_rules"], "created_at": now_iso()})
    await db.leads.update_one({"id": lead["id"]}, {"$set": {"score": score["total_score"],
        "score_band": score["score_band"], "score_version": SCORE_VERSION,
        "qualification_status": qual["qualification_status"],
        "requires_human_review": qual["requires_human_review"],
        "last_activity_at": now_iso(), "updated_at": now_iso()}})
    return score, qual


async def _conv_messages(conv_id: str):
    msgs = await db.messages.find({"conversation_id": conv_id}).sort("created_at", 1).to_list(500)
    return [clean(m) for m in msgs]


async def _run_match(lead: dict):
    pref = await db.inventory_preferences.find_one({"lead_id": lead["id"]}) or {}
    inv = await db.inventory_vehicles.find({"organization_id": lead["organization_id"], "status": "available"}).to_list(1000)
    matches = match_inventory(clean(pref), [clean(v) for v in inv])
    await db.inventory_matches.delete_many({"lead_id": lead["id"]})
    for m in matches:
        await db.inventory_matches.insert_one({"id": new_id(), "organization_id": lead["organization_id"],
            "lead_id": lead["id"], "inventory_vehicle_id": m["inventory_vehicle"]["id"],
            "match_score": m["match_score"], "ranking": m["ranking"], "match_reasons": m["match_reasons"],
            "conflicts": m["conflicts"], "generated_at": now_iso()})
    return matches


# ---------------- public conversation ----------------
class StartConvBody(BaseModel):
    consent: bool = True


class MessageBody(BaseModel):
    content: str


async def _get_dealer_by_slug(slug: str):
    org = await db.organizations.find_one({"slug": slug})
    if not org:
        raise HTTPException(status_code=404, detail="Dealership not found")
    return org


@api.get("/public/{slug}")
async def public_dealer(slug: str):
    org = await _get_dealer_by_slug(slug)
    loc = await db.dealership_locations.find_one({"organization_id": org["id"]})
    return {"organization": {"name": org["name"], "slug": org["slug"]},
            "location": clean(loc) if loc else None}


@api.post("/public/{slug}/conversations")
async def start_conversation(slug: str, body: StartConvBody):
    org = await _get_dealer_by_slug(slug)
    loc = await db.dealership_locations.find_one({"organization_id": org["id"]})
    seller_id = new_id()
    await db.sellers.insert_one({"id": seller_id, "organization_id": org["id"], "first_name": None,
        "last_name": None, "email": None, "phone": None, "preferred_contact_method": None,
        "consent_status": "granted" if body.consent else "declined", "consent_timestamp": now_iso(),
        "marketing_consent": False, "created_at": now_iso(), "updated_at": now_iso()})
    lead_id = new_id()
    await db.leads.insert_one({"id": lead_id, "organization_id": org["id"],
        "dealership_location_id": loc["id"] if loc else None, "seller_id": seller_id,
        "assigned_user_id": None, "source": "web_conversation", "status": "new",
        "qualification_status": "insufficient_information", "conversation_mode": "ai_active",
        "primary_intent": None, "intent_confidence": None, "timeline": None, "appointment_ready": False,
        "score": 0, "score_band": "low", "score_version": SCORE_VERSION, "requires_human_review": False,
        "recommended_next_action": "ask_question", "is_test": False, "last_activity_at": now_iso(),
        "created_at": now_iso(), "updated_at": now_iso()})
    conv_id = new_id()
    await db.conversations.insert_one({"id": conv_id, "organization_id": org["id"], "lead_id": lead_id,
        "channel": "web", "status": "active", "current_stage": "intent_discovery", "rolling_summary": "",
        "ai_active": True, "started_at": now_iso(), "created_at": now_iso(), "updated_at": now_iso()})
    greeting = (f"Hi, I'm {org['name']}'s virtual vehicle assistant (an AI). I can ask a few questions "
                "about your vehicle and help arrange an appraisal or trade-in appointment. Are you looking "
                "to sell your vehicle, trade it in, or explore your options?")
    await db.messages.insert_one({"id": new_id(), "organization_id": org["id"], "conversation_id": conv_id,
        "sender_type": "ai", "content": greeting, "delivery_status": "delivered",
        "model_provider": MODEL_PROVIDER, "model_name": MODEL_NAME, "prompt_version": PROMPT_VERSION,
        "created_at": now_iso()})
    await emit_event(org["id"], "conversation.started", "conversation", conv_id)
    return {"conversation_id": conv_id, "lead_id": lead_id, "messages": await _conv_messages(conv_id)}


@api.get("/public/{slug}/conversations/{conv_id}")
async def get_public_conversation(slug: str, conv_id: str):
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": clean(conv), "messages": await _conv_messages(conv_id)}


@api.post("/public/{slug}/conversations/{conv_id}/messages")
async def post_public_message(slug: str, conv_id: str, body: MessageBody):
    org = await _get_dealer_by_slug(slug)
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = await db.leads.find_one({"id": conv["lead_id"]})

    user_msg_id = new_id()
    await db.messages.insert_one({"id": user_msg_id, "organization_id": org["id"], "conversation_id": conv_id,
        "sender_type": "seller", "content": body.content, "delivery_status": "delivered", "created_at": now_iso()})
    await emit_event(org["id"], "message.received", "message", user_msg_id)

    if not conv.get("ai_active", True):
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"last_activity_at": now_iso()}})
        return {"messages": await _conv_messages(conv_id), "ai_active": False}

    state = await build_state(lead)
    recent = await db.messages.find({"conversation_id": conv_id}).sort("created_at", 1).to_list(50)
    policies = org.get("ai_policies") or ["Never provide a final vehicle value",
                                          "Request a phone number before confirming an appointment"]
    result = await run_orchestrator(dealer_name=org["name"], policies=policies,
        stage=conv["current_stage"], state=state, summary=conv.get("rolling_summary", ""),
        missing=_missing_fields(state), recent_messages=[clean(m) for m in recent], seller_message=body.content)

    if not result["valid"]:
        await db.messages.insert_one({"id": new_id(), "organization_id": org["id"], "conversation_id": conv_id,
            "sender_type": "ai", "content": FALLBACK_MESSAGE, "delivery_status": "delivered",
            "model_provider": MODEL_PROVIDER, "model_name": MODEL_NAME, "prompt_version": PROMPT_VERSION,
            "created_at": now_iso()})
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"requires_human_review": True,
            "status": "needs_review", "last_activity_at": now_iso()}})
        await emit_event(org["id"], "workflow.failed", "conversation", conv_id, {"reason": "ai_output_invalid"})
        await notify(org["id"], "dealership", org["id"], "in_app", "ai_failure", {"lead_id": lead["id"]})
        return {"messages": await _conv_messages(conv_id), "ai_active": True}

    data = result["data"]
    await apply_extracted(lead, data.get("extractedFields"), user_msg_id)

    interp = data.get("sellerMessageInterpretation") or {}
    lead_updates = {"last_activity_at": now_iso(), "updated_at": now_iso()}
    if interp.get("intent") and interp["intent"] != "unclear":
        lead_updates["primary_intent"] = interp["intent"]
        lead_updates["intent_confidence"] = interp.get("confidence")
    if data.get("timeline") and data["timeline"] != "unknown":
        lead_updates["timeline"] = data["timeline"]
    next_action = data.get("nextAction")
    lead_updates["recommended_next_action"] = next_action
    if next_action == "offer_appointment":
        lead_updates["appointment_ready"] = True
    await db.leads.update_one({"id": lead["id"]}, {"$set": lead_updates})
    lead = await db.leads.find_one({"id": lead["id"]})

    await db.messages.insert_one({"id": new_id(), "organization_id": org["id"], "conversation_id": conv_id,
        "sender_type": "ai", "content": data["responseMessage"], "delivery_status": "delivered",
        "structured_payload": data, "model_provider": MODEL_PROVIDER, "model_name": MODEL_NAME,
        "prompt_version": PROMPT_VERSION, "created_at": now_iso()})

    score, qual = await recalc_and_store_score(lead)
    if next_action in ("run_inventory_match", "offer_appointment"):
        await _run_match(lead)

    status_map = {"offer_appointment": "appointment_offered", "request_human": "human_takeover",
                  "run_qualification": "ai_qualifying"}
    new_status = status_map.get(next_action)
    if data.get("requiresHumanReview"):
        new_status = "needs_review"
    if new_status:
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"status": new_status}})

    stage_map = {"request_contact_information": "seller_identification",
                 "run_inventory_match": "inventory_matching", "offer_appointment": "appointment_booking",
                 "request_human": "human_review", "end_conversation": "closed"}
    if next_action in stage_map:
        await db.conversations.update_one({"id": conv_id}, {"$set": {"current_stage": stage_map[next_action],
            "updated_at": now_iso()}})

    if score["score_band"] == "hot":
        await notify(org["id"], "dealership", org["id"], "in_app", "hot_lead",
                     {"lead_id": lead["id"], "score": score["total_score"]})

    resp = {"messages": await _conv_messages(conv_id), "ai_active": True, "next_action": next_action}
    if next_action == "offer_appointment":
        resp["show_appointments"] = True
    return resp


@api.get("/public/{slug}/conversations/{conv_id}/financing-estimate")
async def public_financing(slug: str, conv_id: str):
    org = await _get_dealer_by_slug(slug)
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = await db.leads.find_one({"id": conv["lead_id"]})
    vehicle = await db.seller_vehicles.find_one({"lead_id": lead["id"]}) or {}
    pref = await db.inventory_preferences.find_one({"lead_id": lead["id"]}) or {}
    # replacement price = best matched inventory price, else preference max_price
    match = await db.inventory_matches.find({"lead_id": lead["id"]}).sort("ranking", 1).to_list(1)
    replacement_price = None
    matched_vehicle = None
    if match:
        inv = await db.inventory_vehicles.find_one({"id": match[0]["inventory_vehicle_id"]})
        if inv:
            replacement_price = inv.get("price")
            matched_vehicle = f"{inv.get('year')} {inv.get('make')} {inv.get('model')}"
    if not replacement_price:
        replacement_price = pref.get("max_price")
    est = estimate_financing(
        replacement_price=replacement_price, vehicle=vehicle,
        loan_balance=vehicle.get("estimated_loan_balance") or 0,
        tax_rate=0.13, annual_rate=0.0899, term_months=72,
    )
    if est.get("available"):
        est["matched_vehicle"] = matched_vehicle
    return est


@api.get("/public/{slug}/conversations/{conv_id}/appointments/availability")
async def public_availability(slug: str, conv_id: str):
    org = await _get_dealer_by_slug(slug)
    rules = await db.appointment_availability.find({"organization_id": org["id"], "active": True}).to_list(100)
    booked = await db.appointments.find({"organization_id": org["id"],
        "status": {"$in": ["proposed", "confirmed"]}}).to_list(500)
    slots = generate_slots([clean(r) for r in rules], [clean(b) for b in booked])
    return {"slots": slots}


class BookBody(BaseModel):
    start_time: str
    end_time: str
    appointment_type: str = "in_person_appraisal"


@api.post("/public/{slug}/conversations/{conv_id}/appointments")
async def public_book(slug: str, conv_id: str, body: BookBody):
    org = await _get_dealer_by_slug(slug)
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = await db.leads.find_one({"id": conv["lead_id"]})
    existing = await db.appointments.find_one({"organization_id": org["id"], "start_time": body.start_time,
        "status": {"$in": ["proposed", "confirmed"]}})
    if existing:
        raise HTTPException(status_code=409, detail="That time was just taken. Please pick another slot.")
    loc = await db.dealership_locations.find_one({"organization_id": org["id"]})
    appt_id = new_id()
    appt = {"id": appt_id, "organization_id": org["id"], "dealership_location_id": loc["id"] if loc else None,
        "lead_id": lead["id"], "seller_id": lead["seller_id"], "assigned_user_id": lead.get("assigned_user_id"),
        "appointment_type": body.appointment_type, "start_time": body.start_time, "end_time": body.end_time,
        "time_zone": org.get("time_zone", "America/Toronto"), "status": "confirmed",
        "booking_source": "ai_conversation", "notes": "", "confirmation_sent_at": now_iso(),
        "created_at": now_iso(), "updated_at": now_iso()}
    await db.appointments.insert_one(dict(appt))
    await db.leads.update_one({"id": lead["id"]}, {"$set": {"status": "appointment_booked", "last_activity_at": now_iso()}})
    await db.conversations.update_one({"id": conv_id}, {"$set": {"current_stage": "appointment_confirmed"}})
    await audit(org["id"], "seller", lead["seller_id"], "appointment", appt_id, "created")
    await emit_event(org["id"], "appointment.booked", "appointment", appt_id)
    await notify(org["id"], "dealership", org["id"], "in_app", "appointment_booked", {"appointment_id": appt_id})
    seller = await db.sellers.find_one({"id": lead["seller_id"]})
    if seller and seller.get("email"):
        await notify(org["id"], "seller", seller["email"], "email", "appointment_confirmation", {"start_time": body.start_time})
    confirm = (f"You're booked! Your {body.appointment_type.replace('_', ' ')} is confirmed. "
               "A dealership representative will meet you then. You'll receive a confirmation shortly.")
    await db.messages.insert_one({"id": new_id(), "organization_id": org["id"], "conversation_id": conv_id,
        "sender_type": "ai", "content": confirm, "delivery_status": "delivered", "created_at": now_iso()})
    return {"appointment": clean(appt), "messages": await _conv_messages(conv_id)}


# ---------------- leads ----------------
@api.get("/leads")
async def list_leads(user: dict = Depends(get_current_user), status: Optional[str] = None,
                     score_band: Optional[str] = None, qualification_status: Optional[str] = None,
                     search: Optional[str] = None, sort: str = "newest", page: int = 1, page_size: int = 25):
    q = {"organization_id": _org(user), "is_test": {"$ne": True}}
    if user["role"] == "dealership_representative":
        q["assigned_user_id"] = user["id"]
    if status:
        q["status"] = status
    if score_band:
        q["score_band"] = score_band
    if qualification_status:
        q["qualification_status"] = qualification_status
    sort_map = {"newest": ("created_at", -1), "oldest": ("created_at", 1), "highest_score": ("score", -1),
                "lowest_score": ("score", 1), "recent_activity": ("last_activity_at", -1)}
    sk, sd = sort_map.get(sort, ("created_at", -1))
    leads = await db.leads.find(q).sort(sk, sd).to_list(2000)
    enriched = []
    for lead in leads:
        clean(lead)
        seller = await db.sellers.find_one({"id": lead["seller_id"]}) or {}
        vehicle = await db.seller_vehicles.find_one({"lead_id": lead["id"]}) or {}
        name = " ".join(filter(None, [seller.get("first_name"), seller.get("last_name")])) or "Unknown seller"
        vlabel = " ".join(str(x) for x in [vehicle.get("year"), vehicle.get("make"), vehicle.get("model")] if x) or "—"
        if search:
            s = search.lower()
            if (s not in name.lower() and s not in vlabel.lower()
                    and s not in (seller.get("phone") or "").lower() and s not in (seller.get("email") or "").lower()):
                continue
        appt = await db.appointments.find_one({"lead_id": lead["id"], "status": {"$in": ["confirmed", "proposed"]}})
        enriched.append({**lead, "seller_name": name, "vehicle_label": vlabel,
                         "appointment_status": appt["status"] if appt else None})
    total = len(enriched)
    start = (page - 1) * page_size
    return {"items": enriched[start:start + page_size], "total": total, "page": page, "page_size": page_size}


@api.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    clean(lead)
    seller = await db.sellers.find_one({"id": lead["seller_id"]})
    vehicle = await db.seller_vehicles.find_one({"lead_id": lead_id})
    conv = await db.conversations.find_one({"lead_id": lead_id})
    messages = await _conv_messages(conv["id"]) if conv else []
    score = await db.lead_scores.find({"lead_id": lead_id}).sort("created_at", -1).to_list(1)
    matches = await db.inventory_matches.find({"lead_id": lead_id}).sort("ranking", 1).to_list(10)
    match_out = []
    for m in matches:
        clean(m)
        v = await db.inventory_vehicles.find_one({"id": m["inventory_vehicle_id"]})
        m["vehicle"] = clean(v) if v else None
        match_out.append(m)
    appt = await db.appointments.find_one({"lead_id": lead_id})
    notes = await db.internal_notes.find({"lead_id": lead_id}).sort("created_at", -1).to_list(100)
    audits = await db.audit_events.find({"entity_id": lead_id}).sort("created_at", -1).to_list(50)
    return {"lead": lead, "seller": clean(seller) if seller else None,
            "vehicle": clean(vehicle) if vehicle else None, "conversation": clean(conv) if conv else None,
            "messages": messages, "score": clean(score[0]) if score else None, "matches": match_out,
            "appointment": clean(appt) if appt else None, "notes": [clean(n) for n in notes],
            "activity": [clean(a) for a in audits]}


class LeadPatch(BaseModel):
    status: Optional[str] = None
    assigned_user_id: Optional[str] = None


@api.patch("/leads/{lead_id}")
async def patch_lead(lead_id: str, body: LeadPatch, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        updates["updated_at"] = now_iso()
        await db.leads.update_one({"id": lead_id}, {"$set": updates})
        await audit(_org(user), "user", user["id"], "lead", lead_id, "update", lead.get("status"), updates)
    return clean(await db.leads.find_one({"id": lead_id}))


class VehiclePatch(BaseModel):
    fields: dict


@api.patch("/leads/{lead_id}/vehicle")
async def correct_vehicle(lead_id: str, body: VehiclePatch, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    prev = await db.seller_vehicles.find_one({"lead_id": lead_id}) or {}
    await db.seller_vehicles.update_one({"lead_id": lead_id},
        {"$set": {**body.fields, "updated_at": now_iso()},
         "$setOnInsert": {"id": new_id(), "organization_id": _org(user), "lead_id": lead_id,
                          "seller_id": lead["seller_id"], "created_at": now_iso()}}, upsert=True)
    await audit(_org(user), "user", user["id"], "vehicle", lead_id, "manual_correction",
                {k: prev.get(k) for k in body.fields}, body.fields)
    await recalc_and_store_score(lead)
    return {"success": True}


@api.post("/leads/{lead_id}/assign")
async def assign_lead(lead_id: str, body: dict, user: dict = Depends(get_current_user)):
    await db.leads.update_one({"id": lead_id, "organization_id": _org(user)},
                              {"$set": {"assigned_user_id": body.get("user_id"), "updated_at": now_iso()}})
    await audit(_org(user), "user", user["id"], "lead", lead_id, "assign", None, body.get("user_id"))
    return {"success": True}


@api.post("/leads/{lead_id}/recalculate-score")
async def recalc(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    score, qual = await recalc_and_store_score(lead)
    return {"score": score, "qualification": qual}


@api.post("/leads/{lead_id}/run-inventory-match")
async def run_match_endpoint(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"matches": await _run_match(lead)}


@api.post("/leads/{lead_id}/takeover")
async def takeover(lead_id: str, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.conversations.update_one({"lead_id": lead_id}, {"$set": {"ai_active": False}})
    await db.leads.update_one({"id": lead_id}, {"$set": {"conversation_mode": "human_active",
        "status": "human_takeover", "assigned_user_id": user["id"]}})
    await audit(_org(user), "user", user["id"], "conversation", lead_id, "human_takeover")
    return {"success": True}


@api.post("/leads/{lead_id}/resume-ai")
async def resume_ai(lead_id: str, user: dict = Depends(get_current_user)):
    await db.conversations.update_one({"lead_id": lead_id}, {"$set": {"ai_active": True}})
    await db.leads.update_one({"id": lead_id}, {"$set": {"conversation_mode": "ai_active"}})
    await audit(_org(user), "user", user["id"], "conversation", lead_id, "ai_resumed")
    return {"success": True}


@api.post("/leads/{lead_id}/messages")
async def send_manual_message(lead_id: str, body: MessageBody, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "organization_id": _org(user)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    conv = await db.conversations.find_one({"lead_id": lead_id})
    await db.messages.insert_one({"id": new_id(), "organization_id": _org(user), "conversation_id": conv["id"],
        "sender_type": "human_agent", "sender_user_id": user["id"], "content": body.content,
        "delivery_status": "delivered", "created_at": now_iso()})
    await db.leads.update_one({"id": lead_id}, {"$set": {"last_activity_at": now_iso()}})
    return {"messages": await _conv_messages(conv["id"])}


@api.post("/leads/{lead_id}/notes")
async def add_note(lead_id: str, body: MessageBody, user: dict = Depends(get_current_user)):
    note = {"id": new_id(), "organization_id": _org(user), "lead_id": lead_id, "user_id": user["id"],
            "user_name": f"{user['first_name']} {user['last_name']}", "content": body.content,
            "created_at": now_iso(), "updated_at": now_iso()}
    await db.internal_notes.insert_one(dict(note))
    return clean(note)


# ---------------- inventory ----------------
INVENTORY_COLUMNS = ["stock_number", "vin", "year", "make", "model", "trim", "price", "mileage",
                     "body_type", "fuel_type", "transmission", "drivetrain", "exterior_colour",
                     "seating_capacity", "location", "status", "vehicle_url", "image_url"]


@api.get("/inventory")
async def list_inventory(user: dict = Depends(get_current_user), search: Optional[str] = None,
                         page: int = 1, page_size: int = 25):
    items = await db.inventory_vehicles.find({"organization_id": _org(user)}).sort("created_at", -1).to_list(5000)
    out = [clean(i) for i in items]
    if search:
        s = search.lower()
        out = [i for i in out if s in str(i.get("make", "")).lower() or s in str(i.get("model", "")).lower()
               or s in str(i.get("stock_number", "")).lower() or s in str(i.get("vin", "")).lower()]
    total = len(out)
    start = (page - 1) * page_size
    return {"items": out[start:start + page_size], "total": total, "page": page, "page_size": page_size}


@api.get("/inventory/template", response_class=PlainTextResponse)
async def inventory_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(INVENTORY_COLUMNS)
    w.writerow(["A1234", "1HGCM82633A004352", "2022", "Honda", "CR-V", "EX-L", "34999", "28000",
                "SUV", "gas", "automatic", "AWD", "Silver", "5", "Main Lot", "available",
                "https://example.com/v/a1234", "https://example.com/img/a1234.jpg"])
    return buf.getvalue()


@api.post("/inventory/import")
async def import_inventory(file: UploadFile = File(...),
                           user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    content = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    missing_cols = [c for c in ["stock_number", "make", "model", "year", "price"] if c not in (reader.fieldnames or [])]
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing_cols)}")
    loc = await db.dealership_locations.find_one({"organization_id": _org(user)})
    imported, updated, errors = 0, 0, []
    for idx, row in enumerate(reader, start=2):
        try:
            stock = (row.get("stock_number") or "").strip()
            if not stock or not row.get("make"):
                errors.append({"row": idx, "error": "Missing stock_number or make"}); continue
            doc = {"stock_number": stock, "vin": row.get("vin"), "make": row.get("make"),
                   "model": row.get("model"), "trim": row.get("trim"),
                   "year": int(row["year"]) if row.get("year") else None,
                   "price": float(row["price"]) if row.get("price") else None,
                   "mileage": int(row["mileage"]) if row.get("mileage") else None,
                   "body_type": row.get("body_type"), "fuel_type": row.get("fuel_type"),
                   "transmission": row.get("transmission"), "drivetrain": row.get("drivetrain"),
                   "exterior_colour": row.get("exterior_colour"),
                   "seating_capacity": int(row["seating_capacity"]) if row.get("seating_capacity") else None,
                   "location": row.get("location"), "status": (row.get("status") or "available").strip().lower(),
                   "vehicle_url": row.get("vehicle_url"), "image_url": row.get("image_url"), "updated_at": now_iso()}
            existing = await db.inventory_vehicles.find_one({"organization_id": _org(user), "stock_number": stock})
            if existing:
                await db.inventory_vehicles.update_one({"id": existing["id"]}, {"$set": doc}); updated += 1
            else:
                await db.inventory_vehicles.insert_one({"id": new_id(), "organization_id": _org(user),
                    "dealership_location_id": loc["id"] if loc else None, "source": "csv",
                    "date_added": now_iso(), "created_at": now_iso(), **doc}); imported += 1
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})
    await db.inventory_imports.insert_one({"id": new_id(), "organization_id": _org(user), "imported": imported,
        "updated": updated, "errors": errors, "created_at": now_iso()})
    await emit_event(_org(user), "inventory.imported", "inventory", "batch", {"imported": imported, "updated": updated})
    return {"imported": imported, "updated": updated, "errors": errors}


class InventoryBody(BaseModel):
    stock_number: str
    make: str
    model: str
    year: Optional[int] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    body_type: Optional[str] = None
    drivetrain: Optional[str] = None
    seating_capacity: Optional[int] = None
    status: str = "available"
    image_url: Optional[str] = None
    trim: Optional[str] = None
    fuel_type: Optional[str] = None


@api.post("/inventory")
async def create_inventory(body: InventoryBody,
                           user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    loc = await db.dealership_locations.find_one({"organization_id": _org(user)})
    doc = {"id": new_id(), "organization_id": _org(user), "dealership_location_id": loc["id"] if loc else None,
           "source": "manual", "date_added": now_iso(), "created_at": now_iso(), "updated_at": now_iso(),
           **body.model_dump()}
    await db.inventory_vehicles.insert_one(dict(doc))
    return clean(doc)


@api.patch("/inventory/{inv_id}")
async def update_inventory(inv_id: str, body: dict, user: dict = Depends(get_current_user)):
    body["updated_at"] = now_iso()
    await db.inventory_vehicles.update_one({"id": inv_id, "organization_id": _org(user)}, {"$set": body})
    return clean(await db.inventory_vehicles.find_one({"id": inv_id}))


@api.delete("/inventory/{inv_id}")
async def delete_inventory(inv_id: str, user: dict = Depends(get_current_user)):
    await db.inventory_vehicles.delete_one({"id": inv_id, "organization_id": _org(user)})
    return {"success": True}


# ---------------- qualification rules ----------------
@api.get("/qualification-rules")
async def list_rules(user: dict = Depends(get_current_user)):
    rules = await db.qualification_rules.find({"organization_id": _org(user)}).sort("priority", 1).to_list(200)
    return [clean(r) for r in rules]


@api.post("/qualification-rules")
async def create_rule(body: dict, user: dict = Depends(require_roles("dealership_admin"))):
    doc = {"id": new_id(), "organization_id": _org(user), "active": True, "version": 1,
           "priority": body.get("priority", 100), "created_at": now_iso(), "updated_at": now_iso(), **body}
    await db.qualification_rules.insert_one(dict(doc))
    return clean(doc)


@api.patch("/qualification-rules/{rule_id}")
async def update_rule(rule_id: str, body: dict, user: dict = Depends(require_roles("dealership_admin"))):
    body["updated_at"] = now_iso()
    await db.qualification_rules.update_one({"id": rule_id, "organization_id": _org(user)}, {"$set": body})
    return clean(await db.qualification_rules.find_one({"id": rule_id}))


@api.delete("/qualification-rules/{rule_id}")
async def delete_rule(rule_id: str, user: dict = Depends(require_roles("dealership_admin"))):
    await db.qualification_rules.delete_one({"id": rule_id, "organization_id": _org(user)})
    return {"success": True}


# ---------------- availability ----------------
@api.get("/availability")
async def list_availability(user: dict = Depends(get_current_user)):
    rows = await db.appointment_availability.find({"organization_id": _org(user)}).to_list(200)
    return [clean(r) for r in rows]


@api.post("/availability")
async def create_availability(body: dict,
                              user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    loc = await db.dealership_locations.find_one({"organization_id": _org(user)})
    doc = {"id": new_id(), "organization_id": _org(user), "dealership_location_id": loc["id"] if loc else None,
           "active": True, "created_at": now_iso(), "updated_at": now_iso(), **body}
    await db.appointment_availability.insert_one(dict(doc))
    return clean(doc)


@api.delete("/availability/{av_id}")
async def delete_availability(av_id: str,
                              user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    await db.appointment_availability.delete_one({"id": av_id, "organization_id": _org(user)})
    return {"success": True}


# ---------------- appointments ----------------
@api.get("/appointments")
async def list_appointments(user: dict = Depends(get_current_user)):
    rows = await db.appointments.find({"organization_id": _org(user)}).sort("start_time", 1).to_list(500)
    out = []
    for a in rows:
        clean(a)
        seller = await db.sellers.find_one({"id": a["seller_id"]}) or {}
        a["seller_name"] = " ".join(filter(None, [seller.get("first_name"), seller.get("last_name")])) or "Seller"
        out.append(a)
    return out


@api.post("/appointments/{appt_id}/cancel")
async def cancel_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    await db.appointments.update_one({"id": appt_id, "organization_id": _org(user)},
                                     {"$set": {"status": "cancelled", "updated_at": now_iso()}})
    await audit(_org(user), "user", user["id"], "appointment", appt_id, "cancelled")
    return {"success": True}


@api.post("/appointments/{appt_id}/complete")
async def complete_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    await db.appointments.update_one({"id": appt_id, "organization_id": _org(user)},
                                     {"$set": {"status": "completed", "updated_at": now_iso()}})
    return {"success": True}


@api.post("/appointments/{appt_id}/no-show")
async def noshow_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    await db.appointments.update_one({"id": appt_id, "organization_id": _org(user)},
                                     {"$set": {"status": "no_show", "updated_at": now_iso()}})
    return {"success": True}


# ---------------- analytics + dashboard ----------------
@api.get("/analytics/overview")
async def analytics_overview(user: dict = Depends(get_current_user)):
    org = _org(user)
    base = {"organization_id": org, "is_test": {"$ne": True}}
    leads = await db.leads.find(base).to_list(5000)
    total = len(leads)
    qualified = sum(1 for l in leads if l.get("qualification_status") in ("qualified", "partially_qualified"))
    hot = sum(1 for l in leads if l.get("score_band") == "hot")
    appts = await db.appointments.find({"organization_id": org}).to_list(2000)
    booked = len(appts)
    completed = sum(1 for a in appts if a["status"] == "completed")
    noshow = sum(1 for a in appts if a["status"] == "no_show")
    purchased = sum(1 for l in leads if l.get("status") == "purchased")
    active_conv = await db.conversations.count_documents({"organization_id": org, "status": "active"})
    review = sum(1 for l in leads if l.get("requires_human_review"))
    avg_score = round(sum(l.get("score", 0) for l in leads) / total, 1) if total else 0
    band_dist = {b: sum(1 for l in leads if l.get("score_band") == b) for b in ["hot", "warm", "nurture", "low"]}
    intent_dist = {}
    for l in leads:
        k = l.get("primary_intent") or "unknown"
        intent_dist[k] = intent_dist.get(k, 0) + 1
    return {"total_leads": total, "active_conversations": active_conv, "qualified_leads": qualified,
            "qualification_rate": round(qualified / total * 100, 1) if total else 0, "hot_leads": hot,
            "leads_requiring_review": review, "appointments_booked": booked,
            "lead_to_appointment_rate": round(booked / total * 100, 1) if total else 0,
            "appointment_completion_rate": round(completed / booked * 100, 1) if booked else 0,
            "no_show_rate": round(noshow / booked * 100, 1) if booked else 0,
            "purchased_vehicles": purchased, "average_lead_score": avg_score,
            "score_band_distribution": band_dist, "intent_distribution": intent_dist}


@api.get("/dashboard/home")
async def dashboard_home(user: dict = Depends(get_current_user)):
    org = _org(user)
    base = {"organization_id": org, "is_test": {"$ne": True}}
    new_leads = await db.leads.find({**base, "status": "new"}).sort("created_at", -1).to_list(10)
    hot_leads = await db.leads.find({**base, "score_band": "hot"}).sort("score", -1).to_list(10)
    review_leads = await db.leads.find({**base, "requires_human_review": True}).to_list(10)
    today = datetime.now(timezone.utc).date().isoformat()
    appts = await db.appointments.find({"organization_id": org,
        "status": {"$in": ["confirmed", "proposed"]}}).to_list(200)
    today_appts = [clean(a) for a in appts if (a.get("start_time") or "").startswith(today)]

    async def enrich(ls):
        out = []
        for l in ls:
            clean(l)
            seller = await db.sellers.find_one({"id": l["seller_id"]}) or {}
            v = await db.seller_vehicles.find_one({"lead_id": l["id"]}) or {}
            out.append({**l, "seller_name": " ".join(filter(None, [seller.get("first_name"), seller.get("last_name")])) or "Unknown",
                        "vehicle_label": " ".join(str(x) for x in [v.get("year"), v.get("make"), v.get("model")] if x) or "—"})
        return out
    return {"new_leads": await enrich(new_leads), "hot_leads": await enrich(hot_leads),
            "review_leads": await enrich(review_leads), "today_appointments": today_appts}


# ---------------- organization / users / settings ----------------
@api.get("/organizations/current")
async def current_org(user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"id": _org(user)})
    loc = await db.dealership_locations.find_one({"organization_id": _org(user)})
    return {"organization": clean(org), "location": clean(loc) if loc else None}


@api.patch("/organizations/current")
async def update_org(body: dict, user: dict = Depends(require_roles("dealership_admin"))):
    body["updated_at"] = now_iso()
    await db.organizations.update_one({"id": _org(user)}, {"$set": body})
    return clean(await db.organizations.find_one({"id": _org(user)}))


@api.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    rows = await db.users.find({"organization_id": _org(user)}).to_list(200)
    out = []
    for u in rows:
        clean(u); u.pop("password_hash", None)
        out.append(u)
    return out


class InviteBody(BaseModel):
    first_name: str
    last_name: str
    email: str
    role: str


@api.post("/users/invite")
async def invite_user(body: InviteBody, user: dict = Depends(require_roles("dealership_admin"))):
    from auth import hash_password
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    uid = new_id()
    temp = "Welcome123!"
    await db.users.insert_one({"id": uid, "organization_id": _org(user), "first_name": body.first_name,
        "last_name": body.last_name, "email": email, "role": body.role, "status": "active",
        "auth_provider": "password", "password_hash": hash_password(temp),
        "created_at": now_iso(), "updated_at": now_iso()})
    await notify(_org(user), "user", email, "email", "invitation", {"temp_password": temp})
    return {"success": True, "temp_password": temp}


@api.get("/audit-logs")
async def audit_logs(user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    rows = await db.audit_events.find({"organization_id": _org(user)}).sort("created_at", -1).to_list(200)
    return [clean(r) for r in rows]


# ---------------- platform admin ----------------
@api.get("/platform/organizations")
async def platform_orgs(user: dict = Depends(require_roles("platform_admin"))):
    orgs = await db.organizations.find({}).to_list(500)
    out = []
    for o in orgs:
        clean(o)
        o["lead_count"] = await db.leads.count_documents({"organization_id": o["id"]})
        o["user_count"] = await db.users.count_documents({"organization_id": o["id"]})
        o["appointment_count"] = await db.appointments.count_documents({"organization_id": o["id"]})
        out.append(o)
    return out


@api.get("/platform/failed-workflows")
async def platform_failed(user: dict = Depends(require_roles("platform_admin"))):
    rows = await db.domain_events.find({"event_type": "workflow.failed"}).sort("created_at", -1).to_list(200)
    return [clean(r) for r in rows]


# ---------------- onboarding wizard ----------------
class OnboardingBody(BaseModel):
    organization: dict = {}
    location: dict = {}
    availability: list = []
    inventory: list = []


@api.post("/onboarding/complete")
async def onboarding_complete(body: OnboardingBody,
                              user: dict = Depends(require_roles("dealership_admin"))):
    org_id = _org(user)
    org_updates = {**body.organization, "onboarding_complete": True, "updated_at": now_iso()}
    await db.organizations.update_one({"id": org_id}, {"$set": org_updates})

    loc = await db.dealership_locations.find_one({"organization_id": org_id})
    if body.location:
        if loc:
            await db.dealership_locations.update_one(
                {"id": loc["id"]}, {"$set": {**body.location, "updated_at": now_iso()}})
            loc_id = loc["id"]
        else:
            loc_id = new_id()
            await db.dealership_locations.insert_one({
                "id": loc_id, "organization_id": org_id, "active": True, "country": "CA",
                "created_at": now_iso(), "updated_at": now_iso(), **body.location})
    else:
        loc_id = loc["id"] if loc else None

    for a in body.availability:
        await db.appointment_availability.insert_one({
            "id": new_id(), "organization_id": org_id, "dealership_location_id": loc_id,
            "active": True, "appointment_type": a.get("appointment_type", "in_person_appraisal"),
            "duration_minutes": a.get("duration_minutes", 45), "buffer_minutes": a.get("buffer_minutes", 15),
            "capacity": 1, "day_of_week": a.get("day_of_week"), "start_time": a.get("start_time", "09:00"),
            "end_time": a.get("end_time", "17:00"), "created_at": now_iso(), "updated_at": now_iso()})

    for v in body.inventory:
        await db.inventory_vehicles.insert_one({
            "id": new_id(), "organization_id": org_id, "dealership_location_id": loc_id,
            "source": "onboarding", "status": v.get("status", "available"), "date_added": now_iso(),
            "created_at": now_iso(), "updated_at": now_iso(), **v})

    await audit(org_id, "user", user["id"], "organization", org_id, "onboarding_complete")
    return clean(await db.organizations.find_one({"id": org_id}))


@api.post("/onboarding/skip")
async def onboarding_skip(user: dict = Depends(require_roles("dealership_admin"))):
    await db.organizations.update_one({"id": _org(user)},
        {"$set": {"onboarding_complete": True, "updated_at": now_iso()}})
    return {"success": True}



app.include_router(auth_router)
app.include_router(api)

app.add_middleware(CORSMiddleware, allow_credentials=True,
                   allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.organizations.create_index("slug", unique=True)
    await db.leads.create_index([("organization_id", 1), ("status", 1)])
    await db.messages.create_index("conversation_id")
    await seed_demo()
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    from db import client
    client.close()
