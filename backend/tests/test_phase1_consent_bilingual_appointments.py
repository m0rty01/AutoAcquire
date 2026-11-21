"""Phase 1: bilingual greeting, consent gating for referrals, requested->confirmed appointments."""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient


def _env(path, key):
    for line in open(path):
        if line.strip().startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env("/app/frontend/.env", "REACT_APP_BACKEND_URL")).rstrip("/")
SLUG = "prestige-auto-toronto"
PUB = f"{BASE_URL}/api/public/{SLUG}"
mdb = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]

CREATED = {"convs": [], "leads": []}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@autoacquire.ai", "password": "Admin123!"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    leads = CREATED["leads"]
    convs = CREATED["convs"]
    sellers = [l["seller_id"] for l in mdb.leads.find({"id": {"$in": leads}})]
    for coll in ["inventory_matches", "referrals", "consent_records", "appointments", "inventory_preferences",
                 "seller_vehicles", "lead_scores"]:
        mdb[coll].delete_many({"lead_id": {"$in": leads}})
    mdb.messages.delete_many({"conversation_id": {"$in": convs}})
    mdb.conversations.delete_many({"id": {"$in": convs}})
    mdb.leads.delete_many({"id": {"$in": leads}})
    mdb.sellers.delete_many({"id": {"$in": sellers}})


