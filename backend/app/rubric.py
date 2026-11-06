"""Published, deterministic scoring rubric + persona weighting.

Every module score is computed by pure arithmetic from verified facts.
No LLM ever produces a score. Missing data widens the confidence band; it
never silently becomes an average.
"""
import math
from typing import Optional

MODULES = {
    "air_quality":    {"label": "Air Quality",              "icon": "wind",        "tier": "Live API"},
    "commute":        {"label": "Commute & Connectivity",   "icon": "train-front", "tier": "Computed"},
    "safety_day":     {"label": "Safety (Day)",             "icon": "shield",      "tier": "Mixed"},
    "safety_night":   {"label": "Safety (Late Night)",      "icon": "moon",        "tier": "Mixed"},
    "nightlife":      {"label": "Nightlife & Cafes",        "icon": "beer",        "tier": "Computed"},
    "food":           {"label": "Restaurants & Food",       "icon": "utensils",    "tier": "Computed"},
    "schools":        {"label": "Schools & Childcare",      "icon": "graduation-cap", "tier": "Mixed"},
    "parks":          {"label": "Parks & Green Cover",      "icon": "trees",       "tier": "Computed"},
    "healthcare":     {"label": "Healthcare Access",        "icon": "cross",       "tier": "Computed"},
    "daily_needs":    {"label": "Daily Needs",              "icon": "shopping-basket", "tier": "Computed"},
    "fitness":        {"label": "Fitness & Sports",         "icon": "dumbbell",    "tier": "Computed"},
    "worship":        {"label": "Places of Worship",        "icon": "landmark",    "tier": "Computed"},
    "water":          {"label": "Water Reliability",        "icon": "droplets",    "tier": "Reported"},
    "power":          {"label": "Power Reliability",        "icon": "zap",         "tier": "Reported"},
    "noise":          {"label": "Noise & Construction",     "icon": "volume-2",    "tier": "Mixed"},
    "internet_wfh":   {"label": "Work-From-Home Fit",       "icon": "wifi",        "tier": "Mixed"},
    "pet_friendly":   {"label": "Pet Friendliness",         "icon": "paw-print",   "tier": "Computed"},
    "cost":           {"label": "Rent & Cost Band",         "icon": "indian-rupee","tier": "Reported"},
    "infrastructure": {"label": "Future Infrastructure",    "icon": "hard-hat",    "tier": "Reported"},
    "investment":     {"label": "Investment Signals",       "icon": "trending-up", "tier": "Reported"},
}

PERSONAS = {
    "bachelor": {
        "label": "Bachelor / Young professional",
        "summary": "Rent-sensitive, social, mobile. Cares about late-night safety, food and commute; ignores schools.",
        "weights": {"nightlife": 3, "food": 3, "commute": 3, "safety_night": 3, "cost": 3, "fitness": 2,
                    "internet_wfh": 2, "daily_needs": 2, "air_quality": 2, "water": 2, "power": 2,
                    "safety_day": 1, "healthcare": 1, "parks": 1, "pet_friendly": 1, "noise": 1,
                    "infrastructure": 1, "schools": 0, "worship": 0, "investment": 0},
    },
    "student": {
        "label": "Student",
        "summary": "Maximum price sensitivity, needs transit and cheap food density, low tolerance for isolation.",
        "weights": {"cost": 3, "commute": 3, "food": 3, "daily_needs": 3, "safety_night": 2, "internet_wfh": 2,
                    "nightlife": 2, "water": 2, "power": 2, "fitness": 1, "air_quality": 1, "healthcare": 1,
                    "parks": 1, "noise": 1, "safety_day": 1, "schools": 0, "worship": 0,
                    "pet_friendly": 0, "infrastructure": 0, "investment": 0},
    },
    "family_kids": {
        "label": "Family with young kids",
        "summary": "Schools, clean air, daytime safety and healthcare dominate. Nightlife is close to irrelevant.",
        "weights": {"schools": 3, "safety_day": 3, "healthcare": 3, "parks": 3, "air_quality": 3,
                    "daily_needs": 3, "water": 3, "power": 2, "noise": 2, "commute": 2, "cost": 2,
                    "safety_night": 2, "food": 1, "fitness": 1, "worship": 1, "infrastructure": 1,
                    "pet_friendly": 1, "internet_wfh": 1, "nightlife": 0, "investment": 0},
    },
    "elderly": {
        "label": "Living with elderly parents",
        "summary": "Healthcare proximity, quiet, clean air and utility reliability outweigh everything else.",
        "weights": {"healthcare": 3, "safety_day": 3, "air_quality": 3, "parks": 3, "daily_needs": 3,
                    "noise": 3, "water": 3, "power": 3, "worship": 2, "commute": 2, "cost": 2,
                    "safety_night": 2, "food": 1, "infrastructure": 1, "schools": 0, "nightlife": 0,
                    "fitness": 1, "pet_friendly": 0, "internet_wfh": 0, "investment": 0},
    },
    "wfh_pro": {
        "label": "Work-from-home professional",
        "summary": "Home is the office: power, noise, air and connectivity reliability are the whole game.",
        "weights": {"internet_wfh": 3, "power": 3, "noise": 3, "air_quality": 3, "water": 3, "food": 2,
                    "fitness": 2, "daily_needs": 2, "parks": 2, "safety_day": 2, "cost": 2, "healthcare": 2,
                    "commute": 1, "pet_friendly": 1, "safety_night": 1, "nightlife": 1, "infrastructure": 1,
                    "schools": 0, "worship": 0, "investment": 0},
    },
    "investor": {
        "label": "Investor / ROI",
        "summary": "Buys the trajectory, not the present. Infrastructure pipeline and connectivity drive the score.",
        "weights": {"infrastructure": 3, "investment": 3, "commute": 3, "cost": 3, "schools": 2,
                    "healthcare": 2, "daily_needs": 2, "safety_day": 2, "water": 2, "power": 2,
                    "air_quality": 1, "parks": 1, "food": 1, "noise": 1, "internet_wfh": 1,
                    "nightlife": 0, "worship": 0, "fitness": 0, "pet_friendly": 0, "safety_night": 1},
    },
}

