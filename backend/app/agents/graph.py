"""LangGraph orchestration: Intake -> parallel Collectors -> Verifier -> Scorer
-> Synthesizer -> Presenter. Heavy collection is cached per locality; only the
personalisation pass runs per user."""
import asyncio
import json
import logging
import operator
import time
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from ..config import settings
from ..db import db, utcnow
from ..rubric import (BASELINE_WEIGHTS, MODULES, PERSONAS, composite, select_modules)
from ..services.cache import get_dossier, save_domain, stale_domains
from ..services.citystats import get_city_stats
from ..services.llm import chat_json, ledger_snapshot, new_run_ledger
from . import collectors as C
from .presenter import present
from .scorer import score_all
from .verifier import verify

logger = logging.getLogger("localiq.graph")


def merge_dicts(left: dict, right: dict) -> dict:
    return {**(left or {}), **(right or {})}


class GState(TypedDict, total=False):
    job_id: str
    locality: dict
    persona_key: str
    profile: dict
    overrides: dict
    force: bool
    stale: list
    domains: Annotated[dict, merge_dicts]
    facts: list
    verified: dict
    module_scores: dict
    baseline_module_scores: dict
    selected: list
    weights: dict
    narrative: dict
    composite: dict
    baseline_composite: dict
    cards: list
    started_at: float


async def emit(job_id: Optional[str], agent: str, message: str, status: str = "running",
               meta: Optional[dict] = None):
    if not job_id:
        return
    await db.jobs.update_one({"job_id": job_id}, {"$push": {"trace": {
        "t": utcnow().isoformat(), "agent": agent, "message": message,
        "status": status, "meta": meta or {}}}})


WEB_DOMAINS = ["safety", "civic", "infra", "chatter"]
ALL_DOMAINS = ["air", "geo"] + WEB_DOMAINS + ["community"]


# ------------------------------------------------------------------- nodes
async def node_intake(state: GState) -> dict:
    loc = state["locality"]
    job_id = state.get("job_id")
    await emit(job_id, "intake", f"Resolved '{loc['name']}' (pin {loc['pincode']}) in Bengaluru "
                                 f"at {loc['lat']}, {loc['lon']}")
    persona = PERSONAS.get(state["persona_key"], PERSONAS["bachelor"])
    weights = dict(persona["weights"])
    overrides = state.get("overrides") or {}
    for module, weight in (overrides.get("weights") or {}).items():
        if module in MODULES:
            weights[module] = int(weight)
    selected = select_modules(state["persona_key"], overrides)
    await emit(job_id, "intake", f"Persona '{persona['label']}' -> {len(selected)} modules selected: "
                                 f"{', '.join(MODULES[m]['label'] for m in selected[:6])}...")

    dossier = await get_dossier(loc["slug"])
    cached = dossier.get("domains", {})
    stale = await stale_domains(loc["slug"], ALL_DOMAINS, force=state.get("force", False))
    reused = [d for d in ALL_DOMAINS if d not in stale]
    if reused:
        await emit(job_id, "intake", f"Reusing cached dossier layers: {', '.join(reused)}")
    await emit(job_id, "intake", f"Refreshing stale layers: {', '.join(stale) or 'none'}")
    # Seed every cached layer. A collector that fails leaves the cached copy in
    # place rather than blanking the layer.
    return {"stale": stale, "weights": weights, "selected": selected,
            "domains": {d: cached[d] for d in ALL_DOMAINS if d in cached},
            "started_at": time.time()}


def _skip(state: GState, domain: str) -> bool:
    return domain not in (state.get("stale") or [])


async def node_air(state: GState) -> dict:
    if _skip(state, "air"):
        return {}
    job_id = state.get("job_id")
    await emit(job_id, "collector:air", "Querying OpenWeather Air Pollution API (live)")
    result = await C.collect_air(state["locality"])
    if result["ok"]:
        await save_domain(state["locality"]["slug"], "air", result)
        await emit(job_id, "collector:air",
                   f"CPCB AQI {result['raw'].get('cpcb_aqi')} "
                   f"({(result['raw'].get('band') or {}).get('band')}), "
                   f"{len(result['raw'].get('forecast', []))} forecast points", status="done")
        return {"domains": {"air": {**result, "collected_at": utcnow().isoformat()}}}
    await emit(job_id, "collector:air", f"No data: {result.get('error')}", status="failed")
    return {}


