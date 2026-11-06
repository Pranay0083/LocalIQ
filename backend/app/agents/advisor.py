"""Comparator, grounded chat, and the profile-driven recommender."""
import asyncio
import json
import logging
from typing import Optional

from ..config import settings
from ..db import db, utcnow
from ..localities import BANGALORE, BY_SLUG
from ..rubric import BASELINE_WEIGHTS, MODULES, PERSONAS, composite, select_modules
from ..services.cache import get_dossier, save_domain, stale_domains
from ..services.geo import haversine
from ..services.llm import chat_json, stream_chat
from . import collectors as C
from .scorer import score_all
from .verifier import verify

logger = logging.getLogger("localiq.advisor")

GUARDRAIL = (
    "Never state a number that is not in the data given to you. Never claim a locality is unsafe "
    "for any demographic or community. No investment guarantees, no medical or legal advice. "
    "Say plainly when data is missing. This is decision support, not advice."
)


# ------------------------------------------------------------------ compare
COMPARE_SCHEMA = """{"verdict":"one paragraph naming the recommended locality and why","tradeoff":"the single real trade-off between them, one sentence","per_locality":[{"slug":"","wins":["",""],"loses":["",""],"best_for":""}],"decider":"the one question the user should answer to settle this","cannot_tell":"what the data cannot tell them"}"""


async def compare_localities(reports: list, persona_key: str, profile: dict) -> dict:
    persona = PERSONAS.get(persona_key, PERSONAS["bachelor"])
    blocks = []
    for report in reports:
        lines = [f"{MODULES[m]['label']}: {(report['module_scores'].get(m) or {}).get('score', 'NO DATA')}"
                 for m in report["selected"]]
        blocks.append(
            f"### {report['locality']['name']} (slug {report['locality']['slug']})\n"
            f"Persona score {report['composite'].get('score')} | neutral baseline "
            f"{report['baseline_composite'].get('score')} | coverage "
            f"{report['composite'].get('coverage')}%\n" + "\n".join(lines))

    prompt = f"""PERSON: {persona['label']}. {persona['summary']}
PROFILE: {json.dumps({k: v for k, v in (profile or {}).items() if v}, ensure_ascii=False)[:800]}

{chr(10).join(blocks)}

Compare these Bengaluru localities for this specific person. Use only the scores above.
Schema:
{COMPARE_SCHEMA}"""

    result = await chat_json(prompt, f"You are the comparison agent for LocalIQ. {GUARDRAIL} "
                                     f"Output strict JSON only.", model=settings.model_smart,
                             max_tokens=1500)
    return result if isinstance(result, dict) else {
        "verdict": "Comparison narrative unavailable for this run. The score table below is unaffected.",
        "tradeoff": "", "per_locality": [], "decider": "", "cannot_tell": ""}


# --------------------------------------------------------------------- chat
CHAT_SYSTEM = (f"You are the LocalIQ chat agent, grounded strictly in one locality dossier. "
               f"{GUARDRAIL}")
SOURCES_MARKER = "###SOURCES###"
MISSING_MARKER = "###MISSING###"


def _chat_context(report: dict, question: str, history: list) -> str:
    loc = report["locality"]
    scores = "\n".join(
        f"- {MODULES[m]['label']} [{m}]: {(report['module_scores'].get(m) or {}).get('score', 'NO DATA')} "
        f"| {(report['module_scores'].get(m) or {}).get('reason', '')}"
        for m in report.get("selected", []))
    facts = []
    for card in report.get("cards", []):
        for citation in card.get("citations", [])[:6]:
            facts.append(f"- [{citation['source_type']}] {citation['label']}: {citation.get('value')} "
                         f"({citation.get('source_name')}{' | ' + citation['source_url'] if citation.get('source_url') else ''})")
    turns = "\n".join(f"{h['role']}: {h['content'][:300]}" for h in (history or [])[-6:])

    return f"""LOCALITY: {loc['name']}, Bengaluru.
MODULE SCORES:
{scores}

VERIFIED FACTS AND THEIR SOURCES:
{chr(10).join(facts[:70])}

NARRATIVE ALREADY SHOWN TO USER: {json.dumps(report.get('narrative', {}))[:1200]}

CONVERSATION SO FAR:
{turns or '(new conversation)'}

USER QUESTION: {question}

Answer only from the facts above. If the answer is not in them, say exactly what is missing and
suggest the user contribute it to the community. Cite the source labels you used."""


