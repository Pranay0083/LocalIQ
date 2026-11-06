"""Lens switcher (free, no credit spend) and grounded chat."""
import time
import requests
import pytest
from .conftest import BASE_URL, generate_report


@pytest.fixture(scope="module")
def isolated_report(isolated_owner):
    """A report the throwaway module owner owns, so chat has a clean, uncapped history."""
    return generate_report(isolated_owner, "indiranagar", "family_kids")



class TestLensSwitcher:
    def test_lens_switch_no_credit_spent(self, pro_session, existing_pro_report_id):
        ent_before = pro_session.get(f"{BASE_URL}/api/entitlement", timeout=30).json()
        # pick a persona different from the existing report's
        current = pro_session.get(f"{BASE_URL}/api/reports/{existing_pro_report_id}", timeout=30).json()
        current_persona = current["persona_key"]
        new_persona = "investor" if current_persona != "investor" else "bachelor"

        r = pro_session.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/lens",
                             json={"persona_key": new_persona}, timeout=180)
        assert r.status_code == 200, r.text
        new_report = r.json()
        assert new_report["persona_key"] == new_persona
        assert new_report["persona_key"] != current_persona
        assert new_report.get("lens_of") == existing_pro_report_id
        assert new_report.get("id") and new_report["id"] != existing_pro_report_id

        ent_after = pro_session.get(f"{BASE_URL}/api/entitlement", timeout=30).json()
        # pro users don't burn used anyway, but should be unchanged regardless
        assert ent_after["used"] == ent_before["used"]

    def test_lens_bad_persona(self, pro_session, existing_pro_report_id):
        r = pro_session.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/lens",
                             json={"persona_key": "not_a_persona"}, timeout=30)
        assert r.status_code == 400


class TestReportChat:
    def test_chat_grounded_answer(self, isolated_owner, isolated_report):
        r = isolated_owner.post(f"{BASE_URL}/api/reports/{isolated_report}/chat",
                                json={"message": "How far is the nearest hospital and how long would I walk it?"},
                                timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("answer", ""), str) and len(data["answer"]) > 10
        # used_sources may be a list of chip strings/objects
        assert "used_sources" in data

        # history should now include the new turn
        hist = isolated_owner.get(f"{BASE_URL}/api/reports/{isolated_report}/chat", timeout=30).json()
        assert isinstance(hist, list) and len(hist) >= 2
        assert hist[-2]["role"] == "user"
        assert hist[-1]["role"] == "assistant" and hist[-1]["content"] == data["answer"]

    def test_chat_stream_sse(self, isolated_owner, isolated_report):
        import json as _json

        r = isolated_owner.post(f"{BASE_URL}/api/reports/{isolated_report}/chat/stream",
                                json={"message": "What are the two biggest weak points here?"},
                                timeout=180, stream=True)
        assert r.status_code == 200, r.text
        assert "text/event-stream" in r.headers.get("content-type", "")

        deltas, done = [], None
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            event = _json.loads(line[5:].strip())
            assert event["type"] != "error", event
            if event["type"] == "delta":
                deltas.append(event["text"])
            elif event["type"] == "done":
                done = event
        assert len(deltas) > 5, "expected the answer to arrive in many chunks"
        assert done is not None
        assert len(done["answer"]) > 40
        assert "###SOURCES###" not in done["answer"] and "###MISSING###" not in done["answer"]
        assert "".join(deltas).strip().startswith(done["answer"][:30])
        assert isinstance(done["used_sources"], list)

        hist = isolated_owner.get(f"{BASE_URL}/api/reports/{isolated_report}/chat",
                                  timeout=30).json()
        assert hist[-1]["role"] == "assistant" and hist[-1]["content"] == done["answer"]

    def test_chat_stream_requires_ownership(self, buyer_session, existing_pro_report_id):
        r = buyer_session.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/chat/stream",
                               json={"message": "hello"}, timeout=60)
        assert r.status_code == 404
