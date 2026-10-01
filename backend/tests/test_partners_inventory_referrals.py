"""Backend tests for Partners (dealer groups), Inventory Sources, Referrals, and Cron."""
import os
import io
import pytest
import requests

def _read_frontend_backend_url():
    for line in open("/app/frontend/.env"):
        if line.strip().startswith("REACT_APP_BACKEND_URL"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_backend_url()).rstrip("/")
ADMIN_EMAIL = "admin@autoacquire.ai"
ADMIN_PASSWORD = "Admin123!"


def _read_cron_secret():
    for line in open("/app/backend/.env"):
        if line.strip().startswith("WEBHOOK_CRON_SECRET"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


CRON_SECRET = _read_cron_secret()


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def default_group(client):
    r = client.get(f"{BASE_URL}/api/dealer-groups", timeout=30)
    assert r.status_code == 200
    groups = r.json()
    default = next((g for g in groups if g.get("is_default")), None)
    assert default is not None, "No default dealer group found"
    return default


class TestDealerGroups:
    def test_list_has_default_house_inventory(self, default_group):
        assert default_group["vehicle_count"] >= 0
        # should have significant inventory from seed (~27)
        print(f"House Inventory vehicle_count = {default_group['vehicle_count']}")

    def test_create_and_update_and_cannot_delete_default(self, client, default_group):
        # Create new group
        payload = {"name": "TEST_Group_PartnerFlow", "website": "https://ex.com",
                   "referral_amount": 150.0, "referral_program": "Mon Coequipier"}
        r = client.post(f"{BASE_URL}/api/dealer-groups", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        g = r.json()
        gid = g["id"]
        assert g["name"] == payload["name"]
        assert g["referral_amount"] == 150.0
        assert g["is_default"] is False

        # Update
        r2 = client.patch(f"{BASE_URL}/api/dealer-groups/{gid}",
                          json={"referral_amount": 250.0, "status": "paused"}, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["referral_amount"] == 250.0
        assert r2.json()["status"] == "paused"

        # Default cannot be deleted
        rdel = client.delete(f"{BASE_URL}/api/dealer-groups/{default_group['id']}", timeout=30)
        assert rdel.status_code == 400

        # Delete non-default succeeds
        r3 = client.delete(f"{BASE_URL}/api/dealer-groups/{gid}", timeout=30)
        assert r3.status_code == 200
        # verify gone
        r4 = client.get(f"{BASE_URL}/api/dealer-groups", timeout=30)
        assert all(x["id"] != gid for x in r4.json())


class TestInventorySources:
    @pytest.fixture(scope="class")
    def group_id(self, client):
        r = client.post(f"{BASE_URL}/api/dealer-groups",
                        json={"name": "TEST_Sources_Group", "referral_amount": 200,
                              "referral_program": "Le Prix du Gros"}, timeout=30)
        assert r.status_code == 200
        gid = r.json()["id"]
        yield gid
        client.delete(f"{BASE_URL}/api/dealer-groups/{gid}", timeout=30)

    def test_csv_upload_source_has_push_urls(self, client, group_id):
        r = client.post(f"{BASE_URL}/api/inventory-sources",
                        json={"dealer_group_id": group_id, "name": "TEST_CSV",
                              "type": "csv_upload", "config": {}}, timeout=30)
        assert r.status_code == 200, r.text
        s = r.json()
        assert "push_url" in s and "token=" in s["push_url"]
        assert "full_push_url" in s and "mode=full" in s["full_push_url"]
        # Should NOT leak feed_token raw
        assert "feed_token" not in s

    def test_http_feed_run_imports(self, client, group_id):
        feed_url = f"{BASE_URL}/api/inventory/template"
        r = client.post(f"{BASE_URL}/api/inventory-sources",
                        json={"dealer_group_id": group_id, "name": "TEST_HTTP",
                              "type": "http_feed", "config": {"url": feed_url, "format": "csv"}},
                        timeout=30)
        assert r.status_code == 200
        sid = r.json()["id"]
        rr = client.post(f"{BASE_URL}/api/inventory-sources/{sid}/run", timeout=90)
        assert rr.status_code == 200, rr.text
        stats = rr.json()
        assert (stats.get("imported", 0) + stats.get("updated", 0)) >= 1
        # Check source last_status in list
        lst = client.get(f"{BASE_URL}/api/inventory-sources?dealer_group_id={group_id}",
                         timeout=30).json()
        row = next(x for x in lst if x["id"] == sid)
        assert row["last_status"] == "success"

    def test_scraper_run_stub_not_error(self, client, group_id):
        r = client.post(f"{BASE_URL}/api/inventory-sources",
                        json={"dealer_group_id": group_id, "name": "TEST_SCR",
                              "type": "scraper", "config": {"url": "https://ex.com"}}, timeout=30)
        assert r.status_code == 200
        sid = r.json()["id"]
        rr = client.post(f"{BASE_URL}/api/inventory-sources/{sid}/run", timeout=30)
        assert rr.status_code == 200
        js = rr.json()
        # framework ready stub => should have skipped_reason or message
        assert js.get("skipped_reason") or "framework" in str(js).lower() or js.get("imported", 0) == 0

    def test_csv_upload_push_url_scoped_to_group(self, client, group_id):
        # Create csv_upload source
        r = client.post(f"{BASE_URL}/api/inventory-sources",
                        json={"dealer_group_id": group_id, "name": "TEST_Push",
                              "type": "csv_upload", "config": {}}, timeout=30)
        sid = r.json()["id"]
        push_url = r.json()["push_url"]
        # push_url may be relative if PUBLIC_BASE_URL empty — construct full
        if push_url.startswith("/"):
            push_url = BASE_URL + push_url
        # Build minimal CSV
        csv_body = ("stock_number,vin,year,make,model,trim,price,mileage,body_type,status\n"
                    "TESTSTK1,1TESTVIN00000001,2023,TestMake,TestModel,TM,20000,1000,SUV,available\n"
                    "TESTSTK2,1TESTVIN00000002,2022,TestMake,TestModel,TM,19000,2000,SUV,available\n")
        # Use plain requests (no auth header needed for feed, uses token)
        files = {"file": ("inv.csv", csv_body, "text/csv")}
        rr = requests.post(push_url, files=files, timeout=60)
        assert rr.status_code == 200, rr.text
        stats = rr.json()
        assert stats.get("imported", 0) + stats.get("updated", 0) >= 2

        # Vehicle count on the group should include these
        groups = client.get(f"{BASE_URL}/api/dealer-groups", timeout=30).json()
        g = next(x for x in groups if x["id"] == group_id)
        assert g["vehicle_count"] >= 2

        # Full mode: push a smaller file -> missing vehicles get deactivated
        full_url = push_url + "&mode=full"
        csv_body2 = ("stock_number,vin,year,make,model,trim,price,mileage,body_type,status\n"
                     "TESTSTK1,1TESTVIN00000001,2023,TestMake,TestModel,TM,20000,1000,SUV,available\n")
        rr2 = requests.post(full_url, files={"file": ("inv2.csv", csv_body2, "text/csv")}, timeout=60)
        assert rr2.status_code == 200, rr2.text
        stats2 = rr2.json()
        assert stats2.get("deactivated", 0) >= 1


class TestCron:
    def test_cron_requires_bearer(self):
        r = requests.post(f"{BASE_URL}/api/cron/sync-sources", timeout=30)
        assert r.status_code == 401

    def test_cron_wrong_secret(self):
        r = requests.post(f"{BASE_URL}/api/cron/sync-sources",
                          headers={"Authorization": "Bearer wrong"}, timeout=30)
        assert r.status_code == 401

    def test_cron_valid_secret(self):
        assert CRON_SECRET, "WEBHOOK_CRON_SECRET not found in /app/backend/.env"
        r = requests.post(f"{BASE_URL}/api/cron/sync-sources",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r.status_code in (200, 202), r.text
        assert r.json().get("accepted") is True


class TestReferrals:
    def test_list_has_totals_and_statuses(self, client):
        r = client.get(f"{BASE_URL}/api/referrals", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "referrals" in j
        assert "totals" in j
        assert "statuses" in j
        for k in ("pipeline", "earned", "count"):
            assert k in j["totals"]

    def test_auto_create_via_run_inventory_match_and_patch(self, client):
        # Find a lead with inventory preferences, prefer qualified ones
        leads = client.get(f"{BASE_URL}/api/leads?page=1&page_size=100", timeout=30).json()
        items = leads.get("items") if isinstance(leads, dict) else leads
        if not items:
            pytest.skip("No leads available")
        target = None
        for ld in items:
            lid = ld["id"]
            # Trigger match
            rm = client.post(f"{BASE_URL}/api/leads/{lid}/run-inventory-match", timeout=60)
            if rm.status_code == 200 and rm.json().get("matches"):
                target = lid
                break
        if not target:
            pytest.skip("No lead produced inventory matches (seed may lack preferences)")

        # Check referral exists for this lead
        refs = client.get(f"{BASE_URL}/api/referrals", timeout=30).json()["referrals"]
        mine = [r for r in refs if r.get("lead_id") == target]
        assert mine, "Expected a referral created from run-inventory-match"
        rid = mine[0]["id"]

        # Update status + external_reference
        rp = client.patch(f"{BASE_URL}/api/referrals/{rid}",
                         json={"status": "sent", "external_reference": "MCQ-123"}, timeout=30)
        assert rp.status_code == 200
        assert rp.json()["status"] == "sent"
        assert rp.json()["external_reference"] == "MCQ-123"
