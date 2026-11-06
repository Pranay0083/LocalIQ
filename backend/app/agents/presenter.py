"""Presenter: emits the strict JSON contract the UI renders. The frontend has
zero layout intelligence - block type, order and chart choice are decided here."""
from typing import Optional

from ..rubric import MODULES, cpcb_band
from ..services.cache import domain_age_label

MODULE_DOMAIN = {
    "air_quality": "air", "commute": "geo", "nightlife": "geo", "food": "geo", "schools": "geo",
    "parks": "geo", "healthcare": "geo", "daily_needs": "geo", "fitness": "geo", "worship": "geo",
    "pet_friendly": "geo", "noise": "geo", "safety_day": "safety", "safety_night": "safety",
    "water": "civic", "power": "civic", "infrastructure": "infra", "cost": "chatter",
    "investment": "chatter", "internet_wfh": "geo",
}

CONTRIBUTION_PROMPT = {
    "water": {"claim_type": "water_hours", "cta": "Report your water supply hours",
              "missing": ["Daily supply window", "Tanker dependence", "Borewell status"]},
    "power": {"claim_type": "power_cuts", "cta": "Report power cuts you experienced",
              "missing": ["Outages per month", "Typical duration", "Backup availability"]},
    "cost": {"claim_type": "rent_paid", "cta": "Share the rent you actually pay",
             "missing": ["Configuration", "Monthly rent", "Deposit"]},
    "noise": {"claim_type": "noise", "cta": "Report noise or construction",
              "missing": ["Source of noise", "Time of day", "Duration"]},
    "infrastructure": {"claim_type": "other", "cta": "Know of a project here? Post it with a source",
                       "missing": ["Project name", "Status", "Expected year"]},
}


def _citations(module: str, facts: list) -> list:
    out = []
    for f in facts:
        if f.get("module") != module:
            continue
        out.append({
            "label": f["label"], "value": f.get("value"), "unit": f.get("unit"),
            "source_type": f["source_type"], "source_name": f["source_name"],
            "source_url": f.get("source_url"), "observed_at": f.get("observed_at"),
            "confidence": f.get("confidence"), "note": f.get("note"),
        })
    return out


def _walk_min(metres: Optional[float]) -> Optional[int]:
    if metres is None:
        return None
    return max(1, round(metres / 80))


