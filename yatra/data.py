"""Loads the places CSV and answers questions about it."""
import pandas as pd

from yatra.config import Config
from yatra.geo import haversine


# LOAD & CLEAN CSV
df = pd.read_csv(Config.PLACES_CSV)
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


ICONS = {
    "Heritage":"🏛️","Museum":"🏺","Temple":"🛕","Viewpoint":"🌅",
    "Beach":"🏖️","Food":"🍽️","Cafe":"☕","Shopping":"🛍️",
    "Nature":"🌿","Other":"📍",
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