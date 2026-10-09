"""Live places from OpenStreetMap (Overpass API)."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests as http_requests

from yatra import kinds
from yatra.data import ICONS
from yatra.geo import haversine


# OSM tags for every category (used in live fallback)
ALL_OSM_TAGS = {
    "Heritage" : [("tourism","attraction"),("historic","monument"),("historic","fort")],
    "Museum"   : [("tourism","museum")],
    "Temple"   : [("historic","temple"),("amenity","place_of_worship")],
    "Viewpoint": [("tourism","viewpoint")],
    "Beach"    : [("natural","beach")],
    "Nature"   : [("leisure","park"),("leisure","garden"),("natural","waterfall"),("natural","peak")],
    "Cafe"     : [("amenity","cafe"),("amenity","coffee_shop")],
    "Food"     : [("amenity","restaurant"),("amenity","fast_food"),("amenity","food_court")],
    "Shopping" : [("shop","mall"),("shop","supermarket"),("amenity","marketplace")],
}

# Categories that PRIMARILY come from live OSM (CSV coverage is poor)
LIVE_PRIMARY = {"Cafe", "Food", "Shopping"}
# Categories that use CSV first, live as fallback if CSV < 3 results
LIVE_FALLBACK = {"Heritage","Museum","Temple","Viewpoint","Beach","Nature"}

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OSM_HEADERS = {"User-Agent": "yatra-travel-app/4.0"}


# 7.  LIVE OVERPASS (all categories now supported)
def _valid_name(name):
    if not name or len(name.strip()) < 2: return False
    foreign = re.sub(r'[\x20-\x7E\u0900-\u097F\d\s\-\'\.(),&/]', '', name)
    return len(foreign) / max(len(name), 1) < 0.4

def _overpass_fetch(lat, lon, tags, radius_m):
    union = [f'  {t}["{k}"="{v}"](around:{radius_m},{lat},{lon});\n'
             for k, v in tags for t in ["node","way"]]
    query = f"[out:json][timeout:15];\n(\n{''.join(union)});\nout center tags;"
    for mirror in OVERPASS_MIRRORS:
        try:
            r = http_requests.post(mirror, data={"data": query},
                                   headers=OSM_HEADERS, timeout=18)
            if r.status_code in (429, 502, 503, 504): continue
            r.raise_for_status()
            return r.json().get("elements", [])
        except Exception:
            continue
    return []

def live_fetch(lat, lon, category, radius_m=3000, top_n=15):
    tags = ALL_OSM_TAGS.get(category, [])
    if not tags: return []
    elements = _overpass_fetch(lat, lon, tags, radius_m)
    results  = []
    for e in elements:
        t    = e.get("tags", {})
        name = t.get("name:en") or t.get("name") or t.get("brand")
        if not _valid_name(name): continue
        elat = e.get("lat") or e.get("center",{}).get("lat")
        elon = e.get("lon") or e.get("center",{}).get("lon")
        if not elat or not elon: continue
        dist = float(haversine(lat, lon, np.array([elat]), np.array([elon]))[0])
        results.append({
            "place": name.strip(), "city": t.get("addr:city","—"),
            "lat": round(float(elat),6), "lon": round(float(elon),6),
            "category": category, "icon": ICONS.get(category,"📍"),
            "important": 0,
            "distance": round(dist,2),
            "score": round(max(0, 1 - dist/(radius_m/1000)), 3),
            "source": "live",
            "opening_hours": t.get("opening_hours",""),
            "cuisine":  t.get("cuisine",""),
            "phone":    t.get("phone","") or t.get("contact:phone",""),
            "website":  t.get("website","") or t.get("contact:website",""),
            "address":  (t.get("addr:street","") + " " + t.get("addr:housenumber","")).strip(),
        })
    results.sort(key=lambda x: x["distance"])
    return results[:top_n]

# ── Live top-up for /api/discover ────────────────────────────────
LIVE_TIMEOUT_S = 8          # per server; the page waits at most about 2 x this
LIVE_MAX_KM    = 20         # live searches stay small so they answer quickly
LIVE_CACHE_S   = 6 * 3600   # reuse an answer for 6 hours
_live_cache    = {}         # (lat, lon, kind, radius) -> (time fetched, places)


def live_places(lat, lon, kind, radius_km):
    """One kind of place around a point, fetched live from OpenStreetMap.
    Uses the same rules as the offline build (yatra/kinds.py). Returns [] if the servers are busy."""
    radius_km = min(radius_km, LIVE_MAX_KM)
    key = (round(lat, 2), round(lon, 2), kind, round(radius_km))      # ~1 km grid
    hit = _live_cache.get(key)
    if hit and time.time() - hit[0] < LIVE_CACHE_S:
        return hit[1]

    query = kinds.build_query(kind, lat, lon, radius_km=radius_km, timeout=LIVE_TIMEOUT_S)
    for mirror in OVERPASS_MIRRORS[:2]:
        try:
            r = http_requests.post(mirror, data={"data": query},
                                   headers=OSM_HEADERS, timeout=LIVE_TIMEOUT_S + 2)
            if r.status_code != 200:
                continue
            elements = r.json().get("elements", [])
        except Exception:
            continue
        places = [p for e in elements if (p := kinds.element_to_place(e, kind))]
        _live_cache[key] = (time.time(), places)
        return places
    return []          # not cached, so the next search tries again


def live_top_up(lat, lon, wanted_kinds, radius_km):
    """Fetch several kinds at once (in parallel threads) and return one DataFrame."""
    with ThreadPoolExecutor(max_workers=3) as ex:
        parts = ex.map(lambda k: live_places(lat, lon, k, radius_km), wanted_kinds)
    places = pd.DataFrame([p for part in parts for p in part])
    if not places.empty:
        places["source"] = "live"
        places["category_clean"] = places["category"]
    return places