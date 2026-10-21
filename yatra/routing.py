"""Turn routing-service answers into one simple shape the map can draw.

No Flask and no network in here: each function takes the JSON a service sent back
and returns plain dicts, so the tests can feed in small hand-made answers.
"""

# TomTom rates each traffic incident 0-4 (magnitudeOfDelay). 4 is used for closures.
DELAY_LEVELS = {0: "unknown", 1: "minor", 2: "moderate", 3: "major", 4: "closed"}


def parse_tomtom(data):
    """TomTom Calculate Route answer -> list of routes, fastest first."""
    routes = []
    for r in data.get("routes", []):
        s = r.get("summary", {})
        points = [[round(p["latitude"], 6), round(p["longitude"], 6)]
                  for leg in r.get("legs", []) for p in leg.get("points", [])]
        jams = [{
            "start": sec["startPointIndex"],
            "end":   sec["endPointIndex"],
            "level": DELAY_LEVELS.get(sec.get("magnitudeOfDelay", 0), "unknown"),
            "kind":  sec.get("simpleCategory", "OTHER").lower(),       # jam, road_work, road_closure, other
            "delay_min": round(sec.get("delayInSeconds", 0) / 60),
        } for sec in r.get("sections", [])
          if sec.get("sectionType") == "TRAFFIC" and "startPointIndex" in sec and "endPointIndex" in sec]
        routes.append({
            "distance_km": round(s.get("lengthInMeters", 0) / 1000, 1),
            "minutes":     round(s.get("travelTimeInSeconds", 0) / 60),
            "delay_min":   round(s.get("trafficDelayInSeconds", 0) / 60),
            "points":      points,
            "jams":        jams,
        })
    return sorted(routes, key=lambda r: r["minutes"])


def parse_osrm(data):
    """OSRM answer (geometries=geojson) -> the same shape, without traffic."""
    routes = [{
        "distance_km": round(r.get("distance", 0) / 1000, 1),
        "minutes":     round(r.get("duration", 0) / 60),
        "delay_min":   None,                                           # OSRM knows nothing about traffic
        "points":      [[round(lat, 6), round(lon, 6)] for lon, lat in r["geometry"]["coordinates"]],
        "jams":        [],
    } for r in data.get("routes", [])]
    return sorted(routes, key=lambda r: r["minutes"])