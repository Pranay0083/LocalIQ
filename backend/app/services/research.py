"""Key-free web research: real retrieval, then LLM extraction over the retrieved corpus only.

Discovery is Google News RSS (real headlines, publishers, dates) plus Wikipedia and an
opportunistic Reddit pass. Every Google News link is decoded back to the publisher's own URL,
the page is fetched, and only that fetched text is handed to the model. The model never
browses and can only cite URLs that appear in the corpus, so the Verifier's traceability
check is satisfied by construction.
"""
import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import quote_plus

import httpx

from ..config import settings

logger = logging.getLogger("localiq.research")

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
POLITE_UA = "LocalIQ/1.0 (neighbourhood data research; +https://localiq.in)"

GNEWS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
GNEWS_BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
WIKI = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
REDDIT = "https://www.reddit.com/search.json?q={q}&sort=relevance&t=year&limit=6"

MAX_DOCS = 8
DOC_CHARS = 3800
_fetch_gate = asyncio.Semaphore(10)

_TAG = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_NL = re.compile(r"\n{3,}")


def strip_html(html: str) -> str:
    text = _TAG.sub(" ", html)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", text, flags=re.I)
    text = _ANY_TAG.sub(" ", text)
    text = unescape(text)
    text = _WS.sub(" ", text)
    return _NL.sub("\n\n", text).strip()


async def _get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response | None:
    async with _fetch_gate:
        try:
            return await client.get(url, **kwargs)
        except Exception as exc:
            logger.debug("fetch failed %s: %s", url[:80], exc)
            return None


