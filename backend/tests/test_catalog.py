"""Catalog: localities/personas/modules/trust rubric/entitlement."""
import requests
from .conftest import BASE_URL


class TestCatalog:
    def test_localities_list(self):
        r = requests.get(f"{BASE_URL}/api/localities", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 30
        sample = data[0]
        for key in ("slug", "name", "warm"):
            assert key in sample

    def test_localities_search_by_name(self):
        r = requests.get(f"{BASE_URL}/api/localities", params={"q": "Kora"}, timeout=30)
        assert r.status_code == 200
        assert any("kora" in d["slug"] for d in r.json())

    def test_localities_search_by_pincode(self):
        r = requests.get(f"{BASE_URL}/api/localities", params={"q": "560034"}, timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_localities_search_by_zone(self):
        r = requests.get(f"{BASE_URL}/api/localities", params={"q": "East"}, timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_personas_list(self):
        r = requests.get(f"{BASE_URL}/api/personas", timeout=30)
        assert r.status_code == 200
        keys = {p["key"] for p in r.json()}
        assert {"bachelor", "student", "family_kids", "elderly", "wfh_pro", "investor"}.issubset(keys)

    def test_modules_list(self):
        r = requests.get(f"{BASE_URL}/api/modules", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 15

    def test_trust_rubric(self):
        r = requests.get(f"{BASE_URL}/api/trust/rubric", timeout=30)
        assert r.status_code == 200
        data = r.json()
        for key in ("rubric", "modules", "personas", "baseline_weights",
                    "freshness_policy", "source_types", "principles"):
            assert key in data
        assert len(data["personas"]) >= 6
        assert len(data["modules"]) >= 15

    def test_entitlement_pro(self, pro_session):
        r = pro_session.get(f"{BASE_URL}/api/entitlement", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["pro"] is True
        assert d["can_compare"] is True

    def test_entitlement_buyer(self, buyer_session):
        r = buyer_session.get(f"{BASE_URL}/api/entitlement", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["pro"] is False
        assert d["can_compare"] is False
        assert d["free_limit"] == 5