async def node_geo(state: GState) -> dict:
    if _skip(state, "geo"):
        return {}
    job_id = state.get("job_id")
    await emit(job_id, "collector:geo", "Running Overpass query over OpenStreetMap (2.5 km radius)")
    result = await C.collect_geo(state["locality"])
    if result["ok"]:
        await save_domain(state["locality"]["slug"], "geo", result)
        await emit(job_id, "collector:geo",
                   f"{result['raw'].get('elements_scanned')} OSM elements scanned, "
                   f"{len(result['facts'])} computed facts, nearest metro "
                   f"{result['raw']['metro'].get('nearest_m')} m", status="done")
        return {"domains": {"geo": {**result, "collected_at": utcnow().isoformat()}}}
    await emit(job_id, "collector:geo", f"No data: {result.get('error')}", status="failed")
    return {}


WEB_LABELS = {"safety": "Safety & news", "civic": "Water & power", "infra": "Infrastructure",
              "chatter": "Reputation & chatter"}
WEB_FNS = {"safety": C.collect_safety, "civic": C.collect_civic, "infra": C.collect_infra,
           "chatter": C.collect_chatter}


async def node_web(state: GState) -> dict:
    """Web-search collectors run sequentially under a hard search budget: they are
    the only metered, rate-limited resource in the graph."""
    job_id = state.get("job_id")
    todo = [d for d in WEB_DOMAINS if d in (state.get("stale") or [])][: settings.search_budget]
    if not todo:
        return {}
    out = {}
    for domain in todo:
        label = WEB_LABELS[domain]
        await emit(job_id, f"collector:{domain}", f"{label}: issuing bounded web searches")
        try:
            result = await WEB_FNS[domain](state["locality"])
        except Exception as exc:
            logger.exception("web collector %s failed", domain)
            result = {"ok": False, "facts": [], "raw": {"error": str(exc)[:200]}, "urls": []}
        if result.get("ok"):
            await save_domain(state["locality"]["slug"], domain, result)
            await emit(job_id, f"collector:{domain}",
                       f"{label}: {len(result.get('urls', []))} pages read, "
                       f"{len(result['facts'])} sourced facts", status="done",
                       meta={"urls": result.get("urls", [])[:8], "queries": result.get("queries", [])})
            out[domain] = {**result, "collected_at": utcnow().isoformat()}
        elif result.get("rate_limited"):
            await emit(job_id, f"collector:{domain}",
                       f"{label}: daily research budget reached - keeping the last cached copy of "
                       f"this layer rather than guessing.", status="failed")
        else:
            await emit(job_id, f"collector:{domain}",
                       f"{label}: no usable data returned - this layer will be shown as absent",
                       status="failed")
    return {"domains": out}


async def node_community(state: GState) -> dict:
    job_id = state.get("job_id")
    result = await C.collect_community(state["locality"])
    await emit(job_id, "collector:community",
               f"{result['raw']['posts']} community posts "
               f"({result['raw']['claims']} fact claims, {result['raw']['experiences']} experiences)",
               status="done")
    return {"domains": {"community": {**result, "collected_at": utcnow().isoformat()}}}


async def node_verify(state: GState) -> dict:
    job_id = state.get("job_id")
    domains = state.get("domains") or {}
    facts, urls = [], set()
    for domain, payload in domains.items():
        facts.extend(payload.get("facts") or [])
        urls.update(payload.get("urls") or [])
    result = verify(facts, urls)
    await emit(job_id, "verifier",
               f"{result['stats']['kept']} claims traceable, {result['stats']['dropped']} dropped as "
               f"untraceable, {result['stats']['disputed']} contradiction(s) flagged for moderation",
               status="done", meta={"dropped": [d["label"] for d in result["dropped"]][:6]})
    return {"facts": result["facts"], "verified": result}


