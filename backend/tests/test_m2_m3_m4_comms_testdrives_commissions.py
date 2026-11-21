"""Iteration 12: iteration_11 fixes + M2 comms/automations + M3 test drives + M4 commission tiers/exports."""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient


def _env(path, key):
    for line in open(path):
        if line.strip().startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env("/app/frontend/.env", "REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"
SLUG = "prestige-auto-toronto"
mdb = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]
CREATED = {"leads": [], "convs": [], "users": [], "dgs": [], "refs": [], "sales": [], "tds": [], "appts": [], "emails": []}


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}")
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    s.me = r.json()["user"]
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@autoacquire.ai", "Admin123!")


@pytest.fixture(scope="module")
def manager():
    return _login("manager@autoacquire.ai", "Manager123!")


@pytest.fixture(scope="module")
def rep1():
    return _login("rep1@autoacquire.ai", "Rep123!")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    leads = CREATED["leads"]
    sellers = [l["seller_id"] for l in mdb.leads.find({"id": {"$in": leads}})]
    for coll in ["inventory_matches", "referrals", "consent_records", "appointments", "inventory_preferences",
                 "seller_vehicles", "lead_scores", "activities", "follow_ups", "internal_notes", "sales",
                 "communications", "automation_runs", "test_drives"]:
        mdb[coll].delete_many({"lead_id": {"$in": leads}})
    mdb.commission_transactions.delete_many({"sale_id": {"$in": CREATED["sales"]}})
    mdb.commission_agreements.delete_many({"dealer_group_id": {"$in": CREATED["dgs"]}})
    mdb.messages.delete_many({"conversation_id": {"$in": CREATED["convs"]}})
    mdb.conversations.delete_many({"id": {"$in": CREATED["convs"]}})
    mdb.leads.delete_many({"id": {"$in": leads}})
    mdb.sellers.delete_many({"id": {"$in": sellers}})
    mdb.communications.delete_many({"recipient_type": "staff", "to": {"$in": CREATED["emails"]}})
    mdb.password_reset_tokens.delete_many({"user_id": {"$in": CREATED["users"]}})
    mdb.users.delete_many({"id": {"$in": CREATED["users"]}})
    mdb.dealer_groups.delete_many({"id": {"$in": CREATED["dgs"]}})


