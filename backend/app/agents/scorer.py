"""Deterministic scorer. No LLM ever produces a score."""
import re
from typing import Optional

from ..rubric import D, K, aqi_to_score, distance_score, saturating


def blend(parts) -> tuple:
    """parts = [(score|None, weight)] -> (score|None, coverage 0-1)"""
    num = den = total = 0.0
    for score, weight in parts:
        total += weight
        if score is None:
            continue
        num += score * weight
        den += weight
    if den == 0:
        return None, 0.0
    return round(num / den, 1), round(den / total, 2) if total else 0.0


def clamp(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(max(0.0, min(100.0, value)), 1)


def _rupees(text: str) -> Optional[int]:
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]{3,}", str(text or ""))]
    nums = [n for n in nums if 3000 <= n <= 500000]
    if not nums:
        return None
    return int(sum(nums[:2]) / len(nums[:2]))


IMPACT_WEIGHT = {"high": 3, "medium": 2, "low": 1}
STATUS_WEIGHT = {"completed": 0.4, "under_construction": 1.0, "approved": 0.8,
                 "announced": 0.5, "stalled": 0.2}


def score_all(F: dict, raw: dict) -> dict:
    """F: fact key -> fact dict. raw: domain -> raw payload."""
    def v(key, default=None):
        item = F.get(key)
        return default if item is None or item.get("value") is None else item["value"]

    def d(key):
        item = F.get(key)
        return (item or {}).get("detail") or []

    out = {}

    def put(module, score, drivers, reason, state=None, extra=None):
        if score is None:
            state = state or "none"
            confidence = "none"
        else:
            state = state or "ok"
            confidence = {"ok": "high", "thin": "low"}.get(state, "medium")
        out[module] = {"module": module, "score": clamp(score), "confidence": confidence,
                       "data_state": state, "drivers": drivers, "reason": reason, **(extra or {})}

    geo_ok = bool(raw.get("geo"))

    # air ------------------------------------------------------------------
    air = raw.get("air") or {}
    aqi = air.get("cpcb_aqi")
    put("air_quality", aqi_to_score(aqi),
        [{"label": "CPCB AQI", "value": aqi}, {"label": "Dominant pollutant", "value": air.get("dominant_label")},
         {"label": "Band", "value": (air.get("band") or {}).get("band")}],
        f"AQI {aqi} ({(air.get('band') or {}).get('band', 'n/a')}) measured live and mapped onto the "
        f"CPCB band boundaries." if aqi is not None else "No live air measurement available.")

    # commute --------------------------------------------------------------
    metro_m = v("metro_distance")
    rail_m = v("rail_distance")
    buses = v("bus_stops", 0) if geo_ok else None
    c_score, c_cov = blend([
        (distance_score(metro_m, *D["metro"]), 0.55),
        (saturating(buses, K["bus"]) if buses is not None else None, 0.25),
        (distance_score(rail_m, *D["rail"]), 0.20),
    ])
    put("commute", c_score,
        [{"label": "Nearest metro", "value": f"{metro_m} m" if metro_m else "none within 6 km"},
         {"label": "Bus stops (1.2 km)", "value": buses},
         {"label": "Nearest rail", "value": f"{rail_m} m" if rail_m else "none within 6 km"}],
        "Weighted metro proximity, bus-stop density and suburban rail access.",
        state="thin" if c_cov < 0.6 else None)

    # safety ---------------------------------------------------------------
    incidents = v("media_incidents")
    police_detail = d("count_police")
    police_nearest = police_detail[0]["distance_m"] if police_detail else None
    if geo_ok or incidents is not None:
        base = 62.0
        police_bonus = (distance_score(police_nearest, *D["police"]) or 0) * 0.18
        incident_penalty = min(35.0, (incidents or 0) * 3.0)
        day = base + police_bonus - incident_penalty
        put("safety_day", day,
            [{"label": "Media-reported incidents (12m)",
              "value": incidents if incidents is not None else "no search data"},
             {"label": "Nearest police station", "value": f"{police_nearest} m" if police_nearest else "not mapped"},
             {"label": "Police stations within 2.5 km", "value": v("count_police", 0) if geo_ok else None}],
            "Baseline 62, plus police proximity, minus recency-weighted media-reported incidents. "
            "Media counts are coverage-biased and are not a crime rate.",
            state="thin" if incidents is None else None)
        activity = (v("count_cafe", 0) or 0) + (v("count_bar", 0) or 0)
        night = day - 8 + saturating(activity, K["nightlife"]) * 0.10 - (10 if (incidents or 0) > 6 else 0)
        put("safety_night", night,
            [{"label": "Late-activity venues nearby", "value": activity},
             {"label": "Day safety score", "value": clamp(day)},
             {"label": "Incidents in window", "value": incidents if incidents is not None else "unknown"}],
            "Day score adjusted for night-time street activity and incident volume.",
            state="thin" if incidents is None else None)
    else:
        put("safety_day", None, [], "No safety data collected.")
        put("safety_night", None, [], "No safety data collected.")

    if geo_ok:
        cafes, bars = v("count_cafe", 0), v("count_bar", 0)
        put("nightlife", saturating(cafes + bars, K["nightlife"]),
            [{"label": "Cafes (1.5 km)", "value": cafes}, {"label": "Bars & pubs (1.5 km)", "value": bars}],
            "Saturating density of cafes, bars and pubs within 1.5 km, calibrated against all 34 "
            "Bengaluru localities.")

        restaurants, cuisines = v("count_restaurant", 0), v("cuisine_variety", 0)
        f_score, _ = blend([(saturating(restaurants, K["restaurant"]), 0.7),
                            (saturating(cuisines, K["cuisine"]), 0.3)])
        put("food", f_score,
            [{"label": "Restaurants (1.5 km)", "value": restaurants},
             {"label": "Distinct cuisines tagged", "value": cuisines}],
            "Restaurant density plus cuisine variety.")

        schools, preschools = v("count_school", 0), v("count_preschool", 0)
        school_detail = d("count_school")
        nearest_school = school_detail[0]["distance_m"] if school_detail else None
        rep = v("place_reputation")
        s_score, s_cov = blend([
            (saturating(schools + preschools, K["schools"]), 0.5),
            (distance_score(nearest_school, *D["school"]), 0.3),
            (saturating(rep, 3) if rep else None, 0.2),
        ])
        put("schools", s_score,
            [{"label": "Schools (2.5 km)", "value": schools},
             {"label": "Preschools & daycare", "value": preschools},
             {"label": "Nearest school", "value": f"{nearest_school} m" if nearest_school else "not mapped"}],
            "Inventory and proximity from OpenStreetMap plus published reputation signals. "
            "This is not a school ranking - no ranking is invented.",
            state="thin" if s_cov < 0.7 else None)

        parks, playgrounds = v("count_park", 0), v("count_playground", 0)
        park_detail = d("count_park")
        nearest_park = park_detail[0]["distance_m"] if park_detail else None
        p_score, _ = blend([(saturating(parks + playgrounds, K["parks"]), 0.6),
                            (distance_score(nearest_park, *D["park"]), 0.4)])
        put("parks", p_score,
            [{"label": "Parks & gardens", "value": parks}, {"label": "Playgrounds", "value": playgrounds},
             {"label": "Nearest park", "value": f"{nearest_park} m" if nearest_park else "not mapped"}],
            "Green-space count and proximity. OSM does not reliably map park area, so area is not scored.")

        hospitals, clinics, pharmacies = v("count_hospital", 0), v("count_clinic", 0), v("count_pharmacy", 0)
        hosp_detail = d("count_hospital")
        nearest_hosp = hosp_detail[0]["distance_m"] if hosp_detail else None
        h_score, _ = blend([(distance_score(nearest_hosp, *D["hospital"]), 0.5),
                            (saturating(hospitals + clinics, K["healthcare"]), 0.3),
                            (saturating(pharmacies, K["pharmacy"]), 0.2)])
        put("healthcare", h_score,
            [{"label": "Hospitals (2.5 km)", "value": hospitals}, {"label": "Clinics", "value": clinics},
             {"label": "Nearest hospital", "value": f"{nearest_hosp} m" if nearest_hosp else "not mapped"}],
            "Emergency proximity dominates, then facility and pharmacy density.")

        daily = (v("count_supermarket", 0) + v("count_convenience", 0) + v("count_market", 0)
                 + v("count_atm", 0))
        put("daily_needs", saturating(daily, K["daily_needs"]),
            [{"label": "Supermarkets", "value": v("count_supermarket", 0)},
             {"label": "Grocers & bakeries", "value": v("count_convenience", 0)},
             {"label": "Markets", "value": v("count_market", 0)},
             {"label": "ATMs", "value": v("count_atm", 0)}],
            "Combined density of everyday retail and cash access.")

        put("fitness", saturating(v("count_gym", 0) + v("count_pool", 0), K["fitness"]),
            [{"label": "Gyms & sports centres", "value": v("count_gym", 0)},
             {"label": "Pools", "value": v("count_pool", 0)}],
            "Density of gyms, sports centres and pools within 2 km.")

        put("worship", saturating(v("count_worship", 0), K["worship"]),
            [{"label": "Places of worship (2 km)", "value": v("count_worship", 0)}],
            "Count of mapped places of worship within 2 km.")
    else:
        for module in ["nightlife", "food", "schools", "parks", "healthcare", "daily_needs",
                       "fitness", "worship"]:
            put(module, None, [], "OpenStreetMap collection failed for this locality.")

    # water ----------------------------------------------------------------
    water_fact = F.get("water_supply")
    community_water = F.get("community_water_hours") or F.get("community_water_quality")
    if water_fact or community_water:
        score = 100.0
        reports = (water_fact or {}).get("detail") or []
        score -= min(45, len(reports) * 15)
        tanker = ((water_fact or {}).get("note") or "").lower()
        if "high" in tanker:
            score -= 25
        elif "medium" in tanker:
            score -= 12
        if community_water and community_water.get("source_type") == "community_verified":
            polarity = community_water.get("polarity", "neutral")
            score += {"negative": -15, "positive": 6}.get(polarity, 0)
        put("water", score,
            [{"label": "Sourced disruption reports", "value": len(reports)},
             {"label": "Community claims", "value": (community_water or {}).get("source_name", "none")},
             {"label": "Community polarity", "value": (community_water or {}).get("polarity", "n/a")}],
            "Evidence-based: starts at 100, penalised per sourced disruption report. Corroborated "
            "community claims move it only in the direction they actually report.", state="thin")
    else:
        put("water", None, [], "No verified water-supply data yet for this locality.")

    # power ----------------------------------------------------------------
    power_fact = F.get("power_outages")
    community_power = F.get("community_power_cuts")
    if power_fact or community_power:
        score = 100.0
        reports = (power_fact or {}).get("detail") or []
        score -= min(30, len(reports) * 10)
        monthly = re.findall(r"\d+", (power_fact or {}).get("note") or "")
        if monthly:
            score -= min(45, int(monthly[0]) * 5)
        if community_power and community_power.get("source_type") == "community_verified":
            score += {"negative": -15, "positive": 6}.get(community_power.get("polarity", "neutral"), 0)
        put("power", score,
            [{"label": "Sourced outage notices", "value": len(reports)},
             {"label": "Community claims", "value": (community_power or {}).get("source_name", "none")},
             {"label": "Community polarity", "value": (community_power or {}).get("polarity", "n/a")}],
            "Evidence-based: starts at 100, penalised per sourced outage report.", state="thin")
    else:
        put("power", None, [], "No verified power-reliability data yet for this locality.")

    # noise ----------------------------------------------------------------
    if geo_ok:
        roads = v("major_roads", 0)
        noise_reports = v("noise_reports", 0) or 0
        rail_near = rail_m is not None and rail_m < 800
        score = 100 - min(40, roads * 1.8) - min(25, noise_reports * 8) - (10 if rail_near else 0)
        put("noise", score,
            [{"label": "Major road segments (600 m)", "value": roads},
             {"label": "Sourced noise reports", "value": noise_reports},
             {"label": "Railway within 800 m", "value": "yes" if rail_near else "no"}],
            "Proximity to trunk roads and railways plus reported construction and traffic noise.")
    else:
        put("noise", None, [], "No geodata for noise proxies.")

    # wfh ------------------------------------------------------------------
    w_score, w_cov = blend([
        (out["power"]["score"], 0.4), (out["noise"]["score"], 0.3),
        (saturating(v("count_coworking", 0), K["coworking"]) if geo_ok else None, 0.3),
    ])
    put("internet_wfh", w_score,
        [{"label": "Coworking spaces (3 km)", "value": v("count_coworking", 0) if geo_ok else None},
         {"label": "Power score", "value": out["power"]["score"]},
         {"label": "Noise score", "value": out["noise"]["score"]}],
        "Derived from power reliability, noise, and coworking fallback density.",
        state="thin" if w_cov < 0.7 else None)

    # pets -----------------------------------------------------------------
    pet_score, _ = blend([
        (out["parks"]["score"], 0.5),
        (saturating(v("count_vet", 0) + v("count_petshop", 0), K["pets"]) if geo_ok else None, 0.5)])
    put("pet_friendly", pet_score,
        [{"label": "Vets", "value": v("count_vet", 0) if geo_ok else None},
         {"label": "Pet shops", "value": v("count_petshop", 0) if geo_ok else None},
         {"label": "Parks score", "value": out["parks"]["score"]}],
        "Green space plus veterinary and pet-retail access.")

    # cost -----------------------------------------------------------------
    bands = d("rent_bands")
    mid = None
    for band in bands:
        amount = _rupees(band.get("range_inr"))
        if amount is None:
            continue
        config = (band.get("config") or "").upper().replace(" ", "")
        factor = 1.5 if "1BHK" in config else 0.7 if "3BHK" in config else 1.0
        mid = amount * factor
        break
    if mid:
        put("cost", clamp(100 - (mid - 15000) / 550),
            [{"label": "Normalised 2BHK-equivalent rent", "value": f"Rs {int(mid):,}/mo"}],
            "Affordability curve: Rs 15k/mo scores 100, Rs 70k/mo scores 0. Listing-derived, "
            "not transaction data.", state="thin")
    else:
        put("cost", None, [], "No sourced rent band found yet for this locality.")

    # infrastructure --------------------------------------------------------
    projects = d("infra_projects")
    if projects:
        weight = sum(IMPACT_WEIGHT.get((p.get("impact") or "low").lower(), 1) *
                     STATUS_WEIGHT.get((p.get("status") or "announced").lower(), 0.5)
                     for p in projects)
        put("infrastructure", saturating(weight, K["infra"]),
            [{"label": "Sourced projects", "value": len(projects)},
             {"label": "Impact-weighted pipeline", "value": round(weight, 1)}],
            "Impact-weighted and status-weighted sum of sourced projects in or bordering the locality.",
            state="thin")
    else:
        put("infrastructure", None, [], "No sourced infrastructure project found for this locality.")

    # investment ------------------------------------------------------------
    trend = str(v("price_trend") or "").lower()
    trend_score = {"rising": 85.0, "flat": 55.0, "falling": 25.0}.get(trend)
    inv_score, inv_cov = blend([(out["infrastructure"]["score"], 0.45),
                                (out["commute"]["score"], 0.35), (trend_score, 0.20)])
    put("investment", inv_score,
        [{"label": "Infrastructure pipeline", "value": out["infrastructure"]["score"]},
         {"label": "Connectivity", "value": out["commute"]["score"]},
         {"label": "Reported price trend", "value": trend or "unknown"}],
        "Trajectory proxy: infrastructure pipeline, connectivity and reported price direction.",
        state="thin" if inv_cov < 0.7 else None)

    return out
