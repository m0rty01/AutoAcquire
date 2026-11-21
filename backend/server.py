import logging
import asyncio
import hmac
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Header, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import io, csv, os, secrets

from db import db, new_id, now_iso, clean, audit, emit_event, notify
from auth import auth_router, get_current_user, require_roles
from ai_engine import run_orchestrator, FALLBACK_MESSAGE, MODEL_PROVIDER, MODEL_NAME, PROMPT_VERSION
from engine import run_qualification, compute_score, match_inventory, generate_slots, estimate_financing, SCORE_VERSION
from connectors import run_source_sync
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


async def _default_dealer_group_id(org_id: str) -> str:
    dg = await db.dealer_groups.find_one({"organization_id": org_id, "is_default": True}) \
        or await db.dealer_groups.find_one({"organization_id": org_id})
    if dg:
        return dg["id"]
    dg_id = new_id()
    await db.dealer_groups.insert_one({"id": dg_id, "organization_id": org_id, "name": "House Inventory",
        "slug": "house", "website": None, "locations": [], "referral_amount": 0,
        "referral_program": None, "status": "active", "is_default": True,
        "created_at": now_iso(), "updated_at": now_iso()})
    return dg_id


async def _upsert_referral(lead: dict, vehicle: dict, status: str = "identified"):
    """Create or refresh a referral. Only called after explicit customer consent."""
    dg_id = vehicle.get("dealer_group_id")
    dg = await db.dealer_groups.find_one({"id": dg_id}) if dg_id else None
    seller = await db.sellers.find_one({"id": lead["seller_id"]}) or {}
    label = " ".join(str(x) for x in [vehicle.get("year"), vehicle.get("make"), vehicle.get("model")] if x)
    seller_name = (f"{seller.get('first_name') or ''} {seller.get('last_name') or ''}").strip() or "Customer"
    base = {"organization_id": lead["organization_id"], "lead_id": lead["id"], "dealer_group_id": dg_id,
            "inventory_vehicle_id": vehicle["id"], "seller_name": seller_name, "vehicle_label": label,
            "amount": (dg or {}).get("referral_amount", 0), "updated_at": now_iso()}
    existing = await db.referrals.find_one({"lead_id": lead["id"]})
    if existing:
        updates = dict(base)
        if existing.get("status") == "identified" and status != "identified":
            updates["status"] = status
            updates["status_history"] = existing.get("status_history", []) + [{"status": status, "at": now_iso()}]
        await db.referrals.update_one({"id": existing["id"]}, {"$set": updates})
    else:
        await db.referrals.insert_one({"id": new_id(), "status": status, "external_reference": None,
            "notes": None, "status_history": [{"status": status, "at": now_iso()}],
            "created_at": now_iso(), **base})


async def _run_match(lead: dict):
    pref = await db.inventory_preferences.find_one({"lead_id": lead["id"]}) or {}
    inv = await db.inventory_vehicles.find({"organization_id": lead["organization_id"], "status": "available"}).to_list(2000)
    matches = match_inventory(clean(pref), [clean(v) for v in inv])
    await db.inventory_matches.delete_many({"lead_id": lead["id"]})
    for m in matches:
        v = m["inventory_vehicle"]
        await db.inventory_matches.insert_one({"id": new_id(), "organization_id": lead["organization_id"],
            "lead_id": lead["id"], "inventory_vehicle_id": v["id"], "dealer_group_id": v.get("dealer_group_id"),
            "match_score": m["match_score"], "ranking": m["ranking"], "match_reasons": m["match_reasons"],
            "conflicts": m["conflicts"], "generated_at": now_iso()})
    # Referral/dealership sharing is NOT created here — it is gated behind explicit customer consent.
    return matches


# ---------------- public conversation ----------------
class StartConvBody(BaseModel):
    consent: bool = True
    language: str = "en"


