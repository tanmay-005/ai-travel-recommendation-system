"""Directions: reading TomTom/OSRM answers, and /api/route choosing between them."""
import pytest
import requests

from yatra.routes import directions
from yatra.routing import parse_osrm, parse_tomtom

# A trimmed-down TomTom answer: two routes, the slower one listed first, one traffic jam.
TOMTOM = {"routes": [
    {"summary": {"lengthInMeters": 15540, "travelTimeInSeconds": 1491, "trafficDelayInSeconds": 0},
     "legs": [{"points": [{"latitude": 15.335, "longitude": 76.46}, {"latitude": 15.30, "longitude": 76.42},
                          {"latitude": 15.2689, "longitude": 76.3909}]}],
     "sections": []},
    {"summary": {"lengthInMeters": 12527, "travelTimeInSeconds": 1301, "trafficDelayInSeconds": 420},
     "legs": [{"points": [{"latitude": 15.335, "longitude": 76.46}, {"latitude": 15.31, "longitude": 76.43},
                          {"latitude": 15.29, "longitude": 76.41}, {"latitude": 15.2689, "longitude": 76.3909}]}],
     "sections": [
         {"startPointIndex": 0, "endPointIndex": 3, "sectionType": "TRAVEL_MODE", "travelMode": "car"},
         {"startPointIndex": 1, "endPointIndex": 2, "sectionType": "TRAFFIC", "simpleCategory": "JAM",
          "magnitudeOfDelay": 3, "delayInSeconds": 400}]},
]}

OSRM = {"code": "Ok", "routes": [
    {"distance": 13027, "duration": 1645, "geometry": {"coordinates": [[76.46, 15.335], [76.3909, 15.2689]]}},
]}

FROM, TO = "15.335,76.46", "15.2689,76.3909"


@pytest.fixture(autouse=True)
def empty_cache():
    directions._cache.clear()


# ── reading the answers ────────────────────────────────────────────
def test_tomtom_routes_are_sorted_fastest_first():
    routes = parse_tomtom(TOMTOM)
    assert [r["minutes"] for r in routes] == [22, 25]


def test_tomtom_route_has_distance_delay_and_points():
    best = parse_tomtom(TOMTOM)[0]
    assert best["distance_km"] == 12.5
    assert best["delay_min"] == 7
    assert best["points"][0] == [15.335, 76.46] and len(best["points"]) == 4


def test_only_traffic_sections_become_jams():
    best = parse_tomtom(TOMTOM)[0]
    assert best["jams"] == [{"start": 1, "end": 2, "level": "major", "kind": "jam", "delay_min": 7}]


def test_osrm_points_are_flipped_to_lat_lon_and_have_no_traffic():
    route = parse_osrm(OSRM)[0]
    assert route["points"][0] == [15.335, 76.46]          # OSRM sends [lon, lat]
    assert route["delay_min"] is None and route["jams"] == []


# ── /api/route ─────────────────────────────────────────────────────
def test_uses_tomtom_when_a_key_is_set(app, client, monkeypatch):
    app.config["TOMTOM_API_KEY"] = "test"
    monkeypatch.setattr(directions, "tomtom_routes", lambda *a: parse_tomtom(TOMTOM))
    data = client.get(f"/api/route?from={FROM}&to={TO}").get_json()
    assert data["provider"] == "tomtom" and data["traffic"] is True
    assert len(data["routes"]) == 2


def test_falls_back_to_osrm_when_tomtom_fails(app, client, monkeypatch):
    app.config["TOMTOM_API_KEY"] = "test"
    def broken(*a):
        raise requests.HTTPError("403 quota used up")
    monkeypatch.setattr(directions, "tomtom_routes", broken)
    monkeypatch.setattr(directions, "osrm_routes", lambda *a: parse_osrm(OSRM))
    data = client.get(f"/api/route?from={FROM}&to={TO}").get_json()
    assert data["provider"] == "osrm" and data["traffic"] is False


def test_uses_osrm_without_a_key(client, monkeypatch):
    monkeypatch.setattr(directions, "tomtom_routes", lambda *a: pytest.fail("TomTom must not be called"))
    monkeypatch.setattr(directions, "osrm_routes", lambda *a: parse_osrm(OSRM))
    assert client.get(f"/api/route?from={FROM}&to={TO}").get_json()["provider"] == "osrm"


def test_second_request_comes_from_the_cache(client, monkeypatch):
    calls = []
    monkeypatch.setattr(directions, "osrm_routes", lambda *a: calls.append(1) or parse_osrm(OSRM))
    client.get(f"/api/route?from={FROM}&to={TO}")
    again = client.get(f"/api/route?from={FROM}&to={TO}").get_json()
    assert again["cached"] is True and len(calls) == 1


def test_503_when_both_services_fail(client, monkeypatch):
    def down(*a):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(directions, "osrm_routes", down)
    assert client.get(f"/api/route?from={FROM}&to={TO}").status_code == 503


@pytest.mark.parametrize("query", ["", "from=abc&to=1,2", "from=99,0&to=1,2", "from=15.3,76.4&to=28.6,77.2,5"])
def test_bad_points_are_refused(client, query):
    assert client.get(f"/api/route?{query}").status_code == 400


def test_very_long_trips_are_refused(client):
    r = client.get("/api/route?from=8.08,77.55&to=34.08,74.80")   # Kanyakumari to Srinagar
    assert r.status_code == 400



# ── walking ────────────────────────────────────────────────────────
def test_walk_uses_the_foot_server_and_never_tomtom(app, client, monkeypatch):
    app.config["TOMTOM_API_KEY"] = "test"
    monkeypatch.setattr(directions, "tomtom_routes", lambda *a: pytest.fail("no traffic on foot"))
    modes = []
    monkeypatch.setattr(directions, "osrm_routes", lambda *a: modes.append(a[-1]) or parse_osrm(OSRM))
    data = client.get(f"/api/route?from={FROM}&to={TO}&mode=walk").get_json()
    assert modes == ["walk"] and data["mode"] == "walk" and data["traffic"] is False


def test_osrm_asks_the_server_for_the_chosen_mode(monkeypatch):
    urls = []
    class Answer:
        def raise_for_status(self): pass
        def json(self): return OSRM
    monkeypatch.setattr(directions.requests, "get", lambda url, **kw: urls.append(url) or Answer())
    directions.osrm_routes(15.335, 76.46, 15.2689, 76.3909, "walk")
    directions.osrm_routes(15.335, 76.46, 15.2689, 76.3909)
    assert "routed-foot" in urls[0] and "routed-car" in urls[1]


def test_cache_keeps_car_and_walk_apart(client, monkeypatch):
    calls = []
    monkeypatch.setattr(directions, "osrm_routes", lambda *a: calls.append(a[-1]) or parse_osrm(OSRM))
    client.get(f"/api/route?from={FROM}&to={TO}&mode=car")
    walk = client.get(f"/api/route?from={FROM}&to={TO}&mode=walk").get_json()
    assert walk["cached"] is False and calls == ["car", "walk"]


def test_unknown_mode_is_refused(client):
    assert client.get(f"/api/route?from={FROM}&to={TO}&mode=fly").status_code == 400


def test_long_walks_are_refused(client):
    r = client.get("/api/route?from=15.335,76.46&to=15.15,76.92&mode=walk")   # Hampi to Ballari, ~50 km
    assert r.status_code == 400 and "30 km" in r.get_json()["error"]