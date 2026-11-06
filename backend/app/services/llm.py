"""LLM access: Groq (with built-in web search) or any OpenAI-compatible API, plus JSON
coercion and per-model cost accounting."""
import asyncio
import contextvars
import json
import logging
import re
from typing import AsyncIterator, Optional

from groq import AsyncGroq, APIStatusError
from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger("localiq.llm")

_client = AsyncGroq(api_key=settings.groq_api_key or "unset")
# Free tiers rate-limit hard; the SDK backs off exponentially on 429s.
_compat = AsyncOpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key or "unset",
                      max_retries=4)
# A model served from this machine (Ollama, LM Studio) costs nothing per token.
_COMPAT_IS_LOCAL = any(h in settings.openai_base_url for h in ("localhost", "127.0.0.1"))

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


def _record(model: str, prompt_tokens: int, completion_tokens: int, searches: int = 0,
            free: bool = False):
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


def record_groq(usage, model: str, searches: int = 0):
    _record(model, getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0, searches)


def record_compat(usage, model: str):
    _record(model, getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0, free=_COMPAT_IS_LOCAL)


def _compat_model(model: Optional[str]) -> str:
    """Agents ask for settings.model_fast / model_smart. When Groq is primary and the call
    falls back, translate its model id to the same tier on the OpenAI-compatible provider."""
    tiers = {settings.groq_model_fast: settings.openai_model_fast,
             settings.groq_model_smart: settings.openai_model_smart}
    if settings.llm_provider == "openai":
        return model or settings.openai_model_fast
    return tiers.get(model, settings.openai_model_fast)


def extract_json(text: str):
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start = min([i for i in (candidate.find("{"), candidate.find("[")) if i >= 0], default=-1)
    if start < 0:
        return None
    for end in range(len(candidate), start, -1):
        chunk = candidate[start:end]
        if chunk[-1] not in "}]":
            continue
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    return None


