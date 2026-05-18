# ─────────────────────────────────────────────────────────────────
#  rating.py  —  Generate synthetic ratings dataset
#  Run ONCE after fetch_osm_places.py to create ratings.csv
#
#  Model: each place has a hidden "quality" score drawn from a
#  right-skewed Beta distribution. Users observe quality with
#  personal bias + Gaussian noise → realistic rating variance.
# ─────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

INPUT_CSV  = "india_places_dataset.csv"
OUTPUT_CSV = "ratings.csv"

NUM_USERS        = 100   # simulated users
RATINGS_PER_USER = 60    # each user rates this many places
RANDOM_SEED      = 42

# ── Load places ──────────────────────────────────────────────────
places = pd.read_csv(INPUT_CSV)
places = places.drop_duplicates(subset=["place", "city"]).reset_index(drop=True)
print(f"Loaded {len(places)} unique places")

np.random.seed(RANDOM_SEED)

# ── Assign latent quality to each place ──────────────────────────
# Beta(2, 1.5): most places are decent (3–4 stars), few are terrible/perfect
raw_quality  = np.random.beta(2, 1.5, size=len(places))
# Scale to 1–5 range
place_quality = raw_quality * 4 + 1
quality_map   = dict(zip(places["place"], place_quality))

# ── Generate ratings ─────────────────────────────────────────────
users = [f"U{i}" for i in range(1, NUM_USERS + 1)]
rows  = []

for user in users:
    # Personal rating bias: some users rate high (+0.5), some low (-0.5)
    user_bias = np.random.normal(0, 0.35)

    # Sample places without replacement (sparse = realistic)
    n = min(RATINGS_PER_USER, len(places))
    sampled = places.sample(n=n, replace=False)

    for _, row in sampled.iterrows():
        true_q = quality_map[row["place"]]
        noise  = np.random.normal(0, 0.45)
        raw    = true_q + user_bias + noise
        # Round to nearest 0.5, clip to [0.5, 5.0]
        rating = float(np.clip(round(raw * 2) / 2, 0.5, 5.0))
        rows.append({"user": user, "place": row["place"], "rating": rating})

# ── Save ─────────────────────────────────────────────────────────
rdf = pd.DataFrame(rows)
rdf.to_csv(OUTPUT_CSV, index=False)

print(f"\n✅ Generated {OUTPUT_CSV}")
print(f"   {NUM_USERS} users × {RATINGS_PER_USER} ratings = {len(rdf)} total rows")
print(f"\nRating distribution:")
print(rdf["rating"].value_counts().sort_index().to_string())
print(f"\nMean rating : {rdf['rating'].mean():.2f}")
print(f"Std dev     : {rdf['rating'].std():.2f}")

# Sanity check: top 10 places by avg rating
top = (
    rdf.groupby("place")["rating"]
    .agg(avg="mean", count="count")
    .query("count >= 5")
    .sort_values("avg", ascending=False)
    .head(10)
)
print(f"\nTop 10 places by avg rating:\n{top.round(2).to_string()}")