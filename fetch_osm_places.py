# ─────────────────────────────────────────────────────────────────
#  fetch_osm_places.py  —  Yatra Data Collection  v5.0
#
#  WHY THE OLD SCRIPT WAS SLOW (4-5 hours):
#  Grid approach: 80 cities × ~10 grid points × 6 batches = 4,800 requests
#  At 3.5s sleep each = 4.7 hours
#
#  THIS VERSION: ~8 minutes total
#  Uses Overpass AREA queries — one query covers the ENTIRE city boundary
#  80 cities × 3 batches = 240 requests × 2s sleep = 8 minutes
#  AND gets better coverage (full city, not just near grid points)
#
#  HOW AREA QUERIES WORK:
#  Instead of (around:6000, lat, lon) which is a circle from one point,
#  we use:
#    area["name"="Jaipur"]["admin_level"~"6|8"]->.city;
#    node(area.city)["amenity"="cafe"]; out tags;
#  This fetches every cafe INSIDE Jaipur's administrative boundary.
#  One request = whole city. No grid needed.
# ─────────────────────────────────────────────────────────────────

import requests, pandas as pd, time, os, re, json

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS    = {"User-Agent": "yatra-india-travel/5.0 (student project, educational)"}
OUTPUT_CSV = "india_places_dataset.csv"
SLEEP      = 2.0    # seconds between requests (polite but fast)
MAX_RETRY  = 3

# ── Cities — just name + center coords (center used as fallback only) ──
CITIES = {
    # name used in Overpass area query MUST match OSM's name tag exactly
    "Delhi"              : (28.6139, 77.2090),
    "New Delhi"          : (28.6315, 77.2167),
    "Noida"              : (28.5355, 77.3910),
    "Gurgaon"            : (28.4595, 77.0266),
    "Agra"               : (27.1767, 78.0081),
    "Jaipur"             : (26.9124, 75.7873),
    "Udaipur"            : (24.5854, 73.7125),
    "Jodhpur"            : (26.2389, 73.0243),
    "Jaisalmer"          : (26.9157, 70.9083),
    "Ajmer"              : (26.4499, 74.6399),
    "Pushkar"            : (26.4898, 74.5511),
    "Bikaner"            : (28.0229, 73.3119),
    "Mumbai"             : (19.0760, 72.8777),
    "Pune"               : (18.5204, 73.8567),
    "Nagpur"             : (21.1458, 79.0882),
    "Nashik"             : (19.9975, 73.7898),
    "Aurangabad"         : (19.8762, 75.3433),
    "Varanasi"           : (25.3176, 82.9739),
    "Lucknow"            : (26.8467, 80.9462),
    "Prayagraj"          : (25.4358, 81.8463),
    "Mathura"            : (27.4924, 77.6737),
    "Vrindavan"          : (27.5794, 77.6964),
    "Kanpur"             : (26.4499, 80.3319),
    "Bangalore"          : (12.9716, 77.5946),
    "Mysore"             : (12.2958, 76.6394),
    "Mangalore"          : (12.9141, 74.8560),
    "Hampi"              : (15.3350, 76.4600),
    "Hubli"              : (15.3647, 75.1240),
    "Hyderabad"          : (17.3850, 78.4867),
    "Warangal"           : (17.9784, 79.5941),
    "Tirupati"           : (13.6288, 79.4192),
    "Vijayawada"         : (16.5062, 80.6480),
    "Visakhapatnam"      : (17.6868, 83.2185),
    "Chennai"            : (13.0827, 80.2707),
    "Madurai"            : ( 9.9252, 78.1198),
    "Coimbatore"         : (11.0168, 76.9558),
    "Thanjavur"          : (10.7870, 79.1378),
    "Mahabalipuram"      : (12.6269, 80.1927),
    "Ooty"               : (11.4102, 76.6950),
    "Salem"              : (11.6643, 78.1460),
    "Kochi"              : ( 9.9312, 76.2673),
    "Thiruvananthapuram" : ( 8.5241, 76.9366),
    "Munnar"             : (10.0889, 77.0595),
    "Alleppey"           : ( 9.4981, 76.3388),
    "Kozhikode"          : (11.2588, 75.7804),
    "Thrissur"           : (10.5276, 76.2144),
    "Kolkata"            : (22.5726, 88.3639),
    "Darjeeling"         : (27.0360, 88.2627),
    "Siliguri"           : (26.7271, 88.3953),
    "Howrah"             : (22.5958, 88.2636),
    "Panaji"             : (15.4909, 73.8278),
    "Margao"             : (15.2832, 73.9862),
    "Calangute"          : (15.5444, 73.7550),
    "Amritsar"           : (31.6340, 74.8723),
    "Chandigarh"         : (30.7333, 76.7794),
    "Ludhiana"           : (30.9000, 75.8573),
    "Jalandhar"          : (31.3260, 75.5762),
    "Rishikesh"          : (30.0869, 78.2676),
    "Haridwar"           : (29.9457, 78.1642),
    "Dehradun"           : (30.3165, 78.0322),
    "Mussoorie"          : (30.4598, 78.0644),
    "Nainital"           : (29.3919, 79.4542),
    "Manali"             : (32.2432, 77.1892),
    "Shimla"             : (31.1048, 77.1734),
    "Dharamshala"        : (32.2190, 76.3234),
    "Dalhousie"          : (32.5379, 75.9744),
    "Bhubaneswar"        : (20.2961, 85.8245),
    "Puri"               : (19.8135, 85.8312),
    "Konark"             : (19.8876, 86.0945),
    "Cuttack"            : (20.4625, 85.8830),
    "Srinagar"           : (34.0837, 74.7973),
    "Jammu"              : (32.7266, 74.8570),
    "Leh"                : (34.1526, 77.5770),
    "Guwahati"           : (26.1445, 91.7362),
    "Shillong"           : (25.5788, 91.8933),
    "Ahmedabad"          : (23.0225, 72.5714),
    "Surat"              : (21.1702, 72.8311),
    "Vadodara"           : (22.3072, 73.1812),
    "Somnath"            : (20.9022, 70.3722),
    "Dwarka"             : (22.2442, 68.9685),
    "Bhopal"             : (23.2599, 77.4126),
    "Indore"             : (22.7196, 75.8577),
    "Khajuraho"          : (24.8318, 79.9199),
    "Ujjain"             : (23.1765, 75.7885),
    "Raipur"             : (21.2514, 81.6296),
}

