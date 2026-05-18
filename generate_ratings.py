# import pandas as pd
# import numpy as np

# # Load your Jaipur places dataset
# places = pd.read_csv("places.csv")  # your OSM dataset

# # Define number of test users
# num_users = 5  # change as needed
# users = [f"U{i+1}" for i in range(num_users)]

# # Number of ratings per user
# ratings_per_user = 10  # can be more or less

# rows = []

# for user in users:
#     sampled_places = places["place"].sample(ratings_per_user, random_state=np.random.randint(10000))
#     for place in sampled_places:
#         rating = np.round(np.random.uniform(0, 5), 1)  # random float 0-5 with 1 decimal
#         rows.append({"user": user, "place": place, "rating": rating})

# # Create DataFrame and save
# ratings = pd.DataFrame(rows)
# ratings.to_csv("ratings.csv", index=False)
# print(f"Created new ratings.csv with {num_users} users and {ratings_per_user} ratings each.")
