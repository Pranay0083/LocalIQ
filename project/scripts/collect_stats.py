"""Snapshot the live corpus + cost ledger into project/reports/app_stats.json."""
import asyncio
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.db import db  # noqa: E402

OUT = ROOT / "project" / "reports" / "app_stats.json"


async def main():
    stats = {"generated_at": datetime.now().isoformat(timespec="seconds"), "collections": {}}
    for name in await db.list_collection_names():
        stats["collections"][name] = await db[name].count_documents({})

    tokens, models, per_locality = Counter(), Counter(), defaultdict(lambda: {"runs": 0, "cost": 0.0})
    cost, costed, durations = 0.0, 0, []
    for job in await db.jobs.find({}, {"cost": 1, "locality_name": 1, "created_at": 1,
                                       "finished_at": 1}).to_list(2000):
        entry = job.get("cost") or {}
        if entry.get("llm_calls"):
            costed += 1
            tokens["llm_calls"] += entry.get("llm_calls", 0)
            tokens["prompt"] += entry.get("prompt_tokens", 0)
            tokens["completion"] += entry.get("completion_tokens", 0)
            tokens["web_searches"] += entry.get("web_searches", 0)
            cost += float(entry.get("est_cost_usd") or 0)
            models[entry.get("model", "unrecorded")] += entry.get("llm_calls", 0)
            bucket = per_locality[job.get("locality_name", "?")]
            bucket["runs"] += 1
            bucket["cost"] = round(bucket["cost"] + float(entry.get("est_cost_usd") or 0), 5)
        if job.get("created_at") and job.get("finished_at"):
            try:
                durations.append(round((datetime.fromisoformat(job["finished_at"])
                                        - datetime.fromisoformat(job["created_at"])).total_seconds(), 1))
            except ValueError:
                pass

    durations.sort()
    posts = Counter()
    async for post in db.posts.find({}, {"status": 1, "anonymous": 1}):
        posts[("anonymous_" if post.get("anonymous") else "") + str(post.get("status"))] += 1

    stats["cost"] = {
        "runs_total": stats["collections"].get("jobs", 0), "runs_costed": costed,
        "tokens": dict(tokens), "models": dict(models),
        "total_usd": round(cost, 5), "avg_usd_per_costed_run": round(cost / max(costed, 1), 5),
        "by_locality": dict(per_locality),
    }
    stats["run_seconds"] = {"n": len(durations),
                            "p50": durations[len(durations) // 2] if durations else None,
                            "min": durations[0] if durations else None,
                            "max": durations[-1] if durations else None}
    stats["posts_by_status"] = dict(posts)

    with open(OUT, "w") as handle:
        json.dump(stats, handle, indent=2)
    print(json.dumps(stats["cost"], indent=1))
    print("written to", OUT)


if __name__ == "__main__":
    asyncio.run(main())
