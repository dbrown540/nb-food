#!/usr/bin/env python3
"""Build data/places.json and docs/index.html from OSM raw data + curated overlay.

Pipeline:  data/osm_raw.json  (fetched by scripts/fetch.sh)
         + data/curated.json  (hand-verified overlay: price, health fit, notes)
        -> data/places.json   (merged, deduped, walk-time annotated)
        -> docs/index.html    (self-contained browsable viewer)

Walk times are straight-line distance from 371 Columbus Ave at 80 m/min,
so treat them as a floor; hills and blocks add a minute or two.
"""
import json
import math
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = (37.79960, -122.40740)  # 371 Columbus Ave

GROCERY_SUBTYPES = {
    "supermarket", "greengrocer", "convenience", "deli", "butcher",
    "seafood", "bakery", "health_food", "frozen_food", "tea", "coffee",
    "wine", "alcohol",
}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[-/&+]", " ", s.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s)).strip()


def walk_minutes(lat: float, lon: float) -> int:
    dlat = math.radians(lat - HOME[0])
    dlon = math.radians(lon - HOME[1])
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(HOME[0])) * math.cos(math.radians(lat))
         * math.sin(dlon / 2) ** 2)
    meters = 6371000 * 2 * math.asin(math.sqrt(a))
    return max(1, round(meters / 80))


def address(tags: dict) -> str:
    num, street = tags.get("addr:housenumber"), tags.get("addr:street")
    return f"{num} {street}" if num and street else (street or "")


def category(tags: dict) -> tuple[str, str]:
    amenity = tags.get("amenity")
    if amenity in ("restaurant", "fast_food"):
        return "restaurant", amenity
    if amenity == "cafe":
        return "cafe", "cafe"
    return "grocery", tags.get("shop", "shop")


def main() -> None:
    raw = json.loads((ROOT / "data/osm_raw.json").read_text())["elements"]
    curated = json.loads((ROOT / "data/curated.json").read_text())
    overrides = {norm(k): v for k, v in curated["overrides"].items()}

    places, seen = [], set()
    for el in raw:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None:
            continue
        key = norm(name)
        if key in seen:  # e.g. node + way duplicates
            continue
        seen.add(key)
        cat, subtype = category(tags)
        if cat == "grocery" and subtype not in GROCERY_SUBTYPES:
            continue
        place = {
            "name": name,
            "category": cat,
            "subtype": subtype,
            "cuisine": tags.get("cuisine", "").replace("_", " "),
            "addr": address(tags),
            "walkMin": walk_minutes(lat, lon),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "hours": tags.get("opening_hours", ""),
            "website": tags.get("website", ""),
            "phone": tags.get("phone", ""),
        }
        place.update(overrides.get(key, {}))
        places.append(place)

    for extra in curated["extras"]:
        extra = dict(extra)
        extra["walkMin"] = walk_minutes(extra.pop("lat"), extra.pop("lon"))
        places.append(extra)

    places.sort(key=lambda p: (p["walkMin"], p["name"]))
    (ROOT / "data/places.json").write_text(
        json.dumps(places, indent=1, ensure_ascii=False))

    template = (ROOT / "scripts/viewer_template.html").read_text()
    payload = json.dumps(places, ensure_ascii=False).replace("<", "\\u003c")
    (ROOT / "docs/index.html").write_text(
        template.replace("/*__DATA__*/[]", payload))

    curated_count = sum(1 for p in places if "notes" in p)
    print(f"{len(places)} places -> data/places.json, docs/index.html "
          f"({curated_count} curated)")


if __name__ == "__main__":
    main()
