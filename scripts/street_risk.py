#!/usr/bin/env python3
"""Street risk per POI: SFPD incidents within 150 m, trailing 365 days.

ONE bulk DataSF query (police incidents, dataset wg3w-h783, on the data.sf.gov
domain -- data.sfgov.org now 403s) for every incident in the bbox of the POI
set in data/places.json (padded by 200 m so edge POIs keep their full 150 m
circle) in the window, paged at $limit=50000, saved to
data/crime/nb_incidents_365d.json. Distances are then computed locally
(haversine) for every POI (lat/lon for curated `extras` come from
data/curated.json, since build.py strips them). Output:
data/crime/poi_street_risk.json keyed by the POI `key` (== name unless the
name is shared by several places; see build.py). The percentile is ranked
within the whole set, i.e. every neighborhood in the index.

Counting rule: the dataset has one ROW per incident code, so one incident can
carry several rows (e.g. Assault + Other Miscellaneous). We count DISTINCT
incident_id per bucket, so an incident is counted once in each bucket it
touches; `total` = distinct incidents in any of the three buckets;
`all_incidents` = distinct incidents of any category within 150 m (context).

Usage: python3 scripts/street_risk.py            # fetch + compute
       python3 scripts/street_risk.py --cached   # recompute from the saved pull
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://data.sf.gov/resource/wg3w-h783.json"
UA = "nb-food/0.3 (personal research)"
RADIUS_M = 150
PULL_PAD_M = 200  # pull bbox = POI bbox grown by this, so a POI on the edge still gets its full circle
WINDOW_DAYS = 365
PAGE = 50000
FIELDS = ["row_id", "incident_id", "incident_number", "incident_datetime", "incident_code",
          "incident_category", "incident_subcategory", "incident_description", "resolution",
          "police_district", "analysis_neighborhood", "latitude", "longitude"]
BUCKETS = {
    "violent": {"Assault", "Robbery", "Homicide", "Rape", "Sex Offense",
                "Weapons Offense", "Weapons Carrying Etc"},
    "property": {"Larceny Theft", "Burglary", "Motor Vehicle Theft", "Malicious Mischief",
                 "Stolen Property", "Vandalism"},
    "drug": {"Drug Offense", "Drug Violation", "Disorderly Conduct", "Prostitution"},
}
RAW = ROOT / "data/crime/nb_incidents_365d.json"
OUT = ROOT / "data/crime/poi_street_risk.json"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    x = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 6371000 * 2 * math.asin(math.sqrt(x))


def get(params, timeout=120):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            log(f"retry {attempt + 1}: {type(e).__name__} {str(e)[:100]}")
            time.sleep(5 * (attempt + 1))
    raise SystemExit("DataSF query failed")


def poi_bbox(pois):
    """(south, west, north, east) of the POI set, rounded outward to 1e-4 deg."""
    lats = [p[3] for p in pois]
    lons = [p[4] for p in pois]
    return (math.floor(min(lats) * 1e4) / 1e4, math.floor(min(lons) * 1e4) / 1e4,
            math.ceil(max(lats) * 1e4) / 1e4, math.ceil(max(lons) * 1e4) / 1e4)


def pull_bbox(bbox):
    return (bbox[0] - PULL_PAD_M / 111320, bbox[1] - PULL_PAD_M / (111320 * 0.79),
            bbox[2] + PULL_PAD_M / 111320, bbox[3] + PULL_PAD_M / (111320 * 0.79))


def fetch_incidents(since_iso, box):
    s, w, n, e = (round(v, 5) for v in box)
    where = (f"within_box(point, {n}, {w}, {s}, {e}) AND incident_datetime >= '{since_iso}'")
    rows, offset, t0 = [], 0, time.time()
    while True:
        page = get({"$select": ",".join(FIELDS), "$where": where,
                    "$order": "row_id", "$limit": PAGE, "$offset": offset})
        rows.extend(page)
        log(f"page offset={offset}: {len(page)} rows (cum {len(rows)})")
        if len(page) < PAGE:
            break
        offset += PAGE
    return rows, where, round(time.time() - t0, 1)


def load_pois():
    places = json.loads((ROOT / "data/places.json").read_text())
    extras = {x["name"]: x for x in json.loads((ROOT / "data/curated.json").read_text())["extras"]}
    pois, missing = [], []
    for p in places:
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None and p["name"] in extras:  # build.py strips lat/lon from extras
            lat, lon = extras[p["name"]]["lat"], extras[p["name"]]["lon"]
        if lat is None:
            missing.append(p["name"])
            continue
        pois.append((p.get("key", p["name"]), p["category"], p.get("subtype"), lat, lon))
    return pois, missing


def compute(rows, pois, meta):
    # incident-level table: (incident_id, lat, lon, set of categories)
    incidents = {}
    for r in rows:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        iid = r.get("incident_id") or r["row_id"]
        inc = incidents.setdefault(iid, [lat, lon, set()])
        inc[2].add(r.get("incident_category") or "Unknown")
    inc_list = list(incidents.values())
    out = {}
    for name, cat, sub, lat, lon in pois:
        counts = {"violent": 0, "property": 0, "drug": 0}
        all_n, cats, nearest = 0, {}, None
        for ilat, ilon, icats in inc_list:
            if abs(ilat - lat) > 0.006 or abs(ilon - lon) > 0.0075:  # cheap prefilter (~650 m)
                continue
            d = hav(lat, lon, ilat, ilon)
            nearest = d if nearest is None or d < nearest else nearest
            if d > RADIUS_M:
                continue
            all_n += 1
            for b, members in BUCKETS.items():
                if icats & members:
                    counts[b] += 1
            for c in icats:
                cats[c] = cats.get(c, 0) + 1
        total = sum(counts.values())
        out[name] = {
            "category": cat, "subtype": sub, "lat": lat, "lon": lon,
            "violent": counts["violent"], "property": counts["property"], "drug": counts["drug"],
            "total": total, "per_month": round(total / (WINDOW_DAYS / 30.4375), 2),
            "all_incidents": all_n,
            # SFPD geocodes to intersections/block points; a zero with nearest_incident_m > 150
            # means no snap point inside the circle, NOT a calm block.
            "nearest_incident_m": round(nearest) if nearest is not None else None,
            "top_categories": dict(sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))[:5]),
            "radius_m": RADIUS_M, "window": meta["window"], "source": meta["source"],
            "as_of": meta["as_of"],
        }
    # percentile rank within the set: % of POIs with a strictly lower total (0 = calmest)
    totals = sorted(v["total"] for v in out.values())
    n = len(totals)
    ranked = sorted(out.items(), key=lambda kv: (-kv[1]["total"], -kv[1]["violent"], kv[0]))
    for rank, (name, v) in enumerate(ranked, 1):
        lower = sum(1 for t in totals if t < v["total"])
        v["percentile"] = round(100 * lower / (n - 1), 1) if n > 1 else 0.0
        v["rank"] = rank  # 1 = highest street-risk total of the set
    return out, len(inc_list)


def main():
    now = datetime.now(timezone.utc)
    pois, missing = load_pois()
    log(f"POIs: {len(pois)} with coordinates, {len(missing)} without: {missing}")
    box = poi_bbox(pois)
    if "--cached" in sys.argv and RAW.exists():
        raw = json.loads(RAW.read_text())
        log(f"cached: {len(raw['rows'])} rows fetched {raw['fetched_at']}")
        if any(a < b for a, b in zip(raw["poi_bbox"][:2], box[:2])) or \
                any(a > b for a, b in zip(raw["poi_bbox"][2:], box[2:])):
            raise SystemExit(f"cached pull bbox {raw['poi_bbox']} does not cover the POI set {box}; re-run without --cached")
    else:
        since = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT00:00:00")
        rows, where, secs = fetch_incidents(since, pull_bbox(box))
        log(f"fetched {len(rows)} rows in {secs}s")
        raw = {"source": "DataSF Police Department Incident Reports 2018-present (wg3w-h783)",
               "endpoint": BASE, "poi_bbox": box, "pull_bbox": [round(v, 5) for v in pull_bbox(box)],
               "pull_pad_m": PULL_PAD_M, "where": where,
               "fetched_at": now.isoformat(timespec="seconds"), "window_start": since,
               "fetch_seconds": secs, "rows": rows}
        RAW.write_text(json.dumps(raw, ensure_ascii=False))
        log(f"wrote {RAW} ({RAW.stat().st_size / 1e6:.2f} MB)")
    rows = raw["rows"]
    latest = max((r.get("incident_datetime") or "" for r in rows), default=None)
    meta = {
        "source": f"{raw['source']} via {BASE}; pull bbox {','.join(str(v) for v in raw['pull_bbox'])} "
                  f"(POI bbox {','.join(str(v) for v in raw['poi_bbox'])} + {raw['pull_pad_m']} m pad)",
        "as_of": raw["fetched_at"],
        "window": {"days": WINDOW_DAYS, "start": raw["window_start"], "end": raw["fetched_at"],
                   "latest_incident_in_pull": latest},
    }
    result, n_incidents = compute(rows, pois, meta)
    doc = {"_meta": {**meta, "radius_m": RADIUS_M, "pois": len(pois), "pois_missing_coords": missing,
                     "bbox_rows": len(rows), "bbox_distinct_incidents": n_incidents,
                     "buckets": {k: sorted(v) for k, v in BUCKETS.items()},
                     "counting": "distinct incident_id per bucket; total = distinct incidents in any bucket; "
                                 "all_incidents = distinct incidents of any category within radius",
                     "percentile": "% of the whole POI set (all neighborhoods in data/places.json) with a strictly lower total (0 = calmest); rank 1 = highest",
                     "keyed_by": "POI key from data/places.json (== name unless several places share a name)",
                     "caveat": "incidents are geocoded to intersections/block points (~390 distinct points in this "
                               "pull), so counts are lumpy at 150 m; total=0 with nearest_incident_m>150 is a "
                               "geocoding gap, not a calm block. Reports without a location are excluded upstream.",
                     "generated_by": "scripts/street_risk.py"},
           "pois": result}
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    log(f"wrote {OUT}: {len(result)} POIs")
    ranked = sorted(result.items(), key=lambda kv: kv[1]["rank"])
    print("\nHIGHEST street-risk totals (150 m / 365 d):")
    for name, v in ranked[:10]:
        print(f"  {v['rank']:3} {name:34} total={v['total']:4} v={v['violent']:3} p={v['property']:3} d={v['drug']:3} "
              f"pm={v['per_month']:5.1f} pct={v['percentile']:5.1f} [{v['category']}]")
    print("\nLOWEST among restaurants:")
    rest = [kv for kv in ranked if kv[1]["category"] == "restaurant"]
    for name, v in sorted(rest, key=lambda kv: (kv[1]["total"], kv[1]["violent"], kv[0]))[:5]:
        print(f"  {v['rank']:3} {name:34} total={v['total']:4} v={v['violent']:3} p={v['property']:3} d={v['drug']:3} "
              f"pm={v['per_month']:5.1f} pct={v['percentile']:5.1f}")


if __name__ == "__main__":
    main()
