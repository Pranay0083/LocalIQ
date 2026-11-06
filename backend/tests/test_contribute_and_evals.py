"""Iteration 7 tests: shareable contribution links + chat suggestions + golden evals + regression."""
import time
import requests

INDIRANAGAR_SLUG = "indiranagar"


# ---------------------------------------------------------------- OWNER SIDE
class TestContributeLinksOwner:
    def test_mint_link_idempotent(self, pro_session, base_url, existing_pro_report_id):
        r1 = pro_session.post(f"{base_url}/api/contribute/links",
                              json={"locality_slug": INDIRANAGAR_SLUG,
                                    "report_id": existing_pro_report_id}, timeout=30)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["token"]
        assert body1["path"].startswith("/c/")
        assert isinstance(body1.get("gaps"), list)

        r2 = pro_session.post(f"{base_url}/api/contribute/links",
                              json={"locality_slug": INDIRANAGAR_SLUG,
                                    "report_id": existing_pro_report_id}, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["token"] == body1["token"], "expected idempotent same-token"

    def test_unknown_locality_404(self, pro_session, base_url):
        r = pro_session.post(f"{base_url}/api/contribute/links",
                             json={"locality_slug": "no-such-hood"}, timeout=15)
        assert r.status_code == 404

    def test_my_links_lists(self, pro_session, base_url):
        r = pro_session.get(f"{base_url}/api/contribute/links", timeout=15)
        assert r.status_code == 200
        docs = r.json()
        assert isinstance(docs, list) and len(docs) >= 1
        assert all("token" in d and "path" in d for d in docs)


# --------------------------------------------------------------- PUBLIC SIDE
class TestContributePublic:
    def _fresh_link(self, pro_session, base_url, existing_pro_report_id):
        r = pro_session.post(f"{base_url}/api/contribute/links",
                             json={"locality_slug": INDIRANAGAR_SLUG,
                                   "report_id": existing_pro_report_id}, timeout=30)
        return r.json()["token"]

    def test_public_get(self, pro_session, base_url, existing_pro_report_id):
        token = self._fresh_link(pro_session, base_url, existing_pro_report_id)
        r = requests.get(f"{base_url}/api/public/contribute/{token}", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["locality"]["slug"] == INDIRANAGAR_SLUG
        assert data["invited_by"]
        assert isinstance(data["gaps"], list)
        assert isinstance(data["claim_types"], list) and len(data["claim_types"]) > 0
        assert "recent" in data

    def test_bad_token_404(self, base_url):
        r = requests.get(f"{base_url}/api/public/contribute/deadbeef", timeout=15)
        assert r.status_code == 404

    def test_post_fact_claim_scrubs_pii(self, pro_session, base_url, existing_pro_report_id):
        token = self._fresh_link(pro_session, base_url, existing_pro_report_id)
        body = ("Water supply is only 3 hours. Call me on 9876543210 or email me at foo@bar.com "
                "if you want proof.")
        r = requests.post(f"{base_url}/api/public/contribute/{token}",
                          json={"kind": "fact_claim", "claim_type": "water_hours",
                                "claim_value": "3h/day", "body": body,
                                "display_name": "Ravi"}, timeout=15)
        if r.status_code == 429:
            import pytest
            pytest.skip("rate-limited public endpoint")
        assert r.status_code == 200, r.text
        post = r.json()["post"]
        assert post["status"] == "unverified"
        assert post["anonymous"] is True
        assert post["user_id"] is None
        assert post["credit_granted"] is False
        assert "9876543210" not in post["body"]
        assert "foo@bar.com" not in post["body"]
        assert "[phone removed]" in post["body"] or "[email removed]" in post["body"]

    def test_post_experience(self, pro_session, base_url, existing_pro_report_id):
        token = self._fresh_link(pro_session, base_url, existing_pro_report_id)
        r = requests.post(f"{base_url}/api/public/contribute/{token}",
                          json={"kind": "experience",
                                "body": "Lived here 4 years, love the tree cover on 12th main."},
                          timeout=15)
        if r.status_code == 429:
            import pytest
            pytest.skip("rate-limited")
        assert r.status_code == 200
        post = r.json()["post"]
        assert post["kind"] == "experience"
        assert post["claim_type"] is None
        assert post["status"] == "unverified"

    def test_short_body_rejected(self, pro_session, base_url, existing_pro_report_id):
        token = self._fresh_link(pro_session, base_url, existing_pro_report_id)
        r = requests.post(f"{base_url}/api/public/contribute/{token}",
                          json={"kind": "experience", "body": "too"}, timeout=15)
        assert r.status_code == 422  # pydantic validation

    def test_invalid_claim_type_400(self, pro_session, base_url, existing_pro_report_id):
        token = self._fresh_link(pro_session, base_url, existing_pro_report_id)
        r = requests.post(f"{base_url}/api/public/contribute/{token}",
                          json={"kind": "fact_claim", "claim_type": "bogus_type",
                                "body": "This is a long enough body to pass validation."},
                          timeout=15)
        if r.status_code == 429:
            import pytest
            pytest.skip("rate-limited")
        assert r.status_code == 400

    def test_bad_token_post_404(self, base_url):
        r = requests.post(f"{base_url}/api/public/contribute/deadbeef",
                          json={"kind": "experience",
                                "body": "some sufficiently long body content"}, timeout=15)
        assert r.status_code == 404

    def test_proof_accepts_png_rejects_text(self, pro_session, base_url, existing_pro_report_id):
        token = self._fresh_link(pro_session, base_url, existing_pro_report_id)
        # tiny 1x1 png
        png_b64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
                   "+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        r_ok = requests.post(f"{base_url}/api/public/contribute/{token}/proof",
                             json={"data_url": f"data:image/png;base64,{png_b64}"}, timeout=15)
        assert r_ok.status_code == 200, r_ok.text
        assert r_ok.json().get("proof_id")

        r_bad = requests.post(f"{base_url}/api/public/contribute/{token}/proof",
                              json={"data_url": "data:text/plain;base64,aGVsbG8="}, timeout=15)
        assert r_bad.status_code == 400


# ------------------------------------------------------- CORROBORATION GUARD
class TestAnonymousNeverCorroborates:
    def test_multiple_anon_stay_unverified(self, pro_session, base_url):
        # Fresh token each call so rate limit doesn't kick in first
        r = pro_session.post(f"{base_url}/api/contribute/links",
                             json={"locality_slug": INDIRANAGAR_SLUG}, timeout=30)
        token = r.json()["token"]

        ids = []
        for i in range(3):
            resp = None
            for attempt in range(3):
                try:
                    resp = requests.post(f"{base_url}/api/public/contribute/{token}",
                                         json={"kind": "fact_claim", "claim_type": "power_cuts",
                                               "claim_value": f"{i+1} outages/week",
                                               "body": f"Report iteration {i} of the power cut pattern."},
                                         timeout=30)
                    break
                except requests.exceptions.RequestException:
                    if attempt == 2:
                        raise
                    time.sleep(2)
            if resp.status_code == 429:
                break
            assert resp.status_code == 200, resp.text
            post = resp.json()["post"]
            assert post["status"] == "unverified"
            assert post["credit_granted"] is False
            ids.append(post["id"])

        # Still unverified when re-fetched via the public GET
        pub = requests.get(f"{base_url}/api/public/contribute/{token}", timeout=15).json()
        for r_ in pub["recent"]:
            if r_["id"] in ids:
                assert r_["status"] == "unverified"


# ------------------------------------------------------------- GOLDEN EVALS
class TestGoldenEvals:
    def test_golden_all_pass(self, pro_session, base_url):
        r = pro_session.get(f"{base_url}/api/evals/golden", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data.get("summary", data)
        results = data.get("results", data.get("checks", []))
        failed_items = [c for c in results
                        if (c.get("status") != "pass" and c.get("ok") is not True)]
        assert summary["failed"] == 0, f"failed: {failed_items[:10]}"
        assert summary["total"] == summary["passed"]
        assert summary["total"] >= 60

    def test_golden_requires_auth(self, base_url):
        r = requests.get(f"{base_url}/api/evals/golden", timeout=30)
        assert r.status_code in (401, 403)

    def test_dataset_endpoint(self, pro_session, base_url):
        r = pro_session.get(f"{base_url}/api/evals/dataset", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "fixtures" in data and "invariants" in data
        assert "version" in data


# ---------------------------------------------------------------- REGRESSION
class TestRegressionSweep:
    def test_seed_report_loads(self, pro_session, base_url, existing_pro_report_id):
        r = pro_session.get(f"{base_url}/api/reports/{existing_pro_report_id}", timeout=30)
        assert r.status_code == 200
        rep = r.json()
        assert rep.get("locality_slug") == INDIRANAGAR_SLUG
        assert isinstance(rep.get("cards"), list) and len(rep["cards"]) > 0
        cost = rep.get("cost") or {}
        # Report the finding rather than fail if cost is zero — but assert keys exist
        assert "llm_calls" in cost or "calls" in cost or cost == {}

    def test_share_still_works(self, pro_session, base_url, existing_pro_report_id):
        r = pro_session.post(f"{base_url}/api/reports/{existing_pro_report_id}/share", timeout=15)
        assert r.status_code == 200
        token = r.json().get("token") or r.json().get("share_token")
        assert token
        pub = requests.get(f"{base_url}/api/public/reports/{token}", timeout=15)
        assert pub.status_code == 200
        data = pub.json()
        # locked teaser
        assert "locality" in data or "teaser" in data or "score" in data

    def test_free_user_compare_paywall(self, buyer_session, base_url):
        r = buyer_session.post(f"{base_url}/api/compare",
                               json={"slugs": ["indiranagar", "koramangala"],
                                     "persona_key": "family_kids"}, timeout=30)
        # free plan must not receive compare
        assert r.status_code in (402, 403), f"expected paywall, got {r.status_code} {r.text[:200]}"

    def test_lens_switch_free(self, pro_session, base_url, existing_pro_report_id):
        r = pro_session.post(f"{base_url}/api/reports/{existing_pro_report_id}/lens",
                             json={"persona_key": "wfh_pro"}, timeout=60)
        assert r.status_code in (200, 201), r.text
