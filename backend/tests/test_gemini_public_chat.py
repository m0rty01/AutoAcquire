"""Tests for the public seller AI chat using direct Google Gemini API.

Verifies that the /api/public/{slug}/conversations flow calls the real
Gemini SDK (not the Emergent LLM key) and does NOT fall back to the
human-review placeholder message.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    "https://dealer-lead-hub.preview.emergentagent.com"
SLUG = "prestige-auto-toronto"

FALLBACK_SNIPPET = "having trouble processing that right now"


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def conversation(http):
    """Start a fresh public conversation on prestige-auto-toronto."""
    r = http.post(f"{BASE_URL}/api/public/{SLUG}/conversations",
                  json={"consent": True}, timeout=30)
    assert r.status_code == 200, f"start conv failed: {r.status_code} {r.text}"
    data = r.json()
    assert "conversation_id" in data and "lead_id" in data
    assert isinstance(data.get("messages"), list) and len(data["messages"]) >= 1
    # First message must be the AI greeting
    greet = data["messages"][0]
    assert greet["sender_type"] == "ai"
    assert "virtual vehicle assistant" in greet["content"].lower()
    return data


# ----- Direct Gemini chat: real AI response, no fallback -----

def _send(http, conv_id, content):
    r = http.post(
        f"{BASE_URL}/api/public/{SLUG}/conversations/{conv_id}/messages",
        json={"content": content},
        timeout=60,
    )
    return r


def test_dealer_slug_resolves(http):
    r = http.get(f"{BASE_URL}/api/public/{SLUG}", timeout=15)
    assert r.status_code == 200
    body = r.json()
    org = body.get("organization") or {}
    assert org.get("name")
    assert org.get("slug") == SLUG


def test_first_seller_message_returns_real_gemini_reply(http, conversation):
    conv_id = conversation["conversation_id"]
    seller_msg = ("Hi, I want to sell my 2021 Toyota RAV4 with 42000 km, "
                  "fully paid off")
    r = _send(http, conv_id, seller_msg)
    assert r.status_code == 200, f"post message failed: {r.status_code} {r.text}"
    data = r.json()

    # Must remain AI-active (not routed to human review)
    assert data.get("ai_active") is True, f"AI got deactivated: {data}"

    msgs = data.get("messages") or []
    assert len(msgs) >= 3, f"expected greeting+seller+ai, got {len(msgs)}: {msgs}"

    ai_msgs = [m for m in msgs if m["sender_type"] == "ai"]
    assert len(ai_msgs) >= 2, "no AI reply after seller message"
    latest_ai = ai_msgs[-1]

    content = latest_ai["content"]
    # Not the fallback / human-review placeholder
    assert FALLBACK_SNIPPET not in content.lower(), (
        f"AI returned fallback message (Gemini call likely failed): {content}"
    )
    assert len(content.strip()) > 5

    # Confirm the message is stored with the Gemini provider + configured model
    assert latest_ai.get("model_provider") == "gemini", latest_ai
    expected_model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    # Backend snapshots MODEL_NAME at import — check it matches env value
    assert latest_ai.get("model_name") == expected_model, latest_ai

    # Reply should be relevant — reference vehicle or ask a sensible follow-up
    lower = content.lower()
    relevant = any(kw in lower for kw in [
        "rav4", "toyota", "vehicle", "car", "mileage", "km", "condition",
        "appraisal", "trade", "sell", "appointment", "contact", "phone",
        "email", "name", "great", "thanks",
    ])
    assert relevant, f"AI reply doesn't look contextual: {content}"

    # next_action should be one of the valid orchestrator actions
    assert data.get("next_action") in {
        "ask_question", "confirm_information", "request_contact_information",
        "run_qualification", "run_inventory_match", "offer_appointment",
        "request_human", "end_conversation", "no_action",
    }


def test_multiturn_followup_progresses(http, conversation):
    """Provide a phone number and check the AI continues coherently and
    ideally progresses toward contact capture or appointment."""
    conv_id = conversation["conversation_id"]

    # Small pause so timestamps order cleanly and to avoid burst-rate
    time.sleep(1)

    r = _send(http, conv_id, "Sure — you can reach me at 416-555-0198. "
                             "The RAV4 is in great condition, no accidents.")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ai_active") is True

    msgs = data.get("messages") or []
    ai_msgs = [m for m in msgs if m["sender_type"] == "ai"]
    assert len(ai_msgs) >= 3, "expected at least 3 AI messages after 2 turns"

    latest_ai = ai_msgs[-1]
    assert FALLBACK_SNIPPET not in latest_ai["content"].lower(), (
        f"Fallback returned on turn 2: {latest_ai['content']}"
    )
    assert latest_ai.get("model_provider") == "gemini"
    assert latest_ai.get("model_name") == os.environ.get(
        "GEMINI_MODEL", "gemini-flash-latest")

    # Verify lead now has phone extracted or intent captured
    # Fetch conversation state via GET
    g = http.get(f"{BASE_URL}/api/public/{SLUG}/conversations/{conv_id}",
                 timeout=15)
    assert g.status_code == 200
    conv_body = g.json()
    all_msgs = conv_body.get("messages", [])
    # last message should be an AI message with structured_payload (if valid Gemini)
    ai_with_payload = [m for m in all_msgs
                       if m["sender_type"] == "ai" and m.get("structured_payload")]
    assert ai_with_payload, "no AI message stored with structured_payload — Gemini JSON parse likely failed"

    payload = ai_with_payload[-1]["structured_payload"]
    # sellerMessageInterpretation should exist
    assert "sellerMessageInterpretation" in payload
    assert "nextAction" in payload
    # Sensible progression: contact should be recognised / appointment offered soon
    assert payload["nextAction"] in {
        "ask_question", "confirm_information", "request_contact_information",
        "run_qualification", "run_inventory_match", "offer_appointment",
        "request_human", "end_conversation", "no_action",
    }
