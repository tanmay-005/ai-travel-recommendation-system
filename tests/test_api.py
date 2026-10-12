"""The app from the outside: real HTTP requests through Flask's test client."""
import pytest

from yatra.routes import geocode

HAMPI = {"osm_id": "w123456", "place": "Vijaya Vitthala Temple", "destination": "Hampi",
         "label": "Museum", "lat": 15.3426, "lon": 76.4746}


# ── accounts ───────────────────────────────────────────────────────
def test_register_then_login(client):
    r = client.post("/api/auth/register", json={
        "username": "ravi", "email": "ravi@example.com", "password": "secret123"})
    assert r.status_code == 200
    client.post("/logout")
    r = client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "secret123"})
    assert r.status_code == 200
    assert r.get_json()["user"]["username"] == "ravi"


def test_register_says_which_fields_are_wrong(client):
    r = client.post("/api/auth/register", json={"username": "a", "email": "nope", "password": "123"})
    assert r.status_code == 400
    assert set(r.get_json()["errors"]) == {"username", "email", "password"}


def test_duplicate_username_is_refused(logged_in):
    logged_in.post("/logout")
    r = logged_in.post("/api/auth/register", json={
        "username": "asha", "email": "other@example.com", "password": "secret123"})
    assert r.status_code == 409
    assert "username" in r.get_json()["errors"]


def test_wrong_password_is_refused(logged_in):
    logged_in.post("/logout")
    r = logged_in.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_passwords_are_stored_hashed(app, logged_in):
    from yatra.db import get_db
    with app.app_context():
        stored = get_db().execute("SELECT password FROM users").fetchone()["password"]
    assert stored != "secret123" and stored.startswith("scrypt:")


# ── My Bag ─────────────────────────────────────────────────────────
def test_register_login_save_list(logged_in):
    r = logged_in.post("/api/saved", json=HAMPI)
    assert r.status_code == 201
    bag = logged_in.get("/api/saved").get_json()
    assert [p["place"] for p in bag] == ["Vijaya Vitthala Temple"]
    assert bag[0]["destination"] == "Hampi"


def test_saving_while_logged_out_returns_401(client):
    assert client.post("/api/saved", json=HAMPI).status_code == 401
    assert client.get("/api/saved").status_code == 401


def test_saving_twice_keeps_one_copy(logged_in):
    logged_in.post("/api/saved", json=HAMPI)
    logged_in.post("/api/saved", json=HAMPI)
    assert len(logged_in.get("/api/saved").get_json()) == 1


def test_remove_from_bag(logged_in):
    logged_in.post("/api/saved", json=HAMPI)
    assert logged_in.delete(f"/api/saved/{HAMPI['osm_id']}").status_code == 200
    assert logged_in.get("/api/saved").get_json() == []


def test_bad_place_is_refused(logged_in):
    r = logged_in.post("/api/saved", json={**HAMPI, "osm_id": "DROP TABLE", "lat": "north"})
    assert r.status_code == 400


def test_users_cannot_see_each_others_bag(app, logged_in):
    logged_in.post("/api/saved", json=HAMPI)
    other = app.test_client()
    other.post("/api/auth/register", json={
        "username": "bilal", "email": "bilal@example.com", "password": "secret123"})
    assert other.get("/api/saved").get_json() == []


# ── pages and redirects ────────────────────────────────────────────
def test_bag_page_sends_logged_out_visitors_to_login(client):
    r = client.get("/bag")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/login?next=")


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/\\evil.example"])
def test_login_never_redirects_to_another_site(logged_in, target):
    r = logged_in.get("/login", query_string={"next": target})
    assert r.status_code == 302
    assert r.headers["Location"] == "/"


# ── discovery ──────────────────────────────────────────────────────
def test_discover_manali_fills_all_three_lists(client):
    r = client.get("/api/discover?lat=32.24&lon=77.19")      # roadmap check, step 5.2
    assert r.status_code == 200
    data = r.get_json()
    assert data["top_spots"] and data["hidden_gems"] and data["activities"]
    assert data["live_used"] is False                         # the fake live lookup found nothing


def test_discover_rejects_bad_coordinates(client):
    assert client.get("/api/discover?lat=999&lon=77").status_code == 400
    assert client.get("/api/discover").status_code == 400


# ── geocode (without calling the real Nominatim) ───────────────────
def test_geocode_asks_nominatim_once_then_uses_the_cache(client, monkeypatch):
    calls = []
    def fake_lookup(query):
        calls.append(query)
        return {"name": "Gokarna", "display_name": "Gokarna, Karnataka, India", "lat": 14.55, "lon": 74.32}
    monkeypatch.setattr(geocode, "lookup", fake_lookup)
    geocode._cache.clear()

    first  = client.get("/api/geocode?q=Gokarna").get_json()
    second = client.get("/api/geocode?q=  gokarna ").get_json()
    assert first["cached"] is False and second["cached"] is True
    assert len(calls) == 1


def test_geocode_rejects_too_short_queries(client):
    assert client.get("/api/geocode?q=x").status_code == 400