class MessageBody(BaseModel):
    content: str
    language: Optional[str] = None


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
    language = body.language if body.language in ("en", "fr") else "en"
    await db.conversations.insert_one({"id": conv_id, "organization_id": org["id"], "lead_id": lead_id,
        "channel": "web", "status": "active", "current_stage": "intent_discovery", "rolling_summary": "",
        "language": language, "ai_active": True, "started_at": now_iso(), "created_at": now_iso(), "updated_at": now_iso()})
    if language == "fr":
        greeting = (f"Bonjour, je suis l'assistant virtuel de {org['name']} (une IA). Je peux vous aider à "
                    "trouver le bon véhicule à acheter, ou à vendre ou échanger le vôtre. Cherchez-vous à "
                    "acheter un véhicule, ou à vendre/échanger le vôtre ?")
    else:
        greeting = (f"Hi, I'm {org['name']}'s virtual vehicle assistant (an AI). I can help you find the right "
                    "vehicle to buy, or sell/trade in your current one. Are you looking to buy a vehicle, or to "
                    "sell or trade in yours?")
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
    lead_id = conv["lead_id"]
    consent = await db.consent_records.find_one({"lead_id": lead_id}, sort=[("created_at", -1)])
    appt = await db.appointments.find_one({"lead_id": lead_id,
        "status": {"$in": ["requested", "proposed", "confirmed"]}}, sort=[("created_at", -1)])
    recs = []
    for m in await db.inventory_matches.find({"lead_id": lead_id}).sort("ranking", 1).to_list(3):
        v = await db.inventory_vehicles.find_one({"id": m["inventory_vehicle_id"]})
        if not v:
            continue
        dg = await db.dealer_groups.find_one({"id": v.get("dealer_group_id")}) if v.get("dealer_group_id") else None
        recs.append({"id": v["id"], "year": v.get("year"), "make": v.get("make"), "model": v.get("model"),
            "trim": v.get("trim"), "price": v.get("price"), "mileage": v.get("mileage"),
            "fuel_type": v.get("fuel_type"), "transmission": v.get("transmission"),
            "image_url": v.get("image_url"), "dealer_group_name": dg["name"] if dg else None,
            "match_reasons": m.get("match_reasons", [])})
    return {"conversation": clean(conv), "messages": await _conv_messages(conv_id),
            "recommendations": recs, "consent_status": (consent or {}).get("status"),
            "booked_appointment": clean(appt) if appt else None}


@api.post("/public/{slug}/conversations/{conv_id}/messages")
async def post_public_message(slug: str, conv_id: str, body: MessageBody):
    org = await _get_dealer_by_slug(slug)
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = await db.leads.find_one({"id": conv["lead_id"]})

    if body.language in ("en", "fr") and body.language != conv.get("language"):
        await db.conversations.update_one({"id": conv_id}, {"$set": {"language": body.language}})
        conv["language"] = body.language

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
        missing=_missing_fields(state), recent_messages=[clean(m) for m in recent], seller_message=body.content,
        language=conv.get("language", "en"))

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

    score, qual = await recalc_and_store_score(lead)
    matches = []
    if next_action in ("run_inventory_match", "offer_appointment"):
        matches = await _run_match(lead)

    lang = conv.get("language", "en")
    consented = await db.consent_records.find_one({"lead_id": lead["id"], "status": "accepted"})
    recommendations = []
    for m in matches[:3]:
        v = m["inventory_vehicle"]
        dg = await db.dealer_groups.find_one({"id": v.get("dealer_group_id")}) if v.get("dealer_group_id") else None
        recommendations.append({"id": v["id"], "year": v.get("year"), "make": v.get("make"),
            "model": v.get("model"), "trim": v.get("trim"), "price": v.get("price"), "mileage": v.get("mileage"),
            "body_type": v.get("body_type"), "fuel_type": v.get("fuel_type"), "transmission": v.get("transmission"),
            "exterior_colour": v.get("exterior_colour"), "image_url": v.get("image_url"),
            "vehicle_url": v.get("vehicle_url"), "location": v.get("location"),
            "dealer_group_id": v.get("dealer_group_id"), "dealer_group_name": dg["name"] if dg else None,
            "match_reasons": m.get("match_reasons", [])})

    # Tease the single best match to the customer (inventory stays internal — never a full listing)
    content = data["responseMessage"]
    if matches and not lead.get("match_teased"):
        top = matches[0]["inventory_vehicle"]
        label = " ".join(str(x) for x in [top.get("year"), top.get("make"), top.get("model")] if x)
        price = f" (~${top['price']:,.0f})" if top.get("price") else ""
        if label and lang == "fr":
            content += (f"\n\nBonne nouvelle — d'après vos critères, je pense avoir une bonne correspondance : "
                        f"une {label}{price}. Je peux vous mettre en relation avec le concessionnaire si vous le souhaitez.")
            await db.leads.update_one({"id": lead["id"]}, {"$set": {"match_teased": True}})
        elif label:
            content += (f"\n\nGood news — based on what you're looking for, I think I have a strong match: "
                        f"a {label}{price}. I can connect you with the dealership if you'd like.")
            await db.leads.update_one({"id": lead["id"]}, {"$set": {"match_teased": True}})

    await db.messages.insert_one({"id": new_id(), "organization_id": org["id"], "conversation_id": conv_id,
        "sender_type": "ai", "content": content, "delivery_status": "delivered",
        "structured_payload": data, "model_provider": MODEL_PROVIDER, "model_name": MODEL_NAME,
        "prompt_version": PROMPT_VERSION, "created_at": now_iso()})

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
    if recommendations:
        resp["recommendations"] = recommendations
    resp["can_refer"] = bool(matches) and not consented
    resp["consented"] = bool(consented)
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


async def _active_agreement(language: str):
    v = await db.consent_agreement_versions.find_one({"language": language, "active": True}) \
        or await db.consent_agreement_versions.find_one({"language": "en", "active": True})
    return v