async def answer_question(report: dict, question: str, history: list) -> dict:
    prompt = (_chat_context(report, question, history) + "\nReturn JSON: "
              '{"answer":"2-4 short paragraphs, plain language","used_sources":'
              '["source label strings you actually used"],'
              '"missing":"what you could not answer, or empty string"}')
    result = await chat_json(prompt, f"{CHAT_SYSTEM} Output strict JSON only.",
                             model=settings.model_fast, max_tokens=1100)
    if not isinstance(result, dict):
        return {"answer": "I could not generate an answer for that just now. Please try again.",
                "used_sources": [], "missing": ""}
    return result


def _parse_trailer(trailer: str) -> tuple[list, str]:
    head, _, rest = trailer.partition(MISSING_MARKER)
    sources = [s.strip() for s in head.replace("\n", " ").split("|") if s.strip()][:8]
    missing = rest.strip()
    return sources, "" if missing.upper() in ("", "NONE", "N/A") else missing


async def stream_answer(report: dict, question: str, history: list):
    """Yield ('delta', text) as the answer is written, then ('meta', {...}) once."""
    prompt = (_chat_context(report, question, history) + f"""

Write the answer as 2 to 4 short plain-language paragraphs. No markdown headings, no bullet lists.
When the prose is finished, and only then, append exactly two trailer lines:
{SOURCES_MARKER} the source labels you actually used, separated by |
{MISSING_MARKER} what you could not answer from the facts, or NONE""")

    buffer, emitted, in_trailer = "", 0, False
    holdback = len(SOURCES_MARKER) - 1
    try:
        async for chunk in stream_chat(prompt, CHAT_SYSTEM, model=settings.model_fast,
                                       max_tokens=1100):
            buffer += chunk
            if in_trailer:
                continue
            marker_at = buffer.find(SOURCES_MARKER)
            if marker_at >= 0:
                in_trailer = True
                if marker_at > emitted:
                    yield "delta", buffer[emitted:marker_at]
                emitted = marker_at
                continue
            safe = len(buffer) - holdback
            if safe > emitted:
                yield "delta", buffer[emitted:safe]
                emitted = safe
    except Exception as exc:
        logger.warning("chat stream failed: %s", exc)
        if not buffer:
            yield "meta", {"answer": "I could not generate an answer for that just now. "
                                     "Please try again.", "used_sources": [], "missing": ""}
            return

    if not in_trailer and len(buffer) > emitted:
        yield "delta", buffer[emitted:]

    prose, _, trailer = buffer.partition(SOURCES_MARKER)
    sources, missing = _parse_trailer(trailer)
    yield "meta", {"answer": prose.strip(), "used_sources": sources, "missing": missing}


# ---------------------------------------------------------------- recommend
RECOMMEND_SCHEMA = """{"picks":[{"slug":"","rank":1,"why":"2 sentences grounded in the scores","watch":"one caveat"}],"reasoning":"one paragraph on how you ranked them","ignored":"which of the user's stated needs the data cannot address"}"""


async def _quick_dossier(loc: dict) -> Optional[dict]:
    """Free tiers only (live AQI + OSM geometry). No web search, no LLM."""
    try:
        stale = await stale_domains(loc["slug"], ["air", "geo"])
        dossier = await get_dossier(loc["slug"])
        domains = dict(dossier.get("domains", {}))
        if "air" in stale:
            result = await C.collect_air(loc)
            if result["ok"]:
                await save_domain(loc["slug"], "air", result)
            domains["air"] = result
        if "geo" in stale:
            result = await C.collect_geo(loc)
            if result["ok"]:
                await save_domain(loc["slug"], "geo", result)
            domains["geo"] = result
        return domains
    except Exception as exc:
        logger.warning("quick dossier failed for %s: %s", loc["slug"], exc)
        return None


