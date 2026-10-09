"""Loads the places CSV and answers questions about it."""
import pandas as pd

from yatra.config import Config
from yatra.geo import haversine


# LOAD THE CSV (already cleaned by scripts/build_places.py)
df = pd.read_csv(Config.PLACES_CSV)
df = df.dropna(subset=["place", "lat", "lon", "city"])
TEXT_COLS = ["description", "opening_hours", "fee"]
df[TEXT_COLS] = df[TEXT_COLS].fillna("")
df["category_clean"] = df["category"]


ICONS = {
    "Heritage":"🏛️","Museum":"🏺","Temple":"🛕","Viewpoint":"🌅",
    "Beach":"🏖️","Food":"🍽️","Cafe":"☕","Shopping":"🛍️",
    "Nature":"🌿","Activity":"🧗","Other":"📍",
}

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