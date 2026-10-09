"""What counts as a travel place, and how to read one from OpenStreetMap.

Shared by scripts/build_places.py (offline build) and yatra/osm.py (live top-up),
so a place looks and ranks the same whichever way it was fetched.
"""
import math
import re

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


def build_query(kind, lat, lon, part=None, radius_km=None, timeout=120):
    """Overpass query for one kind in a box around (lat, lon).
    part=None asks for every filter at once; part=i asks for only filter i (a lighter query).
    radius_km defaults to the kind's own radius; the live top-up passes the user's search radius."""
    spec    = KINDS[kind]
    box     = bbox(lat, lon, radius_km or spec["radius_km"])
    filters = spec["filters"] if part is None else [spec["filters"][part]]
    lines   = [
        f'  nwr["{key}"~"^({values})$"]["name"]{extra}({box});'
        for key, values, extra in filters
    ]
    return f"[out:json][timeout:{timeout}];\n(\n" + "\n".join(lines) + "\n);\nout tags center;"


def subtype_of(tags, kind):
    """Which of this kind's filters matched, e.g. 'waterfall' or 'fort'."""
    for key, values, _ in KINDS[kind]["filters"]:
        value = tags.get(key, "")
        if re.fullmatch(values, value):
            if key == "route":
                return "hiking_route"
            return value
    return None


def element_to_place(element, kind, city=""):
    """Turn one Overpass element into a place dict (the columns of places.csv), or None if unusable."""
    tags = element.get("tags", {})
    name = tags.get("name:en") or tags.get("name")
    if not is_valid(name):
        return None
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")
    subtype = subtype_of(tags, kind)
    if lat is None or lon is None or subtype is None:
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
        "important":     has_wiki,
    }
