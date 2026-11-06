"""Deterministic evaluation runner over the golden dataset.

No LLM calls, no network. Safe to run on every deploy. Three kinds of check:

* frozen expectations - hand-checked numbers that must never drift silently
* invariants          - relations that must hold for any input (sparse < dense, absence stays absent)
* production sampling - the same rules applied to reports actually stored in Mongo
"""
import json
from pathlib import Path

from ..agents.scorer import score_all
from ..db import db
from ..rubric import (BASELINE_WEIGHTS, K, MODULES, PERSONAS, aqi_to_score, composite, cpcb_band,
                      distance_score, saturating, select_modules)
from ..services.air import cpcb_aqi

DATASET_PATH = Path(__file__).with_name("golden.json")
DATASET = json.loads(DATASET_PATH.read_text())

FUNCS = {"saturating": saturating, "distance_score": distance_score, "aqi_to_score": aqi_to_score}


def _check(suite, name, passed, detail=""):
    return {"suite": suite, "check": name, "status": "pass" if passed else "fail",
            "detail": str(detail)}


def _scores_for(fixture_key: str) -> dict:
    fixture = DATASET["fixtures"][fixture_key]
    return score_all(fixture["facts"], fixture.get("raw") or {})


def _arithmetic(results):
    for case in DATASET["arithmetic"]:
        fn = FUNCS[case["fn"]]
        actual = fn(*case["args"])
        results.append(_check("arithmetic", f"{case['fn']}({', '.join(map(str, case['args']))})",
                              actual == case["expect"], f"expected={case['expect']} actual={actual}"))
    results.append(_check("arithmetic", "saturating is monotonic",
                          saturating(5, 10) < saturating(20, 10)))
    results.append(_check("arithmetic", "saturation constants calibrated on all 34 localities",
                          all(K[k] == v for k, v in DATASET["saturation_constants"].items()),
                          f"K={K}"))


def _air(results):
    for case in DATASET["cpcb"]:
        converted = cpcb_aqi(case["components"])
        band = cpcb_band(converted["aqi"])
        ok = (converted["aqi"] == case["expect_aqi"]
              and converted["dominant"] == case["expect_dominant"]
              and band["band"] == case["expect_band"])
        results.append(_check("air", f"CPCB worst-sub-index -> {case['expect_aqi']} "
                                     f"({case['expect_band']})", ok,
                              f"aqi={converted['aqi']} dominant={converted['dominant']} "
                              f"band={band['band']}"))


def _scoring(results, cache):
    for fixture_key, expected in DATASET["expected_scores"].items():
        scores = cache[fixture_key]
        for module, value in expected.items():
            actual = (scores.get(module) or {}).get("score")
            results.append(_check("scoring", f"{fixture_key}.{module} == {value}", actual == value,
                                  f"actual={actual}"))

    for fixture_key, modules in DATASET["expected_absent"].items():
        scores = cache[fixture_key]
        missing = [m for m in modules if (scores.get(m) or {}).get("score") is not None]
        results.append(_check("scoring", f"{fixture_key}: absence is never averaged away",
                              not missing, f"unexpectedly scored: {missing}"))

    for rel in DATASET["invariants"]:
        high = (cache[rel["higher"]].get(rel["module"]) or {}).get("score")
        low = (cache[rel["lower"]].get(rel["module"]) or {}).get("score")
        ok = high is not None and low is not None and high > low
        results.append(_check("invariants",
                              f"{rel['module']}: {rel['higher']} scores above {rel['lower']}", ok,
                              f"{high} vs {low}"))

    again = _scores_for("dense_urban")
    identical = all((again[m] or {}).get("score") == (cache["dense_urban"][m] or {}).get("score")
                    for m in cache["dense_urban"])
    results.append(_check("invariants", "scoring is deterministic across runs", identical))


