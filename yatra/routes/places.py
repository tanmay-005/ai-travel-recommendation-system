"""Finding places: /api/discover for the Explore page, /api/search by name."""
import pandas as pd
from flask import Blueprint, jsonify, request

from yatra.data import df, row_to_dict
from yatra.discover import discover
from yatra.geo import haversine
from yatra.osm import live_top_up

bp = Blueprint("places", __name__, url_prefix="/api")


def to_cards(rows):
    """Turn ranked rows into JSON-ready dicts for the frontend."""
    return [row_to_dict(r, {
        "osm_id":        r["osm_id"],
        "kind":          r["kind"],
        "subtype":       r["subtype"],
        "has_wiki":      int(r["has_wiki"]),
        "description":   r["description"],
        "opening_hours": r["opening_hours"],
        "fee":           r["fee"],
        "distance":      round(float(r["distance"]), 2),
        "score":         round(float(r["score"]), 3),
        "source":        r.get("source", "csv"),
    }) for _, r in rows.iterrows()]


MIN_PER_LIST = 5   # fewer than this in a list -> ask OpenStreetMap live for more

def add_live_places(near, lat, lon, radius, top, gems, acts):
    """Small town? Fetch only the kinds whose lists are short, live, and add the new ones."""
    wanted = set()
    if len(top) < MIN_PER_LIST or len(gems) < MIN_PER_LIST:
        wanted |= {"sight", "nature"}
    if len(acts) < MIN_PER_LIST:
        wanted.add("activity")
    if not wanted:
        return near, False

    live = live_top_up(lat, lon, sorted(wanted), radius)
    if live.empty:
        return near, False
    live["distance"] = haversine(lat, lon, live["lat"].values, live["lon"].values)
    known_names = set(near["place"].str.lower())
    live = live[(live["distance"] <= radius)
                & ~live["osm_id"].isin(near["osm_id"])              # already in the CSV
                & ~live["place"].str.lower().isin(known_names)]     # same place, other copy
    live = live.drop_duplicates("osm_id")
    live = live[~live["place"].str.lower().duplicated()]              # one row per name
    if live.empty:
        return near, False
    return pd.concat([near.assign(source="csv"), live], ignore_index=True), True


@bp.route("/discover")
def api_discover():
    """Everything worth knowing around one point, in three ranked lists."""
    lat    = request.args.get("lat", type=float)
    lon    = request.args.get("lon", type=float)
    radius = request.args.get("radius", 25, type=float)
    limit  = request.args.get("limit", 10, type=int)

    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "valid lat and lon required"}), 400
    radius = min(max(radius, 1), 100)    # keep requests sensible: 1-100 km
    limit  = min(max(limit, 1), 30)

    # Distance is computed once for every place, then shared by all three lists.
    dist = haversine(lat, lon, df["lat"].values, df["lon"].values)
    near = df[dist <= radius].copy()
    near["distance"] = dist[dist <= radius]

    top, gems, acts = discover(near, radius, limit)
    near, live_used = add_live_places(near, lat, lon, radius, top, gems, acts)
    if live_used:
        top, gems, acts = discover(near, radius, limit)

    return jsonify({
        "center":      {"lat": lat, "lon": lon},
        "radius_km":   radius,
        "live_used":   live_used,
        "top_spots":   to_cards(top),
        "hidden_gems": to_cards(gems),
        "activities":  to_cards(acts),
    })

@bp.route("/search")
def api_search():
    q     = request.args.get("q","").strip().lower()
    top_n = request.args.get("top_n", 12, type=int)
    if not q: return jsonify([])
    mask = (df["place"].str.lower().str.contains(q,na=False) |
            df["city"].str.lower().str.contains(q,na=False))
    res = df[mask].sort_values("important",ascending=False).head(top_n)
    return jsonify([row_to_dict(r) for _,r in res.iterrows()])