async def node_score(state: GState) -> dict:
    job_id = state.get("job_id")
    domains = state.get("domains") or {}
    raw = {d: (payload.get("raw") or {}) for d, payload in domains.items()}
    F = state["verified"]["scored_facts"]
    module_scores = score_all(F, raw)
    weights = state["weights"]
    persona_composite = composite(module_scores, weights)
    baseline = composite(module_scores, BASELINE_WEIGHTS)
    scored = sum(1 for m in module_scores.values() if m["score"] is not None)
    await emit(job_id, "scorer",
               f"{scored}/{len(module_scores)} modules scored by rubric. Persona score "
               f"{persona_composite['score']}, neutral baseline {baseline['score']}", status="done")
    return {"module_scores": module_scores, "composite": persona_composite,
            "baseline_composite": baseline}


SYNTH_SYSTEM = (
    "You are the synthesis agent for LocalIQ, a neighbourhood quality service for Bengaluru. "
    "You may ONLY reference facts present in the FACTS block you are given. Never state a number "
    "that is not in FACTS. Never claim a locality is unsafe for any demographic or group. Never "
    "give investment guarantees, medical or legal advice. Where data is absent, say it is absent. "
    "Write plainly, in second person, for someone about to spend a lot of money. No marketing tone. "
    "Output strict JSON only."
)

SYNTH_SCHEMA = """{"headline":"one sentence, max 18 words","living_here":"2-3 sentences on what daily life here actually looks like for this person","for_you":"2-3 sentences tying the data to this specific person's stated situation","wins":[{"title":"","detail":""}],"watchouts":[{"title":"","detail":""}],"blind_spots":["what data is missing and why that matters"],"modules":{"module_key":"one sentence for that module"},"verdict":"one paragraph, honest, including what you cannot tell them"}"""


async def node_synthesize(state: GState) -> dict:
    job_id = state.get("job_id")
    loc = state["locality"]
    persona = PERSONAS.get(state["persona_key"], PERSONAS["bachelor"])
    profile = state.get("profile") or {}
    scores = state["module_scores"]
    selected = state["selected"]

    lines = []
    for module in selected:
        entry = scores.get(module) or {}
        drivers = "; ".join(f"{d['label']}={d['value']}" for d in (entry.get("drivers") or [])
                            if d.get("value") is not None)
        lines.append(f"- {MODULES[module]['label']} [{module}]: score="
                     f"{entry.get('score') if entry.get('score') is not None else 'NO DATA'} "
                     f"weight={state['weights'].get(module)} | {drivers}")
    disputes = state["verified"].get("disputes") or []

    prompt = f"""LOCALITY: {loc['name']}, Bengaluru (pin {loc['pincode']}, {loc['zone']} zone).
PERSON: persona = {persona['label']}. {persona['summary']}
PROFILE: {json.dumps({k: v for k, v in profile.items() if v}, ensure_ascii=False)[:900]}
PERSONA-WEIGHTED SCORE: {state['composite'].get('score')} (confidence {state['composite'].get('confidence')}, coverage {state['composite'].get('coverage')}%)
NEUTRAL BASELINE SCORE: {state['baseline_composite'].get('score')}

FACTS (module scores and their driving measurements):
{chr(10).join(lines)}

DISPUTED: {json.dumps(disputes)[:600] if disputes else 'none'}

Write the report for this specific person. Use module keys exactly as given in square brackets.
Schema:
{SYNTH_SCHEMA}"""

    await emit(job_id, "synthesizer", "Writing the persona narrative from verified facts only")
    result = await chat_json(prompt, SYNTH_SYSTEM, model=settings.model_smart, max_tokens=1800)
    if not isinstance(result, dict):
        result = {
            "headline": f"{loc['name']} scored {state['composite'].get('score')} for a "
                        f"{persona['label'].lower()}",
            "living_here": "Narrative generation was unavailable for this run. The scores, "
                           "measurements and sources below are unaffected.",
            "for_you": "", "wins": [], "watchouts": [], "blind_spots": [], "modules": {},
            "verdict": "",
        }
        await emit(job_id, "synthesizer", "Narrative unavailable - report falls back to data only",
                   status="failed")
    else:
        await emit(job_id, "synthesizer", f"Narrative written: \"{str(result.get('headline'))[:90]}\"",
                   status="done")
    return {"narrative": result}