async def _news_items(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    resp = await _get(client, GNEWS.format(q=quote_plus(query)),
                      headers={"User-Agent": BROWSER_UA}, timeout=20)
    if resp is None or resp.status_code != 200:
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return []
    items = []
    for node in root.findall(".//item")[:limit]:
        source = node.find("source")
        items.append({
            "title": (node.findtext("title") or "").strip(),
            "gn_link": node.findtext("link") or "",
            "published": (node.findtext("pubDate") or "")[:16],
            "publisher": source.text if source is not None else "",
            "publisher_url": source.get("url") if source is not None else "",
        })
    return [i for i in items if i["gn_link"]]


async def _resolve_gnews(client: httpx.AsyncClient, gn_link: str) -> str | None:
    """Decode a news.google.com article link back to the publisher's own URL.

    The signing attributes sit in the last 2 KB of a ~600 KB shell page, so the whole
    page has to come down before the batchexecute call can be made."""
    try:
        article_id = gn_link.split("/articles/")[1].split("?")[0]
    except IndexError:
        return None
    shell = await _get(client, gn_link, headers={"User-Agent": BROWSER_UA}, timeout=25,
                       follow_redirects=True)
    if shell is None or shell.status_code != 200:
        return None
    sg = re.search(r'data-n-a-sg="([^"]+)"', shell.text)
    ts = re.search(r'data-n-a-ts="([^"]+)"', shell.text)
    if not sg or not ts:
        return None

    inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
                                        None, None, None, None, None, 0, 1],
                                       "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                        article_id, int(ts.group(1)), sg.group(1)])
    try:
        resp = await client.post(
            GNEWS_BATCH, data={"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])},
            headers={"User-Agent": BROWSER_UA,
                     "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            timeout=25)
    except Exception as exc:
        logger.debug("gnews decode failed: %s", exc)
        return None
    match = re.search(r'garturlres\\",\\"(https?://[^\\"]+)', resp.text)
    return match.group(1).replace("\\u003d", "=").replace("\\u0026", "&") if match else None


async def _read_article(client: httpx.AsyncClient, item: dict) -> dict | None:
    """Resolve to the publisher URL and pull the body. If the publisher blocks the
    fetch we keep the headline — a dated, attributed headline is still real evidence,
    it is simply labelled as such so the extractor does not over-claim from it."""
    url = await _resolve_gnews(client, item["gn_link"])
    if not url:
        return None
    resp = await _get(client, url, headers={"User-Agent": BROWSER_UA}, timeout=25,
                      follow_redirects=True)
    body = strip_html(resp.text) if resp is not None and resp.status_code < 400 else ""
    if len(body) >= 500:
        return {"url": url, "title": item["title"], "source_name": item["publisher"],
                "published": item["published"], "kind": "news", "text": body[:DOC_CHARS]}
    return {"url": url, "title": item["title"], "source_name": item["publisher"],
            "published": item["published"], "kind": "news-headline",
            "text": f"{item['title']}\n(Headline only — the publisher blocked full-text retrieval. "
                    f"Treat this as evidence that this was reported on this date, nothing more.)"}


async def _wikipedia(client: httpx.AsyncClient, title: str) -> dict | None:
    resp = await _get(client, WIKI.format(title=quote_plus(title.replace(" ", "_"))),
                      headers={"User-Agent": POLITE_UA}, timeout=20, follow_redirects=True)
    if resp is None or resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    extract = data.get("extract") or ""
    if len(extract) < 200:
        return None
    return {"url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page")
                   or f"https://en.wikipedia.org/wiki/{quote_plus(title)}",
            "title": data.get("title", title), "source_name": "Wikipedia",
            "published": "", "kind": "reference", "text": extract[:DOC_CHARS]}


async def _reddit(client: httpx.AsyncClient, query: str) -> list[dict]:
    resp = await _get(client, REDDIT.format(q=quote_plus(query)),
                      headers={"User-Agent": POLITE_UA}, timeout=20, follow_redirects=True)
    if resp is None or resp.status_code != 200:
        return []
    try:
        children = resp.json().get("data", {}).get("children", [])
    except ValueError:
        return []
    out = []
    for child in children[:4]:
        post = child.get("data", {})
        body = f"{post.get('title', '')}\n{post.get('selftext', '')}".strip()
        if len(body) < 120:
            continue
        out.append({"url": f"https://www.reddit.com{post.get('permalink', '')}",
                    "title": post.get("title", "")[:160], "source_name": f"r/{post.get('subreddit')}",
                    "published": "", "kind": "forum", "text": body[:DOC_CHARS]})
    return out


# ------------------------------------------------------------------ LLM passes
async def _research_llm(prompt: str, system: str, max_tokens: int = 2200) -> str | None:
    from .llm import chat
    try:
        return await chat(prompt, system=system, model=settings.research_model,
                          max_tokens=max_tokens)
    except Exception as exc:
        logger.warning("research LLM call failed: %s", exc)
        return None


QUERY_SYSTEM = (
    "You turn a research brief into web search queries for Indian news and civic sources. "
    "Return JSON only: {\"queries\":[\"...\"],\"wikipedia\":[\"...\"]}. 4 to 6 news queries, each "
    "quoting the locality name and pairing it with Bengaluru plus one concrete topic term. "
    "0 to 2 Wikipedia article titles that would give factual background. No prose."
)


async def _plan(instruction: str) -> dict:
    from .llm import extract_json
    raw = await _research_llm(f"RESEARCH BRIEF:\n{instruction[:1800]}", QUERY_SYSTEM,
                              max_tokens=500)
    parsed = extract_json(raw or "") or {}
    queries = [q for q in (parsed.get("queries") or []) if isinstance(q, str)][:6]
    wiki = [w for w in (parsed.get("wikipedia") or []) if isinstance(w, str)][:2]
    return {"queries": queries, "wikipedia": wiki}


async def _gather(plan: dict) -> list[dict]:
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        listings = await asyncio.gather(*[_news_items(client, q, 4) for q in plan["queries"]])
        seen, candidates = set(), []
        for batch in listings:
            for item in batch:
                key = item["title"].lower()[:90]
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(item)
        candidates = candidates[:MAX_DOCS + 3]

        jobs = [_read_article(client, item) for item in candidates]
        jobs += [_wikipedia(client, title) for title in plan["wikipedia"]]
        if plan["queries"]:
            jobs.append(_reddit(client, plan["queries"][0]))
        results = await asyncio.gather(*jobs, return_exceptions=True)

    docs, urls = [], set()
    for result in results:
        if isinstance(result, Exception) or result is None:
            continue
        for doc in (result if isinstance(result, list) else [result]):
            if doc and doc["url"] not in urls:
                urls.add(doc["url"])
                docs.append(doc)
    return docs[:MAX_DOCS + 2]


def _corpus(docs: list[dict]) -> str:
    blocks = []
    for i, doc in enumerate(docs, 1):
        blocks.append(
            f"[DOC {i}]\nURL: {doc['url']}\nPUBLISHER: {doc['source_name'] or 'unknown'}\n"
            f"DATE: {doc['published'] or 'undated'}\nTYPE: {doc['kind']}\n"
            f"TITLE: {doc['title']}\nTEXT:\n{doc['text']}\n")
    return "\n".join(blocks)


EXTRACT_SYSTEM = (
    "You extract structured facts from a fixed corpus of documents that were already retrieved "
    "for you. Rules, without exception: use ONLY the documents provided; every claim must carry a "
    "source_url copied verbatim from a DOC block; never invent a URL, a number or a date; if the "
    "corpus does not answer part of the brief, leave that part empty rather than guessing; a "
    "document that mentions Bengaluru generally but not the named locality must not be used as "
    "evidence about that locality. Never write 'not found', 'unknown', 'not established', 'no data' "
    "or any similar apology into a value field - return an empty string or omit the object instead. "
    "A doc of TYPE news-headline supports only the fact that something was reported on that date; "
    "never quote detail from it. Output strict JSON only, no prose, no markdown fence."
)


async def local_research(instruction: str, system: str = "", max_tokens: int = 1600) -> dict:
    """Retrieval-grounded replacement for Groq's browser_search tool."""
    plan = await _plan(instruction)
    if not plan["queries"]:
        return {"ok": False, "error": "query planning failed", "text": "", "urls": [], "queries": []}

    docs = await _gather(plan)
    if not docs:
        return {"ok": False, "error": "retrieval returned nothing usable for this locality",
                "text": "", "urls": [], "queries": plan["queries"], "docs": 0}

    answer = await _research_llm(
        f"RESEARCH BRIEF:\n{instruction}\n\nCORPUS ({len(docs)} documents):\n{_corpus(docs)}",
        EXTRACT_SYSTEM, max_tokens=max(max_tokens, 1600))
    return {"ok": bool(answer), "text": answer or "", "urls": [d["url"] for d in docs],
            "queries": plan["queries"], "docs": len(docs),
            "provider": f"local-retrieval+{settings.research_model}"}