# ── 3 MEGA-BATCHES — each is ONE Overpass request per city ────────
# Grouping similar tags reduces total requests 6x vs one-per-tag

BATCHES = [
    # Batch 1: Heritage, culture, religion
    ("heritage_culture", {
        "node": [
            ("tourism","attraction"), ("historic","monument"),
            ("historic","fort"),      ("tourism","museum"),
            ("historic","temple"),    ("amenity","place_of_worship"),
            ("tourism","viewpoint"),
        ],
        "way": [
            ("tourism","attraction"), ("historic","monument"),
            ("historic","fort"),      ("tourism","museum"),
        ],
    }),

    # Batch 2: Food, cafes, nightlife
    ("food_drink", {
        "node": [
            ("amenity","restaurant"), ("amenity","cafe"),
            ("amenity","fast_food"),  ("amenity","bar"),
            ("amenity","food_court"), ("amenity","ice_cream"),
            ("amenity","bakery"),
        ],
        "way": [
            ("amenity","restaurant"), ("amenity","cafe"),
            ("amenity","fast_food"),
        ],
    }),

    # Batch 3: Nature, parks, shopping, leisure
    ("nature_leisure_shop", {
        "node": [
            ("leisure","park"),         ("leisure","garden"),
            ("natural","beach"),        ("natural","waterfall"),
            ("natural","peak"),         ("tourism","theme_park"),
            ("shop","mall"),            ("amenity","marketplace"),
            ("leisure","nature_reserve"),
        ],
        "way": [
            ("leisure","park"),         ("leisure","garden"),
            ("natural","beach"),        ("shop","mall"),
        ],
    }),
]

# Category clean mapping
CLEAN = {
    "tourism:attraction":"Heritage",   "historic:monument":"Heritage",
    "historic:fort":"Heritage",        "tourism:museum":"Museum",
    "historic:temple":"Temple",        "amenity:place_of_worship":"Temple",
    "tourism:viewpoint":"Viewpoint",   "amenity:restaurant":"Food",
    "amenity:cafe":"Cafe",             "amenity:fast_food":"Food",
    "amenity:bar":"Cafe",              "amenity:food_court":"Food",
    "amenity:ice_cream":"Cafe",        "amenity:bakery":"Cafe",
    "leisure:park":"Nature",           "leisure:garden":"Nature",
    "natural:beach":"Beach",           "natural:waterfall":"Nature",
    "natural:peak":"Nature",           "tourism:theme_park":"Heritage",
    "shop:mall":"Shopping",            "amenity:marketplace":"Shopping",
    "leisure:nature_reserve":"Nature",
}