def _start(lang):
    r = requests.post(f"{PUB}/conversations", json={"consent": True, "language": lang}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED["convs"].append(d["conversation_id"])
    CREATED["leads"].append(d["lead_id"])
    mdb.sellers.update_one({"id": mdb.leads.find_one({"id": d["lead_id"]})["seller_id"]},
                           {"$set": {"first_name": "TEST_Phase1", "email": "test_phase1@example.com"}})
    return d


def _seed_match(lead_id):
    org = mdb.organizations.find_one({"slug": SLUG})
    v = mdb.inventory_vehicles.find_one({"organization_id": org["id"], "status": "available",
                                         "dealer_group_id": {"$ne": None}})
    assert v, "need inventory vehicle with dealer group"
    mdb.inventory_matches.insert_one({"id": str(uuid.uuid4()), "organization_id": org["id"], "lead_id": lead_id,
        "inventory_vehicle_id": v["id"], "dealer_group_id": v["dealer_group_id"], "match_score": 90,
        "ranking": 1, "match_reasons": ["test"], "conflicts": [], "generated_at": "2026-01-01T00:00:00"})
    return v


# Greeting language
class TestGreeting:
    def test_en_greeting_buyer_oriented(self):
        d = _start("en")
        g = d["messages"][0]["content"].lower()
        assert "buy" in g and ("sell" in g or "trade" in g)

    def test_fr_greeting(self):
        d = _start("fr")
        g = d["messages"][0]["content"]
        assert "Bonjour" in g and "acheter" in g
        conv = requests.get(f"{PUB}/conversations/{d['conversation_id']}", timeout=30).json()
        assert conv["conversation"]["language"] == "fr"

    def test_invalid_language_falls_back_en(self):
        d = _start("de")
        assert d["messages"][0]["content"].startswith("Hi")


# Consent gating
class TestConsent:
    def test_agreement_fr_and_en(self):
        d = _start("fr")
        _seed_match(d["lead_id"])
        fr = requests.get(f"{PUB}/conversations/{d['conversation_id']}/consent-agreement",
                          params={"language": "fr"}, timeout=30).json()
        assert fr["language"] == "fr" and "consent" in fr["body_text"].lower()
        assert "{{recipient}}" not in fr["body_text"]
        assert fr["recipient"]["dealer_group_id"]
        en = requests.get(f"{PUB}/conversations/{d['conversation_id']}/consent-agreement",
                          params={"language": "en"}, timeout=30).json()
        assert en["body_text"] != fr["body_text"]

    def test_no_referral_before_consent_then_accept(self):
        d = _start("en")
        v = _seed_match(d["lead_id"])
        assert mdb.referrals.count_documents({"lead_id": d["lead_id"]}) == 0
        r = requests.post(f"{PUB}/conversations/{d['conversation_id']}/consent", json={"accepted": True}, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "accepted"
        assert r.json()["shared_with"] == v["dealer_group_id"]
        ref = mdb.referrals.find_one({"lead_id": d["lead_id"]})
        assert ref and ref["status"] == "sent"
        lead = mdb.leads.find_one({"id": d["lead_id"]})
        assert lead["status"] == "sent_to_dealership" and lead["consent_status"] == "granted"

    def test_decline_creates_no_referral(self):
        d = _start("en")
        _seed_match(d["lead_id"])
        r = requests.post(f"{PUB}/conversations/{d['conversation_id']}/consent", json={"accepted": False}, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "declined"
        assert mdb.referrals.count_documents({"lead_id": d["lead_id"]}) == 0
        assert mdb.consent_records.find_one({"lead_id": d["lead_id"]})["status"] == "declined"
        assert mdb.leads.find_one({"id": d["lead_id"]})["consent_status"] == "declined"

    def test_consent_unknown_conv_404(self):
        r = requests.post(f"{PUB}/conversations/nope/consent", json={"accepted": True}, timeout=30)
        assert r.status_code == 404


# Appointments requested -> confirmed/declined
class TestAppointments:
    def _book(self):
        d = _start("en")
        slots = requests.get(f"{PUB}/conversations/{d['conversation_id']}/appointments/availability", timeout=30).json()["slots"]
        assert slots
        s = slots[-1]
        r = requests.post(f"{PUB}/conversations/{d['conversation_id']}/appointments",
                          json={"start_time": s["start_time"], "end_time": s["end_time"],
                                "appointment_type": s.get("appointment_type", "in_person_appraisal")}, timeout=30)
        assert r.status_code == 200, r.text
        return d, r.json(), s

    def test_book_requested_and_confirm(self, admin):
        d, data, _ = self._book()
        appt = data["appointment"]
        assert appt["status"] == "requested"
        assert mdb.leads.find_one({"id": d["lead_id"]})["status"] == "appointment_requested"
        lst = admin.get(f"{BASE_URL}/api/appointments").json()
        assert any(a["id"] == appt["id"] and a["status"] == "requested" for a in lst)
        r = admin.post(f"{BASE_URL}/api/appointments/{appt['id']}/confirm")
        assert r.status_code == 200
        assert mdb.appointments.find_one({"id": appt["id"]})["status"] == "confirmed"
        assert mdb.leads.find_one({"id": d["lead_id"]})["status"] == "appointment_confirmed"

    def test_book_and_decline(self, admin):
        d, data, _ = self._book()
        r = admin.post(f"{BASE_URL}/api/appointments/{data['appointment']['id']}/decline", json={"reason": "TEST"})
        assert r.status_code == 200
        assert mdb.appointments.find_one({"id": data["appointment"]["id"]})["status"] == "declined"

    def test_requested_slot_hidden_from_availability(self):
        d, data, s = self._book()
        slots = requests.get(f"{PUB}/conversations/{d['conversation_id']}/appointments/availability", timeout=30).json()["slots"]
        assert s["start_time"] not in [x["start_time"] for x in slots]

    def test_double_request_same_slot_rejected(self):
        d, data, s = self._book()
        d2 = _start("en")
        r = requests.post(f"{PUB}/conversations/{d2['conversation_id']}/appointments",
                          json={"start_time": s["start_time"], "end_time": s["end_time"]}, timeout=30)
        assert r.status_code == 409, f"double-booking same slot allowed: {r.status_code}"

    def test_confirm_unknown_404(self, admin):
        assert admin.post(f"{BASE_URL}/api/appointments/nope/confirm").status_code == 404

    def test_decline_unknown_404(self, admin):
        assert admin.post(f"{BASE_URL}/api/appointments/nope/decline").status_code == 404

    def test_confirm_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/appointments/x/confirm", timeout=30).status_code in (401, 403)


# Regression: admin list endpoints
@pytest.mark.parametrize("path", ["/api/dashboard/home", "/api/leads", "/api/inventory", "/api/dealer-groups",
                                  "/api/referrals", "/api/appointments"])
def test_admin_endpoints(admin, path):
    r = admin.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code}"
