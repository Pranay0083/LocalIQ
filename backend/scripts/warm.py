"""Pre-warm the shared dossier cache: free layers (live AQI + OSM geometry) for
every Bengaluru locality, then metered web-research layers under a budget.

Usage:
    python scripts/warm.py geo          # free layers only, all localities
    python scripts/warm.py web 6        # web research for the first 6 localities in list order
"""
import asyncio
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.agents import collectors as C  # noqa: E402
from app.localities import BANGALORE  # noqa: E402
from app.services.cache import save_domain, stale_domains  # noqa: E402


async def warm_free(concurrency: int = 3):
    semaphore = asyncio.Semaphore(concurrency)
    ok = fail = 0
    async def one(loc):
        nonlocal ok, fail
        async with semaphore:
            stale = await stale_domains(loc["slug"], ["air", "geo"])
            for domain, fn in [("air", C.collect_air), ("geo", C.collect_geo)]:
                if domain not in stale:
                    print(f"  = {loc['slug']}/{domain} fresh")
                    continue
                result = await fn(loc)
                if result["ok"]:
                    await save_domain(loc["slug"], domain, result)
                    ok += 1
                    print(f"  + {loc['slug']}/{domain} ok ({len(result['facts'])} facts)")
                else:
                    fail += 1
                    print(f"  ! {loc['slug']}/{domain} FAILED {result.get('error')}")

    await asyncio.gather(*[one(l) for l in BANGALORE])
    print(f"free layers: {ok} ok, {fail} failed")


async def warm_web(limit: int = 6, concurrency: int = 3):
    domains = [("safety", C.collect_safety), ("infra", C.collect_infra),
               ("civic", C.collect_civic), ("chatter", C.collect_chatter)]
    targets = BANGALORE[:limit]
    semaphore = asyncio.Semaphore(concurrency)
    stats = {"ok": 0, "empty": 0, "facts": 0}
    stop = asyncio.Event()

    async def one(loc):
        async with semaphore:
            if stop.is_set():
                return
            stale = await stale_domains(loc["slug"], [d for d, _ in domains])
            if not stale:
                print(f"  = {loc['slug']} all research layers fresh", flush=True)
                return
            for domain, fn in domains:
                if domain not in stale or stop.is_set():
                    continue
                started = time.monotonic()
                try:
                    result = await fn(loc)
                except Exception as exc:
                    print(f"  ! {loc['slug']}/{domain} ERROR {type(exc).__name__}: {exc}", flush=True)
                    continue
                took = round(time.monotonic() - started, 1)
                if result.get("ok"):
                    await save_domain(loc["slug"], domain, result)
                    stats["ok"] += 1
                    stats["facts"] += len(result["facts"])
                    print(f"  + {loc['slug']}/{domain} ok ({len(result['facts'])} facts, "
                          f"{len(result.get('urls', []))} urls, {took}s)", flush=True)
                elif result.get("rate_limited"):
                    print("  ! research budget reached - stopping", flush=True)
                    stop.set()
                    return
                else:
                    stats["empty"] += 1
                    print(f"  ! {loc['slug']}/{domain} no data ({took}s) "
                          f"{str(result.get('raw', {}).get('error'))[:90]}", flush=True)

    await asyncio.gather(*[one(loc) for loc in targets])
    print(f"web layers: {stats['ok']} saved, {stats['empty']} empty, "
          f"{stats['facts']} facts total", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "geo"
    if mode == "geo":
        asyncio.run(warm_free())
    elif mode == "stats":
        from app.services.citystats import compute_city_stats
        print(asyncio.run(compute_city_stats())["stats"])
    else:
        asyncio.run(warm_web(int(sys.argv[2]) if len(sys.argv) > 2 else 6))
