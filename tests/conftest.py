"""Shared test setup. pytest finds this file by itself and hands these fixtures to any test that asks."""
import pandas as pd
import pytest

from yatra import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    # No internet in tests: the live OpenStreetMap top-up returns "nothing found".
    monkeypatch.setattr("yatra.routes.places.live_top_up", lambda *args, **kwargs: pd.DataFrame())
    # Each test gets its own brand-new, empty database file in a temporary folder.
    # No real TomTom calls either, even if your .env has a key (a test can switch it on).
    return create_app({"TESTING": True, "SECRET_KEY": "test-key", "DB_PATH": tmp_path / "test.db",
                       "TOMTOM_API_KEY": ""})


@pytest.fixture
def client(app):
    """A pretend browser: it sends requests to the app and keeps the session cookie."""
    return app.test_client()


@pytest.fixture
def logged_in(client):
    """A client that has already signed up (sign-up also logs you in)."""
    r = client.post("/api/auth/register", json={
        "username": "asha", "email": "asha@example.com", "password": "secret123"})
    assert r.status_code == 200
    return client