"""Turn a destination name ("Hampi") into coordinates, via OpenStreetMap's Nominatim."""
import threading
import time

import requests
from flask import Blueprint, jsonify, request

bp = Blueprint("geocode", __name__, url_prefix="/api")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy asks every app to identify itself and to send at most 1 request per second.
HEADERS       = {"User-Agent": "yatra-go/1.0 (+https://github.com/tanmay-005/ai-travel-recommendation-system)"}
MIN_GAP_S     = 1.0
TIMEOUT_S     = 8
CACHE_MAX     = 500

_cache     = {}                 # "hampi" -> {"name": ..., "lat": ..., "lon": ...}
_lock      = threading.Lock()   # one Nominatim request at a time, across all users
_last_call = 0.0


def lookup(query):
    """Ask Nominatim for the best match in India. Returns a dict, None if nothing matches.
    Raises requests.RequestException if Nominatim can't be reached."""
    global _last_call
    with _lock:
        wait = MIN_GAP_S - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        r = requests.get(NOMINATIM_URL, headers=HEADERS, timeout=TIMEOUT_S, params={
            "q": query, "format": "json", "limit": 1, "countrycodes": "in",
        })
    r.raise_for_status()
    results = r.json()
    if not results:
        return None
    best = results[0]
    return {
        "name":         best.get("name") or best["display_name"].split(",")[0],
        "display_name": best["display_name"],
        "lat":          round(float(best["lat"]), 6),
        "lon":          round(float(best["lon"]), 6),
    }


@bp.route("/geocode")
def api_geocode():
    """/api/geocode?q=Hampi -> {"name": "Hampi", "lat": 15.33, "lon": 76.46, ...}"""
    query = request.args.get("q", "").strip()
    if not 2 <= len(query) <= 100:
        return jsonify({"error": "Type a place name (2-100 characters)."}), 400

    key = " ".join(query.lower().split())          # "  Hampi " and "hampi" share one entry
    if key in _cache:
        return jsonify({**_cache[key], "cached": True})

    try:
        place = lookup(query)
    except requests.RequestException:
        return jsonify({"error": "Place search is unavailable right now. Try again in a minute."}), 503
    if place is None:
        return jsonify({"error": f"No place called '{query}' found in India."}), 404

    if len(_cache) >= CACHE_MAX:                    # keep memory bounded: drop the oldest entry
        _cache.pop(next(iter(_cache)))
    _cache[key] = place
    return jsonify({**place, "cached": False})