def build_renders(module: str, entry: dict, F: dict, raw: dict) -> list:
    def val(key, default=None):
        item = F.get(key)
        return default if not item or item.get("value") is None else item["value"]

    def det(key):
        return (F.get(key) or {}).get("detail") or []

    renders = []
    drivers = entry.get("drivers") or []

    if module == "air_quality":
        air = raw.get("air") or {}
        aqi = air.get("cpcb_aqi")
        if aqi is not None:
            band = cpcb_band(aqi)
            renders.append({"type": "gauge", "title": "Live CPCB AQI", "data": {
                "value": aqi, "min": 0, "max": 500, "band": band["band"], "tone": band["tone"],
                "caption": f"Dominant pollutant {air.get('dominant_label')}",
                "segments": [{"label": "Good", "from": 0, "to": 50, "tone": "positive"},
                             {"label": "Satisfactory", "from": 51, "to": 100, "tone": "positive"},
                             {"label": "Moderate", "from": 101, "to": 200, "tone": "warning"},
                             {"label": "Poor", "from": 201, "to": 300, "tone": "warning"},
                             {"label": "Very Poor", "from": 301, "to": 400, "tone": "negative"},
                             {"label": "Severe", "from": 401, "to": 500, "tone": "negative"}]}})
        series = (air.get("forecast") or [])[:48]
        if series:
            renders.append({"type": "trend_line", "title": "AQI & PM2.5, next 48 hours", "data": {
                "series": [{"label": p["label"], "aqi": p["aqi"], "pm25": p["pm2_5"]} for p in series],
                "lines": [{"key": "aqi", "label": "CPCB AQI", "tone": "primary"},
                          {"key": "pm25", "label": "PM2.5 ug/m3", "tone": "muted"}]}})
        comps = air.get("components") or {}
        if comps:
            renders.append({"type": "stat_grid", "title": "Pollutant concentrations", "data": {"stats": [
                {"label": "PM2.5", "value": comps.get("pm2_5"), "unit": "ug/m3"},
                {"label": "PM10", "value": comps.get("pm10"), "unit": "ug/m3"},
                {"label": "NO2", "value": comps.get("no2"), "unit": "ug/m3"},
                {"label": "SO2", "value": comps.get("so2"), "unit": "ug/m3"},
                {"label": "Ozone", "value": comps.get("o3"), "unit": "ug/m3"},
                {"label": "CO", "value": comps.get("co"), "unit": "ug/m3"}]}})

    elif module == "commute":
        items = []
        for entry_key, kind in [("metro_distance", "Metro"), ("rail_distance", "Railway")]:
            for place in det(entry_key)[:3]:
                items.append({"name": place["name"], "distance_m": place["distance_m"],
                              "walk_min": _walk_min(place["distance_m"]), "kind": kind})
        renders.append({"type": "distance_list", "title": "Transit access", "data": {
            "items": items, "empty_message": "No metro or rail station mapped within 6 km."}})
        renders.append({"type": "stat_grid", "title": "Connectivity", "data": {"stats": [
            {"label": "Bus stops within 1.2 km", "value": val("bus_stops", 0)},
            {"label": "Nearest metro", "value": val("metro_distance"), "unit": "m"},
            {"label": "Major roads within 600 m", "value": val("major_roads", 0)}]}})

    elif module in ("safety_day", "safety_night"):
        renders.append({"type": "stat_grid", "title": "Signals", "data": {
            "stats": [{"label": d["label"], "value": d["value"]} for d in drivers]}})
        incidents = det("media_incidents")
        if module == "safety_day":
            renders.append({"type": "incident_list", "title": "Media-reported incidents", "data": {
                "caption": "These are incidents reported in news media over roughly the last 12 months. "
                           "They are NOT official crime statistics, they under-represent unreported "
                           "crime, and localities with heavier press coverage will show more incidents.",
                "items": incidents[:8],
                "empty_message": "No media-reported incidents surfaced for this locality in the search window."}})
            sentiment = det("resident_sentiment")
            if sentiment:
                renders.append({"type": "quote_list", "title": "Resident chatter (unverified)", "data": {
                    "caption": "Forum and social content. Shown for context only - it never moves a score.",
                    "items": sentiment}})

    elif module == "schools":
        items = [{"name": p["name"], "distance_m": p["distance_m"], "walk_min": _walk_min(p["distance_m"]),
                  "kind": "School"} for p in det("count_school")[:5]]
        items += [{"name": p["name"], "distance_m": p["distance_m"], "walk_min": _walk_min(p["distance_m"]),
                   "kind": "Preschool"} for p in det("count_preschool")[:3]]
        renders.append({"type": "distance_list", "title": "Nearby schools", "data": {
            "items": items, "empty_message": "No named schools mapped nearby in OpenStreetMap."}})
        renders.append({"type": "stat_grid", "title": "Inventory", "data": {
            "stats": [{"label": d["label"], "value": d["value"]} for d in drivers]}})
        rep = det("place_reputation")
        if rep:
            renders.append({"type": "quote_list", "title": "Published reputation signals", "data": {
                "caption": "Sourced mentions. LocalIQ does not invent school rankings.",
                "items": [{"quote": r.get("note"), "source_name": r.get("place"),
                           "source_url": r.get("source_url"), "tone": "mixed"} for r in rep]}})

    elif module == "healthcare":
        items = [{"name": p["name"], "distance_m": p["distance_m"], "walk_min": _walk_min(p["distance_m"]),
                  "kind": "Hospital"} for p in det("count_hospital")[:4]]
        items += [{"name": p["name"], "distance_m": p["distance_m"], "walk_min": _walk_min(p["distance_m"]),
                   "kind": "Clinic"} for p in det("count_clinic")[:3]]
        renders.append({"type": "distance_list", "title": "Nearby care", "data": {
            "items": items, "empty_message": "No named healthcare facility mapped nearby."}})
        renders.append({"type": "stat_grid", "title": "Access", "data": {
            "stats": [{"label": d["label"], "value": d["value"]} for d in drivers]}})

    elif module == "infrastructure":
        projects = det("infra_projects")
        renders.append({"type": "timeline", "title": "Projects in the pipeline", "data": {
            "events": [{"date": p.get("expected_year") or "TBD", "title": p.get("name"),
                        "status": p.get("status"), "kind": p.get("type"),
                        "description": p.get("description"), "impact": p.get("impact"),
                        "source_url": p.get("source_url"), "source_name": p.get("source_name")}
                       for p in projects],
            "empty_message": "No sourced infrastructure project found for this locality."}})

    elif module in ("water", "power"):
        key = "water_supply" if module == "water" else "power_outages"
        item = F.get(key)
        if item:
            renders.append({"type": "text_block", "title": "What sources report", "data": {
                "body": f"{item.get('value')}. {item.get('note') or ''}".strip()}})
            reports = item.get("detail") or []
            if reports:
                renders.append({"type": "timeline", "title": "Reports", "data": {"events": [
                    {"date": r.get("date") or "undated", "title": r.get("claim"),
                     "source_url": r.get("source_url"), "source_name": r.get("source_name"),
                     "status": "reported"} for r in reports]}})
        community = F.get(f"community_{'water_hours' if module == 'water' else 'power_cuts'}")
        if community:
            renders.append({"type": "quote_list", "title": "Community reports", "data": {
                "caption": community.get("note"),
                "items": [{"quote": c.get("body"), "source_name": f"{c.get('upvotes', 0)} upvotes",
                           "source_url": c.get("proof_url"), "tone": "mixed"}
                          for c in (community.get("detail") or [])]}})

    elif module == "cost":
        bands = det("rent_bands")
        renders.append({"type": "stat_grid", "title": "Reported rent bands", "data": {"stats": [
            {"label": b.get("config", "Unit"), "value": b.get("range_inr"), "unit": "INR/mo"} for b in bands]}})

    elif module == "investment":
        renders.append({"type": "stat_grid", "title": "Trajectory inputs", "data": {
            "stats": [{"label": d["label"], "value": d["value"]} for d in drivers]}})

    else:
        renders.append({"type": "stat_grid", "title": "Signals", "data": {
            "stats": [{"label": d["label"], "value": d["value"]} for d in drivers]}})
        top_key = {"nightlife": "count_cafe", "food": "count_restaurant", "parks": "count_park",
                   "daily_needs": "count_supermarket", "fitness": "count_gym",
                   "worship": "count_worship", "pet_friendly": "count_vet",
                   "internet_wfh": "count_coworking"}.get(module)
        if top_key and det(top_key):
            renders.append({"type": "distance_list", "title": "Closest to you", "data": {
                "items": [{"name": p["name"], "distance_m": p["distance_m"],
                           "walk_min": _walk_min(p["distance_m"]), "kind": MODULES[module]["label"]}
                          for p in det(top_key)[:5]], "empty_message": "Nothing named mapped nearby."}})

    return renders


