"""Token and cost metering. Every LLM call is priced the moment it returns, into a process-wide
ledger and into the ledger of the report run it belongs to."""
import contextvars
from typing import Optional

# USD per 1M tokens: (input, output). DEFAULT_RATE covers any model not listed.
PRICING = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.15, 0.60),
}
DEFAULT_RATE = (0.15, 0.60)
SEARCH_USD_PER_1K = 6.5


def _blank_ledger() -> dict:
    return {"prompt": 0, "completion": 0, "searches": 0, "calls": 0,
            "cost_usd": 0.0, "models": set()}


TOKEN_LEDGER = _blank_ledger()
# Per-run ledger so two concurrent report generations cannot bill each other.
_RUN_LEDGER = contextvars.ContextVar("localiq_run_ledger", default=None)


def new_run_ledger() -> dict:
    ledger = _blank_ledger()
    _RUN_LEDGER.set(ledger)
    return ledger


def record(model: str, usage, searches: int = 0, free: bool = False):
    """Price one call from its usage object (prompt_tokens / completion_tokens)."""
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    rate_in, rate_out = (0, 0) if free else PRICING.get(model, DEFAULT_RATE)
    cost = (prompt_tokens / 1_000_000 * rate_in
            + completion_tokens / 1_000_000 * rate_out
            + searches / 1000 * SEARCH_USD_PER_1K)
    for ledger in (TOKEN_LEDGER, _RUN_LEDGER.get()):
        if ledger is None:
            continue
        ledger["calls"] += 1
        ledger["searches"] += searches
        ledger["prompt"] += prompt_tokens
        ledger["completion"] += completion_tokens
        ledger["cost_usd"] = round(ledger["cost_usd"] + cost, 6)
        ledger["models"].add(model)


def ledger_snapshot(ledger: Optional[dict] = None) -> dict:
    data = ledger if ledger is not None else TOKEN_LEDGER
    return {**data, "models": sorted(data["models"]),
            "est_cost_usd": round(data["cost_usd"], 5)}
