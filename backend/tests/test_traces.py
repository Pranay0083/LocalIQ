"""Traces / agent ledger endpoint."""
import requests
from .conftest import BASE_URL


class TestTraces:
    def test_traces_endpoint(self, pro_session):
        r = pro_session.get(f"{BASE_URL}/api/traces", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data
        assert "ledger" in data
        assert isinstance(data["jobs"], list)
