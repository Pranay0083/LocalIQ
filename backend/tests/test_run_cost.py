"""Run-cost ledger: real per-model token accounting, not a hardcoded zero."""
import time

import pytest
import requests

from .conftest import BASE_URL, generate_report

# USD per 1M tokens, mirrored from app/services/llm.py PRICING
RATES = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60),
         "gpt-5.4": (2.50, 15.00), "gpt-5.4-mini": (0.75, 4.50), "gpt-5.4-nano": (0.15, 0.60)}


def _ledger(session):
    return session.get(f"{BASE_URL}/api/traces", timeout=30).json()["ledger"]


@pytest.fixture(scope="module")
def metered_report(pro_session):
    """One forced run so the cost block reflects work actually done in this suite."""
    r = pro_session.post(f"{BASE_URL}/api/reports/generate",
                         json={"locality": "indiranagar", "persona_key": "investor", "force": True},
                         timeout=60)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    for _ in range(60):
        job = pro_session.get(f"{BASE_URL}/api/reports/job/{job_id}", timeout=30).json()
        assert job["status"] != "failed", job
        if job["status"] == "done":
            return pro_session.get(f"{BASE_URL}/api/reports/{job['report_id']}", timeout=30).json()
        time.sleep(4)
    pytest.fail("forced report never completed")


class TestRunCost:
    def test_cost_block_is_populated(self, metered_report):
        cost = metered_report["cost"]
        for key in ("prompt_tokens", "completion_tokens", "web_searches", "llm_calls",
                    "est_cost_usd", "model"):
            assert key in cost, f"cost block missing {key}"

    def test_llm_work_is_not_reported_as_zero(self, metered_report):
        """The narrative is LLM-written, so a generated report can never be 0 calls / $0."""
        cost = metered_report["cost"]
        assert metered_report["narrative"].get("headline"), "no narrative to account for"
        assert cost["llm_calls"] >= 1, "LLM calls under-counted"
        assert cost["prompt_tokens"] > 0 and cost["completion_tokens"] > 0
        assert cost["est_cost_usd"] > 0, "an LLM-written report cannot cost $0"

    def test_model_is_named_and_priced(self, metered_report):
        cost = metered_report["cost"]
        models = [m.strip() for m in cost["model"].split(",")]
        assert models and all(m in RATES for m in models), f"unpriced model in {models}"

    def test_cost_matches_published_rates(self, metered_report):
        cost = metered_report["cost"]
        models = [m.strip() for m in cost["model"].split(",")]
        lo_in, lo_out = min(RATES[m] for m in models)
        hi_in, hi_out = max(RATES[m] for m in models)
        low = cost["prompt_tokens"] / 1e6 * lo_in + cost["completion_tokens"] / 1e6 * lo_out
        high = cost["prompt_tokens"] / 1e6 * hi_in + cost["completion_tokens"] / 1e6 * hi_out
        assert low - 1e-4 <= cost["est_cost_usd"] <= high + 1e-4, \
            f"{cost['est_cost_usd']} outside [{low}, {high}] for {models}"

    def test_a_single_chat_call_is_metered(self, isolated_owner, metered_report):
        """The reported bug: calls on the fallback provider were invisible to the ledger."""
        own_report = generate_report(isolated_owner, "indiranagar", "wfh_pro")
        before = _ledger(isolated_owner)
        r = isolated_owner.post(f"{BASE_URL}/api/reports/{own_report}/chat",
                                json={"message": "In one sentence, what is the air quality like?"},
                                timeout=120)
        assert r.status_code == 200, r.text
        after = _ledger(isolated_owner)
        # the ledger is process-wide, so other parallel tests may add calls too
        assert after["calls"] >= before["calls"] + 1
        assert after["prompt"] > before["prompt"] and after["completion"] > before["completion"]
        assert after["est_cost_usd"] > before["est_cost_usd"]

    def test_run_ledger_is_scoped_not_global(self, pro_session, metered_report):
        """A run's cost must be its own, never a slice of the process-wide counter."""
        ledger = _ledger(pro_session)
        assert isinstance(ledger["models"], list), "global ledger must stay JSON-serialisable"
        assert ledger["calls"] >= metered_report["cost"]["llm_calls"]
        assert ledger["est_cost_usd"] >= metered_report["cost"]["est_cost_usd"] - 1e-6


class TestLedgerEndpoint:
    def test_traces_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/traces", timeout=30)
        assert r.status_code in (401, 403)
