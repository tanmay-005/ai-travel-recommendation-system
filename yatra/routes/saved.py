"""A user's saved places (the bag)."""
import pandas as pd
from flask import Blueprint, Response, jsonify, request, session

from yatra.db import get_db
from yatra.routes.auth import current_user_id

bp = Blueprint("saved", __name__, url_prefix="/api/favourites")

@bp.route("", methods=["GET"])
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

@bp.route("", methods=["POST"])
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


@bp.route("", methods=["DELETE"])
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

@bp.route("/export", methods=["GET"])
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