@api.get("/public/{slug}/conversations/{conv_id}/consent-agreement")
async def public_consent_agreement(slug: str, conv_id: str, language: str = "en"):
    org = await _get_dealer_by_slug(slug)
    conv = await db.conversations.find_one({"id": conv_id, "organization_id": org["id"]})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    language = language if language in ("en", "fr") else "en"
    agreement = await _active_agreement(language)
    top = await db.inventory_matches.find_one({"lead_id": conv["lead_id"]}, sort=[("ranking", 1)])
    dg = await db.dealer_groups.find_one({"id": top["dealer_group_id"]}) if top and top.get("dealer_group_id") else None
    recipient = {"dealer_group_id": dg["id"], "name": dg["name"]} if dg else {"dealer_group_id": None, "name": org["name"]}
    body_text = (agreement or {}).get("body_text", "")
    body_text = body_text.replace("{{recipient}}", recipient["name"]).replace("{{platform}}", "AutoNova AI")
    return {"version_id": (agreement or {}).get("id"), "version": (agreement or {}).get("version"),
            "language": language, "body_text": body_text, "recipient": recipient}


class ConsentBody(BaseModel):
    accepted: bool
    language: str = "en"
    recipient_dealer_group_id: Optional[str] = None


@api.post("/public/{slug}/conversations/{conv_id}/consent")
async def public_consent(slug: str, conv_id: str, body: ConsentBody):
    org = await _get_dealer_by_slug(slug)
    conv = await db.conversations.find_one({"id": conv_id, "organization_id": org["id"]})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = await db.leads.find_one({"id": conv["lead_id"]})
    language = body.language if body.language in ("en", "fr") else "en"
    agreement = await _active_agreement(language)
    top = await db.inventory_matches.find_one({"lead_id": lead["id"]}, sort=[("ranking", 1)])
    dg_id = body.recipient_dealer_group_id or (top.get("dealer_group_id") if top else None)
    # Only allow a recipient dealer group that belongs to this org
    if dg_id and not await db.dealer_groups.find_one({"id": dg_id, "organization_id": org["id"]}):
        dg_id = top.get("dealer_group_id") if top else None
    record = {"id": new_id(), "organization_id": org["id"], "lead_id": lead["id"], "seller_id": lead["seller_id"],
        "agreement_version_id": (agreement or {}).get("id"), "agreement_version": (agreement or {}).get("version"),
        "language": language, "recipient_dealer_group_ids": [dg_id] if dg_id else [],
        "categories": ["contact_details", "vehicle_preferences", "conversation_summary"],
        "status": "accepted" if body.accepted else "declined", "method": "web_click",
        "accepted_at": now_iso() if body.accepted else None, "withdrawn_at": None,
        "created_at": now_iso(), "updated_at": now_iso()}
    await db.consent_records.insert_one(dict(record))
    await audit(org["id"], "seller", lead["seller_id"], "consent", record["id"],
                "accepted" if body.accepted else "declined")
    if body.accepted:
        lead_set = {"consent_status": "granted", "last_activity_at": now_iso()}
        if top:
            v = await db.inventory_vehicles.find_one({"id": top["inventory_vehicle_id"]})
            if v:
                await _upsert_referral(lead, clean(v), status="sent")
            lead_set["status"] = "sent_to_dealership"
            await notify(org["id"], "dealership", org["id"], "in_app", "lead_referred", {"lead_id": lead["id"]})
        await db.leads.update_one({"id": lead["id"]}, {"$set": lead_set})
    else:
        await db.leads.update_one({"id": lead["id"]},
            {"$set": {"consent_status": "declined", "last_activity_at": now_iso()}})
    return {"status": record["status"], "shared_with": dg_id}