# ── Landmark seeds ────────────────────────────────────────────────
LANDMARKS = [
    ("Taj Mahal","Agra",27.1751,78.0421),
    ("Agra Fort","Agra",27.1795,78.0211),
    ("Fatehpur Sikri","Agra",27.0945,77.6610),
    ("Red Fort","Delhi",28.6562,77.2410),
    ("Qutub Minar","Delhi",28.5244,77.1855),
    ("India Gate","Delhi",28.6129,77.2295),
    ("Humayun's Tomb","Delhi",28.5933,77.2507),
    ("Lotus Temple","Delhi",28.5535,77.2588),
    ("Akshardham Temple","Delhi",28.6127,77.2773),
    ("Chandni Chowk","Delhi",28.6506,77.2303),
    ("Jama Masjid","Delhi",28.6507,77.2334),
    ("Hawa Mahal","Jaipur",26.9239,75.8267),
    ("Amber Fort","Jaipur",26.9855,75.8513),
    ("City Palace Jaipur","Jaipur",26.9258,75.8237),
    ("Jantar Mantar Jaipur","Jaipur",26.9248,75.8242),
    ("Nahargarh Fort","Jaipur",26.9396,75.8133),
    ("Jaigarh Fort","Jaipur",26.9897,75.8361),
    ("Albert Hall Museum","Jaipur",26.9115,75.8192),
    ("Mehrangarh Fort","Jodhpur",26.2980,73.0188),
    ("Umaid Bhawan Palace","Jodhpur",26.2880,73.0408),
    ("City Palace Udaipur","Udaipur",24.5764,73.6834),
    ("Lake Palace Udaipur","Udaipur",24.5763,73.6802),
    ("Saheliyon ki Bari","Udaipur",24.5936,73.6820),
    ("Jaisalmer Fort","Jaisalmer",26.9124,70.9101),
    ("Gateway of India","Mumbai",18.9220,72.8347),
    ("Elephanta Caves","Mumbai",18.9633,72.9315),
    ("Chhatrapati Shivaji Terminus","Mumbai",18.9398,72.8355),
    ("Marine Drive","Mumbai",18.9439,72.8232),
    ("Siddhivinayak Temple","Mumbai",19.0169,72.8301),
    ("Juhu Beach","Mumbai",19.0969,72.8266),
    ("Kashi Vishwanath Temple","Varanasi",25.3109,82.9736),
    ("Dashashwamedh Ghat","Varanasi",25.3058,83.0109),
    ("Sarnath","Varanasi",25.3816,83.0243),
    ("Manikarnika Ghat","Varanasi",25.3076,83.0063),
    ("Assi Ghat","Varanasi",25.2941,83.0106),
    ("Dargah Sharif Ajmer","Ajmer",26.4555,74.6310),
    ("Brahma Temple Pushkar","Pushkar",26.4897,74.5511),
    ("Pushkar Lake","Pushkar",26.4892,74.5507),
    ("Virupaksha Temple","Hampi",15.3350,76.4592),
    ("Vittala Temple Hampi","Hampi",15.3355,76.4760),
    ("Charminar","Hyderabad",17.3616,78.4747),
    ("Golconda Fort","Hyderabad",17.3833,78.4011),
    ("Hussain Sagar","Hyderabad",17.4239,78.4738),
    ("Ramoji Film City","Hyderabad",17.2543,78.6820),
    ("Marina Beach","Chennai",13.0500,80.2824),
    ("Kapaleeshwarar Temple","Chennai",13.0339,80.2699),
    ("Fort St. George","Chennai",13.0802,80.2876),
    ("Victoria Memorial","Kolkata",22.5448,88.3426),
    ("Howrah Bridge","Kolkata",22.5851,88.3468),
    ("Dakshineswar Temple","Kolkata",22.6544,88.3577),
    ("Park Street","Kolkata",22.5537,88.3514),
    ("Fort Kochi","Kochi",9.9630,76.2425),
    ("Mattancherry Palace","Kochi",9.9572,76.2596),
    ("Mysore Palace","Mysore",12.3052,76.6552),
    ("Chamundeshwari Temple","Mysore",12.2723,76.6740),
    ("Brindavan Gardens","Mysore",12.4244,76.5673),
    ("Golden Temple","Amritsar",31.6200,74.8765),
    ("Jallianwala Bagh","Amritsar",31.6207,74.8760),
    ("Wagah Border","Amritsar",31.6046,74.5728),
    ("Lakshman Jhula","Rishikesh",30.1290,78.3248),
    ("Ram Jhula","Rishikesh",30.1200,78.3148),
    ("Triveni Ghat","Rishikesh",30.1143,78.3089),
    ("Har Ki Pauri","Haridwar",29.9584,78.1642),
    ("Rohtang Pass","Manali",32.3720,77.2415),
    ("Solang Valley","Manali",32.3174,77.1522),
    ("Hadimba Devi Temple","Manali",32.2417,77.1734),
    ("The Mall Shimla","Shimla",31.1048,77.1732),
    ("Christ Church Shimla","Shimla",31.1053,77.1724),
    ("Naina Devi Temple","Nainital",29.3940,79.4626),
    ("Naini Lake","Nainital",29.3920,79.4575),
    ("Baga Beach","Calangute",15.5543,73.7527),
    ("Basilica of Bom Jesus","Panaji",15.5009,73.9116),
    ("Se Cathedral Goa","Panaji",15.5007,73.9131),
    ("Jagannath Temple Puri","Puri",19.8047,85.8183),
    ("Sun Temple Konark","Konark",19.8876,86.0945),
    ("Lingaraja Temple","Bhubaneswar",20.2384,85.8336),
    ("Dal Lake","Srinagar",34.0947,74.8181),
    ("Nishat Bagh","Srinagar",34.1247,74.8595),
    ("Pangong Lake","Leh",33.7597,78.6724),
    ("Thiksey Monastery","Leh",33.9702,77.6695),
    ("Hemis Monastery","Leh",33.9177,77.6980),
    ("Khajuraho Temples","Khajuraho",24.8518,79.9199),
    ("Mahakal Temple Ujjain","Ujjain",23.1827,75.7682),
    ("Somnath Temple","Somnath",20.8880,70.4011),
    ("Dwarkadhish Temple","Dwarka",22.2381,68.9674),
    ("Brihadeeswarar Temple","Thanjavur",10.7827,79.1317),
    ("Shore Temple Mahabalipuram","Mahabalipuram",12.6167,80.1993),
    ("Meenakshi Temple","Madurai",9.9196,78.1194),
    ("Kamakhya Temple","Guwahati",26.1665,91.7082),
]

