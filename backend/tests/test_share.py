"""Public shareable report links: minting, teaser payload, privacy, dead links."""
import pytest

from .conftest import BASE_URL, _resilient_session


@pytest.fixture(scope="module")
def share_token(pro_session, existing_pro_report_id):
    r = pro_session.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/share", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"] == f"/r/{body['token']}"
    return body["token"]


class TestShareLink:
    def test_token_is_idempotent(self, pro_session, existing_pro_report_id, share_token):
        again = pro_session.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/share", timeout=30)
        assert again.status_code == 200
        assert again.json()["token"] == share_token

    def test_cannot_share_someone_elses_report(self, buyer_session, existing_pro_report_id):
        r = buyer_session.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/share", timeout=30)
        assert r.status_code == 404

    def test_share_requires_auth(self, existing_pro_report_id):
        r = _resilient_session().post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/share", timeout=30)
        assert r.status_code in (401, 403)


class TestPublicTeaser:
    def test_readable_without_auth(self, share_token):
        r = _resilient_session().get(f"{BASE_URL}/api/public/reports/{share_token}", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["locality"]["name"]
        assert isinstance(data["composite"]["score"], (int, float))
        assert isinstance(data["baseline_composite"]["score"], (int, float))
        assert data["persona_label"]
        assert data["narrative"]["headline"]

    def test_teaser_is_capped_and_cards_are_cited(self, share_token):
        data = _resilient_session().get(f"{BASE_URL}/api/public/reports/{share_token}", timeout=30).json()
        assert 0 < len(data["cards"]) <= 3
        assert all(not c.get("empty") for c in data["cards"]), "hero cards must have data"
        assert any(c["citations"] for c in data["cards"]), "teaser must prove its numbers"
        assert data["locked"], "the rest of the report must stay locked"
        locked_modules = {m["module"] for m in data["locked"]}
        assert not locked_modules & {c["module"] for c in data["cards"]}
        assert len(data["cards"]) + len(data["locked"]) == data["modules_total"]

    def test_no_owner_pii_or_full_payload_leak(self, share_token):
        data = _resilient_session().get(f"{BASE_URL}/api/public/reports/{share_token}", timeout=30).json()
        for leaked in ("user_id", "sources", "module_scores", "layers", "cost", "weights", "id"):
            assert leaked not in data, f"public teaser leaked {leaked}"

    def test_dead_link_404(self):
        r = _resilient_session().get(f"{BASE_URL}/api/public/reports/definitely-not-a-token", timeout=30)
        assert r.status_code == 404
