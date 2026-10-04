"""Finding places: nearby, by city, search, and lists for the sidebar."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from flask import Blueprint, Response, jsonify, request

from yatra.data import ICONS, csv_nearby, df, row_to_dict
from yatra.osm import ALL_OSM_TAGS, LIVE_FALLBACK, LIVE_PRIMARY, live_fetch

bp = Blueprint("places", __name__, url_prefix="/api")

@bp.route("/stats")
def api_stats():
    return jsonify({
        "total_places":int(len(df)),"total_cities":int(df["city"].nunique()),
        "total_landmarks":int(df["important"].sum()),
        "categories":df["category_clean"].value_counts().to_dict(),
    })

@bp.route("/categories")
def api_categories():
    cats = sorted(df["category_clean"].unique().tolist())
    for c in ALL_OSM_TAGS:
        if c not in cats: cats.append(c)
    cats = sorted(set(cats))
    return jsonify({"categories":cats,"icons":{c:ICONS.get(c,"📍") for c in cats},
                    "live_categories":sorted(LIVE_PRIMARY | LIVE_FALLBACK)})

@bp.route("/cities")
def api_cities():
    return jsonify(sorted(df["city"].unique().tolist()))

@bp.route("/nearby")
def api_nearby():
    lat      = request.args.get("lat",      type=float)
    lon      = request.args.get("lon",      type=float)
    category = request.args.get("category","").strip() or None
    radius   = request.args.get("radius",   50,  type=float)
    top_n    = request.args.get("top_n",    12,  type=int)

    if lat is None or lon is None:
        return jsonify({"error":"lat and lon required"}), 400

    csv_results, live_results = [], []

    csv_cat = category if (category and category not in LIVE_PRIMARY) else None
    res = csv_nearby(lat, lon, csv_cat, radius, top_n)
    if not res.empty:
        for _, row in res.iterrows():
            csv_results.append(row_to_dict(row,{
                "distance":round(float(row["distance"]),2),
                "score":round(float(row["score"]),3),
            }))

    live_radius_m = min(int(radius * 80), 6000)

    if category in LIVE_PRIMARY:
        live_results = live_fetch(lat, lon, category, live_radius_m, top_n)
    elif category in LIVE_FALLBACK:
        if len(csv_results) < 3:
            live_results = live_fetch(lat, lon, category, live_radius_m, top_n)
    elif category is None:
        all_live_cats = list(LIVE_PRIMARY) + [c for c in LIVE_FALLBACK if
                            len([r for r in csv_results if r["category"]==c]) < 2]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(live_fetch, lat, lon, c, live_radius_m, top_n//3): c
                       for c in all_live_cats}
            for fut in as_completed(futures):
                try: live_results.extend(fut.result())
                except Exception: pass

    # Merge & deduplicate
    seen, merged = set(), []
    for p in csv_results + live_results:
        key = p["place"].lower().strip()
        if key not in seen:
            seen.add(key); merged.append(p)

    merged.sort(key=lambda x: (-x.get("important",0), -x.get("score",0)))
    return jsonify(merged[:top_n])

@bp.route("/search")
def api_search():
    q     = request.args.get("q","").strip().lower()
    top_n = request.args.get("top_n", 12, type=int)
    if not q: return jsonify([])
    mask = (df["place"].str.lower().str.contains(q,na=False) |
            df["city"].str.lower().str.contains(q,na=False))
    res = df[mask].sort_values("important",ascending=False).head(top_n)
    return jsonify([row_to_dict(r) for _,r in res.iterrows()])

@bp.route("/city_places")
def api_city_places():
    city     = request.args.get("city","").strip()
    category = request.args.get("category","").strip() or None
    top_n    = request.args.get("top_n", 15, type=int)
    if not city: return jsonify({"error":"city required"}), 400
    mask = df["city"].str.lower() == city.lower()
    if category: mask &= df["category_clean"] == category
    res = df[mask].copy()
    res = res.sort_values("important", ascending=False).head(top_n)
    return jsonify([row_to_dict(r) for _,r in res.iterrows()])

@bp.route("/export")
def api_export():
    try:    records = json.loads(request.args.get("data","[]"))
    except: records = []
    if not records: return jsonify({"error":"No data provided"}), 400
    csv = pd.DataFrame(records).to_csv(index=False)
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=yatra_places.csv"})

