#!/usr/bin/env python3
"""Neighborhood boundaries for the walk-radius index -> data/neighborhoods.geojson

Two public sources, stdlib only:
  1. DataSF "Analysis Neighborhoods" (dataset j2bu-swwd, the city's 41 standard
     neighborhoods; the same `analysis_neighborhood` label SFPD and DPH rows carry).
     Only the polygons around 371 Columbus are kept (KEEP below).
  2. OpenStreetMap: the Bay Street centerline (every highway way named
     "Bay Street" in the Wharf bbox), via Overpass.

The 41-neighborhood set folds Fisherman's Wharf into "North Beach" (east of
Van Ness) and "Russian Hill" (Ghirardelli / Aquatic Park). build.py therefore
labels a POI "Fisherman's Wharf" when it falls in either of those polygons AND
lies north of the Bay Street centerline (latitude interpolated at the POI's
longitude; extrapolated flat beyond the line's ends). That rule is the only
non-official boundary in the index.

Usage: python3 scripts/fetch_neighborhoods.py
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/neighborhoods.geojson"
UA = "nb-food/0.3 (personal research)"
NHOODS_URL = "https://data.sf.gov/resource/j2bu-swwd.geojson?$limit=100"
KEEP = ["North Beach", "Chinatown", "Russian Hill", "Nob Hill", "Financial District/South Beach"]
MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.private.coffee/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]
BAY_ST_QUERY = ('[out:json][timeout:60];way["name"="Bay Street"]["highway"]'
                '(37.800,-122.432,37.812,-122.398);out geom;')


def get(url, data=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_bay_street():
    body = urllib.parse.urlencode({"data": BAY_ST_QUERY}).encode()
    for url in MIRRORS:
        try:
            payload = get(url, body)
            ways = [w for w in payload["elements"] if w.get("geometry")]
            if ways:
                return ways, url, payload.get("osm3s", {}).get("timestamp_osm_base")
        except Exception as e:  # noqa: BLE001 - try the next mirror
            print(f"  {url}: {type(e).__name__} {str(e)[:80]}", file=sys.stderr)
            time.sleep(3)
    raise SystemExit("Bay Street geometry: every Overpass mirror failed")


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nh = get(NHOODS_URL)
    feats = [f for f in nh["features"] if f["properties"].get("nhood") in KEEP]
    missing = set(KEEP) - {f["properties"]["nhood"] for f in feats}
    if missing:
        raise SystemExit(f"neighborhood polygons missing from DataSF: {sorted(missing)}")
    for f in feats:
        f["properties"] = {"name": f["properties"]["nhood"], "kind": "analysis_neighborhood",
                           "source": "DataSF Analysis Neighborhoods (j2bu-swwd)", "as_of": now}
    ways, mirror, osm_base = fetch_bay_street()
    # one polyline sorted west -> east, from every Bay Street way's nodes (dedup on coords)
    pts = sorted({(round(n["lon"], 7), round(n["lat"], 7)) for w in ways for n in w["geometry"]})
    feats.append({"type": "Feature",
                  "properties": {"name": "Bay Street centerline", "kind": "split_line",
                                 "rule": "POIs in North Beach / Russian Hill north of this line are labeled Fisherman's Wharf",
                                 "source": f"OpenStreetMap via Overpass ({mirror}); osm_base {osm_base}; "
                                           f"{len(ways)} ways named 'Bay Street'",
                                 "as_of": now},
                  "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in pts]}})
    doc = {"type": "FeatureCollection",
           "_meta": {"generated_by": "scripts/fetch_neighborhoods.py", "as_of": now,
                     "sources": [NHOODS_URL, f"Overpass {mirror}"]},
           "features": feats}
    OUT.write_text(json.dumps(doc, ensure_ascii=False))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(feats) - 1} polygons + Bay Street line "
          f"({len(pts)} points), {OUT.stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
