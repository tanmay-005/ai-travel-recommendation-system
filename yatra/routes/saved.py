"""My Bag: the places a logged-in traveller has saved."""
import re

from flask import Blueprint, jsonify, request

from yatra.db import get_db
from yatra.routes.auth import current_user_id, login_required, now_iso

bp = Blueprint("saved", __name__, url_prefix="/api/saved")
OSM_ID_RE = re.compile(r"^[nwr]\d{1,15}$")     # n = node, w = way, r = relation


@bp.route("", methods=["GET"])
@login_required
def list_saved():
    conn = get_db()
    rows = conn.execute(
        "SELECT osm_id, place, destination, label, lat, lon, saved_at FROM bag_items "
        "WHERE user_id=? ORDER BY saved_at DESC", (current_user_id(),)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("", methods=["POST"])
@login_required
def save_place():
    data        = request.get_json(silent=True) or {}
    osm_id      = str(data.get("osm_id") or "")
    place       = str(data.get("place") or "").strip()[:200]
    destination = str(data.get("destination") or "").strip()[:100]
    label       = str(data.get("label") or "").strip()[:50]
    try:
        lat, lon = float(data.get("lat")), float(data.get("lon"))
    except (TypeError, ValueError):
        lat = lon = None
    if (not OSM_ID_RE.match(osm_id) or not place or lat is None
            or not (-90 <= lat <= 90 and -180 <= lon <= 180)):
        return jsonify({"error": "osm_id, place, lat and lon are required"}), 400

    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO bag_items (user_id, osm_id, place, destination, label, lat, lon, saved_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (current_user_id(), osm_id, place, destination, label, lat, lon, now_iso()),
    )
    conn.commit()
    conn.close()
    return jsonify({"saved": True, "osm_id": osm_id}), 201


@bp.route("/<osm_id>", methods=["DELETE"])
@login_required
def remove_place(osm_id):
    conn = get_db()
    conn.execute("DELETE FROM bag_items WHERE user_id=? AND osm_id=?", (current_user_id(), osm_id))
    conn.commit()
    conn.close()
    return jsonify({"saved": False, "osm_id": osm_id})