"""Evals: 27-check golden-set regression."""
import requests
from .conftest import BASE_URL


class TestEvals:
    def test_golden_evals_all_pass(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/evals/golden", timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        # Accept a couple of possible shapes
        checks = data.get("checks") or data.get("results") or []
        passed = sum(1 for c in checks if c.get("passed") or c.get("ok") or c.get("status") == "pass")
        failed = len(checks) - passed
        assert len(checks) >= 20, f"expected >=20 golden checks, got {len(checks)}: {data}"
        assert failed == 0, f"{failed} eval checks failed: {[c for c in checks if not (c.get('passed') or c.get('ok') or c.get('status') == 'pass')]}"
