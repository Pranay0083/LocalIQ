"""Shared fixtures for LocalIQ backend pytest suite."""
import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

frontend_env = dotenv_values(Path(__file__).resolve().parents[2] / "frontend" / ".env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing from environment and frontend/.env")
BASE_URL = base_url.rstrip("/")

CREDS = {
    "pro": {"email": "pro@localiq.in", "password": "pro12345"},
    "buyer": {"email": "buyer@localiq.in", "password": "buyer123"},
    "admin": {"email": "admin@localiq.in", "password": "admin123"},
}


def _resilient_session() -> requests.Session:
    """Retry transient connect errors - the preview ingress occasionally refuses a connection."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    retry = Retry(total=4, connect=4, read=2, backoff_factor=0.8,
                  status_forcelist=(502, 503, 504), allowed_methods=None)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _login(email: str, password: str) -> requests.Session:
    s = _resilient_session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login for {email} failed: {r.status_code} {r.text[:300]}")
    tok = r.json().get("access_token")
    if not tok:
        pytest.fail(f"Login response missing access_token for {email}")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="module")
def pro_session():
    return _login(**CREDS["pro"])


@pytest.fixture(scope="module")
def buyer_session():
    return _login(**CREDS["buyer"])


@pytest.fixture(scope="module")
def admin_session():
    return _login(**CREDS["admin"])


def _register_throwaway() -> requests.Session:
    session = _resilient_session()
    email = f"pytest-{uuid.uuid4().hex[:12]}@pytest.localiq.in"
    r = session.post(f"{BASE_URL}/api/auth/register",
                     json={"email": email, "password": "pytest12345", "name": "Pytest Bot"},
                     timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Throwaway register failed: {r.status_code} {r.text[:300]}")
    session.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return session


@pytest.fixture
def throwaway_session():
    """A brand-new account per test, so per-user daily caps never leak between runs."""
    return _register_throwaway()


@pytest.fixture(scope="module")
def isolated_owner():
    """A brand-new account per test module - own chat history, own daily caps."""
    return _register_throwaway()


def generate_report(session: requests.Session, locality: str, persona_key: str = "family_kids") -> str:
    """Generate (or fetch the cached) report for a warm locality and return its id."""
    r = session.post(f"{BASE_URL}/api/reports/generate",
                     json={"locality": locality, "persona_key": persona_key}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"generate failed: {r.status_code} {r.text[:300]}")
    body = r.json()
    if body.get("report_id"):
        return body["report_id"]
    for _ in range(60):
        job = session.get(f"{BASE_URL}/api/reports/job/{body['job_id']}", timeout=30).json()
        if job["status"] == "done":
            return job["report_id"]
        if job["status"] == "failed":
            pytest.fail(f"report job failed: {job}")
        time.sleep(4)
    pytest.fail("report never completed")


@pytest.fixture(scope="session")
def existing_pro_report_id():
    """An Indiranagar report owned by pro@localiq.in - generated on first use, then reused."""
    return generate_report(_login(**CREDS["pro"]), "indiranagar")
