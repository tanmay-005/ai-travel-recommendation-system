import requests
import pandas as pd
import time

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HEADERS = {
    "User-Agent": "india-travel-recommender/1.0"
}

RADIUS = 30000  # 30 km search radius

# Major Indian cities
CITIES = {

    # Delhi
    "Delhi": (28.6139, 77.2090),
    "New Delhi": (28.6139, 77.2090),
    "Dwarka": (28.5921, 77.0460),
    "Rohini": (28.7495, 77.0565),
    "Karol Bagh": (28.6519, 77.1909),

    # Maharashtra
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Nagpur": (21.1458, 79.0882),
    "Nashik": (19.9975, 73.7898),
    "Aurangabad": (19.8762, 75.3433),

    # Rajasthan
    "Jaipur": (26.9124, 75.7873),
    "Udaipur": (24.5854, 73.7125),
    "Jodhpur": (26.2389, 73.0243),
    "Jaisalmer": (26.9157, 70.9083),
    "Ajmer": (26.4499, 74.6399),

    # Uttar Pradesh
    "Agra": (27.1767, 78.0081),
    "Varanasi": (25.3176, 82.9739),
    "Lucknow": (26.8467, 80.9462),
    "Prayagraj": (25.4358, 81.8463),
    "Mathura": (27.4924, 77.6737),

    # Karnataka
    "Bangalore": (12.9716, 77.5946),
    "Mysore": (12.2958, 76.6394),
    "Mangalore": (12.9141, 74.8560),
    "Hubli": (15.3647, 75.1240),
    "Belgaum": (15.8497, 74.4977),

    # Telangana
    "Hyderabad": (17.3850, 78.4867),
    "Warangal": (17.9784, 79.5941),
    "Nizamabad": (18.6725, 78.0941),
    "Karimnagar": (18.4386, 79.1288),
    "Khammam": (17.2473, 80.1514),

    # Tamil Nadu
    "Chennai": (13.0827, 80.2707),
    "Madurai": (9.9252, 78.1198),
    "Coimbatore": (11.0168, 76.9558),
    "Salem": (11.6643, 78.1460),
    "Tiruchirappalli": (10.7905, 78.7047),

    # West Bengal
    "Kolkata": (22.5726, 88.3639),
    "Haldia": (22.0667, 88.0698),
    "Digha": (21.6237, 87.5070),
    "Siliguri": (26.7271, 88.3953),
    "Darjeeling": (27.0360, 88.2627),

    # Goa
    "Panaji": (15.4909, 73.8278),
    "Margao": (15.2832, 73.9862),
    "Vasco da Gama": (15.3950, 73.8156),
    "Mapusa": (15.5916, 73.8089),
    "Calangute": (15.5444, 73.7550),

    # Punjab
    "Chandigarh": (30.7333, 76.7794),
    "Mohali": (30.7046, 76.7179),
    "Amritsar": (31.6340, 74.8723),
    "Ludhiana": (30.9000, 75.8573),
    "Patiala": (30.3398, 76.3869),
    "Jalandhar": (31.3260, 75.5762),
    "Bathinda": (30.2110, 74.9455),

    #Haryana
    "Panchkula": (30.6942, 76.8606),
    "Ambala": (30.3752, 76.7821),
    "Kurukshetra": (29.9695, 76.8783),

    # Uttarakhand
    "Rishikesh": (30.0869, 78.2676),
    "Haridwar": (29.9457, 78.1642),
    "Dehradun": (30.3165, 78.0322),
    "Mussoorie": (30.4598, 78.0644),
    "Nainital": (29.3919, 79.4542),

    # Himachal Pradesh
    "Manali": (32.2432, 77.1892),
    "Shimla": (31.1048, 77.1734),
    "Dharamshala": (32.2190, 76.3234),
    "Kullu": (31.9578, 77.1095),
    "Solan": (30.9045, 77.0967),

    # Odisha
    "Bhubaneswar": (20.2961, 85.8245),
    "Puri": (19.8135, 85.8312),
    "Cuttack": (20.4625, 85.8830),
    "Konark": (19.8876, 86.0945),
    "Rourkela": (22.2604, 84.8536),

    # Jammu & Kashmir / Ladakh
    "Srinagar": (34.0837, 74.7973),
    "Jammu": (32.7266, 74.8570),
    "Gulmarg": (34.0484, 74.3805),
    "Pahalgam": (34.0159, 75.3180),
    "Leh": (34.1526, 77.5770),

    # Northeast India
    "Guwahati": (26.1445, 91.7362),
    "Shillong": (25.5788, 91.8933),
    "Imphal": (24.8170, 93.9368),
    "Aizawl": (23.7271, 92.7176),
    "Kohima": (25.6751, 94.1086)

}

# Categories to fetch
CATEGORIES = [
    ("tourism", "attraction"),
    ("tourism", "museum"),
    ("tourism", "viewpoint"),
    ("historic", "monument"),
    ("amenity", "restaurant"),
    ("amenity", "cafe"),
    ("shop", "mall"),
    ("shop", "clothes"),
    ("leisure", "park"),
    ("leisure", "garden")
]


def fetch_places(lat, lon, key, value):

    query = f"""
    [out:json][timeout:25];
    (
      node["{key}"="{value}"](around:{RADIUS},{lat},{lon});
      way["{key}"="{value}"](around:{RADIUS},{lat},{lon});
      relation["{key}"="{value}"](around:{RADIUS},{lat},{lon});
    );
    out center tags;
    """

    response = requests.get(
        OVERPASS_URL,
        params={"data": query},
        headers=HEADERS
    )

    response.raise_for_status()

    return response.json()["elements"]


def parse_elements(elements, city, category):

    rows = []

    for e in elements:

        tags = e.get("tags", {})

        name = tags.get("name")

        if not name:
            continue

        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")

        if not lat or not lon:
            continue

        rows.append({
            "place": name,
            "category": category,
            "city": city,
            "lat": lat,
            "lon": lon
        })

    return rows


def main():

    all_rows = []

    for city, (lat, lon) in CITIES.items():

        print(f"\nFetching places for {city}")

        for key, value in CATEGORIES:

            category_name = f"{key}:{value}"

            try:

                print(f"Fetching {category_name}")

                elements = fetch_places(lat, lon, key, value)

                rows = parse_elements(elements, city, category_name)

                print(f"Found {len(rows)} places")

                all_rows.extend(rows)

                time.sleep(2)

            except Exception as e:

                print("Error:", e)

    df = pd.DataFrame(all_rows)

    # Remove duplicates
    df = df.drop_duplicates(subset=["place", "city"])

    df.to_csv("india_places_dataset.csv", index=False)

    print("\nDataset saved as india_places_dataset.csv")
    print("Total places:", len(df))


if __name__ == "__main__":
    main()