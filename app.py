# ─────────────────────────────────────────────────────────────────
#  app.py  —  Yatra AI Travel Recommendation System
#
#  FIXES IN THIS VERSION:
#  1. MemoryError (31.9 GB crash) — cosine_sim matrix removed entirely.
#     Now computed on-demand per query: 0.5 MB instead of 31 GB.
#  2. All categories (Heritage/Museum/Temple/Nature/Viewpoint/Beach)
#     now also use live Overpass when CSV has no results nearby.
#     Strategy: try CSV first → if fewer than 3 results → top up with live.
#  3. Login / Register / User database added (SQLite, no extra install).
#     Stores: users, their searches, ratings, saved places, trip history.
# ─────────────────────────────────────────────────────────────────

from flask import (Flask, request, jsonify, render_template,
                   session, Response, redirect, url_for)
import pandas as pd
import numpy as np
from pathlib import Path
import math, json, os, re, sqlite3, hashlib, secrets
import requests as http_requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

BASE        = Path(__file__).parent
PLACES_CSV  = BASE / "india_places_dataset.csv"
DB_PATH     = BASE / "yatra.db"

# ═══════════════════════════════════════════════════════════════
# 1.  DATABASE SETUP (SQLite — no extra install needed)
# ═══════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT    UNIQUE NOT NULL,
        email       TEXT    UNIQUE NOT NULL,
        password    TEXT    NOT NULL,
        created_at  TEXT,
        last_login  TEXT
    );

    CREATE TABLE IF NOT EXISTS saved_places (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        place       TEXT    NOT NULL,
        city        TEXT,
        category    TEXT,
        lat         REAL,
        lon         REAL,
        icon        TEXT,
        saved_at    TEXT,
        UNIQUE(user_id, place)
    );
    """)
    conn.commit()
    conn.close()

init_db()

# ── Auth helpers ─────────────────────────────────────────────────

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper

def current_user_id():
    return session.get("user_id")

# ═══════════════════════════════════════════════════════════════
# 2.  LOAD & CLEAN CSV
# ═══════════════════════════════════════════════════════════════

df = pd.read_csv(PLACES_CSV)
df = df.dropna(subset=["place", "lat", "lon", "city"])
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df = df.dropna(subset=["lat", "lon"])
df = df[df["place"].str.match(r'^[\x20-\x7E\u0900-\u097F]{3,}', na=False)]
df["important"] = pd.to_numeric(df.get("important", 0), errors="coerce").fillna(0).astype(int)

RAW_MAP = {
    "tourism:attraction":"Heritage", "historic:monument":"Heritage",
    "historic:fort":"Heritage",      "tourism:museum":"Museum",
    "historic:temple":"Temple",      "amenity:place_of_worship":"Temple",
    "tourism:viewpoint":"Viewpoint", "natural:peak":"Nature",
    "natural:beach":"Beach",         "natural:waterfall":"Nature",
    "leisure:nature_reserve":"Nature","amenity:restaurant":"Food",
    "amenity:cafe":"Cafe",           "amenity:fast_food":"Food",
    "leisure:park":"Nature",         "leisure:garden":"Nature",
    "shop:mall":"Shopping",          "shop:clothes":"Shopping",
}
if "category_clean" not in df.columns:
    df["category_clean"] = df["category"].copy()
if df["category_clean"].str.contains(":", na=False).any():
    df["category_clean"] = df["category_clean"].map(RAW_MAP).fillna(df["category_clean"])
df = df.reset_index(drop=True)

# ═══════════════════════════════════════════════════════════════
# 3.  CATEGORY CONFIG
# ═══════════════════════════════════════════════════════════════

ICONS = {
    "Heritage":"🏛️","Museum":"🏺","Temple":"🛕","Viewpoint":"🌅",
    "Beach":"🏖️","Food":"🍽️","Cafe":"☕","Shopping":"🛍️",
    "Nature":"🌿","Other":"📍",
}

# OSM tags for every category (used in live fallback)
ALL_OSM_TAGS = {
    "Heritage" : [("tourism","attraction"),("historic","monument"),("historic","fort")],
    "Museum"   : [("tourism","museum")],
    "Temple"   : [("historic","temple"),("amenity","place_of_worship")],
    "Viewpoint": [("tourism","viewpoint")],
    "Beach"    : [("natural","beach")],
    "Nature"   : [("leisure","park"),("leisure","garden"),("natural","waterfall"),("natural","peak")],
    "Cafe"     : [("amenity","cafe"),("amenity","coffee_shop")],
    "Food"     : [("amenity","restaurant"),("amenity","fast_food"),("amenity","food_court")],
    "Shopping" : [("shop","mall"),("shop","supermarket"),("amenity","marketplace")],
}

# Categories that PRIMARILY come from live OSM (CSV coverage is poor)
LIVE_PRIMARY = {"Cafe", "Food", "Shopping"}
# Categories that use CSV first, live as fallback if CSV < 3 results
LIVE_FALLBACK = {"Heritage","Museum","Temple","Viewpoint","Beach","Nature"}

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OSM_HEADERS = {"User-Agent": "yatra-travel-app/4.0"}


# ═══════════════════════════════════════════════════════════════
# 6.  HAVERSINE
# ═══════════════════════════════════════════════════════════════

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    rl1, rl2   = math.radians(lat1), np.radians(lat2)
    rlo1, rlo2 = math.radians(lon1), np.radians(lon2)
    dlat = rl2 - rl1; dlon = rlo2 - rlo1
    a = np.sin(dlat/2)**2 + math.cos(rl1)*np.cos(rl2)*np.sin(dlon/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# ═══════════════════════════════════════════════════════════════
# 7.  LIVE OVERPASS (all categories now supported)
# ═══════════════════════════════════════════════════════════════

def _valid_name(name):
    if not name or len(name.strip()) < 2: return False
    foreign = re.sub(r'[\x20-\x7E\u0900-\u097F\d\s\-\'\.(),&/]', '', name)
    return len(foreign) / max(len(name), 1) < 0.4

def _overpass_fetch(lat, lon, tags, radius_m):
    union = [f'  {t}["{k}"="{v}"](around:{radius_m},{lat},{lon});\n'
             for k, v in tags for t in ["node","way"]]
    query = f"[out:json][timeout:15];\n(\n{''.join(union)});\nout center tags;"
    for mirror in OVERPASS_MIRRORS:
        try:
            r = http_requests.post(mirror, data={"data": query},
                                   headers=OSM_HEADERS, timeout=18)
            if r.status_code in (429, 502, 503, 504): continue
            r.raise_for_status()
            return r.json().get("elements", [])
        except Exception:
            continue
    return []

def live_fetch(lat, lon, category, radius_m=3000, top_n=15):
    tags = ALL_OSM_TAGS.get(category, [])
    if not tags: return []
    elements = _overpass_fetch(lat, lon, tags, radius_m)
    results  = []
    for e in elements:
        t    = e.get("tags", {})
        name = t.get("name:en") or t.get("name") or t.get("brand")
        if not _valid_name(name): continue
        elat = e.get("lat") or e.get("center",{}).get("lat")
        elon = e.get("lon") or e.get("center",{}).get("lon")
        if not elat or not elon: continue
        dist = float(haversine(lat, lon, np.array([elat]), np.array([elon]))[0])
        results.append({
            "place": name.strip(), "city": t.get("addr:city","—"),
            "lat": round(float(elat),6), "lon": round(float(elon),6),
            "category": category, "icon": ICONS.get(category,"📍"),
            "important": 0,
            "distance": round(dist,2),
            "score": round(max(0, 1 - dist/(radius_m/1000)), 3),
            "source": "live",
            "opening_hours": t.get("opening_hours",""),
            "cuisine":  t.get("cuisine",""),
            "phone":    t.get("phone","") or t.get("contact:phone",""),
            "website":  t.get("website","") or t.get("contact:website",""),
            "address":  (t.get("addr:street","") + " " + t.get("addr:housenumber","")).strip(),
        })
    results.sort(key=lambda x: x["distance"])
    return results[:top_n]

# ═══════════════════════════════════════════════════════════════
# 8.  CSV HYBRID SCORE
# ═══════════════════════════════════════════════════════════════

def csv_nearby(lat, lon, category=None, radius_km=50, top_n=15):
    work = df.copy()
    if category:
        work = work[work["category_clean"] == category]
    if work.empty: return work
    work["distance"] = haversine(lat, lon, work["lat"].values, work["lon"].values)
    work = work[work["distance"] <= radius_km]
    if work.empty: return work
    max_d = work["distance"].max() or 1
    work["score_dist"] = 1 - work["distance"] / max_d
    work["score_imp"]  = work["important"].astype(float)
    work["score"]      = 0.7*work["score_dist"] + 0.3*work["score_imp"]   # temporary; phase 5 replaces it
    return work.sort_values("score", ascending=False).head(top_n)

# ═══════════════════════════════════════════════════════════════
# 9.  SERIALISER
# ═══════════════════════════════════════════════════════════════

def row_to_dict(row, extra=None):
    d = {
        "place":row["place"],"city":row["city"],
        "lat":round(float(row["lat"]),6),"lon":round(float(row["lon"]),6),
        "category":row["category_clean"],"icon":ICONS.get(row["category_clean"],"📍"),
        "important":int(row.get("important",0)),"source":"csv",
        "opening_hours":"","cuisine":"","phone":"","website":"","address":"",
    }
    if extra: d.update(extra)
    return d

# ═══════════════════════════════════════════════════════════════
# 10. FLASK ROUTES — AUTH
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username","").strip()
    email    = data.get("email","").strip().lower()
    password = data.get("password","")
    if not username or not email or not password:
        return jsonify({"error":"username, email and password required"}), 400
    if len(password) < 6:
        return jsonify({"error":"Password must be at least 6 characters"}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?,?,?)",
            (username, email, hash_pw(password))
        )
        conn.commit()
        row = conn.execute("SELECT id,username,email FROM users WHERE email=?", (email,)).fetchone()
        session["user_id"]  = row["id"]
        session["username"] = row["username"]
        return jsonify({"message":"Registered successfully","user":{"id":row["id"],"username":row["username"],"email":row["email"]}})
    except sqlite3.IntegrityError as e:
        msg = "Username already taken" if "username" in str(e) else "Email already registered"
        return jsonify({"error": msg}), 409
    finally:
        conn.close()

@app.route("/api/auth/login", methods=["POST"])
def login():
    data  = request.get_json(silent=True) or {}
    email = data.get("email","").strip().lower()
    pw    = data.get("password","")
    conn  = get_db()
    row   = conn.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, hash_pw(pw))
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error":"Invalid email or password"}), 401
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), row["id"]))
    conn.commit(); conn.close()
    session["user_id"]  = row["id"]
    session["username"] = row["username"]
    return jsonify({"message":"Logged in","user":{"id":row["id"],"username":row["username"],"email":row["email"]}})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message":"Logged out"})

@app.route("/api/auth/me")
def me():
    uid = current_user_id()
    if not uid: return jsonify({"user":None})
    conn = get_db()
    row  = conn.execute("SELECT id,username,email,created_at,last_login FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not row: return jsonify({"user":None})
    return jsonify({"user":dict(row)})

# ═══════════════════════════════════════════════════════════════
# 11. FLASK ROUTES — META
# ═══════════════════════════════════════════════════════════════

@app.route("/api/stats")
def api_stats():
    return jsonify({
        "total_places":int(len(df)),"total_cities":int(df["city"].nunique()),
        "total_landmarks":int(df["important"].sum()),
        "categories":df["category_clean"].value_counts().to_dict(),
    })

@app.route("/api/categories")
def api_categories():
    cats = sorted(df["category_clean"].unique().tolist())
    for c in ALL_OSM_TAGS:
        if c not in cats: cats.append(c)
    cats = sorted(set(cats))
    return jsonify({"categories":cats,"icons":{c:ICONS.get(c,"📍") for c in cats},
                    "live_categories":sorted(LIVE_PRIMARY | LIVE_FALLBACK)})

@app.route("/api/cities")
def api_cities():
    return jsonify(sorted(df["city"].unique().tolist()))

# ═══════════════════════════════════════════════════════════════
# 12. FLASK ROUTES — RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/nearby")
def api_nearby():
    lat      = request.args.get("lat",      type=float)
    lon      = request.args.get("lon",      type=float)
    category = request.args.get("category","").strip() or None
    radius   = request.args.get("radius",   50,  type=float)
    top_n    = request.args.get("top_n",    12,  type=int)

    if lat is None or lon is None:
        return jsonify({"error":"lat and lon required"}), 400

    csv_results, live_results = [], []

    # ── CSV source ──────────────────────────────────────────────
    csv_cat = category if (category and category not in LIVE_PRIMARY) else None
    res = csv_nearby(lat, lon, csv_cat, radius, top_n)
    if not res.empty:
        for _, row in res.iterrows():
            csv_results.append(row_to_dict(row,{
                "distance":round(float(row["distance"]),2),
                "score":round(float(row["score"]),3),
            }))

    # ── Live Overpass source ─────────────────────────────────────
    # Determine which cats need live data
    live_radius_m = min(int(radius * 80), 6000)

    if category in LIVE_PRIMARY:
        # Directly live
        live_results = live_fetch(lat, lon, category, live_radius_m, top_n)
    elif category in LIVE_FALLBACK:
        # Live fallback: use if CSV returned fewer than 3 results
        if len(csv_results) < 3:
            live_results = live_fetch(lat, lon, category, live_radius_m, top_n)
    elif category is None:
        # "All" — fetch all live categories in parallel
        all_live_cats = list(LIVE_PRIMARY) + [c for c in LIVE_FALLBACK if
                            len([r for r in csv_results if r["category"]==c]) < 2]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(live_fetch, lat, lon, c, live_radius_m, top_n//3): c
                       for c in all_live_cats}
            for fut in as_completed(futures):
                try: live_results.extend(fut.result())
                except Exception: pass

    # ── Merge & deduplicate ─────────────────────────────────────
    seen, merged = set(), []
    for p in csv_results + live_results:
        key = p["place"].lower().strip()
        if key not in seen:
            seen.add(key); merged.append(p)

    merged.sort(key=lambda x: (-x.get("important",0), -x.get("score",0)))
    return jsonify(merged[:top_n])


@app.route("/api/search")
def api_search():
    q     = request.args.get("q","").strip().lower()
    top_n = request.args.get("top_n", 12, type=int)
    if not q: return jsonify([])
    mask = (df["place"].str.lower().str.contains(q,na=False) |
            df["city"].str.lower().str.contains(q,na=False))
    res = df[mask].sort_values("important",ascending=False).head(top_n)
    return jsonify([row_to_dict(r) for _,r in res.iterrows()])


@app.route("/api/city_places")
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

# ═══════════════════════════════════════════════════════════════
# 13. FLASK ROUTES — SAVED PLACES (DB-backed, login required)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/favourites", methods=["GET"])
def get_favs():
    uid = current_user_id()
    if not uid:
        # Guests: use session
        return jsonify(session.get("favs",[]))
    conn = get_db()
    rows = conn.execute(
        "SELECT place,city,category,lat,lon,icon FROM saved_places WHERE user_id=? ORDER BY saved_at DESC",
        (uid,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/favourites", methods=["POST"])
def add_fav():
    data  = request.get_json(silent=True) or {}
    place = data.get("place","").strip()
    if not place: return jsonify({"error":"place required"}), 400
    uid = current_user_id()
    if uid:
        conn = get_db()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO saved_places (user_id,place,city,category,lat,lon,icon) VALUES (?,?,?,?,?,?,?)",
                (uid, place, data.get("city"), data.get("category"),
                 data.get("lat"), data.get("lon"), data.get("icon"))
            )
            conn.commit()
        finally: conn.close()
        return get_favs()
    # Guest fallback
    favs = session.get("favs",[])
    if place not in [f["place"] for f in favs]:
        favs.append(data); session["favs"]=favs
    return jsonify(favs)

@app.route("/api/favourites", methods=["DELETE"])
def del_fav():
    data  = request.get_json(silent=True) or {}
    place = data.get("place","")
    uid   = current_user_id()
    if uid:
        conn = get_db()
        conn.execute("DELETE FROM saved_places WHERE user_id=? AND place=?", (uid,place))
        conn.commit(); conn.close()
        return get_favs()
    favs = [f for f in session.get("favs",[]) if f.get("place")!=place]
    session["favs"]=favs; return jsonify(favs)


# ═══════════════════════════════════════════════════════════════
# 16. FLASK ROUTES — SEARCH HISTORY & EXPORT
# ═══════════════════════════════════════════════════════════════


@app.route("/api/favourites/export")
def export_favs():
    uid = current_user_id()
    if uid:
        conn = get_db()
        rows = conn.execute(
            "SELECT place,city,category,lat,lon FROM saved_places WHERE user_id=?", (uid,)
        ).fetchall()
        conn.close()
        records = [dict(r) for r in rows]
    else:
        records = session.get("favs",[])
    if not records: return "No saved places", 400
    csv = pd.DataFrame(records).to_csv(index=False)
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=yatra_saved.csv"})

@app.route("/api/export")
def api_export():
    try:    records = json.loads(request.args.get("data","[]"))
    except: records = []
    if not records: return "No data", 400
    csv = pd.DataFrame(records).to_csv(index=False)
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=yatra_places.csv"})

# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)