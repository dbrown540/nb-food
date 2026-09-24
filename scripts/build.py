#!/usr/bin/env python3
"""Build data/places.json and docs/index.html from OSM raw data + curated overlay.

Pipeline:  data/osm_raw.json  (fetched by scripts/fetch.sh; the North Beach bbox)
         + data/sf_places.json      (citywide OSM base, scripts/fetch_sf_pois.py)
           filtered to the walk-radius neighborhoods in EXPANSION, by polygon
         + data/neighborhoods.geojson (scripts/fetch_neighborhoods.py)
         + data/curated.json  (hand-verified overlay: price, notes, ...)
        -> data/places.json   (merged, deduped, walk-time + neighborhood annotated)
        -> docs/index.html    (self-contained browsable viewer)

Every place carries `neighborhood` (DataSF Analysis Neighborhood polygon; the
part of North Beach / Russian Hill north of Bay Street is labeled Fisherman's
Wharf) and `key`, the identifier the enrichment layers are keyed by. `key` is
the name, except when a second place with the same normalized name sits more
than DUP_M away from the first (chains: Starbucks, Subway...), in which case
it is "Name (address)" or "Name (lat,lon)". Same-name places within DUP_M are
node/way duplicates and are dropped.

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
EXPANSION = {"North Beach", "Chinatown", "Fisherman's Wharf", "Russian Hill"}  # pulled from the citywide base
DUP_M = 150  # same normalized name within this distance = the same place (node + way duplicates)

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


def meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 6371000 * 2 * math.asin(math.sqrt(a))


def point_in_ring(lat: float, lon: float, ring: list) -> bool:
    inside, j = False, len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


class Neighborhoods:
    """data/neighborhoods.geojson -> label(lat, lon). Polygons are tested outer ring
    minus holes; the Bay Street line splits Fisherman's Wharf off North Beach / Russian Hill."""

    def __init__(self, path: Path):
        doc = json.loads(path.read_text())
        self.polys, self.bay = [], None
        for f in doc["features"]:
            g, props = f["geometry"], f["properties"]
            if props.get("kind") == "split_line":
                self.bay = g["coordinates"]  # [[lon, lat], ...] sorted west -> east
            else:
                for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
                    self.polys.append((props["name"], poly))

    def north_of_bay(self, lat: float, lon: float) -> bool:
        pts = self.bay
        if lon <= pts[0][0]:
            line_lat = pts[0][1]
        elif lon >= pts[-1][0]:
            line_lat = pts[-1][1]
        else:
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                if x0 <= lon <= x1:
                    line_lat = y0 + (y1 - y0) * (lon - x0) / ((x1 - x0) or 1e-12)
                    break
        return lat > line_lat

    def label(self, lat: float, lon: float):
        for name, poly in self.polys:
            if point_in_ring(lat, lon, poly[0]) and not any(point_in_ring(lat, lon, h) for h in poly[1:]):
                if name in ("North Beach", "Russian Hill") and self.north_of_bay(lat, lon):
                    return "Fisherman's Wharf"
                return name
        return None


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
    nhoods = Neighborhoods(ROOT / "data/neighborhoods.geojson")

    places, seen = [], {}  # norm(name) -> [(lat, lon), ...] of places already in the set

    def key_for(name: str, lat: float, lon: float, addr: str):
        """None = same place already present; else the layer key for this place."""
        k = norm(name)
        prior = seen.setdefault(k, [])
        if any(meters(lat, lon, plat, plon) <= DUP_M for plat, plon in prior):
            return None
        prior.append((lat, lon))
        if len(prior) == 1:
            return name
        return f"{name} ({addr})" if addr else f"{name} ({lat:.5f},{lon:.5f})"
    for el in raw:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None:
            continue
        cat, subtype = category(tags)
        if cat == "grocery" and subtype not in GROCERY_SUBTYPES:
            continue
        key = key_for(name, lat, lon, address(tags))
        if key is None:  # e.g. node + way duplicates
            continue
        place = {
            "name": name,
            "key": key,
            "neighborhood": nhoods.label(lat, lon),
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
        place.update(overrides.get(norm(name), {}))
        places.append(place)

    for extra in curated["extras"]:
        extra = dict(extra)
        lat, lon = extra.pop("lat"), extra.pop("lon")
        extra["key"] = key_for(extra["name"], lat, lon, extra.get("addr", "")) or extra["name"]
        extra["neighborhood"] = nhoods.label(lat, lon)
        extra["walkMin"] = walk_minutes(lat, lon)
        places.append(extra)
    n_nb = len(places)

    # ---- walk-radius expansion: citywide OSM base, filtered by neighborhood polygon ----
    for r in json.loads((ROOT / "data/sf_places.json").read_text()):
        if not r["name"]:
            continue
        nhood = nhoods.label(r["lat"], r["lon"])
        if nhood not in EXPANSION:
            continue
        key = key_for(r["name"], r["lat"], r["lon"], r["addr"] or "")
        if key is None:  # already in the North Beach bbox set, or a node + way duplicate
            continue
        place = {
            "name": r["name"],
            "key": key,
            "neighborhood": nhood,
            "category": r["category"],
            "subtype": r["subtype"],
            "cuisine": r["cuisine"] or "",
            "addr": r["addr"] or "",
            "walkMin": walk_minutes(r["lat"], r["lon"]),
            "lat": round(r["lat"], 5),
            "lon": round(r["lon"], 5),
            "hours": r["opening_hours"] or "",
            "website": r["website"] or "",
            "phone": r["phone"] or "",
        }
        place.update(overrides.get(norm(r["name"]), {}))
        places.append(place)

    # ---- optional enrichment layers (each produced by its own script; merged by POI name) ----
    def load(p):
        f = ROOT / p
        return json.loads(f.read_text()) if f.exists() else None
    risk = (load("data/crime/poi_street_risk.json") or {}).get("pois", {})
    insp = load("data/inspections/poi_inspections.json") or {}
    menus = {m.get("name"): m for m in (load("data/menus/index.json") or []) if isinstance(m, dict)}
    products = {d["name"]: (f.stem, d) for f in sorted((ROOT / "data/products").glob("*.json"))
                for d in [json.loads(f.read_text())]}
    for p in places:
        r = risk.get(p["key"])
        if r:
            p["risk"] = {k: r.get(k) for k in ("violent", "property", "drug", "total", "per_month", "percentile", "nearest_incident_m")}
        i = insp.get(p["key"])
        if i and i.get("match_confidence") not in (None, "none"):
            p["inspection"] = {k: i.get(k) for k in ("last_score", "last_score_date", "last_inspection_date", "last_inspection_type", "violation_count_last", "last_status", "last_status_date", "closures_all_time", "conditional_pass_all_time", "high_risk_count_all_time", "worst_score_all_time", "inspections_total", "match_confidence", "dataset_range")}
        m = menus.get(p["key"])
        if m and m.get("status") in ("ok", "partial"):
            p["menu_data"] = {"url": m.get("menu_url"), "items": m.get("items_count"), "status": m.get("status"), "slug": m.get("slug")}
        if p["key"] in products:
            slug, d = products[p["key"]]
            p["menu_data"] = {"url": d.get("source_url"), "items": len(d["products"]), "status": d["status"],
                              "slug": slug, "kind": "products"}
    places.sort(key=lambda p: (p["walkMin"], p["name"]))
    (ROOT / "data/places.json").write_text(
        json.dumps(places, indent=1, ensure_ascii=False))

    template = (ROOT / "scripts/viewer_template.html").read_text()
    payload = json.dumps(places, ensure_ascii=False).replace("<", "\\u003c")
    (ROOT / "docs/index.html").write_text(
        template.replace("/*__DATA__*/[]", payload))

    curated_count = sum(1 for p in places if "notes" in p)
    print(f"{len(places)} places -> data/places.json, docs/index.html ({n_nb} from the North Beach bbox + "
          f"{len(places) - n_nb} from the citywide base; {curated_count} curated; "
          f"risk {sum(1 for p in places if 'risk' in p)}, inspections {sum(1 for p in places if 'inspection' in p)}, menus {sum(1 for p in places if 'menu_data' in p)})")
    by_n = {}
    for p in places:
        by_n.setdefault(p["neighborhood"], []).append(p)
    for n, ps in sorted(by_n.items(), key=lambda kv: -len(kv[1])):
        print(f"  {str(n):32} {len(ps):4}  walk max {max(p['walkMin'] for p in ps):2} min  "
              f"menus {sum(1 for p in ps if 'menu_data' in p):3}  inspections {sum(1 for p in ps if 'inspection' in p):3}  "
              f"risk {sum(1 for p in ps if 'risk' in p):3}")


if __name__ == "__main__":
    main()
