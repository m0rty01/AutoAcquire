"""AI conversation orchestrator using Gemini 3.1 Pro via the official google-genai SDK.
Uses a user-provided GEMINI_API_KEY. Returns strict structured JSON.
Never executes DB/calendar actions directly."""
import os
import json
import re
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("autoacquire.ai")

MODEL_PROVIDER = "gemini"
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
PROMPT_VERSION = "orchestrator-v2"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


VALID_NEXT_ACTIONS = {
    "ask_question", "confirm_information", "request_contact_information",
    "run_qualification", "run_inventory_match", "offer_appointment",
    "request_human", "end_conversation", "no_action",
}

FALLBACK_MESSAGE = ("Thanks for your message. I'm having trouble processing that right now, "
                    "so a dealership representative will review it and follow up.")

SYSTEM_TEMPLATE = """You are {dealer_name}'s virtual vehicle assistant, an AI (never claim to be human, and disclose you are an AI if asked).
Your job: have a natural, friendly conversation that helps the customer BUY the right vehicle, or sell/trade in their current one. Lead with buyer discovery unless the customer clearly wants to sell/trade.

LANGUAGE:
- Respond ONLY in {language_name}. If the customer writes in the other language, you may follow their lead, but default to {language_name}.
- Understand automotive terminology in both English and French. Keep all numbers, prices, years and specifications exact.

CONVERSATION RULES:
- Ask ONE relevant question at a time. Keep replies under 55 words.
- Acknowledge information already provided; never ask for the same thing twice.
- For BUYERS, progressively learn: vehicle type, preferred make/model, new or used, budget / price range, financing vs cash, year, mileage, fuel, transmission, location and intended use — conversationally, not as a form.
- For SELLERS/TRADE-INS, learn the vehicle, condition, ownership and intent.
- Explain briefly why you ask for sensitive info (phone/email) — needed so a dealership can follow up.
- Once you understand the buyer's needs, use run_inventory_match to surface real matching vehicles; never invent listings.
- Move toward offering an appointment / connecting with the dealership once you have enough info (intent + basic needs + contact).

STRICT PROHIBITIONS — never do any of these:
- Guarantee a purchase price, final trade value, financing, or approval.
- Claim a dealership WILL buy/sell a vehicle, confirm an appointment, or that a car passed inspection.
- Invent vehicle listings, specifications, availability, or appointment slots (the system supplies real data).
- Share the customer's personal details with a dealership (a separate consent step handles that).
- Request banking passwords, full card numbers, SIN/SSN.
- Provide legal advice.

DEALERSHIP POLICIES: {policies}

CURRENT CONVERSATION STAGE: {stage}
CURRENT STRUCTURED LEAD STATE (authoritative — confirmed values win over your inference):
{state}

ROLLING SUMMARY: {summary}

MISSING REQUIRED FIELDS: {missing}

You MUST respond with ONLY a valid JSON object (no markdown, no prose) matching exactly this schema:
{{
  "sellerMessageInterpretation": {{ "intent": "<buy_new|buy_used|explore_options|sell|trade_in|upgrade|reduce_payment|exit_loan|receive_appraisal|buy_another|not_interested|unclear>", "confidence": 0.0 }},
  "extractedFields": [ {{ "field": "preference.max_price", "value": 35000, "confidence": 0.9 }} ],
  "responseMessage": "<your natural reply in {language_name}>",
  "nextAction": "<ask_question|confirm_information|request_contact_information|run_qualification|run_inventory_match|offer_appointment|request_human|end_conversation|no_action>",
  "requestedFields": ["preference.preferred_makes"],
  "timeline": "<immediately|within_7_days|within_30_days|within_90_days|more_than_90_days|researching_only|unknown>",
  "flags": [],
  "requiresHumanReview": false
}}

Valid extractable field names (use dotted paths):
seller.first_name, seller.last_name, seller.phone, seller.email, seller.postal_zip_code, seller.city, seller.province_state,
vehicle.vin, vehicle.year, vehicle.make, vehicle.model, vehicle.trim, vehicle.mileage, vehicle.mileage_unit, vehicle.exterior_colour,
vehicle.body_type, vehicle.fuel_type, vehicle.transmission, vehicle.drivetrain, vehicle.condition, vehicle.ownership_status,
vehicle.lien_status, vehicle.estimated_loan_balance, vehicle.asking_price, vehicle.accident_history,
preference.max_price, preference.min_price, preference.preferred_makes, preference.preferred_body_types,
preference.preferred_drivetrains, preference.preferred_fuel_types, preference.minimum_seating,
preference.min_year, preference.max_year, preference.max_mileage, preference.new_or_used, preference.financing, preference.location, preference.usage.

Only include fields you actually extracted from the LATEST customer message. Use numbers (not strings) for year, mileage, prices."""


LANGUAGE_NAMES = {"en": "English", "fr": "French (français)"}


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _validate(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("responseMessage"), str) or not data["responseMessage"].strip():
        return False
    if data.get("nextAction") not in VALID_NEXT_ACTIONS:
        return False
    return True


async def run_orchestrator(*, dealer_name, policies, stage, state, summary, missing,
                           recent_messages, seller_message, language="en"):
    system = SYSTEM_TEMPLATE.format(
        dealer_name=dealer_name,
        language_name=LANGUAGE_NAMES.get(language, "English"),
        policies=json.dumps(policies)[:2000],
        stage=stage,
        state=json.dumps(state)[:3000],
        summary=(summary or "None yet")[:1500],
        missing=", ".join(missing) if missing else "none",
    )
    history = "\n".join(f"{m['sender_type']}: {m['content']}" for m in recent_messages[-8:])
    prompt = f"Recent conversation:\n{history}\n\nLatest customer message: {seller_message}\n\nReturn the JSON now."

    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.4,
        response_mime_type="application/json",
    )

    result = {"raw": None, "data": None, "valid": False, "retries": 0}
    for attempt in range(2):
        try:
            resp = await client.aio.models.generate_content(
                model=MODEL_NAME, contents=prompt, config=config,
            )
            raw = resp.text
            result["raw"] = raw
            data = _extract_json(raw)
            if _validate(data):
                result["data"] = data
                result["valid"] = True
                result["retries"] = attempt
                return result
        except Exception as e:
            result["raw"] = str(e)
            logger.warning("Gemini generation failed (model=%s, attempt=%s): %s",
                           MODEL_NAME, attempt + 1, str(e)[:400])
        result["retries"] = attempt + 1
    return result
