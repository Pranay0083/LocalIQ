"""Per-locality dossier cache with per-domain freshness policy."""
from datetime import datetime, timedelta, timezone

from ..db import db, utcnow
from ..rubric import FRESHNESS_POLICY


def is_fresh(domain: str, collected_at: str) -> bool:
    if not collected_at:
        return False
    try:
        stamp = datetime.fromisoformat(collected_at)
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    hours = FRESHNESS_POLICY.get(domain, {}).get("hours", 24)
    if hours <= 0:
        return False
    return utcnow() - stamp < timedelta(hours=hours)


async def get_dossier(slug: str) -> dict:
    doc = await db.dossiers.find_one({"locality_slug": slug}, {"_id": 0})
    return doc or {"locality_slug": slug, "domains": {}}


async def stale_domains(slug: str, wanted: list, force: bool = False) -> list:
    if force:
        return list(wanted)
    dossier = await get_dossier(slug)
    domains = dossier.get("domains", {})
    return [d for d in wanted if not is_fresh(d, (domains.get(d) or {}).get("collected_at", ""))]


async def save_domain(slug: str, domain: str, payload: dict):
    await db.dossiers.update_one(
        {"locality_slug": slug},
        {"$set": {f"domains.{domain}": {**payload, "collected_at": utcnow().isoformat()},
                  "updated_at": utcnow().isoformat()}},
        upsert=True,
    )


def domain_age_label(domains: dict, domain: str) -> str:
    entry = domains.get(domain) or {}
    stamp = entry.get("collected_at")
    if not stamp:
        return "never"
    try:
        dt = datetime.fromisoformat(stamp)
    except ValueError:
        return "unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = utcnow() - dt
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)}m ago"
    if mins < 60 * 24:
        return f"{mins // 60}h ago"
    return f"{mins // (60 * 24)}d ago"