def _new_lead(email="test_i12@example.com", phone=None, assign=None):
    r = requests.post(f"{API}/public/{SLUG}/conversations", json={"consent": True, "language": "en"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED["convs"].append(d["conversation_id"])
    CREATED["leads"].append(d["lead_id"])
    lead = mdb.leads.find_one({"id": d["lead_id"]})
    mdb.sellers.update_one({"id": lead["seller_id"]}, {"$set": {"first_name": "TEST_I12", "email": email, "phone": phone}})
    if assign:
        mdb.leads.update_one({"id": d["lead_id"]}, {"$set": {"assigned_user_id": assign}})
    return d["lead_id"]


def _future(days=5):
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


# ---------- iteration_11 fixes ----------
class TestIter11Fixes:
    def test_rep_patch_unassigned_and_assign(self, rep1):
        lid = _new_lead()
        assert rep1.patch(f"{API}/leads/{lid}", json={"status": "contacted"}).status_code == 403
        mdb.leads.update_one({"id": lid}, {"$set": {"assigned_user_id": rep1.me["id"]}})
        r = rep1.patch(f"{API}/leads/{lid}", json={"assigned_user_id": rep1.me["id"]})
        assert r.status_code == 403, r.text

    def test_notes_errors(self, admin, rep1):
        assert admin.post(f"{API}/leads/{uuid.uuid4()}/notes", json={"content": "x"}).status_code == 404
        lid = _new_lead()
        assert rep1.post(f"{API}/leads/{lid}/notes", json={"content": "x"}).status_code == 403
        assert admin.post(f"{API}/leads/{lid}/notes", json={"content": "  "}).status_code == 400

    def test_customer_patch_email_and_blank(self, admin):
        lid = _new_lead()
        assert admin.patch(f"{API}/leads/{lid}/customer", json={"email": "bad-email"}).status_code == 400
        r = admin.patch(f"{API}/leads/{lid}/customer", json={"first_name": "", "email": ""})
        assert r.status_code in (200, 400), r.text
        s = mdb.sellers.find_one({"id": mdb.leads.find_one({"id": lid})["seller_id"]})
        assert s["first_name"] == "TEST_I12" and s["email"] == "test_i12@example.com"

    def test_messages_no_conversation(self, admin):
        lid = _new_lead()
        mdb.conversations.update_one({"lead_id": lid}, {"$set": {"lead_id": "detached-" + lid}})
        r = admin.post(f"{API}/leads/{lid}/messages", json={"content": "hi"})
        mdb.conversations.update_one({"lead_id": "detached-" + lid}, {"$set": {"lead_id": lid}})
        assert r.status_code == 400, r.text

    def test_forgot_password_invalidates(self, admin):
        email = f"test_i12_{uuid.uuid4().hex[:6]}@test.com"
        r = admin.post(f"{API}/users", json={"first_name": "TEST_U", "last_name": "I12", "email": email, "role": "dealership_representative"})
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED["users"].append(d["user"]["id"])
        CREATED["emails"].append(email)
        assert d["email_status"] == "not_configured" and "token=" in d["setup_url"]
        assert mdb.communications.find_one({"template": "user_invitation", "to": email})
        tok1 = d["setup_url"].split("token=")[1]
        assert requests.post(f"{API}/auth/forgot-password", json={"email": email}).status_code == 200
        assert requests.post(f"{API}/auth/reset-password", json={"token": tok1, "password": "TestPass123!"}).status_code == 400


# ---------- M2 communications ----------
class TestComms:
    def test_config(self, admin):
        c = admin.get(f"{API}/communications/config").json()
        assert c["email"]["configured"] is False and c["sms"]["configured"] is False
        assert "support@autonovaia.ca" in (c["email"]["from"] or "")
        assert c["email"]["webhook_url"].endswith("/api/webhooks/resend")
        assert c["sms"]["inbound_webhook_url"].endswith("/api/webhooks/twilio/inbound")

    def test_send_blocked_then_not_configured_and_retry(self, admin):
        lid = _new_lead(phone=None)
        r = admin.post(f"{API}/leads/{lid}/communications", json={"channel": "sms", "template": "follow_up"})
        assert r.status_code == 200 and r.json()["status"] == "blocked"  # no phone
        blocked_id = r.json()["id"]
        r = admin.post(f"{API}/leads/{lid}/communications", json={"channel": "email", "template": "follow_up"})
        assert r.json()["status"] == "blocked", r.json()  # no operational permission
        assert admin.put(f"{API}/leads/{lid}/communication-permissions",
                         json={"operational": True, "appointment": True, "promotional": False, "source": "TEST"}).status_code == 200
        r = admin.post(f"{API}/leads/{lid}/communications", json={"channel": "email", "template": "follow_up"})
        assert r.json()["status"] == "not_configured", r.json()
        cid = r.json()["id"]
        assert admin.post(f"{API}/leads/{lid}/communications", json={"channel": "email", "template": "user_invitation"}).status_code == 400
        rr = admin.post(f"{API}/communications/{cid}/retry")
        assert rr.status_code == 200 and rr.json()["status"] == "not_configured" and rr.json()["attempts"] == 2
        assert admin.post(f"{API}/communications/{blocked_id}/retry").status_code == 400
        lst = admin.get(f"{API}/communications", params={"channel": "email", "status": "not_configured", "direction": "outbound"}).json()
        assert all(i["channel"] == "email" and i["status"] == "not_configured" for i in lst["items"])
        assert any(i["id"] == cid for i in lst["items"])

    def test_rep_scope(self, rep1):
        items = rep1.get(f"{API}/communications").json()["items"]
        mine = {l["id"] for l in mdb.leads.find({"assigned_user_id": rep1.me["id"]}, {"id": 1})}
        assert all(i.get("lead_id") in mine for i in items)

    def test_webhooks_unsigned(self):
        assert requests.post(f"{API}/webhooks/resend", json={"type": "email.delivered"}).status_code == 401
        assert requests.post(f"{API}/webhooks/twilio/status", data={"MessageSid": "x"}).status_code == 401
        assert requests.post(f"{API}/webhooks/twilio/inbound", data={"Body": "STOP"},
                             headers={"X-Twilio-Signature": "bogus"}).status_code == 401


# ---------- M2 automations ----------
class TestAutomations:
    def test_rules_and_patch(self, manager, rep1):
        rules = manager.get(f"{API}/automations").json()
        assert {r["key"] for r in rules} == {"new_lead", "uncontacted_lead", "appointment_confirmation",
                                              "test_drive_confirmation", "inactive_customer"}
        k = "appointment_confirmation"
        assert manager.patch(f"{API}/automations/{k}", json={"channels": ["fax"]}).status_code == 400
        assert manager.patch(f"{API}/automations/{k}", json={"language": "de"}).status_code == 400
        assert manager.patch(f"{API}/automations/{k}", json={"delay_minutes": -1}).status_code == 400
        assert manager.patch(f"{API}/automations/{k}", json={"template": "nope"}).status_code == 400
        assert rep1.patch(f"{API}/automations/{k}", json={"enabled": True}).status_code == 403
        r = manager.patch(f"{API}/automations/{k}", json={"channels": ["email", "sms"], "delay_minutes": 0})
        assert r.status_code == 200 and r.json()["channels"] == ["email", "sms"]

    def test_appointment_confirm_fires(self, admin):
        lid = _new_lead(phone="+14165550199")
        lead = mdb.leads.find_one({"id": lid})
        aid = str(uuid.uuid4())
        mdb.appointments.insert_one({"id": aid, "organization_id": lead["organization_id"], "lead_id": lid,
            "seller_id": lead["seller_id"], "conversation_id": None, "appointment_type": "vehicle_appraisal",
            "start_time": _future(5), "end_time": _future(5), "status": "requested", "created_at": _future(0)})
        r = admin.post(f"{API}/appointments/{aid}/confirm")
        assert r.status_code == 200, r.text
        runs = list(mdb.automation_runs.find({"lead_id": lid, "rule_key": "appointment_confirmation"}))
        trig = [x for x in runs if x["kind"] == "trigger"]
        assert len(trig) == 1 and trig[0]["status"] == "success", trig
        assert any("reminder scheduled" in a for a in trig[0]["actions"]), trig[0]["actions"]
        assert any(x["kind"] == "reminder" and x["status"] == "scheduled" for x in runs)

    def test_process_idempotent_and_retry(self, manager):
        assert manager.post(f"{API}/automations/process", timeout=120).status_code == 200
        n1 = mdb.automation_runs.count_documents({})
        assert manager.post(f"{API}/automations/process", timeout=120).status_code == 200
        dup = list(mdb.automation_runs.aggregate([{"$group": {"_id": "$idempotency_key", "c": {"$sum": 1}}}, {"$match": {"c": {"$gt": 1}}}]))
        assert not dup, dup[:3]
        n2 = mdb.automation_runs.count_documents({})
        assert n2 - n1 < 5, (n1, n2)
        ok = mdb.automation_runs.find_one({"status": "success", "organization_id": manager.me["organization_id"]})
        assert manager.post(f"{API}/automations/runs/{ok['id']}/retry").status_code == 400
        runs = manager.get(f"{API}/automations/runs", params={"status": "success"}).json()
        assert runs and all(r["status"] == "success" for r in runs)

    def test_cron_auth(self):
        assert requests.post(f"{API}/cron/automations").status_code == 401
        assert requests.post(f"{API}/cron/automations", headers={"Authorization": "Bearer wrong"}).status_code == 401


# ---------- M3 test drives ----------
class TestTestDrives:
    def test_lifecycle(self, admin):
        lid = _new_lead(phone="+14165550198")
        r = admin.post(f"{API}/test-drives", json={"lead_id": lid, "requested_time": _future(3), "notes": "TEST_td"})
        assert r.status_code == 200, r.text
        td = r.json()
        assert td["status"] == "requested" and td["notes"][0]["content"] == "TEST_td"
        tid = td["id"]
        assert admin.post(f"{API}/test-drives/{tid}/complete", json={}).status_code == 400
        assert admin.post(f"{API}/test-drives/{tid}/reschedule", json={}).status_code == 400
        assert admin.post(f"{API}/test-drives/{tid}/reschedule", json={"time": _future(4)}).json()["status"] == "pending_confirmation"
        assert admin.post(f"{API}/test-drives/{tid}/confirm", json={}).json()["status"] == "confirmed"
        assert mdb.leads.find_one({"id": lid})["pipeline_stage"] == "test_drive_scheduled"
        run = mdb.automation_runs.find_one({"lead_id": lid, "rule_key": "test_drive_confirmation", "kind": "trigger"})
        assert run and run["status"] == "success", run
        assert admin.post(f"{API}/test-drives/{tid}/notes", json={"content": "TEST_n2"}).status_code == 200
        assert admin.post(f"{API}/test-drives/{tid}/notes", json={"content": " "}).status_code == 400
        assert admin.post(f"{API}/test-drives/{tid}/link-sale", json={"sale_id": "x"}).status_code == 400
        r = admin.post(f"{API}/test-drives/{tid}/complete", json={"feedback": "TEST_great", "rating": 5})
        assert r.status_code == 200 and r.json()["customer_feedback"] == "TEST_great"
        assert mdb.leads.find_one({"id": lid})["pipeline_stage"] == "test_drive_completed"
        assert admin.post(f"{API}/test-drives/{tid}/cancel", json={}).status_code == 400
        assert admin.post(f"{API}/test-drives/{tid}/link-sale", json={"sale_id": "nope"}).status_code == 400
        assert admin.post(f"{API}/test-drives/{tid}/bogus", json={}).status_code == 404

    def test_decline_noshow_filters_dashboard(self, admin, rep1):
        lid = _new_lead(assign=None)
        tid = admin.post(f"{API}/test-drives", json={"lead_id": lid, "requested_time": _future(6)}).json()["id"]
        assert admin.post(f"{API}/test-drives/{tid}/decline", json={"reason": "TEST"}).json()["status"] == "dealership_declined"
        assert admin.post(f"{API}/test-drives/{tid}/confirm", json={}).status_code == 400
        rows = admin.get(f"{API}/test-drives", params={"status": "dealership_declined"}).json()
        assert all(r["status"] == "dealership_declined" for r in rows) and any(r["id"] == tid for r in rows)
        d = (datetime.now(timezone.utc) + timedelta(days=6)).date().isoformat()
        rows = admin.get(f"{API}/test-drives", params={"date_from": d, "date_to": d}).json()
        assert any(r["id"] == tid for r in rows)
        dash = admin.get(f"{API}/test-drives/dashboard").json()
        for k in ("total", "upcoming", "completed", "cancelled", "no_shows", "conversion_rate"):
            assert k in dash
        assert rep1.post(f"{API}/test-drives/{tid}/notes", json={"content": "x"}).status_code == 403
        assert all(r.get("assigned_user_id") == rep1.me["id"] for r in rep1.get(f"{API}/test-drives").json())
        assert rep1.post(f"{API}/test-drives", json={"lead_id": lid, "requested_time": _future(2)}).status_code == 403
        assert admin.post(f"{API}/test-drives", json={"lead_id": lid, "requested_time": "notadate"}).status_code == 400


# ---------- M4 commissions ----------
def _referral(admin, dg_id):
    lid = _new_lead()
    lead = mdb.leads.find_one({"id": lid})
    rid = str(uuid.uuid4())
    mdb.referrals.insert_one({"id": rid, "organization_id": lead["organization_id"], "lead_id": lid, "dealer_group_id": dg_id,
                              "vehicle_label": "TEST Car", "status": "delivered", "status_history": [], "created_at": _future(0)})
    return rid


def _sale(admin, dg_id, amount=30000):
    r = admin.post(f"{API}/sales", json={"referral_id": _referral(admin, dg_id), "sale_amount": amount})
    assert r.status_code == 200, r.text
    CREATED["sales"].append(r.json()["id"])
    v = admin.post(f"{API}/sales/{r.json()['id']}/verify")
    assert v.status_code == 200, v.text
    return r.json()["id"], v.json()["commission_amount"]


TIERS = [{"name": "T1", "min_sales": 1, "max_sales": 1, "amount_per_sale": 100}, {"name": "T2", "min_sales": 2, "amount_per_sale": 250}]


class TestCommissions:
    def _dg(self, admin, method):
        r = admin.post(f"{API}/dealer-groups", json={"name": f"TEST_I12 {method} {uuid.uuid4().hex[:4]}"})
        assert r.status_code == 200, r.text
        CREATED["dgs"].append(r.json()["id"])
        return r.json()["id"]

    def test_agreement_validation(self, admin, manager):
        dg = self._dg(admin, "val")
        body = {"commission_model": "volume", "volume_tiers": TIERS, "volume_period": "monthly", "volume_method": "retroactive"}
        assert manager.put(f"{API}/dealer-groups/{dg}/commission-agreement", json=body).status_code == 403
        assert admin.put(f"{API}/dealer-groups/{dg}/commission-agreement", json={**body, "volume_tiers": []}).status_code == 400
        bad = [{"min_sales": 1, "max_sales": 3, "amount_per_sale": 1}, {"min_sales": 2, "amount_per_sale": 2}]
        assert admin.put(f"{API}/dealer-groups/{dg}/commission-agreement", json={**body, "volume_tiers": bad}).status_code == 400
        r1 = admin.put(f"{API}/dealer-groups/{dg}/commission-agreement", json=body)
        assert r1.status_code == 200 and r1.json()["agreement_version"] == 1
        r2 = admin.put(f"{API}/dealer-groups/{dg}/commission-agreement", json={**body, "volume_method": "incremental"})
        assert r2.json()["agreement_version"] == 2
        hist = admin.get(f"{API}/dealer-groups/{dg}/commission-agreement/history").json()
        assert len(hist) == 2 and hist[0]["agreement"]["agreement_version"] == 1
        admin.patch(f"{API}/dealer-groups/{dg}", json={"commission_model": "fixed", "commission_rate": 999})
        g = mdb.dealer_groups.find_one({"id": dg})
        assert g["commission_model"] == "volume" and g.get("commission_rate", 0) != 999

    def test_retroactive(self, admin):
        dg = self._dg(admin, "retro")
        admin.put(f"{API}/dealer-groups/{dg}/commission-agreement", json={"commission_model": "volume", "volume_tiers": TIERS,
                  "volume_period": "monthly", "volume_method": "retroactive"})
        s1, a1 = _sale(admin, dg)
        s2, a2 = _sale(admin, dg)
        assert a1 == 100 and a2 == 250
        t1 = list(mdb.commission_transactions.find({"sale_id": s1}))
        assert {t["type"]: t["amount"] for t in t1} == {"sale": 100, "adjustment": 150}, t1

    def test_incremental(self, admin):
        dg = self._dg(admin, "incr")
        admin.put(f"{API}/dealer-groups/{dg}/commission-agreement", json={"commission_model": "volume", "volume_tiers": TIERS,
                  "volume_period": "monthly", "volume_method": "incremental"})
        s1, a1 = _sale(admin, dg)
        s2, a2 = _sale(admin, dg)
        assert (a1, a2) == (100, 250)
        assert mdb.commission_transactions.count_documents({"sale_id": s1, "type": "adjustment"}) == 0
        led = admin.get(f"{API}/commissions/ledger", params={"dealer_group_id": dg}).json()
        assert len(led["rows"]) == 2 and led["total_commission"] == 350
        led = admin.get(f"{API}/commissions/ledger", params={"dealer_group_id": dg, "commission_status": "cancelled"}).json()
        assert led["rows"] == []

    def test_exports_and_rbac(self, admin, rep1):
        r = admin.get(f"{API}/commissions/export", params={"format": "csv"})
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
        head = r.text.splitlines()[0]
        for c in ("Referral ID", "Vehicle", "Dealership", "Sale date", "Verification date", "Sale amount",
                  "Commission model", "Commission amount", "Commission status"):
            assert c in head
        p = admin.get(f"{API}/commissions/export", params={"format": "pdf"})
        assert p.status_code == 200 and p.content[:4] == b"%PDF"
        assert admin.get(f"{API}/commissions/export", params={"format": "xls"}).status_code == 400
        for path in ("/commissions/ledger", "/commissions/export", "/commissions/report"):
            assert rep1.get(f"{API}{path}").status_code == 403
        for s in rep1.get(f"{API}/sales").json()["sales"]:
            assert "sale_amount" not in s and s["commission"] is None