# ─────────────────────────────────────────────────────────────────

def is_valid(name):
    if not name or len(name.strip()) < 2:
        return False
    foreign = re.sub(r'[\x20-\x7E\u0900-\u097F\d\s\-\'\.(),&/]', '', name)
    return len(foreign) / max(len(name), 1) < 0.35


def build_area_query(city_name, node_tags, way_tags):
    """
    Build a single Overpass query that fetches all matching places
    INSIDE the named city's administrative boundary.
    Falls back to a 15km bounding-box if no area is found.
    """
    # Escape quotes in city name
    safe = city_name.replace('"', '\\"')

    node_lines = "\n".join(
        f'  node(area.a)["{k}"="{v}"];' for k, v in node_tags
    )
    way_lines = "\n".join(
        f'  way(area.a)["{k}"="{v}"];' for k, v in way_tags
    )

    return f"""[out:json][timeout:60];
(
  area["name"="{safe}"]["place"~"city|town|village"]->.a;
  area["name"="{safe}"]["admin_level"~"4|5|6|7|8"]->.a;
);
(
{node_lines}
{way_lines}
);
out center tags;"""


def build_bbox_fallback(lat, lon, node_tags, way_tags, radius=15000):
    """Fallback: simple radius query if area query finds nothing."""
    node_lines = "\n".join(
        f'  node["{k}"="{v}"](around:{radius},{lat},{lon});' for k, v in node_tags
    )
    way_lines = "\n".join(
        f'  way["{k}"="{v}"](around:{radius},{lat},{lon});' for k, v in way_tags
    )
    return f"""[out:json][timeout:45];
(
{node_lines}
{way_lines}
);
out center tags;"""


def fetch(query):
    for mirror in OVERPASS_MIRRORS:
        for attempt in range(1, MAX_RETRY + 1):
            try:
                r = requests.post(mirror, data={"data": query},
                                  headers=HEADERS, timeout=65)
                if r.status_code == 429:
                    wait = 8 * attempt
                    print(f"    ⏳ 429 rate limit, waiting {wait}s…")
                    time.sleep(wait)
                    continue
                if r.status_code in (502, 503, 504):
                    time.sleep(4 * attempt)
                    continue
                r.raise_for_status()
                data = r.json().get("elements", [])
                return data
            except requests.Timeout:
                print(f"    ⏱ Timeout attempt {attempt}/{MAX_RETRY}")
                time.sleep(4 * attempt)
            except Exception as e:
                print(f"    ✗ {e}")
                time.sleep(SLEEP)
                break
    return []


