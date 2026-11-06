"""OpenStreetMap / Overpass geodata. All distances are computed geometry,
never produced by a language model."""
import asyncio
import math
from typing import Optional

import httpx

from ..config import settings

CATEGORIES = {
    "cafe": {"amenity": ["cafe"]},
    "bar": {"amenity": ["bar", "pub", "nightclub"]},
    "restaurant": {"amenity": ["restaurant", "fast_food", "food_court"]},
    "hospital": {"amenity": ["hospital"]},
    "clinic": {"amenity": ["clinic", "doctors"]},
    "pharmacy": {"amenity": ["pharmacy"]},
    "school": {"amenity": ["school"]},
    "preschool": {"amenity": ["kindergarten", "childcare"]},
    "college": {"amenity": ["college", "university"]},
    "bank": {"amenity": ["bank"]},
    "atm": {"amenity": ["atm"]},
    "market": {"amenity": ["marketplace"]},
    "police": {"amenity": ["police"]},
    "fire_station": {"amenity": ["fire_station"]},
    "worship": {"amenity": ["place_of_worship"]},
    "vet": {"amenity": ["veterinary"]},
    "cinema": {"amenity": ["cinema"]},
    "library": {"amenity": ["library"]},
    "fuel": {"amenity": ["fuel"]},
    "supermarket": {"shop": ["supermarket", "department_store", "mall"]},
    "convenience": {"shop": ["convenience", "greengrocer", "bakery", "butcher"]},
    "petshop": {"shop": ["pet", "pet_grooming"]},
    "park": {"leisure": ["park", "garden", "nature_reserve"]},
    "playground": {"leisure": ["playground"]},
    "gym": {"leisure": ["fitness_centre", "sports_centre"]},
    "pool": {"leisure": ["swimming_pool"]},
    "coworking": {"office": ["coworking"], "amenity": ["coworking_space"]},
}

QUERY = """[out:json][timeout:60];
(
  nwr["amenity"~"^(cafe|bar|pub|nightclub|restaurant|fast_food|food_court|hospital|clinic|doctors|pharmacy|school|kindergarten|childcare|college|university|bank|atm|marketplace|police|fire_station|place_of_worship|veterinary|cinema|library|fuel|coworking_space)$"](around:2500,{lat},{lon});
  nwr["shop"~"^(supermarket|department_store|mall|convenience|greengrocer|bakery|butcher|pet|pet_grooming)$"](around:2000,{lat},{lon});
  nwr["leisure"~"^(park|garden|nature_reserve|playground|fitness_centre|sports_centre|swimming_pool)$"](around:2500,{lat},{lon});
  nwr["office"="coworking"](around:3000,{lat},{lon});
  nwr["railway"="station"](around:6000,{lat},{lon});
  node["highway"="bus_stop"](around:1200,{lat},{lon});
  way["highway"~"^(motorway|trunk|primary)$"](around:600,{lat},{lon});
);
out center 2500;"""


def haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def _coords(el: dict):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center") or {}
    if "lat" in center:
        return center["lat"], center["lon"]
    return None, None


def _classify(tags: dict) -> list:
    hits = []
    for cat, rules in CATEGORIES.items():
        for key, values in rules.items():
            if tags.get(key) in values:
                hits.append(cat)
                break
    return hits


async def _overpass(body: str) -> list:
    """Public Overpass instances are flaky (504s, read timeouts). Try every
    mirror twice before giving up."""
    endpoints = [u.strip() for u in settings.overpass_url.split(",") if u.strip()]
    last_error = "no endpoint configured"
    async with httpx.AsyncClient(timeout=httpx.Timeout(150.0, connect=15.0)) as client:
        for attempt in range(2):
            for endpoint in endpoints:
                try:
                    resp = await client.post(endpoint, data={"data": body},
                                             headers={"User-Agent": "LocalIQ/1.0 neighbourhood-reports"})
                    if resp.status_code != 200:
                        last_error = f"{endpoint} -> HTTP {resp.status_code}"
                        continue
                    return resp.json().get("elements", [])
                except Exception as exc:
                    last_error = f"{endpoint} -> {type(exc).__name__}"
                    continue
            await asyncio.sleep(3)
    raise RuntimeError(f"All Overpass mirrors failed ({last_error})")


