"""The ranking rules in yatra/discover.py, checked on five hand-made places."""
import pandas as pd
import pytest

from yatra import discover as d

RADIUS = 10   # km


def five_places():
    """A tiny made-up town. Each place exists to test one rule."""
    return pd.DataFrame([
        # famous (has a Wikipedia article) but the furthest away
        {"osm_id": "w1", "place": "Famous Fort",     "kind": "sight",    "has_wiki": 1, "tag_count": 10, "distance": 8.0},
        # no article, very well documented, close: the best hidden gem
        {"osm_id": "n2", "place": "Quiet Waterfall", "kind": "nature",   "has_wiki": 0, "tag_count": 9,  "distance": 2.0},
        # no article, less detail, further: a gem, but ranked below the waterfall
        {"osm_id": "n3", "place": "Old Stepwell",    "kind": "sight",    "has_wiki": 0, "tag_count": 6,  "distance": 5.0},
        # a bare map point (only 2 tags): not good enough for any list
        {"osm_id": "n4", "place": "Bare Boulder",    "kind": "nature",   "has_wiki": 0, "tag_count": 2,  "distance": 1.0},
        # the only activity
        {"osm_id": "r5", "place": "River Rafting",   "kind": "activity", "has_wiki": 0, "tag_count": 5,  "distance": 3.0},
    ])


def names(rows):
    return list(rows["place"])


# ── helper scores ──────────────────────────────────────────────────
def test_closeness_is_1_at_the_centre_and_0_at_the_edge():
    dist = pd.Series([0.0, 5.0, 10.0, 15.0])
    assert list(d.closeness(dist, RADIUS)) == [1.0, 0.5, 0.0, 0.0]    # beyond the edge stays 0


def test_detail_is_capped_at_1():
    tags = pd.Series([0, d.DETAIL_CAP / 2, d.DETAIL_CAP, 50])
    assert list(d.detail(tags)) == [0.0, 0.5, 1.0, 1.0]


def test_each_set_of_weights_adds_up_to_1():
    """So every score stays between 0 and 1 and the weights read as percentages."""
    assert d.TOP_W_FAME + d.TOP_W_DETAIL + d.TOP_W_CLOSE == pytest.approx(1)
    assert d.GEM_W_DETAIL + d.GEM_W_CLOSE == pytest.approx(1)
    assert d.ACT_W_CLOSE + d.ACT_W_DETAIL == pytest.approx(1)


# ── Hidden Gems ────────────────────────────────────────────────────
def test_hidden_gems_exclude_places_with_a_wikipedia_article():
    assert "Famous Fort" not in names(d.hidden_gems(five_places(), RADIUS))


def test_hidden_gems_skip_bare_map_points():
    assert "Bare Boulder" not in names(d.hidden_gems(five_places(), RADIUS))


def test_hidden_gems_prefer_detailed_and_close():
    assert names(d.hidden_gems(five_places(), RADIUS)) == ["Quiet Waterfall", "Old Stepwell"]


# ── Top Spots ──────────────────────────────────────────────────────
def test_famous_place_comes_first_even_when_it_is_furthest():
    assert names(d.top_spots(five_places(), RADIUS))[0] == "Famous Fort"


def test_top_spots_never_include_activities():
    assert "River Rafting" not in names(d.top_spots(five_places(), RADIUS))


# ── Things to Do ───────────────────────────────────────────────────
def test_activities_only_contain_activities():
    assert names(d.activities(five_places(), RADIUS)) == ["River Rafting"]


# ── all three together ─────────────────────────────────────────────
def test_no_place_appears_in_both_top_spots_and_hidden_gems():
    top, gems, _ = d.discover(five_places(), RADIUS)
    assert set(top["osm_id"]).isdisjoint(gems["osm_id"])


def test_limit_caps_every_list():
    top, gems, acts = d.discover(five_places(), RADIUS, limit=1)
    assert len(top) <= 1 and len(gems) <= 1 and len(acts) <= 1