"""City-wide module score distribution, so every module card can say how this
locality compares with the Bengaluru median rather than only an absolute number."""
import logging
import statistics
from datetime import timedelta

from ..db import db, utcnow
from ..rubric import MODULES

logger = logging.getLogger("localiq.citystats")

_CACHE = {"at": None, "data": None}


async def compute_city_stats() -> dict:
    from ..agents.scorer import score_all
    from ..agents.verifier import verify

    buckets = {m: [] for m in MODULES}
    count = 0
    async for doc in db.dossiers.find({"domains.geo.ok": True}):
        domains = doc.get("domains", {})
        facts = []
        for payload in domains.values():
            facts.extend(payload.get("facts") or [])
        verified = verify(facts, set())
        raw = {k: (p.get("raw") or {}) for k, p in domains.items()}
        scores = score_all(verified["scored_facts"], raw)
        for module, entry in scores.items():
            if entry.get("score") is not None:
                buckets[module].append(entry["score"])
        count += 1

    stats = {}
    for module, values in buckets.items():
        if len(values) < 3:
            continue
        values.sort()
        stats[module] = {
            "median": round(statistics.median(values), 1),
            "p25": round(values[len(values) // 4], 1),
            "p75": round(values[3 * len(values) // 4], 1),
            "n": len(values),
        }
    payload = {"key": "bengaluru", "localities": count, "stats": stats,
               "computed_at": utcnow().isoformat()}
    await db.city_stats.update_one({"key": "bengaluru"}, {"$set": payload}, upsert=True)
    _CACHE["at"] = utcnow()
    _CACHE["data"] = payload
    logger.info("city stats computed over %s localities, %s modules", count, len(stats))
    return payload


async def get_city_stats() -> dict:
    if _CACHE["data"] and _CACHE["at"] and utcnow() - _CACHE["at"] < timedelta(hours=6):
        return _CACHE["data"]
    doc = await db.city_stats.find_one({"key": "bengaluru"}, {"_id": 0})
    if doc:
        _CACHE["at"] = utcnow()
        _CACHE["data"] = doc
        return doc
    return {"stats": {}, "localities": 0}


def percentile_of(stats: dict, module: str, score) -> dict:
    entry = (stats.get("stats") or {}).get(module)
    if entry is None or score is None:
        return {}
    if score >= entry["p75"]:
        rank = "top quartile"
    elif score <= entry["p25"]:
        rank = "bottom quartile"
    else:
        rank = "middle of the city"
    return {"city_median": entry["median"], "city_rank": rank,
            "delta": round(score - entry["median"], 1), "n": entry["n"]}