async def node_present(state: GState) -> dict:
    job_id = state.get("job_id")
    domains = state.get("domains") or {}
    raw = {d: (payload.get("raw") or {}) for d, payload in domains.items()}
    city_stats = await get_city_stats()
    cards = present(
        locality=state["locality"],
        persona=PERSONAS.get(state["persona_key"], PERSONAS["bachelor"]),
        module_scores=state["module_scores"],
        selected=state["selected"],
        facts=state["facts"],
        F=state["verified"]["all_facts"],
        raw=raw,
        domains=domains,
        weights=state["weights"],
        narrative=state.get("narrative") or {},
        city_stats=city_stats,
    )
    elapsed = round(time.time() - state.get("started_at", time.time()), 1)
    await emit(job_id, "presenter",
               f"Emitted {len(cards)} module cards with "
               f"{sum(len(c['citations']) for c in cards)} citations in {elapsed}s", status="done")
    return {"cards": cards}


def build_graph():
    graph = StateGraph(GState)
    graph.add_node("intake", node_intake)
    graph.add_node("collect_air", node_air)
    graph.add_node("collect_geo", node_geo)
    graph.add_node("collect_web", node_web)
    graph.add_node("collect_community", node_community)
    graph.add_node("verifier", node_verify)
    graph.add_node("scorer", node_score)
    graph.add_node("synthesizer", node_synthesize)
    graph.add_node("presenter", node_present)

    graph.add_edge(START, "intake")
    for node in ["collect_air", "collect_geo", "collect_web", "collect_community"]:
        graph.add_edge("intake", node)
        graph.add_edge(node, "verifier")
    graph.add_edge("verifier", "scorer")
    graph.add_edge("scorer", "synthesizer")
    graph.add_edge("synthesizer", "presenter")
    graph.add_edge("presenter", END)
    return graph.compile()


GRAPH = build_graph()


async def run_report(locality: dict, persona_key: str, profile: dict, overrides: dict,
                     job_id: Optional[str] = None, force: bool = False) -> dict:
    run_ledger = new_run_ledger()
    state = await GRAPH.ainvoke({
        "job_id": job_id, "locality": locality, "persona_key": persona_key,
        "profile": profile or {}, "overrides": overrides or {}, "force": force, "domains": {},
    })
    spent = ledger_snapshot(run_ledger)
    cost = {
        "prompt_tokens": spent["prompt"],
        "completion_tokens": spent["completion"],
        "web_searches": spent["searches"],
        "llm_calls": spent["calls"],
        "est_cost_usd": spent["est_cost_usd"],
        "model": ", ".join(spent["models"]) or "none \u2014 served from cache",
    }
    domains = state.get("domains") or {}
    sources = []
    for fact in state.get("facts", []):
        if fact.get("source_url"):
            sources.append({"name": fact["source_name"], "url": fact["source_url"],
                            "type": fact["source_type"]})
    seen, unique = set(), []
    for s in sources:
        if s["url"] in seen:
            continue
        seen.add(s["url"])
        unique.append(s)

    return {
        "cards": state.get("cards", []),
        "narrative": state.get("narrative", {}),
        "composite": state.get("composite", {}),
        "baseline_composite": state.get("baseline_composite", {}),
        "module_scores": state.get("module_scores", {}),
        "selected": state.get("selected", []),
        "weights": state.get("weights", {}),
        "disputes": (state.get("verified") or {}).get("disputes", []),
        "dropped": [{"label": d.get("label"), "reason": d.get("drop_reason")}
                    for d in (state.get("verified") or {}).get("dropped", [])],
        "verifier_stats": (state.get("verified") or {}).get("stats", {}),
        "sources": unique,
        "layers": {d: {"ok": bool(p.get("ok")), "collected_at": p.get("collected_at")}
                   for d, p in domains.items()},
        "cost": cost,
    }
