"""
CORS mechanism verification + Auth regression tests.
Context: Backend deployed with env-driven CORS_ORIGINS. Preview has '*',
which Starlette should reflect as the specific request Origin even with
allow_credentials=True.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
# Fallback: also read frontend .env if not set in env
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass

# For CORS header assertions we hit the backend DIRECTLY (localhost:8001).
# The preview ingress (Cloudflare) rewrites/injects its own CORS headers, which
# masks what Starlette actually emits. Production (Render) does not have that
# rewrite, so verifying the middleware at the app layer is the correct test.
DIRECT_URL = os.environ.get("DIRECT_BACKEND_URL", "http://localhost:8001").rstrip("/")

ADMIN_EMAIL = "admin@autoacquire.ai"
ADMIN_PASSWORD = "Admin123!"


# ---------------- CORS preflight tests ----------------

@pytest.mark.parametrize("origin", [
    "https://autonovaia.ca",
    "https://www.autonovaia.ca",
])
def test_cors_preflight_login(origin):
    """OPTIONS preflight to /api/auth/login should reflect the Origin."""
    r = requests.options(
        f"{DIRECT_URL}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=15,
    )
    assert r.status_code in (200, 204), f"preflight status {r.status_code}, body={r.text}"
    # Case-insensitive header access via requests
    aco = r.headers.get("access-control-allow-origin")
    acc = r.headers.get("access-control-allow-credentials")
    assert aco == origin, f"expected ACAO={origin}, got {aco}; all headers={dict(r.headers)}"
    assert acc and acc.lower() == "true", f"expected ACA-Credentials=true, got {acc}"
    # method allowed
    acm = r.headers.get("access-control-allow-methods", "")
    assert "POST" in acm.upper() or "*" in acm, f"POST not in allow-methods: {acm}"


def test_cors_actual_post_login_has_acao():
    """Actual POST /api/auth/login with cross-origin should include ACAO header.

    Note: Starlette CORSMiddleware with allow_origins=['*'] returns '*' on
    actual (non-preflight) responses; it reflects the specific origin only on
    preflight. In production, CORS_ORIGINS will be an explicit list containing
    https://autonovaia.ca, and reflection will produce the exact origin.
    So we only assert that an ACAO header IS present and is either '*' or the
    request origin.
    """
    origin = "https://autonovaia.ca"
    r = requests.post(
        f"{DIRECT_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Origin": origin, "Content-Type": "application/json"},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    aco = r.headers.get("access-control-allow-origin")
    assert aco in (origin, "*"), f"expected ACAO to be '{origin}' or '*', got {aco}"


# ---------------- Auth regression ----------------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 0
    assert "user" in data and data["user"].get("email") == ADMIN_EMAIL
    return data["token"]


def test_auth_me(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, f"/auth/me failed: {r.status_code} {r.text}"
    data = r.json()
    # /auth/me returns nested {user: {...}, organization: {...}}
    user = data.get("user", data)
    assert user.get("email") == ADMIN_EMAIL


def test_leads_authorized(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/leads",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"/leads failed: {r.status_code} {r.text}"
    data = r.json()
    # Accept either list or paginated dict
    assert isinstance(data, (list, dict))


# ---------------- Core app health ----------------

def test_public_prestige_auto_toronto():
    r = requests.get(f"{BASE_URL}/api/public/prestige-auto-toronto", timeout=15)
    assert r.status_code == 200, f"public dealership failed: {r.status_code} {r.text}"


def test_dashboard_home_with_token(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/dashboard/home",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"/dashboard/home failed: {r.status_code} {r.text}"
    data = r.json()
    # Enriched buckets should be present (allow empty lists but keys must exist)
    for key in ("new_leads", "hot_leads", "review_leads"):
        assert key in data, f"dashboard/home missing key {key}: {list(data.keys())}"


def _has_no_objectid(obj):
    """Recursively assert no bson.ObjectId leakage (and _id not present)."""
    from bson import ObjectId  # type: ignore
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in dict: keys={list(obj.keys())}"
        for v in obj.values():
            _has_no_objectid(v)
    elif isinstance(obj, list):
        for v in obj:
            _has_no_objectid(v)
    else:
        assert not isinstance(obj, ObjectId), "ObjectId leaked into response"


def test_leads_list_enriched(admin_token):
    """GET /api/leads returns enriched pagination with seller_name/vehicle_label/appointment_status."""
    r = requests.get(
        f"{BASE_URL}/api/leads?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"/leads failed: {r.status_code} {r.text}"
    data = r.json()
    assert isinstance(data, dict), f"expected paginated dict, got {type(data)}"
    for key in ("items", "total", "page", "page_size"):
        assert key in data, f"missing pagination key {key}"
    items = data["items"]
    assert isinstance(items, list)
    if items:
        first = items[0]
        # Enrichment fields
        for f in ("seller_name", "vehicle_label", "appointment_status"):
            assert f in first, f"lead item missing enrichment field {f}: {list(first.keys())}"


def test_lead_detail_no_objectid_leak(admin_token):
    """GET /api/leads/{id} — regression for clean(lead) fix. Must be 200 and valid JSON with no ObjectId leak."""
    # Get a real lead id
    r = requests.get(
        f"{BASE_URL}/api/leads?page=1&page_size=5",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200
    items = r.json().get("items", [])
    if not items:
        pytest.skip("No leads available to test detail endpoint")
    lead_id = items[0]["id"]

    r = requests.get(
        f"{BASE_URL}/api/leads/{lead_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"/leads/{lead_id} failed: {r.status_code} {r.text}"
    # Must be valid JSON
    data = r.json()
    # Expected keys per problem statement
    expected_keys = ["lead", "seller", "vehicle", "conversation", "messages",
                     "score", "matches", "appointment", "notes"]
    for k in expected_keys:
        assert k in data, f"lead-detail response missing key {k}: {list(data.keys())}"
    # lead must be a dict with an id matching
    assert isinstance(data["lead"], dict)
    assert data["lead"].get("id") == lead_id
    # No ObjectId / _id leakage anywhere
    _has_no_objectid(data)
