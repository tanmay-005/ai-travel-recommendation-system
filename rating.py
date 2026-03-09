import pandas as pd
import random

places = pd.read_csv("india_places_dataset.csv")

places = places.drop_duplicates(subset=["place","city"])

users = [f"U{i}" for i in range(1,101)]

ratings_data = []

for user in users:
    for _, row in places.iterrows():

        rating = round(random.uniform(0.5,5.0),1)

        ratings_data.append({
            "user": user,
            "place": row["place"],
            "rating": rating
        })

ratings_df = pd.DataFrame(ratings_data)

ratings_df.to_csv("ratings.csv", index=False)

print("Dataset generated successfully!")
print("Total rows:", len(ratings_df))