@api.get("/public/{slug}/conversations/{conv_id}/appointments/availability")
async def public_availability(slug: str, conv_id: str):
    org = await _get_dealer_by_slug(slug)
    rules = await db.appointment_availability.find({"organization_id": org["id"], "active": True}).to_list(100)
    booked = await db.appointments.find({"organization_id": org["id"],
        "status": {"$in": ["requested", "proposed", "confirmed"]}}).to_list(500)
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
        "status": {"$in": ["requested", "proposed", "confirmed"]}})
    if existing:
        raise HTTPException(status_code=409, detail="That time was just taken. Please pick another slot.")
    loc = await db.dealership_locations.find_one({"organization_id": org["id"]})
    appt_id = new_id()
    appt = {"id": appt_id, "organization_id": org["id"], "dealership_location_id": loc["id"] if loc else None,
        "lead_id": lead["id"], "seller_id": lead["seller_id"], "assigned_user_id": lead.get("assigned_user_id"),
        "appointment_type": body.appointment_type, "start_time": body.start_time, "end_time": body.end_time,
        "time_zone": org.get("time_zone", "America/Toronto"), "status": "requested",
        "booking_source": "ai_conversation", "notes": "", "confirmation_sent_at": None,
        "created_at": now_iso(), "updated_at": now_iso()}
    await db.appointments.insert_one(dict(appt))
    await db.leads.update_one({"id": lead["id"]}, {"$set": {"status": "appointment_requested", "last_activity_at": now_iso()}})
    await db.conversations.update_one({"id": conv_id}, {"$set": {"current_stage": "appointment_requested"}})
    await audit(org["id"], "seller", lead["seller_id"], "appointment", appt_id, "requested")
    await emit_event(org["id"], "appointment.requested", "appointment", appt_id)
    await notify(org["id"], "dealership", org["id"], "in_app", "appointment_requested", {"appointment_id": appt_id})
    lang = conv.get("language", "en")
    if lang == "fr":
        confirm = (f"Votre demande de rendez-vous ({body.appointment_type.replace('_', ' ')}) a été envoyée. "
                   "Elle est en attente de confirmation par le concessionnaire — vous recevrez un avis dès qu'elle sera confirmée.")
    else:
        confirm = (f"Your {body.appointment_type.replace('_', ' ')} request has been sent. "
                   "It's pending confirmation by the dealership — you'll be notified as soon as it's confirmed.")
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
    for lead in leads:
        clean(lead)
    lead_ids = [l["id"] for l in leads]
    seller_ids = list({l["seller_id"] for l in leads if l.get("seller_id")})
    # Batched lookups (avoids N+1 queries against the DB)
    sellers = {s["id"]: s for s in await db.sellers.find({"id": {"$in": seller_ids}}).to_list(None)}
    vehicles = {}
    for v in await db.seller_vehicles.find({"lead_id": {"$in": lead_ids}}).to_list(None):
        vehicles.setdefault(v["lead_id"], v)
    appts = {}
    for a in await db.appointments.find(
            {"lead_id": {"$in": lead_ids}, "status": {"$in": ["confirmed", "proposed"]}}).to_list(None):
        appts.setdefault(a["lead_id"], a)
    enriched = []
    for lead in leads:
        seller = sellers.get(lead.get("seller_id")) or {}
        vehicle = vehicles.get(lead["id"]) or {}
        name = " ".join(filter(None, [seller.get("first_name"), seller.get("last_name")])) or "Unknown seller"
        vlabel = " ".join(str(x) for x in [vehicle.get("year"), vehicle.get("make"), vehicle.get("model")] if x) or "—"
        if search:
            s = search.lower()
            if (s not in name.lower() and s not in vlabel.lower()
                    and s not in (seller.get("phone") or "").lower() and s not in (seller.get("email") or "").lower()):
                continue
        appt = appts.get(lead["id"])
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
    return {"lead": clean(lead), "seller": clean(seller) if seller else None,
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


async def _run_csv_import(org_id: str, content: str, source: str = "csv", mode: str = "incremental",
                          dealer_group_id: str = None, source_id: str = None):
    """Shared CSV import used by authenticated upload and the token feed endpoint."""
    if dealer_group_id is None:
        dealer_group_id = await _default_dealer_group_id(org_id)
    reader = csv.DictReader(io.StringIO(content))
    missing_cols = [c for c in ["stock_number", "make", "model", "year", "price"] if c not in (reader.fieldnames or [])]
    if missing_cols:
        detail = f"Missing required columns: {', '.join(missing_cols)}"
        await db.inventory_imports.insert_one({"id": new_id(), "organization_id": org_id, "source": source,
            "source_id": source_id, "dealer_group_id": dealer_group_id, "status": "failed", "mode": mode,
            "imported": 0, "updated": 0, "deactivated": 0, "errors": [{"row": 1, "error": detail}],
            "created_at": now_iso()})
        if source == "feed":
            await notify(org_id, "dealership", org_id, "in_app", "feed_sync_failed", {"error": detail})
        raise HTTPException(status_code=400, detail=detail)
    loc = await db.dealership_locations.find_one({"organization_id": org_id})
    imported, updated, errors, seen = 0, 0, [], set()
    run_at = now_iso()
    for idx, row in enumerate(reader, start=2):
        try:
            stock = (row.get("stock_number") or "").strip()
            if not stock or not row.get("make"):
                errors.append({"row": idx, "error": "Missing stock_number or make"}); continue
            seen.add(stock)
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
                   "vehicle_url": row.get("vehicle_url"), "image_url": row.get("image_url"),
                   "dealer_group_id": dealer_group_id, "source_id": source_id, "last_seen_at": run_at,
                   "updated_at": run_at}
            existing = await db.inventory_vehicles.find_one(
                {"organization_id": org_id, "dealer_group_id": dealer_group_id, "stock_number": stock})
            if existing:
                await db.inventory_vehicles.update_one({"id": existing["id"]}, {"$set": doc}); updated += 1
            else:
                await db.inventory_vehicles.insert_one({"id": new_id(), "organization_id": org_id,
                    "dealership_location_id": loc["id"] if loc else None, "source": source,
                    "date_added": run_at, "created_at": run_at, **doc}); imported += 1
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})
    deactivated = 0
    if mode == "full" and seen:
        scope = {"organization_id": org_id, "stock_number": {"$nin": list(seen)}, "status": {"$ne": "unavailable"}}
        scope["source_id"] = source_id if source_id else None
        res = await db.inventory_vehicles.update_many(scope, {"$set": {"status": "unavailable", "updated_at": run_at}})
        deactivated = res.modified_count
    await db.inventory_imports.insert_one({"id": new_id(), "organization_id": org_id, "source": source,
        "source_id": source_id, "dealer_group_id": dealer_group_id, "status": "completed", "mode": mode,
        "imported": imported, "updated": updated, "deactivated": deactivated, "errors": errors,
        "created_at": now_iso()})
    await emit_event(org_id, "inventory.imported", "inventory", "batch",
                     {"imported": imported, "updated": updated, "deactivated": deactivated, "source": source})
    if source == "feed" and errors:
        await notify(org_id, "dealership", org_id, "in_app", "feed_sync_skipped",
                     {"skipped": len(errors), "imported": imported, "updated": updated})
    return {"imported": imported, "updated": updated, "deactivated": deactivated, "errors": errors}


