"""OpenWeather Air Pollution -> Indian CPCB AQI."""
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..config import settings
from ..rubric import cpcb_band

BASE = "http://api.openweathermap.org/data/2.5/air_pollution"

# CPCB breakpoints: pollutant -> [(c_lo, c_hi, i_lo, i_hi)]
BREAKPOINTS = {
    "pm2_5": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200), (90, 120, 201, 300), (120, 250, 301, 400), (250, 1000, 401, 500)],
    "pm10":  [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200), (250, 350, 201, 300), (350, 430, 301, 400), (430, 1000, 401, 500)],
    "no2":   [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200), (180, 280, 201, 300), (280, 400, 301, 400), (400, 1000, 401, 500)],
    "so2":   [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200), (380, 800, 201, 300), (800, 1600, 301, 400), (1600, 3000, 401, 500)],
    "co":    [(0, 1000, 0, 50), (1000, 2000, 51, 100), (2000, 10000, 101, 200), (10000, 17000, 201, 300), (17000, 34000, 301, 400), (34000, 60000, 401, 500)],
    "o3":    [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200), (168, 208, 201, 300), (208, 748, 301, 400), (748, 1500, 401, 500)],
}

POLLUTANT_LABELS = {"pm2_5": "PM2.5", "pm10": "PM10", "no2": "NO\u2082", "so2": "SO\u2082", "co": "CO", "o3": "O\u2083"}


def sub_index(pollutant: str, value: float) -> Optional[float]:
    table = BREAKPOINTS.get(pollutant)
    if table is None or value is None:
        return None
    for c_lo, c_hi, i_lo, i_hi in table:
        if c_lo <= value <= c_hi:
            return round(i_lo + (i_hi - i_lo) * (value - c_lo) / (c_hi - c_lo))
    return 500.0


def cpcb_aqi(components: dict) -> dict:
    subs = {}
    for pollutant in BREAKPOINTS:
        val = components.get(pollutant)
        if val is None:
            continue
        idx = sub_index(pollutant, val)
        if idx is not None:
            subs[pollutant] = idx
    if not subs:
        return {"aqi": None, "dominant": None, "sub_indices": {}}
    dominant = max(subs, key=lambda p: subs[p])
    return {"aqi": subs[dominant], "dominant": dominant, "sub_indices": subs}


async def fetch_air(lat: float, lon: float) -> dict:
    params = {"lat": lat, "lon": lon, "appid": settings.openweather_key}
    async with httpx.AsyncClient(timeout=20) as client:
        current = await client.get(BASE, params=params)
        current.raise_for_status()
        forecast = await client.get(f"{BASE}/forecast", params=params)
        forecast.raise_for_status()

    cur = current.json()["list"][0]
    computed = cpcb_aqi(cur["components"])
    band = cpcb_band(computed["aqi"]) if computed["aqi"] is not None else {"band": "Unknown", "tone": "neutral"}

    series, daily = [], {}
    for entry in forecast.json()["list"]:
        stamp = datetime.fromtimestamp(entry["dt"], tz=timezone.utc)
        aqi = cpcb_aqi(entry["components"])["aqi"]
        if aqi is None:
            continue
        series.append({
            "t": stamp.isoformat(),
            "label": stamp.strftime("%d %b %H:%M"),
            "aqi": aqi,
            "pm2_5": round(entry["components"].get("pm2_5", 0), 1),
            "pm10": round(entry["components"].get("pm10", 0), 1),
        })
        key = stamp.strftime("%d %b")
        daily.setdefault(key, []).append(aqi)

    return {
        "observed_at": datetime.fromtimestamp(cur["dt"], tz=timezone.utc).isoformat(),
        "components": {k: round(v, 2) for k, v in cur["components"].items()},
        "cpcb_aqi": computed["aqi"],
        "dominant": computed["dominant"],
        "dominant_label": POLLUTANT_LABELS.get(computed["dominant"], computed["dominant"]),
        "sub_indices": computed["sub_indices"],
        "band": band,
        "owm_index": cur["main"]["aqi"],
        "forecast": series[:96],
        "daily_avg": [{"label": k, "aqi": round(sum(v) / len(v))} for k, v in list(daily.items())[:5]],
    }