def parse(elements, city, all_tags):
    """Extract place rows from Overpass elements."""
    tag_set = {(k, v) for k, v in all_tags}
    rows = []
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name:en") or tags.get("name") or tags.get("brand")
        if not is_valid(name):
            continue
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if not lat or not lon:
            continue

        # Match the first tag that fits
        cat = "Other"
        for k, v in all_tags:
            if tags.get(k) == v:
                cat = CLEAN.get(f"{k}:{v}", "Other")
                break

        rows.append({
            "place"    : name.strip(),
            "category" : cat,
            "city"     : city,
            "lat"      : round(float(lat), 7),
            "lon"      : round(float(lon), 7),
            "important": 0,
        })
    return rows


# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    all_rows  = []
    done_keys = set()  # "CityName|BatchName"

    progress_file = "fetch_progress.json"
    if os.path.exists(OUTPUT_CSV):
        existing = pd.read_csv(OUTPUT_CSV)
        if "important" not in existing.columns:
            existing["important"] = 0
        all_rows = existing.to_dict("records")
        print(f"▶ Loaded {len(all_rows)} existing rows")

    if os.path.exists(progress_file):
        with open(progress_file) as f:
            done_keys = set(json.load(f))
        print(f"▶ {len(done_keys)} city×batch combos already done\n")

    # ── Layer 1: Landmark seeds ──────────────────────────────────
    print("━━━━ Seeding landmarks ━━━━")
    existing_names = {r["place"] for r in all_rows}
    added = 0
    for name, city, lat, lon in LANDMARKS:
        if name not in existing_names:
            all_rows.append({"place": name, "category": "Heritage",
                             "city": city, "lat": round(lat,7),
                             "lon": round(lon,7), "important": 1})
            added += 1
    print(f"  ✓ {added} landmark seeds\n")

    # ── Layer 2: Area queries per city ───────────────────────────
    print("━━━━ Area-based city sweep ━━━━")
    total = len(CITIES)
    total_new = 0

    for idx, (city, (clat, clon)) in enumerate(CITIES.items(), 1):
        city_new = 0

        for batch_name, tag_groups in BATCHES:
            key = f"{city}|{batch_name}"
            if key in done_keys:
                continue

            node_tags = tag_groups.get("node", [])
            way_tags  = tag_groups.get("way", [])
            all_tags  = node_tags + way_tags

            # Try area query first
            query    = build_area_query(city, node_tags, way_tags)
            elements = fetch(query)

            # If area query returned nothing, use radius fallback
            if not elements:
                print(f"  ⚠ Area query empty for {city}/{batch_name}, using radius fallback")
                query    = build_bbox_fallback(clat, clon, node_tags, way_tags)
                elements = fetch(query)

            rows = parse(elements, city, all_tags)
            all_rows.extend(rows)
            city_new += len(rows)
            done_keys.add(key)
            time.sleep(SLEEP)

        total_new += city_new
        pct = idx / total * 100
        bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
        print(f"[{bar}] {idx:>2}/{total} {city:<22} +{city_new} places")

        # Save every 5 cities
        if idx % 5 == 0 or idx == total:
            df_tmp = pd.DataFrame(all_rows)
            df_tmp = df_tmp.sort_values("important", ascending=False)
            df_tmp = df_tmp.drop_duplicates(subset=["place","city"], keep="first")
            df_tmp.to_csv(OUTPUT_CSV, index=False)
            with open(progress_file, "w") as f:
                json.dump(list(done_keys), f)
            print(f"  💾 Saved {len(df_tmp)} total rows")

    # Final
    final = pd.DataFrame(all_rows)
    final = final.sort_values("important", ascending=False)
    final = final.drop_duplicates(subset=["place","city"], keep="first")
    final.to_csv(OUTPUT_CSV, index=False)
    if os.path.exists(progress_file):
        os.remove(progress_file)

    print(f"\n{'━'*55}")
    print(f"✅  {len(final)} places · {final['city'].nunique()} cities")
    print(f"    Landmark seeds: {final['important'].sum()}")
    print(f"\nCategory breakdown:")
    print(final["category"].value_counts().to_string())
    print(f"\nTop 10 cities by cafe count:")
    print(final[final["category"]=="Cafe"]["city"].value_counts().head(10).to_string())


if __name__ == "__main__":
    import sys
    print("╔══════════════════════════════════════════╗")
    print("║  Yatra Data Fetcher  v5.0                ║")
    print("║  Est. time: 8-15 minutes (vs 4-5 hours)  ║")
    print("╚══════════════════════════════════════════╝\n")
    main()