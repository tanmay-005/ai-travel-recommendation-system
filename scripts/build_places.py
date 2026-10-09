"""Build data/places.csv from OpenStreetMap: sights, nature and activities around India's travel hubs.

Run from the project root (venv active):
    python scripts/build_places.py --dry-run        # print one query, fetch nothing
    python scripts/build_places.py --city Manali    # fetch one city, to test
    python scripts/build_places.py                  # fetch every city (20-40 min)

Raw answers are cached in data/.cache/, so a rerun skips cities already fetched.
Delete that folder to force a fresh download.
"""
import argparse
import json
import math
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT       = Path(__file__).resolve().parent.parent
OUTPUT_CSV = ROOT / "data" / "places.csv"
CACHE_DIR  = ROOT / "data" / ".cache"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS   = {"User-Agent": "yatra-go/1.0 (student project, educational)"}
SLEEP     = 3.0   # seconds between requests, to be polite to the free API
MAX_RETRY = 2     # tries per mirror before moving to the next one
OFFLINE   = False # set by --offline: use only cached answers, never contact the servers

# Travel hubs: name -> (lat, lon) of the centre. Places are fetched in a circle around each one.
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
    "Ujjain"             : (23.1765, 75.7885),
    "Raipur"             : (21.2514, 81.6296),
    "Gangtok"            : (27.3389, 88.6065),
    "Kasol"              : (32.0100, 77.3150),
    "Bir"                : (32.0420, 76.7230),
    "Kaza"               : (32.2276, 78.0710),
    "Auli"               : (30.5280, 79.5660),
    "Mount Abu"          : (24.5926, 72.7156),
    "Lonavala"           : (18.7546, 73.4062),
    "Gokarna"            : (14.5479, 74.3188),
    "Madikeri"           : (12.4244, 75.7382),   # Coorg
    "Kodaikanal"         : (10.2381, 77.4892),
    "Wayanad"            : (11.6854, 76.1320),
    "Puducherry"         : (11.9416, 79.8083),
    "Port Blair"         : (11.6234, 92.7265),
    "Tawang"             : (27.5860, 91.8590),
    "Kaziranga"          : (26.5775, 93.1711),
}

# What a traveller wants, in three kinds.
# Each filter is (OSM key, allowed values, extra condition).
# The extra condition ["wikidata"] keeps only well-known examples of very common things,
# so we get the Golden Temple but not every neighbourhood shrine.
KINDS = {
    "sight": {
        "radius_km": 15,
        "filters": [
            ("historic", "fort|castle|monument|ruins|archaeological_site|tomb", ""),
            ("tourism",  "museum|viewpoint|attraction", ""),
            ("amenity",  "place_of_worship", '["wikidata"]'),
        ],
    },
    "nature": {
        "radius_km": 40,
        "filters": [
            ("natural",  "waterfall|peak|cave_entrance|beach|hot_spring", ""),
            ("waterway", "waterfall", ""),
            ("water",    "lake", ""),
            ("leisure",  "park|garden", '["wikidata"]'),
        ],
    },
    "activity": {
        "radius_km": 30,
        "filters": [
            ("tourism",  "camp_site|zoo|theme_park|aquarium", ""),
            ("leisure",  "water_park|nature_reserve", ""),
            ("boundary", "national_park", ""),
            ("route",    "hiking", ""),
            ("sport",    "climbing|canoe|paragliding|scuba_diving", ""),
        ],
    },
}

# Friendly category for today's sidebar pills (subtype -> category).
# Anything not listed falls back to the kind: nature -> Nature, activity -> Activity.
CATEGORY = {
    "fort": "Heritage", "castle": "Heritage", "monument": "Heritage", "ruins": "Heritage",
    "archaeological_site": "Heritage", "tomb": "Heritage", "attraction": "Heritage",
    "museum": "Museum", "viewpoint": "Viewpoint", "place_of_worship": "Temple",
    "beach": "Beach",
}

# Names that are just a type or a number (e.g. "Temple", "Lake", "2620") tell a traveller nothing.
GENERIC_NAMES = {"temple", "tomb", "tank", "lake", "peak", "waterfall", "fort", "park",
                 "viewpoint", "view point", "museum", "ruins", "cave"}