@api.post("/inventory/import")
async def import_inventory(file: UploadFile = File(...),
                           user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    content = (await file.read()).decode("utf-8", errors="ignore")
    return await _run_csv_import(_org(user), content, source="csv")


def _mask_token(tok: str) -> str:
    return f"{tok[:6]}\u2026{tok[-4:]}" if tok and len(tok) > 12 else tok


async def _get_or_create_feed_token(org_id: str) -> str:
    org = await db.organizations.find_one({"id": org_id})
    tok = (org or {}).get("inventory_feed_token")
    if not tok:
        tok = secrets.token_urlsafe(24)
        await db.organizations.update_one({"id": org_id},
            {"$set": {"inventory_feed_token": tok, "updated_at": now_iso()}})
    return tok


@api.get("/inventory/feed-config")
async def inventory_feed_config(user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    tok = await _get_or_create_feed_token(_org(user))
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    push = f"{base}/api/inventory/feed?token={tok}" if base else f"/api/inventory/feed?token={tok}"
    recent = await db.inventory_imports.find({"organization_id": _org(user), "source": "feed"}) \
        .sort("created_at", -1).to_list(10)
    return {
        "token_masked": _mask_token(tok),
        "push_url": push,
        "full_push_url": f"{push}&mode=full",
        "header_name": "X-Feed-Token",
        "recent_imports": [clean(r) for r in recent],
    }


@api.post("/inventory/feed-config/regenerate")
async def regenerate_feed_token(user: dict = Depends(require_roles("dealership_admin"))):
    tok = secrets.token_urlsafe(24)
    await db.organizations.update_one({"id": _org(user)},
        {"$set": {"inventory_feed_token": tok, "updated_at": now_iso()}})
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    push = f"{base}/api/inventory/feed?token={tok}" if base else f"/api/inventory/feed?token={tok}"
    return {"token_masked": _mask_token(tok), "push_url": push, "full_push_url": f"{push}&mode=full"}


@api.post("/inventory/feed")
async def inventory_feed(file: UploadFile = File(...), token: Optional[str] = None, mode: str = "incremental",
                         x_feed_token: Optional[str] = Header(default=None)):
    """Token-authenticated CSV ingestion for external DMS / inventory feeds (SFTP alternative)."""
    supplied = token or x_feed_token
    if not supplied:
        raise HTTPException(status_code=401, detail="Missing feed token")
    src = await db.inventory_sources.find_one({"feed_token": supplied})
    if src:
        org_id, dg_id, source_id = src["organization_id"], src.get("dealer_group_id"), src["id"]
    else:
        org = await db.organizations.find_one({"inventory_feed_token": supplied})
        if not org:
            raise HTTPException(status_code=403, detail="Invalid feed token")
        org_id, dg_id, source_id = org["id"], await _default_dealer_group_id(org["id"]), None
    content = (await file.read()).decode("utf-8", errors="ignore")
    try:
        stats = await _run_csv_import(org_id, content, source="feed",
                                      mode="full" if mode == "full" else "incremental",
                                      dealer_group_id=dg_id, source_id=source_id)
    except HTTPException:
        if source_id:
            await db.inventory_sources.update_one({"id": source_id},
                {"$set": {"last_run_at": now_iso(), "last_status": "failed", "updated_at": now_iso()}})
        raise
    if source_id:
        await db.inventory_sources.update_one({"id": source_id}, {"$set": {"last_run_at": now_iso(),
            "last_status": "success", "last_stats": {k: stats[k] for k in ("imported", "updated", "deactivated")},
            "updated_at": now_iso()}})
    return stats


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


@api.post("/appointments/{appt_id}/confirm")
async def confirm_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    appt = await db.appointments.find_one({"id": appt_id, "organization_id": _org(user)})
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt["status"] not in ("requested", "proposed"):
        raise HTTPException(status_code=400, detail=f"Cannot confirm an appointment that is {appt['status']}")
    await db.appointments.update_one({"id": appt_id}, {"$set": {"status": "confirmed",
        "confirmation_sent_at": now_iso(), "confirmed_by": user["id"], "updated_at": now_iso()}})
    await db.leads.update_one({"id": appt["lead_id"]}, {"$set": {"status": "appointment_confirmed"}})
    await audit(_org(user), "user", user["id"], "appointment", appt_id, "confirmed")
    await emit_event(_org(user), "appointment.confirmed", "appointment", appt_id)
    seller = await db.sellers.find_one({"id": appt["seller_id"]})
    if seller and seller.get("email"):
        await notify(_org(user), "seller", seller["email"], "email", "appointment_confirmation",
                     {"start_time": appt["start_time"]})
    return {"success": True}


class DeclineBody(BaseModel):
    reason: Optional[str] = None


@api.post("/appointments/{appt_id}/decline")
async def decline_appointment(appt_id: str, body: DeclineBody = DeclineBody(), user: dict = Depends(get_current_user)):
    appt = await db.appointments.find_one({"id": appt_id, "organization_id": _org(user)})
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    await db.appointments.update_one({"id": appt_id},
        {"$set": {"status": "declined", "decline_reason": body.reason, "updated_at": now_iso()}})
    await db.leads.update_one({"id": appt["lead_id"]}, {"$set": {"status": "appointment_declined"}})
    await audit(_org(user), "user", user["id"], "appointment", appt_id, "declined")
    return {"success": True}


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
        for l in ls:
            clean(l)
        lead_ids = [l["id"] for l in ls]
        seller_ids = list({l["seller_id"] for l in ls if l.get("seller_id")})
        smap = {s["id"]: s for s in await db.sellers.find({"id": {"$in": seller_ids}}).to_list(None)}
        vmap = {}
        for v in await db.seller_vehicles.find({"lead_id": {"$in": lead_ids}}).to_list(None):
            vmap.setdefault(v["lead_id"], v)
        out = []
        for l in ls:
            seller = smap.get(l.get("seller_id")) or {}
            v = vmap.get(l["id"]) or {}
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


# ---------------- dealer groups (partners) ----------------
def _feed_urls(source_id_token: str):
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    push = f"{base}/api/inventory/feed?token={source_id_token}" if base else f"/api/inventory/feed?token={source_id_token}"
    return {"push_url": push, "full_push_url": f"{push}&mode=full"}


class DealerGroupBody(BaseModel):
    name: str
    website: Optional[str] = None
    referral_amount: float = 0
    referral_program: Optional[str] = None
    locations: list = []
    status: str = "active"


@api.get("/dealer-groups")
async def list_dealer_groups(user: dict = Depends(get_current_user)):
    groups = await db.dealer_groups.find({"organization_id": _org(user)}).sort("created_at", 1).to_list(500)
    out = []
    for g in groups:
        clean(g)
        g["vehicle_count"] = await db.inventory_vehicles.count_documents(
            {"organization_id": _org(user), "dealer_group_id": g["id"], "status": "available"})
        g["source_count"] = await db.inventory_sources.count_documents(
            {"organization_id": _org(user), "dealer_group_id": g["id"]})
        out.append(g)
    return out


@api.post("/dealer-groups")
async def create_dealer_group(body: DealerGroupBody, user: dict = Depends(require_roles("dealership_admin"))):
    doc = {"id": new_id(), "organization_id": _org(user), "slug": body.name.lower().replace(" ", "-")[:40],
           "is_default": False, "created_at": now_iso(), "updated_at": now_iso(), **body.model_dump()}
    await db.dealer_groups.insert_one(dict(doc))
    return clean(doc)


@api.patch("/dealer-groups/{dg_id}")
async def update_dealer_group(dg_id: str, body: dict, user: dict = Depends(require_roles("dealership_admin"))):
    body.pop("id", None); body.pop("is_default", None)
    body["updated_at"] = now_iso()
    await db.dealer_groups.update_one({"id": dg_id, "organization_id": _org(user)}, {"$set": body})
    return clean(await db.dealer_groups.find_one({"id": dg_id}))


@api.delete("/dealer-groups/{dg_id}")
async def delete_dealer_group(dg_id: str, user: dict = Depends(require_roles("dealership_admin"))):
    dg = await db.dealer_groups.find_one({"id": dg_id, "organization_id": _org(user)})
    if dg and dg.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete the default dealer group")
    await db.dealer_groups.delete_one({"id": dg_id, "organization_id": _org(user)})
    await db.inventory_sources.delete_many({"dealer_group_id": dg_id, "organization_id": _org(user)})
    return {"success": True}


# ---------------- inventory sources (connectors) ----------------
class SourceBody(BaseModel):
    dealer_group_id: str
    name: str
    type: str  # csv_upload | http_feed | scraper | api
    config: dict = {}
    schedule: str = "every_6_hours"
    enabled: bool = True


def _source_out(s: dict):
    clean(s)
    if s.get("feed_token"):
        s.update(_feed_urls(s["feed_token"]))
        s.pop("feed_token", None)
    return s


@api.get("/inventory-sources")
async def list_sources(user: dict = Depends(get_current_user), dealer_group_id: Optional[str] = None):
    q = {"organization_id": _org(user)}
    if dealer_group_id:
        q["dealer_group_id"] = dealer_group_id
    rows = await db.inventory_sources.find(q).sort("created_at", 1).to_list(500)
    return [_source_out(r) for r in rows]


@api.post("/inventory-sources")
async def create_source(body: SourceBody, user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    if body.type not in ("csv_upload", "http_feed", "scraper", "api"):
        raise HTTPException(status_code=400, detail="Invalid source type")
    doc = {"id": new_id(), "organization_id": _org(user), "last_run_at": None, "last_status": "never",
           "last_stats": {}, "created_at": now_iso(), "updated_at": now_iso(), **body.model_dump()}
    if body.type == "csv_upload":
        doc["feed_token"] = secrets.token_urlsafe(24)
    await db.inventory_sources.insert_one(dict(doc))
    return _source_out(dict(doc))


@api.patch("/inventory-sources/{sid}")
async def update_source(sid: str, body: dict, user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    body.pop("id", None); body.pop("feed_token", None)
    body["updated_at"] = now_iso()
    await db.inventory_sources.update_one({"id": sid, "organization_id": _org(user)}, {"$set": body})
    return _source_out(await db.inventory_sources.find_one({"id": sid}))


@api.delete("/inventory-sources/{sid}")
async def delete_source(sid: str, user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    await db.inventory_sources.delete_one({"id": sid, "organization_id": _org(user)})
    return {"success": True}


@api.post("/inventory-sources/{sid}/run")
async def run_source(sid: str, user: dict = Depends(require_roles("dealership_admin", "dealership_manager"))):
    src = await db.inventory_sources.find_one({"id": sid, "organization_id": _org(user)})
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        stats = await run_source_sync(clean(dict(src)))
        status = "success" if not stats.get("skipped_reason") else "idle"
        await db.inventory_sources.update_one({"id": sid}, {"$set": {"last_run_at": now_iso(),
            "last_status": status, "last_stats": {k: stats.get(k, 0) for k in ("imported", "updated", "deactivated")},
            "updated_at": now_iso()}})
        return stats
    except Exception as e:
        await db.inventory_sources.update_one({"id": sid}, {"$set": {"last_run_at": now_iso(),
            "last_status": "failed", "last_error": str(e), "updated_at": now_iso()}})
        raise HTTPException(status_code=400, detail=f"Sync failed: {e}")


# ---------------- referrals ----------------
REFERRAL_STATUSES = ["identified", "sent", "accepted", "converted", "paid", "lost"]


@api.get("/referrals")
async def list_referrals(user: dict = Depends(get_current_user), status: Optional[str] = None):
    q = {"organization_id": _org(user)}
    if status:
        q["status"] = status
    rows = await db.referrals.find(q).sort("created_at", -1).to_list(1000)
    groups = {g["id"]: g for g in await db.dealer_groups.find({"organization_id": _org(user)}).to_list(500)}
    out = []
    for r in rows:
        clean(r)
        g = groups.get(r.get("dealer_group_id"))
        r["dealer_group_name"] = g["name"] if g else None
        out.append(r)
    totals = {"pipeline": sum(r.get("amount", 0) for r in out if r["status"] not in ("paid", "lost")),
              "earned": sum(r.get("amount", 0) for r in out if r["status"] == "paid"),
              "count": len(out)}
    return {"referrals": out, "totals": totals, "statuses": REFERRAL_STATUSES}


@api.patch("/referrals/{rid}")
async def update_referral(rid: str, body: dict, user: dict = Depends(get_current_user)):
    ref = await db.referrals.find_one({"id": rid, "organization_id": _org(user)})
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")
    updates = {"updated_at": now_iso()}
    for k in ("external_reference", "notes", "amount"):
        if k in body:
            updates[k] = body[k]
    if body.get("status") and body["status"] in REFERRAL_STATUSES:
        updates["status"] = body["status"]
        hist = ref.get("status_history", []) + [{"status": body["status"], "at": now_iso()}]
        updates["status_history"] = hist
    await db.referrals.update_one({"id": rid}, {"$set": updates})
    return clean(await db.referrals.find_one({"id": rid}))


# ---------------- cron: scheduled source sync ----------------
async def _sync_all_sources():
    sources = await db.inventory_sources.find({"enabled": True, "type": {"$in": ["http_feed", "scraper", "api"]}}).to_list(1000)
    for src in sources:
        try:
            stats = await run_source_sync(clean(dict(src)))
            status = "success" if not stats.get("skipped_reason") else "idle"
            await db.inventory_sources.update_one({"id": src["id"]}, {"$set": {"last_run_at": now_iso(),
                "last_status": status, "last_stats": {k: stats.get(k, 0) for k in ("imported", "updated", "deactivated")},
                "updated_at": now_iso()}})
        except Exception as e:
            await db.inventory_sources.update_one({"id": src["id"]}, {"$set": {"last_run_at": now_iso(),
                "last_status": "failed", "last_error": str(e), "updated_at": now_iso()}})


@api.post("/cron/sync-sources")
async def cron_sync_sources(request: Request, authorization: Optional[str] = Header(default=None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not secret or not token or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    asyncio.create_task(_sync_all_sources())
    return {"accepted": True}


app.include_router(auth_router)
app.include_router(api)

_cors_env = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_env,
    allow_origin_regex=r"https://([a-z0-9-]+\.)*(autonovaia\.ca|onrender\.com|ravijha\.co)$",
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.organizations.create_index("slug", unique=True)
    await db.leads.create_index([("organization_id", 1), ("status", 1)])
    await db.messages.create_index("conversation_id")
    await db.sellers.create_index("id")
    await db.seller_vehicles.create_index("lead_id")
    await db.appointments.create_index("lead_id")
    await db.appointments.create_index([("organization_id", 1), ("status", 1)])
    await db.inventory_vehicles.create_index([("organization_id", 1), ("dealer_group_id", 1)])
    await db.inventory_sources.create_index("feed_token")
    await db.referrals.create_index([("organization_id", 1), ("status", 1)])
    await seed_demo()
    await _migrate_dealer_groups()
    await _seed_consent_agreements()
    logger.info("Startup complete")


CONSENT_EN = (
    "AutoNova AI — Consent to Share Your Information\n\n"
    "AutoNova AI is an independent service that helps you find a suitable vehicle and connects you with "
    "participating dealerships. To put you in contact with {{recipient}}, we need your permission to share the "
    "information you provided in this conversation.\n\n"
    "What will be shared: your contact details (name, phone, email), your vehicle preferences and budget, and a "
    "summary of this conversation.\n\n"
    "Who receives it: {{recipient}}.\n\n"
    "Why: so the dealership can follow up about the vehicle you're interested in and arrange an appointment.\n\n"
    "How it's used: only to contact you about this request. We do not sell your information. You can withdraw your "
    "consent at any time by contacting AutoNova AI, subject to applicable law.\n\n"
    "By accepting, you agree to share the information above with the named dealership. If you decline, your personal "
    "information will not be forwarded.")

CONSENT_FR = (
    "AutoNova AI — Consentement au partage de vos renseignements\n\n"
    "AutoNova AI est un service indépendant qui vous aide à trouver un véhicule adapté et vous met en relation avec "
    "des concessionnaires partenaires. Pour vous mettre en contact avec {{recipient}}, nous avons besoin de votre "
    "autorisation pour partager les renseignements fournis dans cette conversation.\n\n"
    "Ce qui sera partagé : vos coordonnées (nom, téléphone, courriel), vos préférences de véhicule et votre budget, "
    "ainsi qu'un résumé de cette conversation.\n\n"
    "Qui les reçoit : {{recipient}}.\n\n"
    "Pourquoi : afin que le concessionnaire puisse faire un suivi concernant le véhicule qui vous intéresse et "
    "organiser un rendez-vous.\n\n"
    "Utilisation : uniquement pour vous contacter au sujet de cette demande. Nous ne vendons pas vos renseignements. "
    "Vous pouvez retirer votre consentement en tout temps en communiquant avec AutoNova AI, sous réserve de la loi "
    "applicable.\n\n"
    "En acceptant, vous consentez à partager les renseignements ci-dessus avec le concessionnaire nommé. Si vous "
    "refusez, vos renseignements personnels ne seront pas transmis.")


async def _seed_consent_agreements():
    for lang, text in (("en", CONSENT_EN), ("fr", CONSENT_FR)):
        if not await db.consent_agreement_versions.find_one({"language": lang, "active": True}):
            await db.consent_agreement_versions.insert_one({"id": new_id(), "version": "1.0", "language": lang,
                "body_text": text, "active": True, "created_at": now_iso()})


async def _migrate_dealer_groups():
    """Ensure every org has a default dealer group and existing inventory is assigned to it."""
    orgs = await db.organizations.find({}).to_list(1000)
    for org in orgs:
        dg_id = await _default_dealer_group_id(org["id"])
        await db.inventory_vehicles.update_many(
            {"organization_id": org["id"], "dealer_group_id": {"$exists": False}},
            {"$set": {"dealer_group_id": dg_id}})


@app.on_event("shutdown")
async def shutdown():
    from db import client
    client.close()
