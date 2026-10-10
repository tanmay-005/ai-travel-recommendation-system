"""Live places from OpenStreetMap (Overpass API)."""
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests as http_requests

from yatra import kinds



OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OSM_HEADERS = {"User-Agent": "yatra-travel-app/4.0"}


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