"""The discovery engine: rank the places around a point into three lists.

Every function takes a DataFrame of places that are already within range
(it must have a "distance" column in km) and returns the best rows, sorted.
No Flask in here, so each function can be tested with a small hand-made table.
"""

# ── Tuning knobs ─────────────────────────────────────────────────
# Top Spots: famous first, then well-documented, then close by.
TOP_W_FAME     = 0.5   # has a Wikipedia/Wikidata article
TOP_W_DETAIL   = 0.3   # how much mappers have documented it
TOP_W_CLOSE    = 0.2   # nearer is better

# Hidden Gems: no article, but well documented and near.
GEM_W_DETAIL   = 0.6
GEM_W_CLOSE    = 0.4
GEM_MIN_TAGS   = 4     # name + type + at least 2 more details; skips bare, unverified points

# Things to Do: near first, but a documented activity beats a bare "2 tent".
ACT_W_CLOSE    = 0.7
ACT_W_DETAIL   = 0.3

DETAIL_CAP     = 12    # tag_count at or above this counts as "fully documented" (90% of places have <= 8)
SEE_KINDS      = {"sight", "nature"}


def closeness(distance_km, radius_km):
    """1.0 at the centre, 0.0 at the edge of the search circle."""
    return (1 - distance_km / radius_km).clip(lower=0, upper=1)


def detail(tag_count):
    """0..1: how well documented a place is on OpenStreetMap."""
    return (tag_count / DETAIL_CAP).clip(upper=1)


def top_spots(rows, radius_km, limit=10, exclude=()):
    """The famous places to see: sights and nature, ranked by fame, detail and closeness.
    Famous places always come first: fame alone (0.5) is worth as much as perfect detail + closeness."""
    see = rows[rows["kind"].isin(SEE_KINDS)
               & ~rows["osm_id"].isin(list(exclude))
               & ((rows["has_wiki"] == 1) | (rows["tag_count"] >= GEM_MIN_TAGS))].copy()
    see["score"] = (TOP_W_FAME   * see["has_wiki"]
                    + TOP_W_DETAIL * detail(see["tag_count"])
                    + TOP_W_CLOSE  * closeness(see["distance"], radius_km))
    return see.sort_values("score", ascending=False).head(limit)


def hidden_gems(rows, radius_km, limit=10):
    """Good places most visitors miss: no Wikipedia article, but well documented and near."""
    gems = rows[rows["kind"].isin(SEE_KINDS)
                & (rows["has_wiki"] == 0)
                & (rows["tag_count"] >= GEM_MIN_TAGS)].copy()
    gems["score"] = (GEM_W_DETAIL * detail(gems["tag_count"])
                     + GEM_W_CLOSE * closeness(gems["distance"], radius_km))
    return gems.sort_values("score", ascending=False).head(limit)


def activities(rows, radius_km, limit=10):
    """Things to do: treks, camps, parks, adventure sports - closest and best documented first."""
    act = rows[rows["kind"] == "activity"].copy()
    act["score"] = (ACT_W_CLOSE  * closeness(act["distance"], radius_km)
                    + ACT_W_DETAIL * detail(act["tag_count"]))
    return act.sort_values("score", ascending=False).head(limit)


def discover(rows, radius_km, limit=10):
    """All three lists. Gems are picked first so a small town still gets some;
    Top Spots then skips them, so no place appears twice."""
    gems = hidden_gems(rows, radius_km, limit)
    top  = top_spots(rows, radius_km, limit, exclude=gems["osm_id"])
    acts = activities(rows, radius_km, limit)
    return top, gems, acts