def is_valid(name):
    """Skip unnamed places and names written mostly in non-Latin, non-Devanagari scripts."""
    if not name or len(name.strip()) < 3:
        return False
    clean = name.strip().lower()
    if clean in GENERIC_NAMES or re.sub(r"[\s.,\-]", "", clean).isdigit():
        return False
    foreign = re.sub(r"[\x20-\x7E\u0900-\u097F\d\s\-\'\.(),&/]", "", name)
    return len(foreign) / max(len(name), 1) < 0.35


def bbox(lat, lon, radius_km):
    """A square box around (lat, lon), as (south, west, north, east).
    Overpass searches a box much faster than a circle; to_row() trims the corners later."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return f"{lat - dlat:.4f},{lon - dlon:.4f},{lat + dlat:.4f},{lon + dlon:.4f}"


def build_query(kind, lat, lon, part=None):
    """Overpass query for one kind in a box around (lat, lon).
    part=None asks for every filter at once; part=i asks for only filter i (a lighter query)."""
    spec    = KINDS[kind]
    box     = bbox(lat, lon, spec["radius_km"])
    filters = spec["filters"] if part is None else [spec["filters"][part]]
    lines   = [
        f'  nwr["{key}"~"^({values})$"]["name"]{extra}({box});'
        for key, values, extra in filters
    ]
    return "[out:json][timeout:120];\n(\n" + "\n".join(lines) + "\n);\nout tags center;"


def fetch(query):
    """POST the query to Overpass, trying each mirror with retries. Returns a list of elements."""
    for mirror in OVERPASS_MIRRORS:
        for attempt in range(1, MAX_RETRY + 1):
            try:
                r = requests.post(mirror, data={"data": query}, headers=HEADERS, timeout=150)
                if r.status_code in (429, 502, 503, 504):
                    wait = 15 * attempt
                    print(f"    {mirror.split('/')[2]} busy ({r.status_code}), waiting {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json().get("elements", [])
            except requests.RequestException as e:
                print(f"    {mirror.split('/')[2]} attempt {attempt}: {type(e).__name__}")
                time.sleep(5 * attempt)
    raise RuntimeError("all Overpass mirrors failed")


def fetch_cached(city, kind, lat, lon):
    """Fetch one city+kind, reusing saved answers from earlier runs.
    Each filter is fetched (and saved) separately, so one heavy filter can't sink the rest.
    Returns (elements, fetched_anything_new), or (None, ...) if some filter still failed."""
    stem = f"{city.replace(' ', '_')}_{kind}"
    done = CACHE_DIR / f"{stem}.json"
    if done.exists():                       # whole kind finished in an earlier run
        return json.loads(done.read_text(encoding="utf-8")), False

    elements, fetched, failed = [], False, False
    for i in range(len(KINDS[kind]["filters"])):
        part = CACHE_DIR / f"{stem}_{i}.json"
        if part.exists():
            elements += json.loads(part.read_text(encoding="utf-8"))
            continue
        if OFFLINE:
            failed = True
            continue
        try:
            got = fetch(build_query(kind, lat, lon, part=i))
        except RuntimeError:
            failed = True
            continue
        part.write_text(json.dumps(got), encoding="utf-8")
        elements += got
        fetched = True
        time.sleep(SLEEP)

    if failed:
        return None, fetched
    done.write_text(json.dumps(elements), encoding="utf-8")   # all parts done: save as one file
    for i in range(len(KINDS[kind]["filters"])):
        (CACHE_DIR / f"{stem}_{i}.json").unlink(missing_ok=True)
    return elements, fetched


def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def subtype_of(tags, kind):
    """Which of this kind's filters matched, e.g. 'waterfall' or 'fort'."""
    for key, values, _ in KINDS[kind]["filters"]:
        value = tags.get(key, "")
        if re.fullmatch(values, value):
            if key == "route":
                return "hiking_route"
            return value
    return None


def to_row(element, city, kind, clat, clon):
    """Turn one Overpass element into one CSV row, or None if it isn't usable."""
    tags = element.get("tags", {})
    name = tags.get("name:en") or tags.get("name")
    if not is_valid(name):
        return None
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")
    subtype = subtype_of(tags, kind)
    if lat is None or lon is None or subtype is None:
        return None

    dist_km = km_between(clat, clon, float(lat), float(lon))
    if dist_km > KINDS[kind]["radius_km"]:      # outside the circle: a corner of the search box
        return None

    has_wiki = int("wikipedia" in tags or "wikidata" in tags)
    return {
        "osm_id":        f"{element['type'][0]}{element['id']}",
        "place":         name.strip(),
        "city":          city,
        "lat":           round(float(lat), 6),
        "lon":           round(float(lon), 6),
        "kind":          kind,
        "subtype":       subtype,
        "category":      CATEGORY.get(subtype, kind.title()),
        "has_wiki":      has_wiki,
        "heritage":      int("heritage" in tags),
        "tag_count":     len(tags),
        "description":   (tags.get("description:en") or tags.get("description") or "")[:300],
        "opening_hours": tags.get("opening_hours", ""),
        "fee":           tags.get("fee", ""),
        "important":     has_wiki,   # temporary: keeps today's "landmark" badge working until phase 5
        "dist_km":       round(dist_km, 2),
    }


