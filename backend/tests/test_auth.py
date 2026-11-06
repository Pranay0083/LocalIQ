"""Auth: register/login/logout/me/wrong password."""
import uuid
import requests
from .conftest import BASE_URL, CREDS


class TestAuth:
    def test_login_pro_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=CREDS["pro"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == CREDS["pro"]["email"]
        assert data["plan"] in ("pro_monthly", "pro_annual")
        assert isinstance(data.get("access_token"), str) and len(data["access_token"]) > 20

    def test_login_buyer_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=CREDS["buyer"], timeout=30)
        assert r.status_code == 200
        assert r.json()["plan"] == "free"

    def test_login_wrong_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": CREDS["pro"]["email"], "password": "wrongpass!!"}, timeout=30)
        assert r.status_code == 401

    def test_me_returns_user(self, pro_session):
        r = pro_session.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == CREDS["pro"]["email"]

    def test_me_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code in (401, 403)

    def test_register_and_logout(self):
        email = f"test_{uuid.uuid4().hex[:10]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/register",
                          json={"email": email, "password": "testpass123", "name": "TEST User"},
                          timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["plan"] == "free"
        token = data["access_token"]
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}"})
        # /me should work
        r2 = s.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r2.status_code == 200
        # duplicate register -> 409
        r3 = requests.post(f"{BASE_URL}/api/auth/register",
                           json={"email": email, "password": "another", "name": "dup"}, timeout=30)
        assert r3.status_code == 409
        # logout endpoint
        r4 = s.post(f"{BASE_URL}/api/auth/logout", timeout=30)
        assert r4.status_code == 200

    def test_profile_update(self, pro_session):
        r = pro_session.put(f"{BASE_URL}/api/auth/profile",
                            json={"stage": "buyer", "household": "couple",
                                  "work_locality": "whitefield", "work_mode": "hybrid",
                                  "budget_band": "60k_plus", "commute_tolerance": "30",
                                  "free_text": "quiet with parks",
                                  "persona_key": "family_kids"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["persona_key"] == "family_kids"
