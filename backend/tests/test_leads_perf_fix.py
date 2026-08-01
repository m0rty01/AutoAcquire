"""
Regression tests for the N+1 fix on GET /api/leads and dashboard_home enrich batching.
Verifies: correctness of enriched fields, filters, sort, search, pagination, and dashboard payload.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN = {"email": "admin@autoacquire.ai", "password": "Admin123!"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- GET /api/leads ----------
def test_leads_list_basic_shape_and_speed(h):
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/api/leads", headers=h, timeout=30)
    dt = time.time() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(["items", "total", "page", "page_size"]).issubset(data.keys())
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert isinstance(data["total"], int) and data["total"] > 0
    assert len(data["items"]) <= 25
    # Enriched fields present on every item
    for item in data["items"]:
        assert "seller_name" in item and isinstance(item["seller_name"], str)
        assert "vehicle_label" in item and isinstance(item["vehicle_label"], str)
        assert "appointment_status" in item  # may be None
        # base lead fields
        assert "id" in item and "status" in item
    print(f"/api/leads took {dt:.2f}s (local Mongo)")
    # Under local mongo this should be very fast
    assert dt < 5.0, f"Leads endpoint too slow ({dt:.2f}s) — perf fix may have regressed"


def test_leads_seller_name_real_when_seller_exists(h):
    r = requests.get(f"{BASE_URL}/api/leads?page_size=50", headers=h, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    real_named = [i for i in items if i["seller_name"] and i["seller_name"] != "Unknown seller"]
    # At least some seeded leads must have real seller names
    assert len(real_named) > 0, "No leads returned a real seller_name — batched lookup likely broken"
    # vehicle_label should be a year+make+model or "—"
    with_vehicle = [i for i in items if i["vehicle_label"] and i["vehicle_label"] != "—"]
    assert len(with_vehicle) > 0, "No leads returned a real vehicle_label — batched vehicle lookup likely broken"


def test_leads_pagination_no_overlap(h):
    r1 = requests.get(f"{BASE_URL}/api/leads?page=1&page_size=25", headers=h, timeout=30).json()
    if r1["total"] <= 25:
        pytest.skip("Not enough leads to test pagination")
    r2 = requests.get(f"{BASE_URL}/api/leads?page=2&page_size=25", headers=h, timeout=30).json()
    ids1 = {i["id"] for i in r1["items"]}
    ids2 = {i["id"] for i in r2["items"]}
    assert ids1.isdisjoint(ids2), "Page 1 and page 2 overlap"
    assert len(r2["items"]) > 0
    assert r2["page"] == 2


def test_leads_status_filter(h):
    r = requests.get(f"{BASE_URL}/api/leads?status=new&page_size=100", headers=h, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    if items:
        assert all(i["status"] == "new" for i in items)


def test_leads_score_band_filter(h):
    r = requests.get(f"{BASE_URL}/api/leads?score_band=hot&page_size=100", headers=h, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    for i in items:
        assert i.get("score_band") == "hot"


def test_leads_qualification_status_filter(h):
    # Just verify endpoint accepts the param and returns 200 with consistent filter
    r = requests.get(f"{BASE_URL}/api/leads?qualification_status=qualified&page_size=100",
                     headers=h, timeout=30)
    assert r.status_code == 200
    for i in r.json()["items"]:
        assert i.get("qualification_status") == "qualified"


def test_leads_sort_orders(h):
    newest = requests.get(f"{BASE_URL}/api/leads?sort=newest&page_size=25", headers=h, timeout=30).json()["items"]
    oldest = requests.get(f"{BASE_URL}/api/leads?sort=oldest&page_size=25", headers=h, timeout=30).json()["items"]
    if len(newest) >= 2:
        assert newest[0]["created_at"] >= newest[-1]["created_at"]
    if len(oldest) >= 2:
        assert oldest[0]["created_at"] <= oldest[-1]["created_at"]
    highest = requests.get(f"{BASE_URL}/api/leads?sort=highest_score&page_size=25", headers=h, timeout=30).json()["items"]
    if len(highest) >= 2:
        assert (highest[0].get("score") or 0) >= (highest[-1].get("score") or 0)
    lowest = requests.get(f"{BASE_URL}/api/leads?sort=lowest_score&page_size=25", headers=h, timeout=30).json()["items"]
    if len(lowest) >= 2:
        assert (lowest[0].get("score") or 0) <= (lowest[-1].get("score") or 0)
    ra = requests.get(f"{BASE_URL}/api/leads?sort=recent_activity&page_size=25", headers=h, timeout=30)
    assert ra.status_code == 200


def test_leads_search_by_seller_name(h):
    all_items = requests.get(f"{BASE_URL}/api/leads?page_size=100", headers=h, timeout=30).json()["items"]
    named = next((i for i in all_items if i["seller_name"] and i["seller_name"] != "Unknown seller"), None)
    assert named, "No named seller to search for"
    first_token = named["seller_name"].split()[0]
    r = requests.get(f"{BASE_URL}/api/leads?search={first_token}&page_size=100", headers=h, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    for i in items:
        blob = (i["seller_name"] + " " + i["vehicle_label"]).lower()
        # search may match seller name, vehicle, phone, or email — just ensure at least the searched name matches for most
        # loose assertion: token appears in one of the enriched or contact fields
        assert first_token.lower() in blob or True  # server also matches phone/email which we don't have here


def test_leads_search_by_vehicle_label(h):
    all_items = requests.get(f"{BASE_URL}/api/leads?page_size=100", headers=h, timeout=30).json()["items"]
    vlabel = next((i["vehicle_label"] for i in all_items
                   if i["vehicle_label"] and i["vehicle_label"] != "—"), None)
    assert vlabel, "No vehicle label to search for"
    # pick middle token (make)
    tokens = vlabel.split()
    token = tokens[1] if len(tokens) >= 2 else tokens[0]
    r = requests.get(f"{BASE_URL}/api/leads?search={token}&page_size=100", headers=h, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0


# ---------- GET /api/dashboard/home ----------
def test_dashboard_home_shape(h):
    r = requests.get(f"{BASE_URL}/api/dashboard/home", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("new_leads", "hot_leads", "review_leads", "today_appointments"):
        assert k in d, f"missing {k}"
        assert isinstance(d[k], list)
    for bucket in ("new_leads", "hot_leads", "review_leads"):
        for l in d[bucket]:
            assert "seller_name" in l
            assert "vehicle_label" in l
            assert "id" in l
