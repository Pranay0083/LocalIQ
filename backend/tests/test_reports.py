"""Reports: existing report fetch, lens switcher, chat, and cached generation path."""
import time
import requests
import pytest
from .conftest import BASE_URL


class TestExistingReport:
    def test_fetch_existing_report(self, pro_session, existing_pro_report_id):
        r = pro_session.get(f"{BASE_URL}/api/reports/{existing_pro_report_id}", timeout=30)
        assert r.status_code == 200, r.text
        doc = r.json()
        for key in ("id", "locality", "persona_key", "persona_label", "composite",
                    "baseline_composite", "narrative", "cards", "sources", "module_scores"):
            assert key in doc, f"missing {key}"
        # never leak Mongo _id
        assert "_id" not in doc
        # locality expected to be Indiranagar
        assert doc["locality"]["slug"] == "indiranagar"
        # persona label present
        assert isinstance(doc["persona_label"], str)
        # composite scores
        assert doc["composite"].get("score") is not None
        assert doc["baseline_composite"].get("score") is not None
        # cards should be a non-empty list
        assert isinstance(doc["cards"], list) and len(doc["cards"]) > 0

    def test_report_bad_id(self, pro_session):
        r = pro_session.get(f"{BASE_URL}/api/reports/notanid", timeout=30)
        assert r.status_code == 400

    def test_report_not_owned(self, buyer_session, existing_pro_report_id):
        r = buyer_session.get(f"{BASE_URL}/api/reports/{existing_pro_report_id}", timeout=30)
        assert r.status_code == 404

    def test_chat_history_endpoint(self, pro_session, existing_pro_report_id):
        r = pro_session.get(f"{BASE_URL}/api/reports/{existing_pro_report_id}/chat", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestCachedGeneration:
    """Verify entitlement.used is unchanged when the same locality+persona is re-requested."""

    def test_cached_path_does_not_increment_used(self, buyer_session):
        ent_before = buyer_session.get(f"{BASE_URL}/api/entitlement", timeout=30).json()
        used_before = ent_before["used"]
        # Ask for a locality+persona we assume the buyer has NOT generated. Even if not cached,
        # we can only test the cached path if there is already a report. So first try to find one.
        reports = buyer_session.get(f"{BASE_URL}/api/reports", timeout=30).json()
        if not reports:
            pytest.skip("buyer has no existing reports to exercise cached path")
        existing = reports[0]
        slug = existing["locality_slug"]
        persona = existing["persona_key"]
        r = buyer_session.post(f"{BASE_URL}/api/reports/generate",
                               json={"locality": slug, "persona_key": persona}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("cached") is True
        assert body.get("report_id")
        ent_after = buyer_session.get(f"{BASE_URL}/api/entitlement", timeout=30).json()
        assert ent_after["used"] == used_before, "cached generation must NOT increment used"
