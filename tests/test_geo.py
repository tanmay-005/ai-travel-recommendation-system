"""Distance maths, checked against distances you can look up on any map."""
import numpy as np
import pytest

from yatra.geo import haversine

DELHI = (28.6139, 77.2090)
AGRA  = (27.1767, 78.0081)


def km(a, b):
    """Distance between two (lat, lon) points, as a plain number."""
    return float(haversine(a[0], a[1], np.array([b[0]]), np.array([b[1]]))[0])


def test_delhi_to_agra_is_about_180_km():
    assert km(DELHI, AGRA) == pytest.approx(180, abs=5)     # straight line, not by road


def test_a_point_is_zero_km_from_itself():
    assert km(DELHI, DELHI) == pytest.approx(0, abs=1e-9)


def test_distance_is_the_same_both_ways():
    assert km(DELHI, AGRA) == pytest.approx(km(AGRA, DELHI))


def test_many_points_at_once():
    """The app measures thousands of places in one call, so it must accept arrays."""
    lats = np.array([28.6139, 27.1767, 26.9124])            # Delhi, Agra, Jaipur
    lons = np.array([77.2090, 78.0081, 75.7873])
    d = haversine(*DELHI, lats, lons)
    assert len(d) == 3
    assert d[0] == pytest.approx(0, abs=1e-9)
    assert d[1] < d[2]                                      # Agra is closer to Delhi than Jaipur