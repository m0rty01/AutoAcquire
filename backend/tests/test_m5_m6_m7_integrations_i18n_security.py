"""Iteration 13: iteration_12 fixes + M5 partner integrations + M6 language prefs + M7 rate limit / rep isolation / health."""
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
C = {"leads": [], "convs": [], "dgs": [], "sales": [], "code_maps": [], "veh": [], "vmaps": [], "logs_before": None}
_SESS = {}


def _login(email, pw):
    if email in _SESS:
        return _SESS[email]
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code}")
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    s.me = r.json()["user"]
    _SESS[email] = s
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


def _future(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    leads = C["leads"]
    sellers = [l["seller_id"] for l in mdb.leads.find({"id": {"$in": leads}})]
    for coll in ["inventory_matches", "referrals", "consent_records", "appointments", "inventory_preferences",
                 "seller_vehicles", "lead_scores", "activities", "follow_ups", "internal_notes", "sales",
                 "communications", "automation_runs", "test_drives"]:
        mdb[coll].delete_many({"lead_id": {"$in": leads}})
    mdb.commission_transactions.delete_many({"$or": [{"sale_id": {"$in": C["sales"]}}, {"triggered_by_sale_id": {"$in": C["sales"]}}]})
    mdb.commission_agreements.delete_many({"dealer_group_id": {"$in": C["dgs"]}})
    mdb.messages.delete_many({"conversation_id": {"$in": C["convs"]}})
    mdb.conversations.delete_many({"id": {"$in": C["convs"]}})
    mdb.leads.delete_many({"id": {"$in": leads}})
    mdb.sellers.delete_many({"id": {"$in": sellers}})
    mdb.dealer_groups.delete_many({"id": {"$in": C["dgs"]}})
    mdb.code_mappings.delete_many({"id": {"$in": C["code_maps"]}})
    mdb.inventory_vehicles.delete_many({"id": {"$in": C["veh"]}})
    mdb.external_vehicle_mappings.delete_many({"id": {"$in": C["vmaps"]}})


def _new_lead(assign=None, phone="+14165550177"):
    r = requests.post(f"{API}/public/{SLUG}/conversations", json={"consent": True, "language": "en"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    C["convs"].append(d["conversation_id"])
    C["leads"].append(d["lead_id"])
    lead = mdb.leads.find_one({"id": d["lead_id"]})
    mdb.sellers.update_one({"id": lead["seller_id"]}, {"$set": {"first_name": "TEST_I13", "email": "test_i13@example.com", "phone": phone,
        "communication_permissions": {"operational": True, "appointment": True, "promotional": False}}})
    mdb.leads.update_one({"id": d["lead_id"]}, {"$set": {"assigned_user_id": assign}})
    return d["lead_id"], d["conversation_id"]


def _reminder(lid):
    return mdb.automation_runs.find_one({"lead_id": lid, "kind": "reminder"})


# ---------- iteration_12 fixes: reminders ----------
class TestReminderFixes:
    def _confirmed_td(self, admin):
        lid, _ = _new_lead()
        tid = admin.post(f"{API}/test-drives", json={"lead_id": lid, "requested_time": _future(4)}).json()["id"]
        assert admin.post(f"{API}/test-drives/{tid}/confirm", json={}).json()["status"] == "confirmed"
        rem = _reminder(lid)
        assert rem and rem["status"] == "scheduled", rem
        return lid, tid, rem

    @pytest.mark.parametrize("action,body", [("cancel", {"reason": "TEST"}), ("reschedule", {"time": None}),
                                             ("no-show", {}), ("complete", {"feedback": "TEST"})])
    def test_td_action_cancels_reminder(self, admin, action, body):
        lid, tid, rem = self._confirmed_td(admin)
        if action == "reschedule":
            body = {"time": _future(6)}
        r = admin.post(f"{API}/test-drives/{tid}/{action}", json=body)
        assert r.status_code == 200, r.text
        assert mdb.automation_runs.find_one({"id": rem["id"]})["status"] == "cancelled"

    def test_td_decline_cancels_reminder(self, admin):
        lid, tid, rem = self._confirmed_td(admin)
        r = admin.post(f"{API}/test-drives/{tid}/decline", json={"reason": "TEST"})
        assert r.status_code == 400  # by design: a confirmed drive must be cancelled, not declined
        assert admin.post(f"{API}/test-drives/{tid}/cancel", json={}).status_code == 200
        assert mdb.automation_runs.find_one({"id": rem["id"]})["status"] == "cancelled"

    def test_stale_reminder_skipped(self, admin, manager):
        lid, tid, rem = self._confirmed_td(admin)
        mdb.test_drives.update_one({"id": tid}, {"$set": {"scheduled_at": _future(9)}})  # time changed behind the run's back
        mdb.automation_runs.update_one({"id": rem["id"]}, {"$set": {"run_at": "2000-01-01T00:00:00+00:00"}})
        assert manager.post(f"{API}/automations/process", timeout=120).status_code == 200
        st = mdb.automation_runs.find_one({"id": rem["id"]})
        assert st["status"] == "skipped", st
        assert mdb.communications.count_documents({"lead_id": lid, "automation_run_id": rem["id"]}) == 0

    @pytest.mark.parametrize("action", ["decline", "cancel"])
    def test_appointment_cancel_decline(self, admin, action):
        lid, _ = _new_lead()
        lead = mdb.leads.find_one({"id": lid})
        aid = str(uuid.uuid4())
        mdb.appointments.insert_one({"id": aid, "organization_id": lead["organization_id"], "lead_id": lid, "seller_id": lead["seller_id"],
            "appointment_type": "vehicle_appraisal", "start_time": _future(5), "end_time": _future(5), "status": "requested", "created_at": _future(0)})
        assert admin.post(f"{API}/appointments/{aid}/confirm").status_code == 200
        rem = _reminder(lid)
        assert rem and rem["status"] == "scheduled"
        assert admin.post(f"{API}/appointments/{aid}/{action}", json={}).status_code == 200
        assert mdb.automation_runs.find_one({"id": rem["id"]})["status"] == "cancelled"

    def test_automations_rbac(self, rep1, manager):
        assert rep1.get(f"{API}/automations").status_code == 403
        assert rep1.get(f"{API}/automations/runs").status_code == 403
        assert manager.get(f"{API}/automations").status_code == 200


# ---------- iteration_12 fixes: commissions ----------
TIERS = [{"name": "T1", "min_sales": 1, "max_sales": 1, "amount_per_sale": 100}, {"name": "T2", "min_sales": 2, "amount_per_sale": 250}]


def _dg(admin, method):
    r = admin.post(f"{API}/dealer-groups", json={"name": f"TEST_I13 {method} {uuid.uuid4().hex[:4]}"})
    assert r.status_code == 200, r.text
    C["dgs"].append(r.json()["id"])
    assert admin.put(f"{API}/dealer-groups/{r.json()['id']}/commission-agreement", json={"commission_model": "volume",
        "volume_tiers": TIERS, "volume_period": "monthly", "volume_method": method}).status_code == 200
    return r.json()["id"]


def _sale(admin, dg_id, verify=True):
    lid, _ = _new_lead()
    lead = mdb.leads.find_one({"id": lid})
    rid = str(uuid.uuid4())
    mdb.referrals.insert_one({"id": rid, "organization_id": lead["organization_id"], "lead_id": lid, "dealer_group_id": dg_id,
                              "vehicle_label": "TEST Car", "status": "delivered", "status_history": [], "created_at": _future(0)})
    r = admin.post(f"{API}/sales", json={"referral_id": rid, "sale_amount": 30000})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    C["sales"].append(sid)
    if verify:
        v = admin.post(f"{API}/sales/{sid}/verify")
        assert v.status_code == 200, v.text
        return sid, v.json()["commission_amount"]
    return sid, None


class TestCommissionFixes:
    def test_reject_cancels_uplift_and_guards(self, admin):
        dg = _dg(admin, "retroactive")
        s1, a1 = _sale(admin, dg)
        s2, a2 = _sale(admin, dg)
        assert (a1, a2) == (100, 250)
        adj = mdb.commission_transactions.find_one({"type": "adjustment", "triggered_by_sale_id": s2})
        assert adj and adj["status"] == "payable" and adj["sale_id"] == s1
        sales = {s["id"]: s for s in admin.get(f"{API}/sales").json()["sales"]}
        assert sales[s1]["commission_adjustments"] == 150
        assert admin.post(f"{API}/sales/{s1}/verify").status_code == 400  # double verify
        assert admin.post(f"{API}/sales/{s2}/reject").status_code == 200
        assert mdb.commission_transactions.find_one({"id": adj["id"]})["status"] == "cancelled"
        assert admin.post(f"{API}/sales/{s2}/reject").status_code == 400
        sales = {s["id"]: s for s in admin.get(f"{API}/sales").json()["sales"]}
        assert sales[s1]["commission_adjustments"] == 0

    def test_effective_date_ignores_old_sales(self, admin):
        dg = _dg(admin, "incremental")
        s0, a0 = _sale(admin, dg)
        assert a0 == 100
        mdb.sales.update_one({"id": s0}, {"$set": {"verified_at": "2020-01-01T00:00:00+00:00"}})
        s1, a1 = _sale(admin, dg)
        assert a1 == 100, "sale verified before effective_date must not count toward tier volume"


# ---------- M5 partner integrations ----------
class TestIntegrations:
    def test_list_and_rbac(self, admin, manager, rep1):
        r = admin.get(f"{API}/integrations")
        assert r.status_code == 200
        d = {i["partner_key"]: i for i in r.json()}
        assert set(d) == {"le_don_de_lauto", "le_prix_du_gros", "h_gregoire"}
        assert d["le_prix_du_gros"]["status"] == "pending_credentials" and d["le_prix_du_gros"]["kind"] == "code_mapping"
        assert d["le_don_de_lauto"]["status"] == "sandbox"
        assert manager.get(f"{API}/integrations").status_code == 200
        assert rep1.get(f"{API}/integrations").status_code == 403
        assert rep1.get(f"{API}/integrations/mappings").status_code == 403
        assert rep1.patch(f"{API}/integrations/h_gregoire", json={"active": True, "sandbox": True}).status_code == 403
        assert rep1.post(f"{API}/integrations/le_don_de_lauto/sync").status_code == 403
        assert rep1.post(f"{API}/integrations/code-mappings", json={"ldda_code": "x", "lpdg_code": "y"}).status_code == 403
        assert manager.post(f"{API}/integrations/le_don_de_lauto/sync").status_code == 403
        assert admin.get(f"{API}/integrations/bogus/logs").status_code in (200, 404)
        assert admin.post(f"{API}/integrations/bogus/sync").status_code == 404

    def test_ldda_resync_no_duplicates_and_lpdg_sync_400(self, admin):
        before = mdb.inventory_vehicles.count_documents({"source": "partner:le_don_de_lauto:sample"})
        r = admin.post(f"{API}/integrations/le_don_de_lauto/sync")
        assert r.status_code == 200, r.text
        st = r.json()["stats"]
        assert st["imported"] == 0 and st["updated"] == 4 and st["sold"] == 1, st
        assert mdb.inventory_vehicles.count_documents({"source": "partner:le_don_de_lauto:sample"}) == before == 4
        assert all(v["is_sample"] for v in mdb.inventory_vehicles.find({"source": "partner:le_don_de_lauto:sample"}))
        assert admin.post(f"{API}/integrations/le_prix_du_gros/sync").status_code == 400
        logs = admin.get(f"{API}/integrations/le_don_de_lauto/logs").json()
        assert logs and logs[0]["sandbox"] is True and "stats" in logs[0]

    def test_hg_pending_then_sandbox_sync(self, admin):
        org = admin.me["organization_id"]
        r = admin.patch(f"{API}/integrations/h_gregoire", json={"active": True})
        assert r.status_code == 400 and "Pending credentials" in r.json()["detail"]
        assert admin.post(f"{API}/integrations/h_gregoire/sync").status_code == 400  # inactive
        try:
            assert admin.patch(f"{API}/integrations/h_gregoire", json={"active": True, "sandbox": True}).status_code == 200
            st = admin.post(f"{API}/integrations/h_gregoire/sync").json()["stats"]
            veh = list(mdb.inventory_vehicles.find({"organization_id": org, "source": "partner:h_gregoire:sample"}))
            C["veh"] += [v["id"] for v in veh]
            C["vmaps"] += [m["id"] for m in mdb.external_vehicle_mappings.find({"organization_id": org, "source": "h_gregoire"})]
            assert st["imported"] == 3 and st["sold"] == 1, st
            hy = [v for v in veh if v["make"] == "Hyundai"][0]
            assert hy["model"] == "Tucson" and hy["mileage"] == 45000 and hy["price"] == 21000 and hy["inventory_code"] == "HG-500"
            assert all(v["is_sample"] for v in veh)
            st2 = admin.post(f"{API}/integrations/h_gregoire/sync").json()["stats"]
            assert st2["imported"] == 0 and st2["updated"] == 3
            d = {i["partner_key"]: i for i in admin.get(f"{API}/integrations").json()}
            assert d["h_gregoire"]["status"] == "sandbox" and d["h_gregoire"]["vehicle_count"] == 2
        finally:
            admin.patch(f"{API}/integrations/h_gregoire", json={"active": False, "sandbox": False})
            mdb.integration_sync_logs.delete_many({"organization_id": org, "partner_key": "h_gregoire"})
            mdb.partner_integrations.update_one({"organization_id": org, "partner_key": "h_gregoire"},
                                                {"$set": {"last_stats": {}, "last_errors": [], "last_sync_at": None, "last_success_at": None}})

    def test_sample_never_matched(self, admin):
        lid, _ = _new_lead()
        lead = mdb.leads.find_one({"id": lid})
        mdb.inventory_preferences.update_one({"lead_id": lid}, {"$set": {"lead_id": lid, "organization_id": lead["organization_id"],
            "preferred_makes": ["Toyota", "Honda", "Mazda"], "preferred_models": ["RAV4", "CR-V", "CX-5"], "budget_max": 40000}}, upsert=True)
        r = admin.post(f"{API}/leads/{lid}/run-inventory-match")
        assert r.status_code == 200, r.text
        ids = [m["inventory_vehicle"]["id"] if "inventory_vehicle" in m else m.get("inventory_vehicle_id") for m in r.json()["matches"]]
        samples = {v["id"] for v in mdb.inventory_vehicles.find({"is_sample": True})}
        assert not (set(ids) & samples)

    def test_code_mapping_conflict_flow(self, admin):
        tag = uuid.uuid4().hex[:5]
        r = admin.post(f"{API}/integrations/code-mappings", json={"ldda_code": f"TEST_LD{tag}", "lpdg_code": f"TEST_PG{tag}"})
        assert r.status_code == 200 and r.json()["status"] == "unmatched", r.text
        mid = r.json()["id"]
        C["code_maps"].append(mid)
        assert admin.post(f"{API}/integrations/code-mappings", json={"ldda_code": f"TEST_LD{tag}", "lpdg_code": f"TEST_PG{tag}"}).json()["status"] == "unchanged"
        assert admin.post(f"{API}/integrations/mappings/{mid}/resolve", json={"action": "keep_existing"}).status_code == 400
        r = admin.post(f"{API}/integrations/code-mappings", json={"ldda_code": f"TEST_LD{tag}", "lpdg_code": f"TEST_PGX{tag}"})
        assert r.json() == {"status": "conflict", "id": mid}
        m = mdb.code_mappings.find_one({"id": mid})
        assert m["lpdg_code"] == f"TEST_PG{tag}" and m["status"] == "conflict"
        conf = admin.get(f"{API}/integrations/mappings", params={"status": "conflict"}).json()
        assert any(c["id"] == mid for c in conf["code_mappings"]) and all(c["status"] == "conflict" for c in conf["code_mappings"])
        assert admin.post(f"{API}/integrations/mappings/{mid}/resolve", json={"action": "bogus"}).status_code == 400
        assert admin.post(f"{API}/integrations/mappings/{mid}/resolve", json={"action": "keep_existing"}).status_code == 200
        m = mdb.code_mappings.find_one({"id": mid})
        assert m["status"] == "active" and m["lpdg_code"] == f"TEST_PG{tag}" and m["history"][-1]["resolution"] == "keep_existing"
        admin.post(f"{API}/integrations/code-mappings", json={"ldda_code": f"TEST_LD{tag}", "lpdg_code": f"TEST_PGY{tag}"})
        assert admin.post(f"{API}/integrations/mappings/{mid}/resolve", json={"action": "accept_proposed"}).status_code == 200
        m = mdb.code_mappings.find_one({"id": mid})
        assert m["lpdg_code"] == f"TEST_PGY{tag}" and m["history"][-1]["previous"]["lpdg_code"] == f"TEST_PG{tag}"
        assert admin.post(f"{API}/integrations/mappings/nope/resolve", json={"action": "keep_existing"}).status_code == 404

    def test_vin_matched_mapping_accept_keeps_vin(self, admin):
        r = admin.post(f"{API}/integrations/code-mappings", json={"ldda_code": "LD102", "lpdg_code": "TEST_PG-A", "vin": "SAMPLEVIN0000LDDA2"})
        assert r.status_code == 200 and r.json()["status"] == "active", r.text
        mid = r.json()["id"]
        C["code_maps"].append(mid)
        assert mdb.code_mappings.find_one({"id": mid})["match_method"] == "vin"
        admin.post(f"{API}/integrations/code-mappings", json={"ldda_code": "LD102", "lpdg_code": "TEST_PG-B"})
        admin.post(f"{API}/integrations/mappings/{mid}/resolve", json={"action": "accept_proposed"})
        m = mdb.code_mappings.find_one({"id": mid})
        assert m["lpdg_code"] == "TEST_PG-B"
        assert m.get("vin") == "SAMPLEVIN0000LDDA2", f"accept_proposed wiped VIN: {m.get('vin')}"


# ---------- M6 preferences ----------
class TestPreferences:
    def test_language_pref(self, manager):
        assert manager.patch(f"{API}/me/preferences", json={"language": "de"}).status_code == 400
        try:
            assert manager.patch(f"{API}/me/preferences", json={"language": "fr"}).json()["language"] == "fr"
            assert manager.get(f"{API}/auth/me").json()["user"]["preferred_language"] == "fr"
        finally:
            manager.patch(f"{API}/me/preferences", json={"language": "en"})
        assert manager.get(f"{API}/auth/me").json()["user"]["preferred_language"] == "en"


# ---------- M7 security / monitoring ----------
class TestSecurity:
    def test_health(self, admin, manager, rep1):
        assert requests.get(f"{API}/health").json()["status"] == "ok"
        r = admin.get(f"{API}/system/health")
        assert r.status_code == 200
        names = " ".join(c["name"] for c in r.json()["checks"])
        for n in ("Database", "Email provider", "SMS provider", "delivery (24h)", "Background jobs", "Inventory sync"):
            assert n in names
        db_check = [c for c in r.json()["checks"] if c["name"] == "Database"][0]
        assert db_check["ok"] is True
        assert manager.get(f"{API}/system/health").status_code == 403
        assert rep1.get(f"{API}/system/health").status_code == 403

    def test_login_rate_limit(self):
        email = f"test_rl_{uuid.uuid4().hex[:8]}@example.com"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}).status_code for _ in range(22)]
        assert codes[:20] == [401] * 20, codes
        assert codes[20] == 429 and codes[21] == 429, codes

    def test_forgot_silent_limit(self):
        email = f"test_fp_{uuid.uuid4().hex[:8]}@example.com"
        for _ in range(5):
            r = requests.post(f"{API}/auth/forgot-password", json={"email": email})
            assert r.status_code == 200
        doc = mdb.rate_limits.find_one({"key": {"$regex": f"^forgot:{email}"}})
        assert doc and doc["count"] == 5

    def test_chat_length(self):
        lid, cid = _new_lead()
        r = requests.post(f"{API}/public/{SLUG}/conversations/{cid}/messages", json={"content": "a" * 2001})
        assert r.status_code == 400, r.text

    def test_rep_isolation(self, rep1, admin):
        mine = {l["id"] for l in mdb.leads.find({"assigned_user_id": rep1.me["id"]}, {"id": 1})}
        for ep, key in (("appointments", None), ("referrals", None), ("sales", "sales")):
            r = rep1.get(f"{API}/{ep}")
            assert r.status_code == 200, (ep, r.status_code)
            rows = r.json()[key] if key else r.json()
            rows = rows if isinstance(rows, list) else rows.get("referrals", rows.get("items", []))
            assert all(x["lead_id"] in mine for x in rows), ep
        lid, _ = _new_lead(assign=None)
        lead = mdb.leads.find_one({"id": lid})
        aid = str(uuid.uuid4())
        mdb.appointments.insert_one({"id": aid, "organization_id": lead["organization_id"], "lead_id": lid, "seller_id": lead["seller_id"],
            "appointment_type": "vehicle_appraisal", "start_time": _future(5), "end_time": _future(5), "status": "requested", "created_at": _future(0)})
        assert rep1.post(f"{API}/appointments/{aid}/confirm").status_code == 404
        assert rep1.post(f"{API}/appointments/{aid}/cancel").status_code == 404
        assert admin.get(f"{API}/appointments").status_code == 200