async def _compat_chat(system: str, prompt: str, max_tokens: int, model: Optional[str] = None,
                       temperature: float = 0.2, json_mode: bool = False) -> Optional[str]:
    """One call to the OpenAI-compatible provider. None when it is not configured or fails."""
    if not settings.openai_api_key and not _COMPAT_IS_LOCAL:
        return None
    compat_model = _compat_model(model)
    kwargs = {
        "model": compat_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": max(max_tokens, 700),
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = await _compat.chat.completions.create(**kwargs)
        record_compat(resp.usage, compat_model)
        return resp.choices[0].message.content
    except Exception as exc:
        logger.warning("%s call failed: %s", compat_model, exc)
        return None


async def stream_chat(prompt: str, system: str = "You are a precise analyst.",
                      model: Optional[str] = None, max_tokens: int = 1200,
                      temperature: float = 0.3) -> AsyncIterator[str]:
    """Yield the answer token by token. Falls back to a single yield if streaming fails."""
    if settings.llm_provider == "openai":
        compat_model = _compat_model(model)
        stream = await _compat.chat.completions.create(
            model=compat_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=max(max_tokens, 700), temperature=temperature, stream=True,
            stream_options={"include_usage": True})
        usage = None
        async for chunk in stream:
            usage = chunk.usage or usage
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
        record_compat(usage, compat_model)
        return

    groq_model = model or settings.model_fast
    # Groq reports usage on the final chunk under x_groq; its SDK has no stream_options.
    stream = await _client.chat.completions.create(
        model=groq_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=max(max_tokens, 700), temperature=temperature, stream=True)
    usage = None
    async for chunk in stream:
        chunk_usage = getattr(getattr(chunk, "x_groq", None), "usage", None)
        if chunk_usage:
            usage = chunk_usage
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
    record_groq(usage, groq_model)


async def chat(prompt: str, system: str = "You are a precise analyst.", model: Optional[str] = None,
               max_tokens: int = 1200, temperature: float = 0.2, json_mode: bool = False,
               allow_fallback: bool = True) -> Optional[str]:
    if settings.llm_provider == "openai":
        return await _compat_chat(system, prompt, max_tokens, model, temperature, json_mode)

    kwargs = {
        "model": model or settings.model_fast,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": max(max_tokens, 700),
        "temperature": temperature,
        "reasoning_effort": "low",
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_error = None
    for attempt in range(3):
        try:
            resp = await _client.chat.completions.create(**kwargs)
            _record(kwargs["model"], getattr(resp.usage, "prompt_tokens", 0) or 0,
                    getattr(resp.usage, "completion_tokens", 0) or 0)
            content = resp.choices[0].message.content
            if content and content.strip():
                return content
            kwargs["max_tokens"] = kwargs["max_tokens"] * 2
            continue
        except APIStatusError as exc:
            last_error = exc
            # 413 means the request alone exceeds the tier's tokens-per-minute; waiting cannot fix it.
            if exc.status_code in (429, 503):
                await asyncio.sleep(2 ** attempt * 1.5)
                continue
            break
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1.5)
    logger.warning("groq chat failed (%s), trying fallback", last_error)
    if allow_fallback:
        return await _compat_chat(system, prompt, max_tokens, kwargs["model"], temperature,
                                  json_mode)
    return None


async def chat_json(prompt: str, system: str, model: Optional[str] = None, max_tokens: int = 1400):
    raw = await chat(prompt + "\n\nRespond with valid JSON only.", system=system, model=model,
                     max_tokens=max_tokens, json_mode=True)
    parsed = extract_json(raw or "")
    if parsed is None and raw:
        parsed = extract_json(raw)
    return parsed


async def web_research(instruction: str, system: str, max_tokens: int = 1600) -> dict:
    """Dispatch research to Groq's browser_search or to the local retrieval pipeline.

    RESEARCH_PROVIDER: 'groq' (Groq only) | 'local' (retrieval only) | 'auto' (Groq, then local)."""
    from .research import local_research

    provider = settings.research_provider
    if provider == "local" or (provider == "auto" and not settings.groq_api_key):
        return await local_research(instruction, system, max_tokens)

    result = await _groq_web_research(instruction, system, max_tokens)
    if result.get("ok") or provider == "groq":
        return result
    logger.info("groq research unavailable (%s) - falling back to local retrieval",
                result.get("error") or "rate limited")
    fallback = await local_research(instruction, system, max_tokens)
    if not fallback.get("ok"):
        return result
    return fallback


async def _groq_web_research(instruction: str, system: str, max_tokens: int = 1600) -> dict:
    """One Groq call with the built-in browser_search tool.
    Returns model text plus the URLs the model actually opened."""
    last_error = None
    resp = None
    for attempt in range(2):
        try:
            resp = await _client.chat.completions.create(
                model=settings.model_search,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": instruction}],
                tools=[{"type": "browser_search"}],
                max_tokens=max_tokens,
                temperature=0.1,
                reasoning_effort="low",
            )
            break
        except APIStatusError as exc:
            last_error = exc
            if exc.status_code == 429:
                logger.warning("web_research rate limited")
                return {"ok": False, "rate_limited": True, "error": "Groq daily token budget reached",
                        "text": "", "urls": [], "queries": []}
            await asyncio.sleep(2 + attempt * 3)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(2)
    if resp is None:
        logger.warning("web_research failed: %s", last_error)
        return {"ok": False, "error": str(last_error)[:300], "text": "", "urls": [], "queries": []}

    message = resp.choices[0].message
    executed = getattr(message, "executed_tools", None) or []
    urls, queries, searches = [], [], 0
    for tool in executed:
        data = tool if isinstance(tool, dict) else tool.model_dump()
        name = (data.get("type") or data.get("name") or "")
        args = data.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        args = args or {}
        output = str(data.get("output") or "")
        if "search" in name:
            searches += 1
            if args.get("query"):
                queries.append(args["query"])
        for match in re.findall(r"https?://[^\s\)\]\"'<>]+", output):
            clean = match.rstrip(".,;")
            if clean not in urls and len(urls) < 25:
                urls.append(clean)
    record_groq(resp.usage, settings.model_search, searches=searches)
    return {"ok": True, "text": message.content or "", "urls": urls, "queries": queries,
            "tool_calls": len(executed)}


def ledger_snapshot(ledger: Optional[dict] = None) -> dict:
    data = ledger if ledger is not None else TOKEN_LEDGER
    return {**data, "models": sorted(data["models"]),
            "est_cost_usd": round(data["cost_usd"], 5)}
