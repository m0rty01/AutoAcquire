"""Milestone 1A (Customer Profile CRM endpoints) + 1B (User Management) regression tests."""
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
API = f"{BASE_URL}/api"
SLUG = "prestige-auto-toronto"
mdb = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]

CREATED = {"leads": [], "convs": [], "users": [], "orgs": [], "sales": [], "consents": []}


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
                 "seller_vehicles", "lead_scores", "activities", "follow_ups", "internal_notes", "sales"]:
        mdb[coll].delete_many({"lead_id": {"$in": leads}})
    mdb.messages.delete_many({"conversation_id": {"$in": CREATED["convs"]}})
    mdb.conversations.delete_many({"id": {"$in": CREATED["convs"]}})
    mdb.leads.delete_many({"id": {"$in": leads}})
    mdb.sellers.delete_many({"id": {"$in": sellers}})
    mdb.password_reset_tokens.delete_many({"user_id": {"$in": CREATED["users"]}})
    mdb.users.delete_many({"id": {"$in": CREATED["users"]}})
    mdb.dealer_groups.delete_many({"organization_id": {"$in": CREATED["orgs"]}})
    mdb.organizations.delete_many({"id": {"$in": CREATED["orgs"]}})


def _new_lead():
    r = requests.post(f"{API}/public/{SLUG}/conversations", json={"consent": True, "language": "en"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED["convs"].append(d["conversation_id"])
    CREATED["leads"].append(d["lead_id"])
    lead = mdb.leads.find_one({"id": d["lead_id"]})
    mdb.sellers.update_one({"id": lead["seller_id"]}, {"$set": {"first_name": "TEST_M1", "email": "test_m1@example.com"}})
    return d["lead_id"]


def _uid(session, email):
    return next(u["id"] for u in session.get(f"{API}/users").json() if u["email"] == email)


def _mk_user(session, role, **extra):
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    r = session.post(f"{API}/users", json={"first_name": "TEST_U", "last_name": "M1", "email": email, "role": role, **extra})
    if r.status_code == 200:
        CREATED["users"].append(r.json()["user"]["id"])
    return email, r


# ---------- Milestone 1A: profile ----------
class TestProfile:
    def test_profile_sections_admin(self, admin):
        lid = _new_lead()
        r = admin.get(f"{API}/leads/{lid}/profile")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["lead", "customer", "overview", "preferences", "trade_in", "matches", "messages", "activities",
                  "appointments", "test_drives", "referrals", "sales", "communications", "consents", "follow_ups",
                  "communication_permissions"]:
            assert k in d, k
        assert d["can_view_financials"] is True
        assert "_id" not in d["lead"]

    def test_seed_lead_profile(self, admin):
        r = admin.get(f"{API}/leads/63459406-e18e-4c58-84b7-f56fdecbd5a9/profile")
        assert r.status_code == 200
        d = r.json()
        assert len(d["consents"]) >= 1 and len(d["referrals"]) >= 1 and len(d["sales"]) >= 1
        assert "sale_amount" in d["sales"][0]

    def test_rep_forbidden_unassigned(self, rep1):
        lid = _new_lead()
        r = rep1.get(f"{API}/leads/{lid}/profile")
        assert r.status_code == 403
        assert rep1.get(f"{API}/leads/{lid}").status_code == 403

    def test_rep_no_financials(self, admin, rep1):
        lid = _new_lead()
        assert admin.post(f"{API}/leads/{lid}/assign", json={"user_id": rep1.me["id"]}).status_code == 200
        lead = mdb.leads.find_one({"id": lid})
        mdb.sales.insert_one({"id": str(uuid.uuid4()), "organization_id": lead["organization_id"], "lead_id": lid,
                              "sale_amount": 12345, "status": "reported", "created_at": "2026-01-01T00:00:00+00:00"})
        r = rep1.get(f"{API}/leads/{lid}/profile")
        assert r.status_code == 200
        d = r.json()
        assert d["can_view_financials"] is False
        assert d["sales"] and "sale_amount" not in d["sales"][0] and "commission" not in d["sales"][0]


class TestCustomerAndFollowUps:
    def test_patch_customer(self, admin):
        lid = _new_lead()
        r = admin.patch(f"{API}/leads/{lid}/customer", json={"first_name": "TEST_Edited", "city": "Ottawa", "preferred_language": "fr"})
        assert r.status_code == 200
        d = admin.get(f"{API}/leads/{lid}/profile").json()
        assert d["customer"]["first_name"] == "TEST_Edited" and d["customer"]["city"] == "Ottawa"
        assert d["overview"]["preferred_language"] == "fr"
        assert any(a["activity_type"] == "customer_updated" for a in d["activities"])

    def test_patch_customer_bad_lang(self, admin):
        lid = _new_lead()
        r = admin.patch(f"{API}/leads/{lid}/customer", json={"preferred_language": "de"})
        assert r.status_code == 400

    def test_follow_up_lifecycle(self, admin):
        lid = _new_lead()
        r = admin.post(f"{API}/leads/{lid}/follow-ups", json={"due_at": "2027-02-01T10:00:00Z", "note": "TEST_call"})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        d = admin.get(f"{API}/leads/{lid}/profile").json()
        assert d["overview"]["next_follow_up"]["id"] == fid
        assert admin.post(f"{API}/follow-ups/{fid}/complete").status_code == 200
        d = admin.get(f"{API}/leads/{lid}/profile").json()
        assert d["overview"]["next_follow_up"] is None
        assert admin.post(f"{API}/follow-ups/{fid}/complete").status_code == 400

    def test_follow_up_bad_date(self, admin):
        lid = _new_lead()
        assert admin.post(f"{API}/leads/{lid}/follow-ups", json={"due_at": "notadate"}).status_code == 400

    def test_comm_permissions(self, admin):
        lid = _new_lead()
        r = admin.put(f"{API}/leads/{lid}/communication-permissions",
                      json={"operational": True, "appointment": False, "promotional": True})
        assert r.status_code == 200
        d = admin.get(f"{API}/leads/{lid}/profile").json()
        assert d["communication_permissions"] == {"operational": True, "appointment": False, "promotional": True}
        assert len(d["communication_permission_history"]) == 1

    def test_consent_withdraw(self, admin):
        lid = _new_lead()
        lead = mdb.leads.find_one({"id": lid})
        cid = str(uuid.uuid4())
        orig = {"id": cid, "organization_id": lead["organization_id"], "lead_id": lid, "seller_id": lead["seller_id"],
                "status": "accepted", "agreement_version": "v1", "language": "en", "recipient_dealer_group_ids": [],
                "accepted_at": "2026-01-01T00:00:00+00:00", "created_at": "2026-01-01T00:00:00+00:00"}
        mdb.consent_records.insert_one(dict(orig))
        mdb.leads.update_one({"id": lid}, {"$set": {"consent_status": "accepted"}})
        r = admin.post(f"{API}/leads/{lid}/consent/withdraw", json={"reason": "TEST_customer request"})
        assert r.status_code == 200, r.text
        recs = list(mdb.consent_records.find({"lead_id": lid}, {"_id": 0}))
        assert len(recs) == 2
        o = next(x for x in recs if x["id"] == cid)
        assert o == orig
        w = next(x for x in recs if x["id"] != cid)
        assert w["status"] == "withdrawn" and w["withdraws_record_id"] == cid
        assert mdb.leads.find_one({"id": lid})["consent_status"] == "withdrawn"
        assert admin.post(f"{API}/leads/{lid}/consent/withdraw", json={}).status_code == 400


class TestAssign:
    def test_rep_cannot_assign(self, rep1):
        lid = _new_lead()
        assert rep1.post(f"{API}/leads/{lid}/assign", json={"user_id": rep1.me["id"]}).status_code == 403

    def test_cross_org_and_inactive(self, admin, manager):
        lid = _new_lead()
        reg = requests.post(f"{API}/auth/register", json={"first_name": "TEST", "last_name": "Other",
                            "email": f"test_{uuid.uuid4().hex[:8]}@test.com", "password": "Passw0rd!",
                            "organization_name": f"TEST_Org_{uuid.uuid4().hex[:6]}"})
        assert reg.status_code == 200
        CREATED["users"].append(reg.json()["user"]["id"])
        CREATED["orgs"].append(reg.json()["user"]["organization_id"])
        assert manager.post(f"{API}/leads/{lid}/assign", json={"user_id": reg.json()["user"]["id"]}).status_code == 400
        email, r = _mk_user(admin, "dealership_representative")
        uid = r.json()["user"]["id"]
        assert admin.post(f"{API}/users/{uid}/deactivate").status_code == 200
        assert manager.post(f"{API}/leads/{lid}/assign", json={"user_id": uid}).status_code == 400
        rep2 = _uid(admin, "rep2@autoacquire.ai")
        assert manager.post(f"{API}/leads/{lid}/assign", json={"user_id": rep2}).status_code == 200
        assert mdb.leads.find_one({"id": lid})["assigned_user_id"] == rep2

    def test_rep_patch_lead_bypass(self, rep1):
        """Security probe: rep should not be able to self-assign via PATCH /leads/{id}."""
        lid = _new_lead()
        r = rep1.patch(f"{API}/leads/{lid}", json={"assigned_user_id": rep1.me["id"]})
        assert r.status_code == 403, f"rep could PATCH unassigned lead: {r.status_code}"

    def test_notes_unknown_lead(self, admin):
        """Notes endpoint should 404 for non-existent lead."""
        r = admin.post(f"{API}/leads/{uuid.uuid4()}/notes", json={"content": "TEST_orphan"})
        assert r.status_code == 404, f"got {r.status_code}"


# ---------- Milestone 1B: user management ----------
class TestUsers:
    def test_manager_role_limits(self, manager):
        _, r = _mk_user(manager, "dealership_admin")
        assert r.status_code == 403
        r = manager.get(f"{API}/users/roles").json()
        assert r["manageable"] == ["dealership_representative"]

    def test_invite_flow(self, manager):
        email, r = _mk_user(manager, "dealership_representative")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user"]["status"] == "invited" and "password_hash" not in d["user"]
        assert "/reset-password?token=" in d["setup_url"] and d["setup_url"].startswith("https://")
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "Whatever1!"}).status_code == 401
        tok = d["setup_url"].split("token=")[1]
        assert requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "short"}).status_code == 400
        assert requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "TestPass123!"}).status_code == 200
        lr = requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPass123!"})
        assert lr.status_code == 200
        assert lr.json()["user"]["status"] == "active"
        assert requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "TestPass123!"}).status_code == 400
        u = next(x for x in manager.get(f"{API}/users", params={"search": email}).json())
        assert u["last_login_at"]

    def test_list_filters(self, admin):
        r = admin.get(f"{API}/users", params={"role": "dealership_representative"})
        assert r.status_code == 200 and all(u["role"] == "dealership_representative" for u in r.json())
        r = admin.get(f"{API}/users", params={"search": "rep1@"})
        assert [u["email"] for u in r.json()] == ["rep1@autoacquire.ai"]
        assert all("password_hash" not in u for u in admin.get(f"{API}/users").json())

    def test_rep_users_access(self, rep1):
        r = rep1.get(f"{API}/users")
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            assert all("phone" not in u and "last_login_at" not in u for u in r.json())
        _, c = _mk_user(rep1, "dealership_representative")
        assert c.status_code == 403

    def test_edit_user(self, admin, manager):
        email, r = _mk_user(admin, "dealership_representative")
        uid = r.json()["user"]["id"]
        groups = admin.get(f"{API}/dealer-groups").json()
        gid = groups[0]["id"] if groups else None
        p = admin.patch(f"{API}/users/{uid}", json={"first_name": "TEST_Renamed", "role": "dealership_manager", "dealer_group_id": gid})
        assert p.status_code == 200, p.text
        assert p.json()["first_name"] == "TEST_Renamed" and p.json()["role"] == "dealership_manager"
        assert p.json()["dealer_group_id"] == gid
        # manager can't edit now-manager or admin
        assert manager.patch(f"{API}/users/{uid}", json={"first_name": "x"}).status_code == 403
        assert manager.patch(f"{API}/users/{_uid(admin, 'admin@autoacquire.ai')}", json={"first_name": "x"}).status_code == 403
        assert admin.patch(f"{API}/users/{uid}", json={"role": "platform_admin"}).status_code == 403
        assert admin.patch(f"{API}/users/{uid}", json={"dealer_group_id": "nope"}).status_code == 400
        assert admin.patch(f"{API}/users/{uid}", json={"organization_id": "x"}).status_code == 403

    def test_self_role_change(self, admin):
        assert admin.patch(f"{API}/users/{admin.me['id']}", json={"role": "dealership_manager"}).status_code == 400
        assert mdb.users.find_one({"id": admin.me["id"]})["role"] == "dealership_admin"

    def test_deactivate_reactivate(self, admin):
        email, r = _mk_user(admin, "dealership_representative")
        uid = r.json()["user"]["id"]
        tok = r.json()["setup_url"].split("token=")[1]
        assert requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "TestPass123!"}).status_code == 200
        lr = requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPass123!"})
        utok = lr.json()["token"]
        assert admin.post(f"{API}/users/{uid}/deactivate").status_code == 200
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPass123!"}).status_code == 403
        assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {utok}"}).status_code == 401
        assert admin.post(f"{API}/users/{uid}/deactivate").status_code == 400
        rr = admin.post(f"{API}/users/{uid}/reactivate")
        assert rr.status_code == 200 and rr.json()["status"] == "active"
        assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {utok}"}).status_code == 200
        assert admin.post(f"{API}/users/{admin.me['id']}/deactivate").status_code == 400

    def test_password_reset(self, admin):
        email, r = _mk_user(admin, "dealership_representative")
        uid = r.json()["user"]["id"]
        setup_tok = r.json()["setup_url"].split("token=")[1]
        rr = admin.post(f"{API}/users/{uid}/password-reset")
        assert rr.status_code == 200 and "reset_url" in rr.json()
        assert requests.post(f"{API}/auth/reset-password", json={"token": setup_tok, "password": "TestPass123!"}).status_code == 400
        t1 = rr.json()["reset_url"].split("token=")[1]
        t2 = admin.post(f"{API}/users/{uid}/password-reset").json()["reset_url"].split("token=")[1]
        assert requests.post(f"{API}/auth/reset-password", json={"token": t1, "password": "TestPass123!"}).status_code == 400
        assert requests.post(f"{API}/auth/reset-password", json={"token": t2, "password": "NewPass123!"}).status_code == 200
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "NewPass123!"}).status_code == 200