def _persona(results, cache):
    for persona_key, spec in DATASET["persona_modules"].items():
        selected = set(select_modules(persona_key))
        missing = [m for m in spec["includes"] if m not in selected]
        leaked = [m for m in spec["excludes"] if m in selected]
        results.append(_check("persona", f"{persona_key}: module set matches the rubric",
                              not missing and not leaked,
                              f"missing={missing} unexpected={leaked}"))

    persona_scores = {key: composite(cache["dense_urban"], PERSONAS[key]["weights"])["score"]
                      for key in PERSONAS}
    spread = max(persona_scores.values()) - min(persona_scores.values())
    results.append(_check("persona", "persona weighting actually moves the composite",
                          spread >= DATASET["persona_spread_min"],
                          f"spread={spread} {persona_scores}"))
    baseline = composite(cache["dense_urban"], BASELINE_WEIGHTS)
    results.append(_check("persona", "neutral baseline computes", baseline["score"] is not None,
                          f"baseline={baseline['score']}"))
    return persona_scores, baseline["score"]


async def _production(results):
    contract = DATASET["block_contract"]
    reports = await db.reports.find({}, {"cards": 1, "locality_slug": 1}) \
        .sort("created_at", -1).limit(DATASET["sample_size"]).to_list(DATASET["sample_size"])

    bad_blocks, untraceable, ghost_scores, uncited = [], [], [], []
    sampled_cards = sampled_citations = 0

    for report in reports:
        for card in report.get("cards", []):
            sampled_cards += 1
            for block in card.get("renders", []):
                required = contract.get(block.get("type"))
                if required is None:
                    bad_blocks.append(f"{card['module']}:{block.get('type')}")
                    continue
                missing = [k for k in required if k not in (block.get("data") or {})]
                if missing:
                    bad_blocks.append(f"{card['module']}:{block['type']} missing {missing}")
            for citation in card.get("citations", []):
                sampled_citations += 1
                if citation.get("source_type") in ("media", "official", "forum") \
                        and not citation.get("source_url"):
                    untraceable.append(citation.get("label"))
            if card.get("score") is not None and not card.get("citations"):
                uncited.append(f"{report.get('locality_slug')}:{card['module']}")
            if card.get("empty") and card.get("score") is not None:
                ghost_scores.append(f"{report.get('locality_slug')}:{card['module']}")

    results.append(_check("production", "every render block matches the UI contract",
                          not bad_blocks, f"cards={sampled_cards} bad={bad_blocks[:5]}"))
    results.append(_check("production", "every media/official claim is traceable to a URL",
                          not untraceable, f"citations={sampled_citations} untraceable={untraceable[:5]}"))
    results.append(_check("production", "no scored module without a citation behind it",
                          not uncited, f"uncited={uncited[:5]}"))
    results.append(_check("production", "an empty module never carries a score",
                          not ghost_scores, f"ghosts={ghost_scores[:5]}"))

    unverified = await db.posts.count_documents({"anonymous": True,
                                                 "status": {"$in": ["corroborated", "verified"]}})
    results.append(_check("production", "an anonymous contribution can never reach verified",
                          unverified == 0, f"promoted={unverified}"))

    known = set(MODULES)
    stray = {c["module"] for r in reports for c in r.get("cards", [])} - known
    results.append(_check("production", "every stored card maps to a rubric module", not stray,
                          f"stray={sorted(stray)}"))


async def run_golden() -> dict:
    results = []
    cache = {key: _scores_for(key) for key in DATASET["fixtures"]}

    _arithmetic(results)
    _air(results)
    _scoring(results, cache)
    persona_scores, baseline = _persona(results, cache)
    await _production(results)

    suites = {}
    for row in results:
        stats = suites.setdefault(row["suite"], {"total": 0, "passed": 0})
        stats["total"] += 1
        stats["passed"] += row["status"] == "pass"

    passed = sum(1 for r in results if r["status"] == "pass")
    return {
        "dataset_version": DATASET["version"],
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed,
                    "suites": suites, "persona_scores": persona_scores, "baseline": baseline},
        "results": results,
    }
