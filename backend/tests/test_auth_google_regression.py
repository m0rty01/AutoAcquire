"""Regression tests for auth refactor: email/password still works;
new POST /api/auth/google validation cases; old /google/session removed."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dealer-lead-hub.preview.emergentagent.com").rstrip("/")


def test_login_email_password_returns_token_and_user():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@autoacquire.ai", "password": "Admin123!"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
    assert data["user"]["email"] == "admin@autoacquire.ai"
    assert data["user"]["role"] in ("dealership_admin", "platform_admin")


def test_login_bad_password_401():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@autoacquire.ai", "password": "wrongpass"})
    assert r.status_code == 401


def test_token_authorizes_me_and_leads():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@autoacquire.ai", "password": "Admin123!"})
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    me = requests.get(f"{BASE_URL}/api/auth/me", headers=h)
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "admin@autoacquire.ai"

    leads = requests.get(f"{BASE_URL}/api/leads", headers=h)
    assert leads.status_code == 200, leads.text


def test_google_invalid_credential_returns_401():
    r = requests.post(f"{BASE_URL}/api/auth/google",
                      json={"credential": "not-a-real-google-id-token"})
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


def test_google_missing_credential_returns_422():
    r = requests.post(f"{BASE_URL}/api/auth/google", json={})
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


def test_old_emergent_google_session_endpoint_is_404():
    r = requests.post(f"{BASE_URL}/api/auth/google/session",
                      headers={"X-Session-ID": "irrelevant"})
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"