async def recommend(profile: dict, persona_key: str, limit: int = 5) -> dict:
    persona = PERSONAS.get(persona_key, PERSONAS["bachelor"])
    weights = persona["weights"]

    candidates = list(BANGALORE)
    anchor = (profile or {}).get("work_locality")
    if anchor and anchor in BY_SLUG:
        base = BY_SLUG[anchor]
        candidates.sort(key=lambda l: haversine(base["lat"], base["lon"], l["lat"], l["lon"]))
        candidates = candidates[:10]
    else:
        warm = await db.dossiers.find({}, {"locality_slug": 1, "_id": 0}).to_list(200)
        warm_slugs = {w["locality_slug"] for w in warm}
        candidates.sort(key=lambda l: (l["slug"] not in warm_slugs,))
        candidates = candidates[:10]

    semaphore = asyncio.Semaphore(3)

    async def evaluate(loc):
        async with semaphore:
            domains = await _quick_dossier(loc)
            if not domains:
                return None
            facts = []
            for payload in domains.values():
                facts.extend(payload.get("facts") or [])
            verified = verify(facts, set())
            raw = {d: (p.get("raw") or {}) for d, p in domains.items()}
            module_scores = score_all(verified["scored_facts"], raw)
            persona_total = composite(module_scores, weights)
            return {"locality": loc, "module_scores": module_scores, "composite": persona_total,
                    "baseline": composite(module_scores, BASELINE_WEIGHTS)}

    results = [r for r in await asyncio.gather(*[evaluate(l) for l in candidates]) if r]
    results = [r for r in results if r["composite"].get("score") is not None]
    results.sort(key=lambda r: r["composite"]["score"], reverse=True)
    shortlist = results[:limit]

    selected = select_modules(persona_key)
    table = []
    for r in shortlist:
        rows = ", ".join(f"{MODULES[m]['label']}={(r['module_scores'].get(m) or {}).get('score')}"
                         for m in selected[:8])
        table.append(f"- {r['locality']['name']} (slug {r['locality']['slug']}) "
                     f"score {r['composite']['score']} | {rows}")

    prompt = f"""PERSON: {persona['label']}. {persona['summary']}
PROFILE: {json.dumps({k: v for k, v in (profile or {}).items() if v}, ensure_ascii=False)[:900]}

CANDIDATE BENGALURU LOCALITIES, ALREADY SCORED BY THE RUBRIC:
{chr(10).join(table)}

Rank these for this person and explain. Only use the scores above.
Schema:
{RECOMMEND_SCHEMA}"""

    narrative = await chat_json(prompt, f"You are the LocalIQ recommendation agent. {GUARDRAIL} "
                                        f"Output strict JSON only.", model=settings.model_smart,
                                max_tokens=1400)
    if not isinstance(narrative, dict):
        narrative = {"picks": [{"slug": r["locality"]["slug"], "rank": i + 1, "why": "", "watch": ""}
                               for i, r in enumerate(shortlist)],
                     "reasoning": "Ranking is by rubric score; narrative unavailable this run.",
                     "ignored": ""}

    return {
        "persona": {"key": persona_key, "label": persona["label"], "summary": persona["summary"]},
        "candidates": [{
            "slug": r["locality"]["slug"], "name": r["locality"]["name"],
            "zone": r["locality"]["zone"], "blurb": r["locality"]["blurb"],
            "score": r["composite"]["score"], "baseline": r["baseline"]["score"],
            "confidence": r["composite"]["confidence"], "coverage": r["composite"].get("coverage"),
            "top_modules": [{"module": m, "label": MODULES[m]["label"],
                             "score": (r["module_scores"].get(m) or {}).get("score")}
                            for m in selected[:5]],
        } for r in shortlist],
        "narrative": narrative,
        "evaluated": len(results),
        "generated_at": utcnow().isoformat(),
    }
