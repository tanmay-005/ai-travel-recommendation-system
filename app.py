# app.py
from flask import Flask, request, jsonify, render_template
import pandas as pd
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import math

app = Flask(__name__)

# --------------------------------
# Load datasets
# --------------------------------

DATA_DIR = Path(__file__).parent
PLACES_CSV = DATA_DIR / "india_places_dataset.csv"
RATINGS_CSV = DATA_DIR / "ratings.csv"

places_df = pd.read_csv(PLACES_CSV)

# Remove bad rows
places_df = places_df.dropna(subset=["place", "lat", "lon"])

places_df["lat"] = places_df["lat"].astype(float)
places_df["lon"] = places_df["lon"].astype(float)

# Load ratings (if exists)
try:
    ratings_df = pd.read_csv(RATINGS_CSV)
except:
    ratings_df = pd.DataFrame(columns=["user", "place", "rating"])

# --------------------------------
# Category Mapping
# --------------------------------

def map_category(cat):

    cat = str(cat).lower()

    if "tourism" in cat or "historic" in cat or "attraction" in cat:
        return "Heritage"

    if "restaurant" in cat or "cafe" in cat or "food" in cat:
        return "Food"

    if "shop" in cat or "mall" in cat or "market" in cat:
        return "Bazaar"

    if "park" in cat or "garden" in cat or "nature" in cat:
        return "Nature"

    return "Other"


places_df["category_clean"] = places_df["category"].apply(map_category)

# --------------------------------
# Content-Based Model
# --------------------------------

places_df["content"] = (
    places_df["category_clean"].astype(str) + " " +
    places_df["city"].astype(str)
)

tfidf = TfidfVectorizer(stop_words="english")

tfidf_matrix = tfidf.fit_transform(places_df["content"])

cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

place_indices = pd.Series(
    places_df.index,
    index=places_df["place"]
).drop_duplicates()

# --------------------------------
# Haversine Distance (Vectorized)
# --------------------------------

def haversine_vectorized(lat1, lon1, lat2, lon2):

    R = 6371

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2

    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    return R * c


# --------------------------------
# Routes
# --------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------
# Recommend Similar Places
# --------------------------------

@app.route("/recommend_by_place")
def recommend_by_place():

    place_name = request.args.get("place")

    if not place_name:
        return jsonify({"error": "Place name required"})

    matches = places_df[
        places_df["place"].str.lower().str.contains(place_name.lower())
    ]

    if matches.empty:
        return jsonify({"error": f"{place_name} not found"})

    idx = matches.index[0]

    sim_scores = list(enumerate(cosine_sim[idx]))

    sim_scores = sorted(sim_scores,
                        key=lambda x: x[1],
                        reverse=True)

    top_indices = [i for i, _ in sim_scores[1:6]]

    results = places_df.iloc[top_indices]["place"].tolist()

    return jsonify({
        "input": place_name,
        "recommendations": results
    })


# --------------------------------
# Collaborative Recommendation
# --------------------------------

@app.route("/recommend_for_user")
def recommend_for_user():

    user_id = request.args.get("user")

    if user_id not in ratings_df["user"].unique():
        return jsonify({"error": "User not found"})

    user_rated = ratings_df[
        ratings_df["user"] == user_id]["place"].tolist()

    top_places = ratings_df[
        ~ratings_df["place"].isin(user_rated)
    ]

    top_places = top_places.groupby("place")["rating"] \
        .mean().sort_values(ascending=False)

    recommendations = top_places.head(5).index.tolist()

    return jsonify({
        "input": user_id,
        "recommendations": recommendations
    })


# --------------------------------
# Location-Based Recommendation
# --------------------------------

@app.route("/recommend_nearby")
def recommend_nearby():

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    category = request.args.get("category")

    if lat is None or lon is None:
        return jsonify({"error": "Location required"})

    lat = float(lat)
    lon = float(lon)

    df = places_df.copy()

    # Filter category
    if category and category != "":
        df = df[df["category_clean"] == category]

    # Compute distances (FAST vectorized)
    df["distance"] = haversine_vectorized(
        lat,
        lon,
        df["lat"].values,
        df["lon"].values
    )

    df = df.sort_values("distance")

    results = df.head(5)[[
        "place",
        "city",
        "lat",
        "lon",
        "category_clean",
        "distance"
    ]]

    return jsonify(results.to_dict(orient="records"))


# --------------------------------

if __name__ == "__main__":
    app.run(debug=True)