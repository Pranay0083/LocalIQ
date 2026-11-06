"""Verifier: the trust gate. Deterministic traceability checks against the raw
retrieved payload, contradiction detection, per-field confidence."""
import re
from urllib.parse import urlparse

TRACEABLE_TYPES = {"media", "official", "forum"}
GOV_HINTS = ("gov.in", "nic.in", "bmrcl", "bwssb", "bescom", "bbmp", "bda.", "karnataka")


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except ValueError:
        return ""


def verify(facts: list, collected_urls: set) -> dict:
    kept, dropped, disputes = [], [], []
    hosts = {_host(u) for u in collected_urls if u}

    for item in facts:
        stype = item.get("source_type")
        if stype in TRACEABLE_TYPES:
            url = item.get("source_url")
            if not url or not re.match(r"^https?://", url):
                dropped.append({**item, "drop_reason": "no source URL - not traceable to a retrieved page"})
                continue
            host = _host(url)
            if hosts and host and host not in hosts:
                item = {**item, "confidence": "low",
                        "note": (item.get("note") or "") +
                                " URL cited by the agent but not among the pages it opened."}
            if stype == "official" and not any(h in (host or "") for h in GOV_HINTS):
                item = {**item, "source_type": "media",
                        "note": (item.get("note") or "") + " Reclassified: not on an official domain."}
        if stype == "community_unverified":
            item = {**item, "scored": False}
        kept.append(item)

    by_key = {f["key"]: f for f in kept}
    for domain, community_key, official_key in [
        ("water", "community_water_hours", "water_supply"),
        ("power", "community_power_cuts", "power_outages"),
    ]:
        community = by_key.get(community_key)
        official = by_key.get(official_key)
        if community and official:
            c_text = str(community.get("value", "")).lower()
            o_text = (str(official.get("value", "")) + " " + str(official.get("note", ""))).lower()
            complains = any(w in c_text for w in ("cut", "no supply", "outage", "tanker", "shortage", "hours"))
            reassures = any(w in o_text for w in ("no disruption", "normal", "uninterrupted", "no outage"))
            if complains and reassures:
                disputes.append({
                    "module": domain,
                    "community_claim": community.get("value"),
                    "official_claim": official.get("value"),
                    "status": "disputed",
                    "note": "Community reports contradict the official/utility source. Surfaced as a "
                            "dispute rather than resolved automatically; queued for human moderation.",
                })

    scored = [f for f in kept if f.get("scored") is not False]
    return {
        "facts": kept,
        "scored_facts": {f["key"]: f for f in scored},
        "all_facts": {f["key"]: f for f in kept},
        "dropped": dropped,
        "disputes": disputes,
        "stats": {"in": len(facts), "kept": len(kept), "dropped": len(dropped),
                  "disputed": len(disputes)},
    }
