"""Collector agents. Each has a strict tool allow-list and returns typed,
cited facts or an explicit no-data marker. Never prose, never an unsourced number."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..db import db, utcnow
from ..services import air as air_svc
from ..services import geo as geo_svc
from ..services.llm import chat_json, extract_json, web_research

logger = logging.getLogger("localiq.collect")

RESEARCH_SYSTEM = (
    "You are a neighbourhood data collector for Bengaluru, India. Use web search aggressively. "
    "Report ONLY what you actually found on pages you opened. Every claim must carry the exact "
    "source URL you read it on. If you find nothing, return an empty list. Never invent, never "
    "estimate, never generalise from other localities. Output strict JSON only, no prose."
)


def fact(key, label, value, module, source_type, source_name, *, unit=None, source_url=None,
         confidence="high", observed_at=None, note=None, detail=None) -> dict:
    return {
        "key": key, "label": label, "value": value, "unit": unit, "module": module,
        "source_type": source_type, "source_name": source_name, "source_url": source_url,
        "confidence": confidence, "observed_at": observed_at or utcnow().isoformat(),
        "note": note, "detail": detail,
    }


# ---------------------------------------------------------------- Tier 1: air
async def collect_air(loc: dict) -> dict:
    try:
        data = await air_svc.fetch_air(loc["lat"], loc["lon"])
    except Exception as exc:
        logger.warning("air collector failed: %s", exc)
        return {"ok": False, "facts": [], "raw": {}, "error": str(exc)[:200]}

    src = ("OpenWeather Air Pollution API", "https://openweathermap.org/api/air-pollution")
    facts = [
        fact("aqi_current", "CPCB AQI (now)", data["cpcb_aqi"], "air_quality", "live_api", src[0],
             source_url=src[1], observed_at=data["observed_at"],
             note=f"Band: {data['band']['band']}. Dominant pollutant {data['dominant_label']}."),
        fact("pm25", "PM2.5", data["components"].get("pm2_5"), "air_quality", "live_api", src[0],
             unit="ug/m3", source_url=src[1], observed_at=data["observed_at"]),
        fact("pm10", "PM10", data["components"].get("pm10"), "air_quality", "live_api", src[0],
             unit="ug/m3", source_url=src[1], observed_at=data["observed_at"]),
        fact("no2", "NO2", data["components"].get("no2"), "air_quality", "live_api", src[0],
             unit="ug/m3", source_url=src[1], observed_at=data["observed_at"]),
        fact("o3", "Ozone", data["components"].get("o3"), "air_quality", "live_api", src[0],
             unit="ug/m3", source_url=src[1], observed_at=data["observed_at"]),
    ]
    return {"ok": True, "facts": facts, "raw": data}


# ------------------------------------------------------------ Tier 2: geodata
GEO_FACTS = [
    ("cafe", "Cafes within 1.5 km", "nightlife"), ("bar", "Bars & pubs within 1.5 km", "nightlife"),
    ("restaurant", "Restaurants within 1.5 km", "food"), ("hospital", "Hospitals within 2.5 km", "healthcare"),
    ("clinic", "Clinics within 2 km", "healthcare"), ("pharmacy", "Pharmacies within 1.5 km", "healthcare"),
    ("school", "Schools within 2.5 km", "schools"), ("preschool", "Preschools & daycare within 2.5 km", "schools"),
    ("college", "Colleges within 2.5 km", "schools"), ("park", "Parks & gardens within 2.5 km", "parks"),
    ("playground", "Playgrounds within 2 km", "parks"), ("gym", "Gyms & sports centres within 2 km", "fitness"),
    ("pool", "Swimming pools within 2.5 km", "fitness"), ("supermarket", "Supermarkets within 2 km", "daily_needs"),
    ("convenience", "Grocers & bakeries within 1.5 km", "daily_needs"), ("atm", "ATMs within 1.5 km", "daily_needs"),
    ("market", "Markets within 2 km", "daily_needs"), ("police", "Police stations within 2.5 km", "safety_day"),
    ("worship", "Places of worship within 2 km", "worship"), ("vet", "Veterinary clinics within 2.5 km", "pet_friendly"),
    ("petshop", "Pet shops within 2.5 km", "pet_friendly"), ("coworking", "Coworking spaces within 3 km", "internet_wfh"),
]

OSM_SRC = ("OpenStreetMap via Overpass API", "https://www.openstreetmap.org/copyright")


async def collect_geo(loc: dict) -> dict:
    try:
        data = await geo_svc.fetch_geo(loc["lat"], loc["lon"])
    except Exception as exc:
        logger.warning("geo collector failed: %s", exc)
        return {"ok": False, "facts": [], "raw": {}, "error": str(exc)[:200]}

    facts = []
    for cat, label, module in GEO_FACTS:
        entry = data["counts"][cat]
        facts.append(fact(f"count_{cat}", label, entry["count"], module, "computed", OSM_SRC[0],
                          source_url=OSM_SRC[1], unit="places",
                          note=f"Nearest: {entry['nearest_name']} at {entry['nearest_m']} m"
                               if entry["nearest_name"] else "No named entry in OSM",
                          detail=entry["top"]))
    if data["metro"]["nearest_m"] is not None:
        facts.append(fact("metro_distance", "Nearest metro station", data["metro"]["nearest_m"], "commute",
                          "computed", OSM_SRC[0], unit="m", source_url=OSM_SRC[1],
                          note=data["metro"]["nearest_name"], detail=data["metro"]["top"]))
    else:
        facts.append(fact("metro_distance", "Nearest metro station", None, "commute", "computed",
                          OSM_SRC[0], source_url=OSM_SRC[1], confidence="high",
                          note="No metro station mapped within 6 km"))
    if data["rail"]["nearest_m"] is not None:
        facts.append(fact("rail_distance", "Nearest railway station", data["rail"]["nearest_m"], "commute",
                          "computed", OSM_SRC[0], unit="m", source_url=OSM_SRC[1],
                          note=data["rail"]["nearest_name"], detail=data["rail"]["top"]))
    facts.append(fact("bus_stops", "Bus stops within 1.2 km", data["bus_stops_1200m"], "commute",
                      "computed", OSM_SRC[0], unit="stops", source_url=OSM_SRC[1]))
    facts.append(fact("major_roads", "Major road segments within 600 m", data["major_road_segments_600m"],
                      "noise", "computed", OSM_SRC[0], unit="segments", source_url=OSM_SRC[1],
                      note="Motorway / trunk / primary classified roads near the centroid"))
    facts.append(fact("cuisine_variety", "Distinct cuisines tagged", data["cuisine_variety"], "food",
                      "computed", OSM_SRC[0], unit="cuisines", source_url=OSM_SRC[1],
                      detail=data["cuisines"]))
    return {"ok": True, "facts": facts, "raw": data}


# --------------------------------------------------- Tier 3: agentic research
async def _research_json(instruction: str, schema_hint: str) -> dict:
    result = await web_research(f"{instruction}\n\nReturn JSON matching exactly this shape:\n{schema_hint}",
                                RESEARCH_SYSTEM)
    if not result.get("ok"):
        return {"ok": False, "data": None, "urls": [], "error": result.get("error"),
                "rate_limited": result.get("rate_limited", False)}
    parsed = extract_json(result.get("text", ""))
    if parsed is None and result.get("text"):
        parsed = await chat_json(
            f"Convert these research notes into JSON matching:\n{schema_hint}\n\nNOTES:\n{result['text'][:6000]}",
            system="You restructure research notes into JSON. Drop any claim without a source URL.")
    return {"ok": parsed is not None, "data": parsed, "urls": result.get("urls", []),
            "queries": result.get("queries", []), "text": result.get("text", "")[:4000]}


SAFETY_SCHEMA = """{"incidents":[{"date":"YYYY-MM-DD","headline":"","category":"chain snatching|theft|burglary|assault|traffic|cyber|other","source_url":"","source_name":"","location_hint":""}],"police_context":{"jurisdiction":"","note":"","source_url":""},"official_stats":[{"metric":"","value":"","period":"","source_url":"","source_name":""}]}"""


async def collect_safety(loc: dict) -> dict:
    since = (utcnow() - timedelta(days=365)).strftime("%B %Y")
    out = await _research_json(
        f"Find crime and safety incidents reported in news media for {loc['name']}, Bengaluru "
        f"(pin code {loc['pincode']}) since {since}. Search terms should include the locality name with "
        f"'crime', 'theft', 'chain snatching', 'police', 'robbery'. Also find which police station has "
        f"jurisdiction and any published Bengaluru city police statistics for this area. "
        f"Return at most 8 incidents, newest first.", SAFETY_SCHEMA)
    if not out["ok"]:
        return {"ok": False, "facts": [], "raw": {"error": out.get("error")},
                "rate_limited": out.get("rate_limited", False), "urls": out.get("urls", [])}

    data = out["data"] or {}
    incidents = [i for i in (data.get("incidents") or []) if i.get("source_url")]
    facts = [fact("media_incidents", "Media-reported incidents (12 months)", len(incidents),
                  "safety_day", "media", "Aggregated news search", confidence="medium",
                  source_url=incidents[0]["source_url"] if incidents else (out.get("urls") or [None])[0],
                  note="Media-reported incidents are not official crime statistics and under-represent "
                       "unreported crime. Localities with heavier press coverage will show more incidents.",
                  detail=incidents)]
    police = data.get("police_context") or {}
    if police.get("jurisdiction"):
        facts.append(fact("police_jurisdiction", "Police jurisdiction", police["jurisdiction"], "safety_day",
                          "official" if police.get("source_url") else "media",
                          police.get("source_url") and "Police / press source" or "Web search",
                          source_url=police.get("source_url"), confidence="medium", note=police.get("note")))
    for i, stat in enumerate(data.get("official_stats") or []):
        if not stat.get("source_url"):
            continue
        facts.append(fact(f"crime_stat_{i}", stat.get("metric", "Official statistic"), stat.get("value"),
                          "safety_day", "official", stat.get("source_name", "Government source"),
                          source_url=stat["source_url"], confidence="medium", note=stat.get("period")))
    return {"ok": True, "facts": facts, "raw": data, "urls": out.get("urls", []), "queries": out.get("queries", [])}


CIVIC_SCHEMA = """{"water":{"supply_pattern":"","tanker_dependence":"high|medium|low|unknown","reports":[{"claim":"","date":"","source_url":"","source_name":""}]},"power":{"outage_pattern":"","typical_outages_per_month":null,"reports":[{"claim":"","date":"","source_url":"","source_name":""}]}}"""


async def collect_civic(loc: dict) -> dict:
    out = await _research_json(
        f"Find reported water supply reliability and power outage patterns for {loc['name']}, Bengaluru. "
        f"Search BWSSB water supply schedules and disruption notices, BESCOM scheduled power cut notices, "
        f"and news reports about water tanker dependence or borewell issues in this specific locality. "
        f"Only report findings that name this locality.", CIVIC_SCHEMA)
    if not out["ok"]:
        return {"ok": False, "facts": [], "raw": {"error": out.get("error")},
                "rate_limited": out.get("rate_limited", False), "urls": out.get("urls", [])}

    data = out["data"] or {}
    facts = []
    water = data.get("water") or {}
    w_reports = [r for r in (water.get("reports") or []) if r.get("source_url")]
    if water.get("supply_pattern") or w_reports:
        facts.append(fact("water_supply", "Reported water supply pattern",
                          water.get("supply_pattern") or "Reports found", "water", "media",
                          "BWSSB notices / press reports", confidence="medium",
                          source_url=w_reports[0]["source_url"] if w_reports else None,
                          note=f"Tanker dependence reported as: {water.get('tanker_dependence', 'unknown')}",
                          detail=w_reports))
    power = data.get("power") or {}
    p_reports = [r for r in (power.get("reports") or []) if r.get("source_url")]
    if power.get("outage_pattern") or p_reports:
        facts.append(fact("power_outages", "Reported power outage pattern",
                          power.get("outage_pattern") or "Reports found", "power", "media",
                          "BESCOM notices / press reports", confidence="medium",
                          source_url=p_reports[0]["source_url"] if p_reports else None,
                          note=(f"Typical outages per month reported: {power['typical_outages_per_month']}"
                                if power.get("typical_outages_per_month") is not None else None),
                          detail=p_reports))
    return {"ok": True, "facts": facts, "raw": data, "urls": out.get("urls", []), "queries": out.get("queries", [])}


INFRA_SCHEMA = """{"projects":[{"name":"","type":"metro|road|rail|water|sewage|airport|other","status":"announced|approved|under_construction|completed|stalled","expected_year":"","impact":"high|medium|low","description":"","source_url":"","source_name":""}]}"""


async def collect_infra(loc: dict) -> dict:
    out = await _research_json(
        f"Find planned and under-construction infrastructure projects that affect {loc['name']}, Bengaluru. "
        f"Search BMRCL Namma Metro phase 2 and 3 line and station plans, BBMP and BDA road, flyover and "
        f"underpass projects, BWSSB water and sewage upgrades, and Bengaluru suburban rail. Include only "
        f"projects whose route or catchment includes or borders this locality. Give the expected "
        f"completion year where published. CRITICAL: every single project object MUST carry the exact "
        f"source_url of a page you actually opened - drop any project you cannot attribute to a URL.",
        INFRA_SCHEMA)
    if not out["ok"]:
        return {"ok": False, "facts": [], "raw": {"error": out.get("error")},
                "rate_limited": out.get("rate_limited", False), "urls": out.get("urls", [])}

    data = out["data"] or {}
    projects = [p for p in (data.get("projects") or []) if p.get("source_url") and p.get("name")]
    facts = []
    if projects:
        facts.append(fact("infra_projects", "Infrastructure projects in the pipeline", len(projects),
                          "infrastructure", "official", "Authority announcements & press coverage",
                          confidence="medium", source_url=projects[0]["source_url"], detail=projects))
    return {"ok": True, "facts": facts, "raw": data, "urls": out.get("urls", []), "queries": out.get("queries", [])}


CHATTER_SCHEMA = """{"rent_bands":[{"config":"1BHK|2BHK|3BHK","range_inr":"","source_url":"","source_name":""}],"price_trend":{"direction":"rising|flat|falling|unknown","note":"","source_url":"","source_name":""},"noise_construction":[{"claim":"","source_url":"","source_name":""}],"resident_sentiment":[{"quote":"","theme":"","tone":"positive|negative|mixed","source_url":"","source_name":""}],"reputation":[{"place":"","kind":"school|hospital|market|park|cafe","note":"","source_url":"","source_name":""}]}"""


async def collect_chatter(loc: dict) -> dict:
    out = await _research_json(
        f"Research what residents actually say about living in {loc['name']}, Bengaluru. Search Reddit "
        f"r/bangalore, Quora, local forums and news for: current rent ranges by BHK, whether property "
        f"prices are rising or falling, complaints about construction noise or traffic noise, and "
        f"reputation of local schools, hospitals and markets. Tag forum content honestly as forum "
        f"content. Maximum 5 sentiment quotes.", CHATTER_SCHEMA)
    if not out["ok"]:
        return {"ok": False, "facts": [], "raw": {"error": out.get("error")},
                "rate_limited": out.get("rate_limited", False), "urls": out.get("urls", [])}

    data = out["data"] or {}
    facts = []
    bands = [b for b in (data.get("rent_bands") or []) if b.get("source_url") and b.get("range_inr")]
    if bands:
        facts.append(fact("rent_bands", "Reported rent bands", "; ".join(
            f"{b.get('config', '?')}: Rs {b['range_inr']}" for b in bands[:4]), "cost", "media",
            bands[0].get("source_name", "Web search"), source_url=bands[0]["source_url"],
            confidence="low", note="Listing-derived ranges, not transaction data.", detail=bands))
    trend = data.get("price_trend") or {}
    if trend.get("direction") and trend.get("direction") != "unknown" and trend.get("source_url"):
        facts.append(fact("price_trend", "Reported price trend", trend["direction"], "investment", "media",
                          trend.get("source_name", "Web search"), source_url=trend["source_url"],
                          confidence="low", note=trend.get("note")))
    noise = [n for n in (data.get("noise_construction") or []) if n.get("source_url")]
    if noise:
        facts.append(fact("noise_reports", "Reported noise & construction issues", len(noise), "noise",
                          "media", noise[0].get("source_name", "Web search"),
                          source_url=noise[0]["source_url"], confidence="low", detail=noise))
    sentiment = [s for s in (data.get("resident_sentiment") or []) if s.get("quote")]
    if sentiment:
        facts.append(fact("resident_sentiment", "Resident chatter found", len(sentiment), "safety_day",
                          "forum", "Reddit / forums / local coverage", confidence="low",
                          source_url=sentiment[0].get("source_url"),
                          note="Forum content is unverified and shown for context only. It never moves a score.",
                          detail=sentiment[:5]))
    reputation = [r for r in (data.get("reputation") or []) if r.get("source_url") and r.get("place")]
    if reputation:
        facts.append(fact("place_reputation", "Places with published reputation signals", len(reputation),
                          "schools", "media", reputation[0].get("source_name", "Web search"),
                          source_url=reputation[0]["source_url"], confidence="low", detail=reputation))
    return {"ok": True, "facts": facts, "raw": data, "urls": out.get("urls", []), "queries": out.get("queries", [])}


# ---------------------------------------------------------------- community
CLAIM_MODULE = {
    "water_hours": "water", "water_quality": "water", "power_cuts": "power", "noise": "noise",
    "parking": "daily_needs", "rent_paid": "cost", "safety_night": "safety_night", "internet": "internet_wfh",
}

NEGATIVE_MARKERS = ("no supply", "tanker", "shortage", "outage", "power cut", "cuts", "dry",
                    "erratic", "alternate day", "borewell", "load shedding", "problem", "unreliable",
                    "contaminated", "muddy", "hours without", "frequent")
POSITIVE_MARKERS = ("never", "reliable", "uninterrupted", "no issue", "no problem", "regular",
                    "daily", "rarely", "consistent", "clean", "always on")


def claim_polarity(text: str) -> str:
    """Deterministic polarity so a resident reporting that things WORK does not
    push a score down. Only a net-negative report penalises."""
    low = (text or "").lower()
    net = sum(1 for m in NEGATIVE_MARKERS if m in low) - sum(1 for m in POSITIVE_MARKERS if m in low)
    if net >= 1:
        return "negative"
    if net <= -1:
        return "positive"
    return "neutral"


async def collect_community(loc: dict) -> dict:
    posts = await db.posts.find({"locality_slug": loc["slug"], "status": {"$ne": "removed"}}) \
        .sort("created_at", -1).limit(200).to_list(200)
    facts = []
    claims = [p for p in posts if p.get("kind") == "fact_claim"]
    experiences = [p for p in posts if p.get("kind") == "experience"]

    grouped: dict = {}
    for claim in claims:
        grouped.setdefault(claim.get("claim_type", "other"), []).append(claim)

    for claim_type, items in grouped.items():
        module = CLAIM_MODULE.get(claim_type, "daily_needs")
        contributors = {str(i.get("user_id")) for i in items if not i.get("anonymous")}
        verified = len(contributors) >= 2 and any(i.get("proof_url") for i in items)
        polarities = [claim_polarity(f"{i.get('claim_value', '')} {i.get('body', '')}") for i in items]
        negatives = polarities.count("negative")
        positives = polarities.count("positive")
        polarity = "negative" if negatives > positives else "positive" if positives > negatives else "neutral"
        facts.append(fact(f"community_{claim_type}", f"Community claim: {claim_type.replace('_', ' ')}",
                          items[0].get("claim_value") or items[0].get("body", "")[:120], module,
                          "community_verified" if verified else "community_unverified",
                          f"{len(items)} report(s) from {len(contributors)} contributor(s)",
                          confidence="medium" if verified else "low",
                          note=("Corroborated by independent contributors with proof. "
                                if verified else "Awaiting independent corroboration - not scored. ")
                               + f"Net polarity across reports: {polarity} "
                                 f"({negatives} negative, {positives} positive).",
                          detail=[{"body": i.get("body", "")[:220], "value": i.get("claim_value"),
                                   "proof_url": i.get("proof_url"), "upvotes": i.get("upvotes", 0),
                                   "polarity": p, "created_at": i.get("created_at")}
                                  for i, p in list(zip(items, polarities))[:5]]))
        facts[-1]["polarity"] = polarity

    if experiences:
        scored = [e for e in experiences if (e.get("upvotes", 0) - e.get("downvotes", 0)) >= 2]
        tones = [e.get("sentiment") for e in scored if e.get("sentiment")]
        facts.append(fact("community_sentiment", "Community experience posts", len(experiences),
                          "safety_day", "community_unverified", "LocalIQ community",
                          confidence="low",
                          note="Resident sentiment, not fact. Only posts above the vote threshold "
                               "feed the sentiment signal, and sentiment never sets a score.",
                          detail=[{"body": e.get("body", "")[:220], "sentiment": e.get("sentiment"),
                                   "topics": e.get("topics", []), "upvotes": e.get("upvotes", 0),
                                   "author": e.get("author_name"), "created_at": e.get("created_at")}
                                  for e in experiences[:8]]))
        facts[-1]["value"] = len(experiences)
        facts[-1]["detail"] = facts[-1]["detail"]
        facts[-1]["note"] += f" {len(tones)} post(s) above threshold."

    return {"ok": True, "facts": facts, "raw": {"posts": len(posts), "claims": len(claims),
                                                "experiences": len(experiences)}}
