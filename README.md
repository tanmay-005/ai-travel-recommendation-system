# 🌍 AI-Powered Travel Recommendation System

A **location-aware travel recommendation platform** that suggests nearby tourist attractions, restaurants, parks, and marketplaces based on a user's **current location and preferences**.

The system integrates **geospatial filtering, machine learning–based recommendation techniques, and interactive map visualization** to help travelers discover relevant destinations efficiently.

---

# 🚀 Features

✔ **Location-Based Recommendations**
Suggests nearby places based on the user's latitude and longitude.

✔ **Hybrid Recommendation Engine**
Combines:

* Content-Based Filtering
* Collaborative Filtering
* Distance-Based Ranking

✔ **Interactive Map Interface**
Visualizes recommended places using **Leaflet.js and OpenStreetMap**.

✔ **Route Navigation**
Displays directions from the user's location to the selected destination.

✔ **Multi-City Dataset Generation**
Automatically collects tourism data using **OpenStreetMap Overpass API**.

✔ **User Rating System**
Simulated ratings dataset used for collaborative filtering.

---

# 🧠 System Architecture

```
User Interface (HTML / CSS / JavaScript)
            │
            ▼
Flask Backend (REST API)
            │
            ▼
Recommendation Engine
 ├── Content-Based Filtering
 ├── Collaborative Filtering
 └── Location-Based Filtering
            │
            ▼
Dataset (OpenStreetMap + Generated Ratings)
```

---

# 🛠️ Technologies Used

### Backend

* Python
* Flask
* Pandas
* NumPy
* Scikit-learn

### Frontend

* HTML
* CSS
* JavaScript

### Maps & Geospatial

* Leaflet.js
* OpenStreetMap
* Leaflet Routing Machine

### Data Collection

* Overpass API (OpenStreetMap)

---

# 📊 Machine Learning Techniques

### Content-Based Filtering

Analyzes place attributes such as **category, tags, and descriptions** to recommend similar locations.

### Collaborative Filtering

Uses **user rating patterns** to suggest locations liked by users with similar preferences.

### Location-Based Filtering

Uses the **Haversine Distance Formula** to prioritize places closest to the user.

---

# 📂 Project Structure

```
ai-travel-recommendation-system
│
├── app.py                     # Flask backend server
├── fetch_osm_places.py        # Script to collect place data from OSM
├── generate_ratings.py        # Script to generate user ratings dataset
│
├── india_places_dataset.csv   # Places dataset
├── ratings.csv                # User ratings dataset
│
├── templates
│   └── index.html             # Frontend UI
│
├── requirements.txt
└── README.md
```

---

# 📍 How It Works

1️⃣ User shares location or searches a city
2️⃣ Backend receives coordinates
3️⃣ Nearby places are filtered using geospatial distance
4️⃣ Recommendation engine ranks results
5️⃣ Results are displayed on an interactive map
6️⃣ Users can click a place to view **navigation routes**

---

# ⚙️ Installation & Setup

Clone the repository:

```bash
git clone https://github.com/tanmay-005/ai-travel-recommendation-system.git
cd ai-travel-recommendation-system
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```

---

# 📈 Future Improvements

* Real user review integration
* Sentiment analysis for travel reviews
* AI-based itinerary planner
* Mobile application version
* Personalized travel trend prediction
* Advanced deep learning recommender models

---

# 👨‍💻 Author

**Tanmay Rana**

GitHub:
https://github.com/tanmay-005

---

⭐ If you found this project useful, consider giving it a **star**!
