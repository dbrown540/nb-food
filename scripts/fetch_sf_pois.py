#!/usr/bin/env python3
"""Citywide POI base: every restaurant / cafe / fast_food / grocery-type shop in
San Francisco from OpenStreetMap via Overpass.

  scripts/overpass_sf_query.txt  (template: {bbox}, {timeout})
    -> data/sf_osm_raw.json      raw Overpass elements (gitignored; ~MBs)
    -> data/sf_places.json       normalized rows, one per OSM element
    -> data/sf.db  table places  append-only, stamped fetched_at + source

Mirrors are tried in order with retries + backoff; if the full bbox times out
on every mirror the bbox is split into 4 quadrants and each is fetched alone
(elements are de-duplicated on (type, id) since ways/relations can straddle
a quadrant edge). Stdlib only (Python 3.9).

Usage: python3 scripts/fetch_sf_pois.py            # network pull + normalize + db
       python3 scripts/fetch_sf_pois.py --cached   # re-normalize from the saved raw
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SF_BBOX = (37.7030, -122.5200, 37.8330, -122.3550)  # south, west, north, east
MIRRORS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
UA = "nb-food/0.2 (personal research; danny@therenthacker.com)"
MAX_STALE_DAYS = 14  # a mirror whose osm_base is older than this is kept only as a fallback
GROCERY_SHOPS = {"supermarket", "greengrocer", "convenience", "grocery",
                 "health_food", "butcher", "seafood", "bakery", "deli"}
RAW = ROOT / "data/sf_osm_raw.json"
OUT = ROOT / "data/sf_places.json"
DB = ROOT / "data/sf.db"
QUERY_TMPL = (ROOT / "scripts/overpass_sf_query.txt").read_text()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def query_for(bbox, timeout):
    return QUERY_TMPL.format(bbox=",".join(f"{v:.4f}" for v in bbox), timeout=timeout)


def post(url, query, timeout):
    """One Overpass POST, form-encoded exactly like `--data-urlencode data@file`."""
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout + 30) as r:
        payload = json.load(r)
    if "remark" in payload and "elements" not in payload:
        raise RuntimeError(payload["remark"])
    if payload.get("remark", "").startswith("runtime error"):
        raise RuntimeError(payload["remark"])
    return payload


def staleness_days(payload):
    ts = payload.get("osm3s", {}).get("timestamp_osm_base")
    if not ts:
        return None
    base = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - base).total_seconds() / 86400


def fetch_bbox(bbox, label, timeout=180, attempts_per_mirror=2):
    """Try every mirror (each with retries + backoff). Returns (payload, mirror, secs) or None.
    A mirror that answers with stale OSM data (osm_base older than MAX_STALE_DAYS) is kept as a
    fallback while the remaining mirrors are tried; the freshest answer wins."""
    q = query_for(bbox, timeout)
    fallback = None
    for url in MIRRORS:
        for attempt in range(attempts_per_mirror):
            t0 = time.time()
            try:
                log(f"[{label}] POST {url} (attempt {attempt + 1})")
                payload = post(url, q, timeout)
                secs = time.time() - t0
                stale = staleness_days(payload)
                log(f"[{label}] ok: {len(payload['elements'])} elements in {secs:.1f}s from {url} "
                    f"(osm_base {payload.get('osm3s', {}).get('timestamp_osm_base')}, "
                    f"{stale:.1f} d old)" if stale is not None else
                    f"[{label}] ok: {len(payload['elements'])} elements in {secs:.1f}s from {url}")
                if stale is not None and stale > MAX_STALE_DAYS:
                    log(f"[{label}] STALE mirror (> {MAX_STALE_DAYS} d); keeping as fallback, trying next")
                    if fallback is None or stale < fallback[3]:
                        fallback = (payload, url, secs, stale)
                    break  # next mirror
                return payload, url, secs
            except urllib.error.HTTPError as e:
                log(f"[{label}] HTTP {e.code} from {url} after {time.time() - t0:.1f}s")
                if e.code in (400,):  # bad query, no point retrying anywhere
                    raise
            except Exception as e:  # timeouts, 429/504, JSON errors, runtime remarks
                log(f"[{label}] fail {type(e).__name__}: {str(e)[:120]} after {time.time() - t0:.1f}s")
            time.sleep(5 * (attempt + 1))
    if fallback:
        log(f"[{label}] no fresh mirror answered; using stale data from {fallback[1]} ({fallback[3]:.1f} d old)")
        return fallback[:3]
    return None


def quadrants(bbox):
    s, w, n, e = bbox
    mid_lat, mid_lon = (s + n) / 2, (w + e) / 2
    return {
        "SW": (s, w, mid_lat, mid_lon), "SE": (s, mid_lon, mid_lat, e),
        "NW": (mid_lat, w, n, mid_lon), "NE": (mid_lat, mid_lon, n, e),
    }


def fetch_all():
    """Full bbox first; on failure, 4 quadrants. Returns dict with elements + provenance."""
    t_start = time.time()
    prov = {"bbox": SF_BBOX, "mode": "full", "mirror": None, "quadrants": {}, "failed_quadrants": []}
    got = fetch_bbox(SF_BBOX, "full")
    if got:
        payload, url, secs = got
        prov.update(mirror=url, seconds=round(secs, 1))
        elements = payload["elements"]
        prov["osm3s"] = payload.get("osm3s", {})
    else:
        log("full bbox failed on every mirror; splitting into quadrants")
        prov["mode"] = "quadrants"
        seen, elements = set(), []
        for name, qb in quadrants(SF_BBOX).items():
            got = fetch_bbox(qb, f"quad-{name}", timeout=240, attempts_per_mirror=3)
            if not got:
                log(f"[quad-{name}] FAILED on every mirror")
                prov["failed_quadrants"].append(name)
                continue
            payload, url, secs = got
            prov["quadrants"][name] = {"bbox": qb, "mirror": url, "seconds": round(secs, 1),
                                       "elements": len(payload["elements"])}
            prov["osm3s"] = payload.get("osm3s", {})
            for el in payload["elements"]:
                k = (el["type"], el["id"])
                if k not in seen:
                    seen.add(k)
                    elements.append(el)
        prov["mirror"] = sorted({q["mirror"] for q in prov["quadrants"].values()})
    prov["total_seconds"] = round(time.time() - t_start, 1)
    return {"elements": elements, "provenance": prov}


def category(tags):
    amenity = tags.get("amenity")
    if amenity in ("restaurant", "fast_food"):
        return "restaurant", amenity
    if amenity == "cafe":
        return "cafe", "cafe"
    shop = tags.get("shop")
    if shop in GROCERY_SHOPS:
        return "grocery", shop
    return None, None


def address(tags):
    num, street = tags.get("addr:housenumber"), tags.get("addr:street")
    if num and street:
        return f"{num} {street}"
    return street or tags.get("addr:full", "") or ""


def normalize(elements):
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        cat, subtype = category(tags)
        if cat is None:  # tag matched the regex but not our list (shouldn't happen)
            continue
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None:
            continue
        rows.append({
            "osm_type": el["type"],
            "osm_id": el["id"],
            "name": tags.get("name") or None,
            "category": cat,
            "subtype": subtype,
            "cuisine": (tags.get("cuisine") or "").replace("_", " ") or None,
            "addr": address(tags) or None,
            "postal": tags.get("addr:postcode") or None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "website": tags.get("website") or tags.get("contact:website") or None,
            "phone": tags.get("phone") or tags.get("contact:phone") or None,
            "opening_hours": tags.get("opening_hours") or None,
        })
    rows.sort(key=lambda r: (r["category"], (r["name"] or "~").lower(), r["osm_type"], r["osm_id"]))
    return rows


def load_db(rows, fetched_at, source):
    db = sqlite3.connect(DB)
    db.execute("""CREATE TABLE IF NOT EXISTS places (
        osm_type TEXT NOT NULL, osm_id INTEGER NOT NULL, name TEXT, category TEXT NOT NULL,
        subtype TEXT, cuisine TEXT, addr TEXT, postal TEXT, lat REAL NOT NULL, lon REAL NOT NULL,
        website TEXT, phone TEXT, opening_hours TEXT,
        fetched_at TEXT NOT NULL, source TEXT NOT NULL,
        PRIMARY KEY (osm_type, osm_id, fetched_at))""")  # append-only: each fetch adds a snapshot
    db.execute("CREATE INDEX IF NOT EXISTS places_cat ON places(category, subtype)")
    db.execute("CREATE INDEX IF NOT EXISTS places_latlon ON places(lat, lon)")
    db.executemany(
        "INSERT OR IGNORE INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r["osm_type"], r["osm_id"], r["name"], r["category"], r["subtype"], r["cuisine"],
          r["addr"], r["postal"], r["lat"], r["lon"], r["website"], r["phone"],
          r["opening_hours"], fetched_at, source) for r in rows])
    db.commit()
    n = db.execute("SELECT count(*) FROM places WHERE fetched_at=?", (fetched_at,)).fetchone()[0]
    db.close()
    return n


def report(rows):
    by_cat = {}
    for r in rows:
        c = by_cat.setdefault(r["category"], {"n": 0, "named": 0, "website": 0, "addr": 0, "sub": {}})
        c["n"] += 1
        c["named"] += bool(r["name"])
        c["website"] += bool(r["website"])
        c["addr"] += bool(r["addr"])
        c["sub"][r["subtype"]] = c["sub"].get(r["subtype"], 0) + 1
    for cat, c in sorted(by_cat.items()):
        print(f"{cat:11} n={c['n']:5}  named={c['named']:5}  website={c['website']:5}  addr={c['addr']:5}  "
              + " ".join(f"{k}={v}" for k, v in sorted(c["sub"].items(), key=lambda kv: -kv[1])))
    n = len(rows)
    print(f"{'TOTAL':11} n={n:5}  named={sum(bool(r['name']) for r in rows):5}  "
          f"website={sum(bool(r['website']) for r in rows):5}  addr={sum(bool(r['addr']) for r in rows):5}")


def main():
    if "--cached" in sys.argv and RAW.exists():
        raw = json.loads(RAW.read_text())
        log(f"cached raw: {len(raw['elements'])} elements ({raw['provenance']['mode']}, {raw['provenance']['mirror']})")
    else:
        raw = fetch_all()
        raw["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        raw["query_template"] = QUERY_TMPL
        RAW.write_text(json.dumps(raw, ensure_ascii=False))
        log(f"wrote {RAW} ({RAW.stat().st_size / 1e6:.1f} MB)")
    fetched_at = raw.get("fetched_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    prov = raw["provenance"]
    mirror = prov["mirror"] if isinstance(prov["mirror"], str) else ",".join(prov["mirror"] or [])
    osm_base = prov.get("osm3s", {}).get("timestamp_osm_base", "unknown")
    source = (f"OpenStreetMap via Overpass ({mirror}); osm_base {osm_base}; "
              f"bbox {','.join(str(v) for v in SF_BBOX)}")

    rows = normalize(raw["elements"])
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    log(f"wrote {OUT}: {len(rows)} places")
    n = load_db(rows, fetched_at, source)
    log(f"sqlite {DB}: {n} rows stamped fetched_at={fetched_at}")
    report(rows)
    if prov.get("failed_quadrants"):
        print("FAILED QUADRANTS:", prov["failed_quadrants"])
    print("provenance:", json.dumps({k: v for k, v in prov.items() if k != "osm3s"}))


if __name__ == "__main__":
    main()
