"""Compare and Recommend premium gating."""
import requests
import pytest
from .conftest import BASE_URL


class TestCompareGating:
    def test_compare_free_user_402(self, buyer_session):
        r = buyer_session.post(f"{BASE_URL}/api/compare",
                               json={"slugs": ["hsr-layout", "indiranagar"]}, timeout=30)
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", {})
        # detail may be dict or string
        if isinstance(detail, dict):
            assert detail.get("code") == "premium"

    def test_compare_bad_slug(self, pro_session):
        r = pro_session.post(f"{BASE_URL}/api/compare",
                             json={"slugs": ["nowhere-xxxxx", "indiranagar"]}, timeout=60)
        assert r.status_code == 404


class TestRecommendGating:
    def test_recommend_second_run_gated_for_free_user(self, buyer_session):
        """Free user gets one free run then 402. If they've already used it, expect 402 immediately."""
        ent = buyer_session.get(f"{BASE_URL}/api/entitlement", timeout=30).json()
        if ent.get("can_recommend"):
            # burn the free run (may take ~30s)
            r = buyer_session.post(f"{BASE_URL}/api/recommend", timeout=180)
            assert r.status_code in (200, 402)
        r2 = buyer_session.post(f"{BASE_URL}/api/recommend", timeout=30)
        assert r2.status_code == 402
        detail = r2.json().get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("code") == "premium"
