"""Community: feed, PII scrubbing, fact-claim proof requirement, votes."""
import base64
import pytest
import requests
from .conftest import BASE_URL

# 1x1 transparent PNG
_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
)


class TestCommunityFeed:
    def test_list_posts_public(self):
        r = requests.get(f"{BASE_URL}/api/community/posts", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_leaderboard(self):
        r = requests.get(f"{BASE_URL}/api/community/leaderboard", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_filter_by_kind(self):
        r = requests.get(f"{BASE_URL}/api/community/posts", params={"kind": "fact_claim"}, timeout=30)
        assert r.status_code == 200
        for post in r.json():
            assert post["kind"] == "fact_claim"


class TestPosting:
    def test_experience_pii_scrubbed(self, throwaway_session):
        body = "TEST_POST auto-cleanup: living here is nice, call me on 9845012345 for details on the street."
        r = throwaway_session.post(f"{BASE_URL}/api/community/posts",
                             json={"locality_slug": "indiranagar", "kind": "experience",
                                   "body": body}, timeout=60)
        assert r.status_code == 200, r.text
        post = r.json()
        assert "[phone removed]" in post["body"]
        assert "9845012345" not in post["body"]
        assert post["pii_scrubbed"] >= 1

    def test_fact_claim_requires_proof(self, pro_session):
        r = pro_session.post(f"{BASE_URL}/api/community/posts",
                             json={"locality_slug": "indiranagar", "kind": "fact_claim",
                                   "claim_type": "water_hours", "claim_value": "6 hrs/day",
                                   "body": "TEST_POST fact claim without proof upload here."},
                             timeout=30)
        assert r.status_code == 400

    def test_body_too_short_rejected(self, pro_session):
        r = pro_session.post(f"{BASE_URL}/api/community/posts",
                             json={"locality_slug": "indiranagar", "kind": "experience",
                                   "body": "short"}, timeout=30)
        assert r.status_code == 422  # Pydantic validation error

    def test_fact_claim_with_proof(self, throwaway_session):
        data_url = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()
        pr = throwaway_session.post(f"{BASE_URL}/api/community/proof",
                              json={"data_url": data_url}, timeout=30)
        assert pr.status_code == 200, pr.text
        proof_id = pr.json()["proof_id"]
        r = throwaway_session.post(f"{BASE_URL}/api/community/posts",
                             json={"locality_slug": "indiranagar", "kind": "fact_claim",
                                   "claim_type": "water_hours", "claim_value": "6 hrs/day",
                                   "body": "TEST_POST_FC proof-attached claim about water hours.",
                                   "proof_id": proof_id}, timeout=60)
        assert r.status_code == 200, r.text
        post = r.json()
        assert post["proof_url"]
        assert post["kind"] == "fact_claim"


class TestVoting:
    def _make_post(self, session):
        r = session.post(f"{BASE_URL}/api/community/posts",
                         json={"locality_slug": "hsr-layout", "kind": "experience",
                               "body": "TEST_VOTE seed post for vote tests, generally nice locality."},
                         timeout=60)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_upvote_then_duplicate_409(self, throwaway_session, buyer_session):
        post_id = self._make_post(throwaway_session)
        r1 = buyer_session.post(f"{BASE_URL}/api/community/posts/{post_id}/vote",
                                json={"value": 1}, timeout=30)
        assert r1.status_code == 200, r1.text
        assert r1.json()["upvotes"] >= 1
        r2 = buyer_session.post(f"{BASE_URL}/api/community/posts/{post_id}/vote",
                                json={"value": 1}, timeout=30)
        assert r2.status_code == 409

    def test_switch_vote_direction(self, throwaway_session, buyer_session):
        post_id = self._make_post(throwaway_session)
        buyer_session.post(f"{BASE_URL}/api/community/posts/{post_id}/vote",
                           json={"value": 1}, timeout=30)
        r = buyer_session.post(f"{BASE_URL}/api/community/posts/{post_id}/vote",
                               json={"value": -1}, timeout=30)
        assert r.status_code == 200
        post = r.json()
        assert post["downvotes"] >= 1
