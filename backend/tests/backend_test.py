"""AutoAcquire AI — backend integration tests (pytest).
Covers auth, tenant isolation, public seller chat, leads, inventory, appointments, analytics, RBAC, platform admin.
"""
import os
import io
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dealer-lead-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
SLUG = "prestige-auto-toronto"

ADMIN = {"email": "admin@autoacquire.ai", "password": "Admin123!"}
MANAGER = {"email": "manager@autoacquire.ai", "password": "Manager123!"}
REP = {"email": "rep1@autoacquire.ai", "password": "Rep123!"}
PLATFORM = {"email": "platform@autoacquire.ai", "password": "Platform123!"}


# ---------- fixtures ----------
def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text[:200]}"
    return r.json()


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)["token"]


@pytest.fixture(scope="session")
def rep_token():
    return _login(REP)["token"]


@pytest.fixture(scope="session")
def platform_token():
    return _login(PLATFORM)["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- auth ----------
class TestAuth:
    def test_login_success(self):
        data = _login(ADMIN)
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["user"]["email"] == ADMIN["email"]
        assert data["user"]["role"] == "dealership_admin"
        assert data["user"]["organization_id"]

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN["email"], "password": "wrong"})
        assert r.status_code == 401

    def test_me_endpoint(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=_h(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == ADMIN["email"]
        assert body["organization"]["slug"] == SLUG

    def test_me_no_token(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401


# ---------- tenant isolation & platform ----------
class TestRBAC:
    def test_platform_orgs_admin_denied(self, admin_token):
        r = requests.get(f"{API}/platform/organizations", headers=_h(admin_token))
        assert r.status_code == 403

    def test_platform_orgs_platform_ok(self, platform_token):
        r = requests.get(f"{API}/platform/organizations", headers=_h(platform_token))
        assert r.status_code == 200
        orgs = r.json()
        assert isinstance(orgs, list) and len(orgs) >= 1
        assert any(o.get("slug") == SLUG for o in orgs)
        # counts present
        assert "lead_count" in orgs[0] and "user_count" in orgs[0]

    def test_rep_cannot_create_rule(self, rep_token):
        r = requests.post(f"{API}/qualification-rules",
                          headers=_h(rep_token),
                          json={"name": "TEST_rule", "field_name": "vehicle.year",
                                "operator": "greater_than_or_equal", "comparison_value": 2010,
                                "success_result": "qualified", "failure_result": "partially_qualified"})
        assert r.status_code == 403


# ---------- public seller chat (AI) ----------
class TestPublicChat:
    convo_id = None
    lead_id = None

    def test_public_dealer_info(self):
        r = requests.get(f"{API}/public/{SLUG}")
        assert r.status_code == 200
        body = r.json()
        assert body["organization"]["slug"] == SLUG

    def test_start_conversation(self):
        r = requests.post(f"{API}/public/{SLUG}/conversations", json={"consent": True}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("conversation_id") and body.get("lead_id")
        assert isinstance(body.get("messages"), list) and len(body["messages"]) >= 1
        assert body["messages"][0]["sender_type"] == "ai"
        TestPublicChat.convo_id = body["conversation_id"]
        TestPublicChat.lead_id = body["lead_id"]

    def test_send_seller_message_ai_replies(self):
        assert TestPublicChat.convo_id, "start conversation must run first"
        msg = "Hi, I want to trade in my 2021 Toyota RAV4 XLE, 84000 km, still owe 14000, for a 3-row AWD SUV under 35000. My phone is 4165551234, name John Smith, postal M5V2T6, email john@example.com."
        r = requests.post(f"{API}/public/{SLUG}/conversations/{TestPublicChat.convo_id}/messages",
                          json={"content": msg}, timeout=90)
        assert r.status_code == 200, r.text[:400]
        body = r.json()
        assert body.get("ai_active") is True
        # at least 3 messages now (greeting, seller, ai)
        assert len(body["messages"]) >= 3
        # last message should be from ai
        ai_msgs = [m for m in body["messages"] if m["sender_type"] == "ai"]
        assert len(ai_msgs) >= 2
        # next_action must be a known action string OR None if fallback fired
        na = body.get("next_action")
        if na is not None:
            assert isinstance(na, str)

    def test_lead_updated_from_ai_extraction(self, admin_token):
        """After AI processing, the lead's seller_vehicles and score should be updated."""
        assert TestPublicChat.lead_id
        # Give AI a small buffer
        time.sleep(1)
        r = requests.get(f"{API}/leads/{TestPublicChat.lead_id}", headers=_h(admin_token))
        # Lead may be excluded from listing (is_test False by default) but direct GET works
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # score should have been recalculated (>0 or explanation present)
        assert body.get("score") is not None, "score missing"
        assert body["score"].get("total_score") is not None
        # vehicle fields should be present (make/model/year)
        veh = body.get("vehicle") or {}
        # Extraction is AI-dependent so we just assert something got saved (make or model)
        has_extracted = any(veh.get(k) for k in ["make", "model", "year", "mileage"])
        assert has_extracted, f"AI did not extract vehicle fields: vehicle={veh}"


# ---------- leads ----------
class TestLeads:
    def test_dashboard_home(self, admin_token):
        r = requests.get(f"{API}/dashboard/home", headers=_h(admin_token))
        assert r.status_code == 200
        b = r.json()
        for k in ["new_leads", "hot_leads", "review_leads", "today_appointments"]:
            assert k in b and isinstance(b[k], list)

    def test_list_leads(self, admin_token):
        r = requests.get(f"{API}/leads", headers=_h(admin_token))
        assert r.status_code == 200
        b = r.json()
        assert "items" in b and "total" in b
        assert isinstance(b["items"], list)

    def test_filter_by_score_band(self, admin_token):
        r = requests.get(f"{API}/leads?score_band=hot", headers=_h(admin_token))
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["score_band"] == "hot"

    def test_lead_detail(self, admin_token):
        # get first lead id
        lst = requests.get(f"{API}/leads", headers=_h(admin_token)).json()["items"]
        if not lst:
            pytest.skip("no leads seeded")
        lid = lst[0]["id"]
        r = requests.get(f"{API}/leads/{lid}", headers=_h(admin_token))
        assert r.status_code == 200
        b = r.json()
        for k in ["lead", "seller", "vehicle", "conversation", "messages", "score", "matches", "notes", "activity"]:
            assert k in b

    def test_recalculate_score_is_deterministic(self, admin_token):
        lst = requests.get(f"{API}/leads", headers=_h(admin_token)).json()["items"]
        if not lst:
            pytest.skip("no leads")
        lid = lst[0]["id"]
        r1 = requests.post(f"{API}/leads/{lid}/recalculate-score", headers=_h(admin_token))
        assert r1.status_code == 200
        s1 = r1.json()["score"]
        r2 = requests.post(f"{API}/leads/{lid}/recalculate-score", headers=_h(admin_token))
        s2 = r2.json()["score"]
        assert s1["total_score"] == s2["total_score"], "score not deterministic"
        assert s1["score_band"] == s2["score_band"]

    def test_vehicle_correction_triggers_recalc(self, admin_token):
        lst = requests.get(f"{API}/leads", headers=_h(admin_token)).json()["items"]
        if not lst:
            pytest.skip("no leads")
        lid = lst[0]["id"]
        r = requests.patch(f"{API}/leads/{lid}/vehicle",
                           headers=_h(admin_token),
                           json={"fields": {"condition": "excellent"}})
        assert r.status_code == 200
        # verify audit event exists
        detail = requests.get(f"{API}/leads/{lid}", headers=_h(admin_token)).json()
        assert any(a.get("action") == "manual_correction" for a in detail["activity"])

    def test_takeover_and_resume(self, admin_token):
        lst = requests.get(f"{API}/leads", headers=_h(admin_token)).json()["items"]
        if not lst:
            pytest.skip("no leads")
        lid = lst[0]["id"]
        r = requests.post(f"{API}/leads/{lid}/takeover", headers=_h(admin_token))
        assert r.status_code == 200
        det = requests.get(f"{API}/leads/{lid}", headers=_h(admin_token)).json()
        assert det["conversation"]["ai_active"] is False
        assert det["lead"]["status"] == "human_takeover"
        # manual message
        mr = requests.post(f"{API}/leads/{lid}/messages",
                           headers=_h(admin_token), json={"content": "TEST_manual_msg"})
        assert mr.status_code == 200
        assert any(m["content"] == "TEST_manual_msg" and m["sender_type"] == "human_agent"
                   for m in mr.json()["messages"])
        rr = requests.post(f"{API}/leads/{lid}/resume-ai", headers=_h(admin_token))
        assert rr.status_code == 200
        det2 = requests.get(f"{API}/leads/{lid}", headers=_h(admin_token)).json()
        assert det2["conversation"]["ai_active"] is True

    def test_run_inventory_match(self, admin_token):
        lst = requests.get(f"{API}/leads", headers=_h(admin_token)).json()["items"]
        if not lst:
            pytest.skip("no leads")
        # find a lead that has preference — try first few
        for it in lst[:5]:
            r = requests.post(f"{API}/leads/{it['id']}/run-inventory-match", headers=_h(admin_token))
            assert r.status_code == 200
            if r.json().get("matches"):
                return
        # ok if none matched (no preferences)


# ---------- inventory ----------
class TestInventory:
    def test_list_inventory(self, admin_token):
        r = requests.get(f"{API}/inventory", headers=_h(admin_token))
        assert r.status_code == 200
        b = r.json()
        assert b["total"] >= 1
        item = b["items"][0]
        assert item.get("make") and item.get("model")
        assert "_id" not in item  # mongo id should be stripped

    def test_template_csv(self):
        r = requests.get(f"{API}/inventory/template")
        assert r.status_code == 200
        assert "stock_number" in r.text and "make" in r.text

    def test_csv_import(self, admin_token):
        csv_data = ("stock_number,vin,year,make,model,trim,price,mileage,body_type,fuel_type,transmission,drivetrain,exterior_colour,seating_capacity,location,status,vehicle_url,image_url\n"
                    "TEST_A1,VIN_TEST_1,2022,Honda,CR-V,EX,32000,25000,SUV,gas,automatic,AWD,Silver,5,Main,available,,\n"
                    "TEST_BAD,,2021,,,EX,,,,,,,,,,,,\n")
        files = {"file": ("inv.csv", csv_data, "text/csv")}
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/inventory/import", files=files, headers=headers)
        assert r.status_code == 200, r.text[:300]
        b = r.json()
        assert b["imported"] + b["updated"] >= 1
        assert isinstance(b["errors"], list) and len(b["errors"]) >= 1

    def test_rep_cannot_import(self, rep_token):
        files = {"file": ("inv.csv", "stock_number,make,model,year,price\n", "text/csv")}
        headers = {"Authorization": f"Bearer {rep_token}"}
        r = requests.post(f"{API}/inventory/import", files=files, headers=headers)
        assert r.status_code == 403


# ---------- qualification rules ----------
class TestRules:
    def test_admin_can_crud_rule(self, admin_token):
        # list
        r = requests.get(f"{API}/qualification-rules", headers=_h(admin_token))
        assert r.status_code == 200
        # create
        payload = {"name": "TEST_min_year", "field_name": "vehicle.year",
                   "operator": "greater_than_or_equal", "comparison_value": 2005,
                   "success_result": "qualified", "failure_result": "partially_qualified",
                   "score_adjustment": -10, "priority": 200}
        c = requests.post(f"{API}/qualification-rules", headers=_h(admin_token), json=payload)
        assert c.status_code == 200
        rule_id = c.json()["id"]
        # patch
        p = requests.patch(f"{API}/qualification-rules/{rule_id}", headers=_h(admin_token), json={"priority": 250})
        assert p.status_code == 200
        # delete
        d = requests.delete(f"{API}/qualification-rules/{rule_id}", headers=_h(admin_token))
        assert d.status_code == 200


# ---------- appointments ----------
class TestAppointments:
    def test_list_appointments(self, admin_token):
        r = requests.get(f"{API}/appointments", headers=_h(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_availability_and_book_then_conflict(self):
        # start fresh convo
        start = requests.post(f"{API}/public/{SLUG}/conversations", json={"consent": True}, timeout=15)
        conv_id = start.json()["conversation_id"]
        # get slots
        av = requests.get(f"{API}/public/{SLUG}/conversations/{conv_id}/appointments/availability")
        assert av.status_code == 200
        slots = av.json().get("slots", [])
        if not slots:
            pytest.skip("no availability slots generated")
        slot = slots[0]
        book1 = requests.post(f"{API}/public/{SLUG}/conversations/{conv_id}/appointments",
                              json={"start_time": slot["start_time"], "end_time": slot["end_time"]})
        assert book1.status_code == 200, book1.text[:300]
        body = book1.json()
        assert body["appointment"]["status"] == "confirmed"
        # try to double book same slot with a NEW conversation → expect 409
        start2 = requests.post(f"{API}/public/{SLUG}/conversations", json={"consent": True})
        cid2 = start2.json()["conversation_id"]
        book2 = requests.post(f"{API}/public/{SLUG}/conversations/{cid2}/appointments",
                              json={"start_time": slot["start_time"], "end_time": slot["end_time"]})
        assert book2.status_code == 409


# ---------- analytics ----------
class TestAnalytics:
    def test_overview(self, admin_token):
        r = requests.get(f"{API}/analytics/overview", headers=_h(admin_token))
        assert r.status_code == 200
        b = r.json()
        for k in ["total_leads", "qualification_rate", "hot_leads", "score_band_distribution"]:
            assert k in b
        assert set(b["score_band_distribution"].keys()) >= {"hot", "warm", "nurture", "low"}