def build(cities):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    rows, failed = [], []
    for i, (city, (clat, clon)) in enumerate(cities.items(), 1):
        counts = {}
        for kind in KINDS:
            elements, _ = fetch_cached(city, kind, clat, clon)
            if elements is None:
                failed.append(f"{city} ({kind})")
                counts[kind] = "FAILED"
                continue
            new = [r for e in elements if (r := to_row(e, city, kind, clat, clon))]
            rows.extend(new)
            counts[kind] = len(new)
        print(f"[{i:>2}/{len(cities)}] {city:<20} " +
              "  ".join(f"{k} {n:>4}" for k, n in counts.items()), flush=True)

    if failed:
        reason = "not in the cache yet" if OFFLINE else "servers too busy"
        print(f"\n{len(failed)} still missing ({reason}): {', '.join(failed)}")
        print("Everything else is saved. Run without --offline later to fetch just these.")

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # A place near two hubs (Delhi and Noida) was fetched twice: keep it under the nearer hub.
    df = df.sort_values("dist_km").drop_duplicates("osm_id", keep="first")
    # The same spot is sometimes mapped twice (a point and an outline): keep one.
    # The same place is often mapped twice under one name (a fort and a "viewpoint" on it, or a
    # point and an outline). Same name, same hub, within 1 km = one place: keep the best-documented.
    df = drop_near_duplicates(df)
    return df.drop(columns="dist_km").sort_values(["city", "kind", "place"]).reset_index(drop=True)


def drop_near_duplicates(df, within_km=1.0):
    """Merge rows that are really one place. Best-documented copy wins (Wikipedia link, then most tags)."""
    df = df.sort_values(["has_wiki", "tag_count"], ascending=False)

    # Treks: a long route is often mapped as several pieces with one name -> one row per trek name.
    treks = df[df["subtype"] == "hiking_route"]
    treks = treks[~treks.assign(name=treks["place"].str.lower()).duplicated(["name", "city"])]

    # Everything else: same name, same hub, within 1 km -> one place (e.g. Amber Fort + its "viewpoint").
    others = df[df["subtype"] != "hiking_route"]
    keep = []
    for _, group in others.groupby([others["place"].str.lower(), "city"], sort=False):
        kept = []
        for idx, row in group.iterrows():
            if all(km_between(row.lat, row.lon, k.lat, k.lon) > within_km for k in kept):
                kept.append(row)
                keep.append(idx)
    return pd.concat([treks, others.loc[keep]])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", help="fetch only this city (must be a key in CITIES)")
    parser.add_argument("--dry-run", action="store_true", help="print one query and stop")
    parser.add_argument("--offline", action="store_true",
                        help="rebuild the CSV from cached answers only, without contacting the servers")
    args = parser.parse_args()

    global OFFLINE
    OFFLINE = args.offline

    if args.dry_run:
        lat, lon = CITIES["Manali"]
        print(build_query("nature", lat, lon))
        return

    cities = CITIES
    if args.city:
        if args.city not in CITIES:
            raise SystemExit(f"Unknown city {args.city!r}. Pick one of: {', '.join(CITIES)}")
        cities = {args.city: CITIES[args.city]}

    df = build(cities)
    if df.empty:
        raise SystemExit("No places found - nothing written.")
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\nWrote {len(df):,} places in {df['city'].nunique()} cities to {OUTPUT_CSV.relative_to(ROOT)}")
    print("\nBy kind:\n" + df["kind"].value_counts().to_string())
    print("\nTop subtypes:\n" + df["subtype"].value_counts().head(15).to_string())
    print(f"\nWith a Wikipedia/Wikidata link: {df['has_wiki'].sum():,} ({df['has_wiki'].mean():.0%})")


if __name__ == "__main__":
    main()