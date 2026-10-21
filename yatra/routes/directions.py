"""Driving routes between two points: live traffic and alternatives from TomTom,
or plain alternatives from OSRM when there's no TomTom key or TomTom fails."""
import time

import requests
from flask import Blueprint, current_app, jsonify, request

from yatra.geo import haversine
from yatra.routing import parse_osrm, parse_tomtom

bp = Blueprint("directions", __name__, url_prefix="/api")

TOMTOM_URL = "https://api.tomtom.com/routing/1/calculateRoute/{a}:{b}/json"
OSRM_URL   = "https://routing.openstreetmap.de/routed-car/route/v1/driving/{a};{b}"
TIMEOUT_S  = 8
MAX_KM     = 500            # straight-line limit, so one click can't burn a long, slow request
CACHE_S    = 5 * 60         # traffic changes, so answers are only reused for 5 minutes
_cache     = {}             # (from, to) rounded to ~100 m -> (time saved, answer)


def tomtom_routes(lat1, lon1, lat2, lon2, key):
    r = requests.get(TOMTOM_URL.format(a=f"{lat1},{lon1}", b=f"{lat2},{lon2}"), timeout=TIMEOUT_S, params={
        "key": key, "traffic": "true", "maxAlternatives": 2, "routeType": "fastest",
        "travelMode": "car", "sectionType": "traffic",
    })
    r.raise_for_status()
    return parse_tomtom(r.json())


def osrm_routes(lat1, lon1, lat2, lon2):
    r = requests.get(OSRM_URL.format(a=f"{lon1},{lat1}", b=f"{lon2},{lat2}"), timeout=TIMEOUT_S, params={
        "alternatives": "true", "overview": "full", "geometries": "geojson",
    })
    r.raise_for_status()
    return parse_osrm(r.json())


def point(text):
    """'15.335,76.46' -> (15.335, 76.46), or None if it isn't a valid point."""
    try:
        lat, lon = (float(x) for x in str(text).split(","))
    except ValueError:
        return None
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


@bp.route("/route")
def api_route():
    """/api/route?from=15.335,76.46&to=15.27,76.39 -> up to 3 routes, fastest first."""
    a, b = point(request.args.get("from")), point(request.args.get("to"))
    if not a or not b:
        return jsonify({"error": "from and to must look like lat,lon"}), 400
    if float(haversine(a[0], a[1], [b[0]], [b[1]])[0]) > MAX_KM:
        return jsonify({"error": f"Directions are limited to {MAX_KM} km."}), 400

    key = (round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_S:
        return jsonify({**hit[1], "cached": True})

    answer = None
    tomtom_key = current_app.config.get("TOMTOM_API_KEY")
    if tomtom_key:
        try:
            answer = {"provider": "tomtom", "traffic": True, "routes": tomtom_routes(*a, *b, tomtom_key)}
        except (requests.RequestException, ValueError, KeyError):
            answer = None                                    # quota used up, network trouble: fall back
    if not answer or not answer["routes"]:
        try:
            answer = {"provider": "osrm", "traffic": False, "routes": osrm_routes(*a, *b)}
        except (requests.RequestException, ValueError, KeyError):
            return jsonify({"error": "Directions are unavailable right now. Try again in a minute."}), 503
    if not answer["routes"]:
        return jsonify({"error": "No road route found between these points."}), 404

    _cache[key] = (time.time(), answer)
    return jsonify({**answer, "cached": False})