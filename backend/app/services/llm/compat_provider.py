"""Any OpenAI-compatible API: OpenAI, Gemini, OpenRouter, or a local Ollama / LM Studio server."""
import logging
from typing import AsyncIterator, Optional

from openai import AsyncOpenAI

from ...config import settings
from .ledger import record

logger = logging.getLogger("localiq.llm")

# Free tiers rate-limit hard; the SDK backs off exponentially on 429s.
_client = AsyncOpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key or "unset",
                      max_retries=4)
# A model served from this machine costs nothing per token.
IS_LOCAL = any(h in settings.openai_base_url for h in ("localhost", "127.0.0.1"))


def configured() -> bool:
    return bool(settings.openai_api_key) or IS_LOCAL


def model_for(model: Optional[str]) -> str:
    """Agents ask for settings.model_fast / model_smart. When Groq is primary and a call falls back
    here, translate its model id to the same tier on this provider."""
    if settings.llm_provider == "openai":
        return model or settings.openai_model_fast
    tiers = {settings.groq_model_fast: settings.openai_model_fast,
             settings.groq_model_smart: settings.openai_model_smart}
    return tiers.get(model, settings.openai_model_fast)


async def chat(system: str, prompt: str, max_tokens: int, model: Optional[str] = None,
               temperature: float = 0.2, json_mode: bool = False) -> Optional[str]:
    """One completion. None when the provider is not configured or the call fails."""
    if not configured():
        return None
    compat_model = model_for(model)
    kwargs = {
        "model": compat_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": max(max_tokens, 700),
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = await _client.chat.completions.create(**kwargs)
        record(compat_model, resp.usage, free=IS_LOCAL)
        return resp.choices[0].message.content
    except Exception as exc:
        logger.warning("%s call failed: %s", compat_model, exc)
        return None


async def stream(system: str, prompt: str, max_tokens: int, model: Optional[str] = None,
                 temperature: float = 0.3) -> AsyncIterator[str]:
    compat_model = model_for(model)
    response = await _client.chat.completions.create(
        model=compat_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=max(max_tokens, 700), temperature=temperature, stream=True,
        stream_options={"include_usage": True})
    usage = None
    async for chunk in response:
        usage = chunk.usage or usage
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
    record(compat_model, usage, free=IS_LOCAL)
