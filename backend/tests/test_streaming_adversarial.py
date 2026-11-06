"""Adversarial tests for streaming chat: marker leakage, rent honesty, ownership 404."""
import json
import re

import pytest
import requests

from .conftest import BASE_URL, _login, generate_report


@pytest.fixture(scope="module")
def owned_report(isolated_owner):
    """Whitefield has no rent or power data, which is what the honesty test needs."""
    return generate_report(isolated_owner, "whitefield", "family_kids")


def _stream(session, report_id, question):
    return session.post(f"{BASE_URL}/api/reports/{report_id}/chat/stream",
                        json={"message": question}, stream=True, timeout=180)


def _drain(response):
    """Return (delta_texts, concatenated, done_event, marker_leaked_midstream)."""
    deltas, concat, done, leaked = [], "", None, False
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        event = json.loads(line[5:].strip())
        assert event["type"] != "error", event
        if event["type"] == "delta":
            if "###" in event["text"]:
                leaked = True
            deltas.append(event["text"])
            concat += event["text"]
        elif event["type"] == "done":
            done = event
    return deltas, concat, done, leaked


def test_sse_contract_headers_and_frame_count(isolated_owner, owned_report):
    r = _stream(isolated_owner, owned_report,
                "In two paragraphs, what makes this locality's air quality what it is?")
    assert r.status_code == 200, r.text
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert r.headers.get("cache-control") == "no-cache"
    assert r.headers.get("x-accel-buffering") == "no"

    deltas, concat, done, leaked = _drain(r)
    assert not leaked, "### marker leaked mid-stream in a delta frame"
    assert len(deltas) > 5, f"Expected >5 delta frames, got {len(deltas)}"
    assert done is not None
    assert "###SOURCES###" not in done["answer"] and "###MISSING###" not in done["answer"]
    assert "###" not in concat, f"### leaked into concatenated stream: {concat[-200:]}"
    assert done["answer"].strip().startswith(concat.strip()[:40]) or \
        concat.strip().startswith(done["answer"].strip()[:40])
    assert isinstance(done["used_sources"], list)


def test_rent_honesty(isolated_owner, owned_report):
    """Whitefield has no rent data; the model MUST refuse rather than invent."""
    resp = _stream(isolated_owner, owned_report,
                   "What is the average rent for a 2BHK apartment here in rupees per month?")
    assert resp.status_code == 200
    _, _, done, _ = _drain(resp)
    assert done is not None

    answer = done["answer"].lower()
    invented = re.search(r"(?:rs\.?|inr|\u20b9)\s*[\d,]{3,}", answer) or \
        re.search(r"\b\d{2},?\d{3}\b\s*(?:per month|/month|pm)", answer)
    assert not invented, f"Model appears to have invented a rent number: {done['answer']}"
    refusals = ["don't have", "do not have", "no data", "not available", "cannot", "can't",
                "unavailable", "missing", "not in", "no rent", "no information"]
    assert any(s in answer for s in refusals), f"Expected an honest refusal; got: {done['answer']}"
    assert done["missing"], f"Expected non-empty 'missing'; got answer={done['answer']!r}"


def test_ownership_404_for_non_owner_streaming(existing_pro_report_id):
    buyer = _login("buyer@localiq.in", "buyer123")
    r = buyer.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/chat/stream",
                   json={"message": "hello"}, timeout=30)
    assert r.status_code == 404, f"Expected 404 for non-owner, got {r.status_code}: {r.text}"


def test_streaming_requires_auth(existing_pro_report_id):
    r = requests.post(f"{BASE_URL}/api/reports/{existing_pro_report_id}/chat/stream",
                      json={"message": "hello"}, timeout=30)
    assert r.status_code in (401, 403)


def test_multi_turn_context_persists(isolated_owner, owned_report):
    _, _, done1, _ = _drain(_stream(isolated_owner, owned_report,
                                    "How is the water supply situation here?"))
    assert done1 and done1["answer"]

    _, concat2, done2, _ = _drain(_stream(isolated_owner, owned_report,
                                          "And how does that compare to the air quality?"))
    assert done2 and done2["answer"]
    assert "###" not in concat2 and "###" not in done2["answer"]

    hist = isolated_owner.get(f"{BASE_URL}/api/reports/{owned_report}/chat", timeout=30).json()
    assert len(hist) >= 4
    assert hist[-4]["role"] == "user"
    assert hist[-3]["role"] == "assistant" and hist[-3]["content"] == done1["answer"]
    assert hist[-2]["role"] == "user"
    assert hist[-1]["role"] == "assistant" and hist[-1]["content"] == done2["answer"]
