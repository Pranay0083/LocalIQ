"""Groq: gpt-oss models with low reasoning effort, plus the hosted browser_search tool."""
import asyncio
import json
import logging
import re
from typing import AsyncIterator, Optional

from groq import APIStatusError, AsyncGroq

from ...config import settings
from .ledger import record

logger = logging.getLogger("localiq.llm")

_client = AsyncGroq(api_key=settings.groq_api_key or "unset")


async def chat(system: str, prompt: str, max_tokens: int, model: Optional[str] = None,
               temperature: float = 0.2, json_mode: bool = False) -> tuple[Optional[str], Exception | None]:
    """Up to three attempts. Returns (content, last_error); content is None when every attempt failed."""
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
            record(kwargs["model"], resp.usage)
            content = resp.choices[0].message.content
            if content and content.strip():
                return content, None
            # Reasoning models can spend the whole budget thinking; give the answer room.
            kwargs["max_tokens"] = kwargs["max_tokens"] * 2
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
    return None, last_error


async def stream(system: str, prompt: str, max_tokens: int, model: Optional[str] = None,
                 temperature: float = 0.3) -> AsyncIterator[str]:
    groq_model = model or settings.model_fast
    # Groq reports usage on the final chunk under x_groq; its SDK has no stream_options.
    response = await _client.chat.completions.create(
        model=groq_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=max(max_tokens, 700), temperature=temperature, stream=True)
    usage = None
    async for chunk in response:
        chunk_usage = getattr(getattr(chunk, "x_groq", None), "usage", None)
        if chunk_usage:
            usage = chunk_usage
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
    record(groq_model, usage)


async def web_search(instruction: str, system: str, max_tokens: int = 1600) -> dict:
    """One call with the built-in browser_search tool.
    Returns the model's text plus the URLs it actually opened."""
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
    record(settings.model_search, resp.usage, searches=searches)
    return {"ok": True, "text": message.content or "", "urls": urls, "queries": queries,
            "tool_calls": len(executed)}