def present(locality: dict, persona: dict, module_scores: dict, selected: list, facts: list,
            F: dict, raw: dict, domains: dict, weights: dict, narrative: dict,
            city_stats: dict) -> list:
    from ..services.citystats import percentile_of

    cards = []
    for module in selected:
        entry = module_scores.get(module)
        if not entry:
            continue
        domain = MODULE_DOMAIN.get(module, "geo")
        citations = _citations(module, facts)
        if module == "safety_night" and not citations:
            citations = _citations("safety_day", facts)
        if module == "investment" and not citations:
            # derived module: it is scored from the infrastructure and commute inputs,
            # so it must carry their sources rather than none at all
            citations = _citations("infrastructure", facts) + _citations("commute", facts)
        card = {
            "id": module,
            "module": module,
            "title": MODULES[module]["label"],
            "icon": MODULES[module]["icon"],
            "tier": MODULES[module]["tier"],
            "weight": weights.get(module, 0),
            "score": entry.get("score"),
            "confidence": entry.get("confidence"),
            "data_state": entry.get("data_state"),
            "reason": entry.get("reason"),
            "freshness": domain_age_label(domains, domain),
            "city": percentile_of(city_stats or {}, module, entry.get("score")),
            "renders": build_renders(module, entry, F, raw),
            "citations": citations,
            "narrative": (narrative.get("modules") or {}).get(module),
            "contribute": CONTRIBUTION_PROMPT.get(module) if entry.get("score") is None
                          or entry.get("data_state") == "thin" else None,
        }
        if entry.get("score") is None:
            card["empty"] = {
                "message": entry.get("reason"),
                "missing": (CONTRIBUTION_PROMPT.get(module) or {}).get("missing", []),
                "cta_label": (CONTRIBUTION_PROMPT.get(module) or {}).get("cta",
                                                                         "Be the first to report this"),
            }
        cards.append(card)
    return cards