async def fetch_geo(lat: float, lon: float) -> dict:
    elements = await _overpass(QUERY.format(lat=lat, lon=lon))

    buckets: dict = {cat: [] for cat in CATEGORIES}
    metro, rail, bus_stops, major_roads = [], [], 0, 0
    cuisines = set()

    for el in elements:
        tags = el.get("tags") or {}
        elat, elon = _coords(el)

        if tags.get("highway") in ("motorway", "trunk", "primary"):
            major_roads += 1
            continue
        if tags.get("highway") == "bus_stop":
            bus_stops += 1
            continue

        if elat is None:
            continue
        dist = haversine(lat, lon, elat, elon)
        name = tags.get("name") or tags.get("name:en") or "Unnamed"

        if tags.get("railway") == "station":
            entry = {"name": name, "distance_m": dist, "lat": elat, "lon": elon}
            is_metro = tags.get("station") == "subway" or "metro" in name.lower() or tags.get("network", "").lower().find("metro") >= 0
            (metro if is_metro else rail).append(entry)
            continue

        if tags.get("cuisine"):
            for c in tags["cuisine"].split(";"):
                cuisines.add(c.strip().lower())

        for cat in _classify(tags):
            buckets[cat].append({"name": name, "distance_m": dist, "lat": elat, "lon": elon})

    for lst in list(buckets.values()) + [metro, rail]:
        lst.sort(key=lambda x: x["distance_m"])

    def summarize(cat, radius):
        items = [i for i in buckets[cat] if i["distance_m"] <= radius]
        named = [i for i in items if i["name"] != "Unnamed"]
        return {
            "count": len(items),
            "nearest_m": items[0]["distance_m"] if items else None,
            "nearest_name": named[0]["name"] if named else None,
            "top": named[:6],
        }

    return {
        "counts": {
            "cafe": summarize("cafe", 1500), "bar": summarize("bar", 1500),
            "restaurant": summarize("restaurant", 1500), "hospital": summarize("hospital", 2500),
            "clinic": summarize("clinic", 2000), "pharmacy": summarize("pharmacy", 1500),
            "school": summarize("school", 2500), "preschool": summarize("preschool", 2500),
            "college": summarize("college", 2500), "bank": summarize("bank", 1500),
            "atm": summarize("atm", 1500), "market": summarize("market", 2000),
            "police": summarize("police", 2500), "fire_station": summarize("fire_station", 2500),
            "worship": summarize("worship", 2000), "vet": summarize("vet", 2500),
            "cinema": summarize("cinema", 2500), "library": summarize("library", 2500),
            "supermarket": summarize("supermarket", 2000), "convenience": summarize("convenience", 1500),
            "petshop": summarize("petshop", 2500), "park": summarize("park", 2500),
            "playground": summarize("playground", 2000), "gym": summarize("gym", 2000),
            "pool": summarize("pool", 2500), "coworking": summarize("coworking", 3000),
            "fuel": summarize("fuel", 2500),
        },
        "metro": {"count": len(metro), "nearest_m": metro[0]["distance_m"] if metro else None,
                  "nearest_name": metro[0]["name"] if metro else None, "top": metro[:4]},
        "rail": {"count": len(rail), "nearest_m": rail[0]["distance_m"] if rail else None,
                 "nearest_name": rail[0]["name"] if rail else None, "top": rail[:3]},
        "bus_stops_1200m": bus_stops,
        "major_road_segments_600m": major_roads,
        "cuisine_variety": len(cuisines),
        "cuisines": sorted(cuisines)[:14],
        "elements_scanned": len(elements),
    }


def distance_to(lat: float, lon: float, other_lat: float, other_lon: float) -> Optional[float]:
    if None in (lat, lon, other_lat, other_lon):
        return None
    return haversine(lat, lon, other_lat, other_lon)
