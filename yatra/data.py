"""Loads the places CSV and answers questions about it."""
import pandas as pd

from yatra.config import Config


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