"""The one door to language models. Agents call chat / chat_json / stream_chat / web_research;
this module decides which provider answers and meters every call.

Routing:
- LLM_PROVIDER=groq (default): Groq first; if it fails, the same tier on the OpenAI-compatible
  provider when one is configured.
- LLM_PROVIDER=openai: the OpenAI-compatible provider only.
- Web research: Groq's hosted browser_search when GROQ_API_KEY is set (RESEARCH_PROVIDER=auto),
  otherwise, or when that fails, the key-free retrieval pipeline in services/research.py.
"""
import json
import logging
import re
from typing import AsyncIterator, Optional

from ...config import settings
from . import compat_provider, groq_provider
from .ledger import PRICING, ledger_snapshot, new_run_ledger  # noqa: F401  (re-exported)

logger = logging.getLogger("localiq.llm")


def extract_json(text: str):
    """The first JSON object or array in a reply, fenced or not."""
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


async def chat(prompt: str, system: str = "You are a precise analyst.", model: Optional[str] = None,
               max_tokens: int = 1200, temperature: float = 0.2, json_mode: bool = False,
               allow_fallback: bool = True) -> Optional[str]:
    if settings.llm_provider == "openai":
        return await compat_provider.chat(system, prompt, max_tokens, model, temperature, json_mode)

    content, error = await groq_provider.chat(system, prompt, max_tokens, model, temperature, json_mode)
    if content is not None:
        return content
    logger.warning("groq chat failed (%s), trying fallback", error)
    if allow_fallback:
        return await compat_provider.chat(system, prompt, max_tokens, model or settings.model_fast,
                                          temperature, json_mode)
    return None


async def chat_json(prompt: str, system: str, model: Optional[str] = None, max_tokens: int = 1400):
    raw = await chat(prompt + "\n\nRespond with valid JSON only.", system=system, model=model,
                     max_tokens=max_tokens, json_mode=True)
    return extract_json(raw or "")


async def stream_chat(prompt: str, system: str = "You are a precise analyst.",
                      model: Optional[str] = None, max_tokens: int = 1200,
                      temperature: float = 0.3) -> AsyncIterator[str]:
    """Yield the answer token by token."""
    provider = compat_provider if settings.llm_provider == "openai" else groq_provider
    async for delta in provider.stream(system, prompt, max_tokens, model, temperature):
        yield delta


async def web_research(instruction: str, system: str, max_tokens: int = 1600) -> dict:
    """RESEARCH_PROVIDER: 'groq' (Groq only) | 'local' (retrieval only) | 'auto' (Groq, then local)."""
    from ..research import local_research

    provider = settings.research_provider
    if provider == "local" or (provider == "auto" and not settings.groq_api_key):
        return await local_research(instruction, system, max_tokens)

    result = await groq_provider.web_search(instruction, system, max_tokens)
    if result.get("ok") or provider == "groq":
        return result
    logger.info("groq research unavailable (%s) - falling back to local retrieval",
                result.get("error") or "rate limited")
    fallback = await local_research(instruction, system, max_tokens)
    return fallback if fallback.get("ok") else result