BASELINE_WEIGHTS = {m: 1 for m in MODULES}

ALWAYS_INCLUDE = ["air_quality", "safety_day", "commute", "infrastructure"]

FRESHNESS_POLICY = {
    "air": {"hours": 6, "label": "6 hours"},
    "geo": {"hours": 24 * 30, "label": "30 days"},
    "safety": {"hours": 24 * 7, "label": "7 days"},
    "civic": {"hours": 24 * 14, "label": "14 days"},
    "infra": {"hours": 24 * 60, "label": "60 days"},
    "chatter": {"hours": 24 * 7, "label": "7 days"},
    "community": {"hours": 0, "label": "always live"},
}

SOURCE_TYPES = {
    "live_api": {"label": "Live API", "trust": 5},
    "computed": {"label": "Computed (OpenStreetMap)", "trust": 5},
    "official": {"label": "Official / Government", "trust": 4},
    "media": {"label": "News / Media", "trust": 3},
    "community_verified": {"label": "Community-verified", "trust": 3},
    "community_unverified": {"label": "Community-unverified", "trust": 1},
    "forum": {"label": "Forum / Unverified", "trust": 1},
}


def saturating(n: float, k: float) -> float:
    """0-100 with diminishing returns. k = count that reaches ~63."""
    if n <= 0:
        return 0.0
    return round(100 * (1 - math.exp(-n / k)), 1)


def distance_score(metres: Optional[float], good: float, bad: float) -> Optional[float]:
    if metres is None:
        return None
    if metres <= good:
        return 100.0
    if metres >= bad:
        return 0.0
    return round(100 * (bad - metres) / (bad - good), 1)


def cpcb_band(aqi: float) -> dict:
    for lo, hi, label, tone in [
        (0, 50, "Good", "positive"), (51, 100, "Satisfactory", "positive"),
        (101, 200, "Moderate", "warning"), (201, 300, "Poor", "warning"),
        (301, 400, "Very Poor", "negative"), (401, 10000, "Severe", "negative"),
    ]:
        if lo <= aqi <= hi:
            return {"band": label, "tone": tone, "low": lo, "high": min(hi, 500)}
    return {"band": "Unknown", "tone": "neutral", "low": 0, "high": 0}


def aqi_to_score(aqi: Optional[float]) -> Optional[float]:
    """Piecewise, anchored to the CPCB band boundaries so a score always means
    the same thing as the band it sits in."""
    if aqi is None:
        return None
    bands = [(0, 50, 100, 85), (51, 100, 85, 70), (101, 200, 70, 45),
             (201, 300, 45, 25), (301, 400, 25, 10), (401, 500, 10, 0)]
    for lo, hi, s_hi, s_lo in bands:
        if lo <= aqi <= hi:
            return round(s_hi - (s_hi - s_lo) * (aqi - lo) / (hi - lo), 1)
    return 0.0


# Saturation constants, calibrated against the measured distribution across all
# 34 Bengaluru localities so the median locality lands near 55 and the spread
# uses the full 0-100 range. k = median_count / 0.8.
K = {
    "nightlife": 25, "restaurant": 110, "cuisine": 40, "schools": 70, "parks": 110,
    "healthcare": 85, "pharmacy": 20, "daily_needs": 80, "fitness": 50, "worship": 60,
    "pets": 5, "coworking": 8, "bus": 35, "infra": 5,
}

# Distance bands (metres): score 100 at or below `good`, 0 at or above `bad`.
D = {
    "metro": (800, 4000), "rail": (1500, 6000), "police": (800, 4000),
    "school": (250, 1500), "park": (200, 1200), "hospital": (500, 3000),
}


from .rubric_doc import RUBRIC_DOC  # noqa: E402,F401


def select_modules(persona_key: str, overrides: Optional[dict] = None) -> list:
    weights = dict(PERSONAS.get(persona_key, PERSONAS["bachelor"])["weights"])
    overrides = overrides or {}
    for module, weight in (overrides.get("weights") or {}).items():
        if module in MODULES:
            weights[module] = int(weight)
    dropped = set(overrides.get("dropped") or [])
    added = set(overrides.get("added") or [])
    selected = [m for m, w in weights.items() if w >= 2 or m in ALWAYS_INCLUDE]
    selected = [m for m in selected if m not in dropped]
    for m in added:
        if m in MODULES and m not in selected:
            selected.append(m)
    return sorted(set(selected), key=lambda m: (-weights.get(m, 0), m))


def composite(module_scores: dict, weights: dict) -> dict:
    num = den = 0.0
    covered = 0
    for module, entry in module_scores.items():
        score = entry.get("score")
        weight = weights.get(module, 0)
        if score is None or weight == 0:
            continue
        num += score * weight
        den += weight
        covered += 1
    if den == 0:
        return {"score": None, "confidence": "none", "modules_scored": 0}
    total_weight = sum(w for m, w in weights.items() if w > 0)
    coverage = den / total_weight if total_weight else 0
    confidence = "high" if coverage >= 0.8 else "medium" if coverage >= 0.55 else "low"
    return {
        "score": round(num / den),
        "confidence": confidence,
        "coverage": round(coverage * 100),
        "modules_scored": covered,
    }
