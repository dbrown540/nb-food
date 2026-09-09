#!/usr/bin/env python3
"""Attach SF DPH health-inspection history to the North Beach POIs.

Inputs (produced by scripts/fetch_inspections.py; CSVs are committed):
  data/inspections/inspections_2016_2019.csv            LIVES era, numeric score
  data/inspections/current/inspections_2020_2023.csv    placard era, per-violation rows
  data/inspections/current/inspections_2024_present.csv placard era, one row/inspection
  data/places.json                                      the POI set (built)

Output:
  data/inspections/poi_inspections.json  keyed by POI name (+ a "_meta" key)

Matching, per POI:
  name kinds   exact    normalized token sets equal
               compact  tokens joined with no spaces equal ("Wheat Field"=="Wheatfield")
               subset   one token set contains the other
               overlap  >= 2 shared identity tokens (address match required)
               fuzzy    joined strings >= FUZZY_RATIO similar (address match required)
  normalization: NFKD->ascii, lowercase, dots removed, & -> and, apostrophes
               dropped, generic words (STOP) removed, trailing-s singularized.
  address      when both sides have a street number + street, they must agree;
               agreement makes "name+address" and overrides coordinates.
  geography    otherwise the DPH coordinates must be within SAME_M ("same
               building"; calibrated: name+address pairs sit <= 65 m apart) for
               subset matches, or <= NEAR_M / a North Beach-area zip for exact
               ones. Place-name tokens (north, beach, grant...) carry no identity.
  confidence   "name+address" | "name-only" | "none".  Nothing else is inferred.

Scores exist only in the 2016-2019 data (DPH dropped LIVES scoring in 2021);
later eras record Pass / Conditional Pass / Closure plus violations.
"""
import csv
import difflib
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSP = ROOT / "data/inspections"
TODAY = date.today().isoformat()

DATASETS = {  # dataset id -> (csv path, meta path)
    "pyih-qa8i": (INSP / "inspections_2016_2019.csv",
                  INSP / "inspections_2016_2019.meta.json"),
    "5tti-66ds": (INSP / "current/inspections_2020_2023.csv",
                  INSP / "current/inspections_2020_2023.meta.json"),
    "tvy3-wexg": (INSP / "current/inspections_2024_present.csv",
                  INSP / "current/inspections_2024_present.meta.json"),
}
SOURCE_URL = "https://data.sf.gov/resource/{}.json"

# words that carry no identity; dropped from BOTH sides before comparing
STOP = {"the", "restaurant", "cafe", "caffe", "and", "inc", "llc", "co",
        "corp", "company", "ltd", "dba", "of", "by", "at", "on"}
# geographic words: kept for equality tests but never count as identity
PLACE = {"north", "beach", "chinatown", "san", "francisco", "sf", "telegraph",
         "hill", "nob", "russian", "columbus", "grant", "stockton", "broadway",
         "wharf", "fisherman", "pier", "embarcadero", "washington", "square",
         "jackson", "pacific", "powell", "kearny", "bay", "union", "new"}
NB_ZIPS = {"94133", "94108", "94111", "94109", "94104", "94102", "94105"}
SAME_M = 120        # "same building" (name+address pairs measured <= 65 m)
NEAR_M = 400        # corroborates an exact-name match
CONFLICT_M = 1000   # farther than this rejects any name match
DF_DISTINCT = 20    # a token on <= this many DPH business names is "distinctive"
DF_UNIQUE = 3       # ...on <= this many is near-unique (enough with zip only)
FUZZY_RATIO = 0.85  # spelling variant, trusted only with a street-address match
FUZZY_STRONG = 0.90  # ...or, at this level, with same-building coordinates


def norm_tokens(name: str) -> list:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("&", " and ").replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    out = []
    for t in s.split():
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def parse_addr(addr: str):
    """-> (street number, first street word) or None. '373 Columbus Avenue' -> ('373','columbus')."""
    if not addr:
        return None
    s = unicodedata.normalize("NFKD", addr).encode("ascii", "ignore").decode().lower()
    m = re.match(r"\s*(\d+)[a-z]?(?:\s*[-;]\s*\d+)?\s+([a-z0-9]+)", s)
    if not m:
        return None
    street = m.group(2)
    if street in ("n", "s", "e", "w", "north", "south", "east", "west", "the", "a", "b"):
        m2 = re.match(r"\s*\d+[a-z]?(?:\s*[-;]\s*\d+)?\s+[a-z]+\s+([a-z0-9]+)", s)
        street = m2.group(1) if m2 else street
    return m.group(1), street


def meters(lat1, lon1, lat2, lon2) -> float:
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 6371000 * 2 * math.asin(math.sqrt(a))


def norm_status(s: str):
    s = (s or "").strip().upper()
    if not s:
        return None
    if s.startswith("CONDIT"):  # dataset has CONDITIIONAL / CONDITONA typos
        return "Conditional Pass"
    if s.startswith("PASS"):
        return "Pass"
    if s.startswith("CLOS"):
        return "Closure"
    return s.title()


# --------------------------------------------------------------------------
# Load the three eras into one business index:
#   businesses[(dataset, biz_id)] = {name, address, postal, lat, lon,
#                                    inspections: {inspection_key: {...}}}
# --------------------------------------------------------------------------
def load_businesses() -> dict:
    biz = {}

    def get(ds, bid, name, address, postal, lat, lon):
        key = (ds, bid)
        if key not in biz:
            biz[key] = {"dataset": ds, "id": bid, "name": name, "address": address,
                        "postal": (postal or "")[:5], "lat": float(lat) if lat else None,
                        "lon": float(lon) if lon else None, "inspections": {}}
        return biz[key]

    with DATASETS["pyih-qa8i"][0].open() as f:
        for r in csv.DictReader(f):
            b = get("pyih-qa8i", r["business_id"], r["business_name"],
                    r["business_address"], r["postal"], r["lat"], r["lon"])
            insp = b["inspections"].setdefault(r["inspection_id"], {
                "date": r["inspection_date"], "type": r["inspection_type"],
                "score": int(r["inspection_score"]) if r["inspection_score"] else None,
                "status": None, "violations": [], "high_risk": 0})
            if r["violation_description"]:
                insp["violations"].append(r["violation_description"])
                if r["risk_category"] == "High Risk":
                    insp["high_risk"] += 1

    with DATASETS["5tti-66ds"][0].open() as f:
        for r in csv.DictReader(f):
            # no stable business id in this era: name+address is the identity
            b = get("5tti-66ds", f'{r["name"]}|{r["address"]}', r["name"],
                    r["address"], r["postal"], r["lat"], r["lon"])
            insp = b["inspections"].setdefault(r["inspection_id"], {
                "date": r["date"], "type": r["inspection_type"], "score": None,
                "status": norm_status(r["facility_status"]), "violations": [],
                "high_risk": 0})
            if r["violation_observed"]:
                insp["violations"].append(
                    f'{r["violation_observed"]}: {r["description"]}')
                if r["violation_observed"].startswith("Major"):
                    insp["high_risk"] += 1

    # tvy3-wexg is two feeds: typed rows (one-time 2025-07 load) and untyped
    # rows (monthly loads since). Where they overlap, the same inspection
    # appears twice; drop an untyped row whose typed twin exists.
    with DATASETS["tvy3-wexg"][0].open() as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: r["inspection_type"] == "")  # typed first
    typed = set()
    for r in rows:
        status = norm_status(r["facility_rating_status"])
        if r["violation_count"]:
            vcount = int(float(r["violation_count"]))
        elif not r["violation_codes"] and status == "Pass":
            vcount = 0  # documented interpretation, see _meta.notes
        else:
            vcount = None
        twin = (r["permit_number"], r["inspection_date"], status, vcount)
        if r["inspection_type"]:
            typed.add(twin)
        elif twin in typed:
            continue
        b = get("tvy3-wexg", r["permit_number"], r["dba"], r["street_address"],
                "", r["lat"], r["lon"])
        key = f'{r["permit_number"]}_{r["inspection_date"]}_{r["inspection_type"]}'
        b["inspections"][key] = {
            "date": r["inspection_date"], "type": r["inspection_type"] or None,
            "score": None, "status": status, "violation_count": vcount,
            "violation_codes": sorted(set(
                re.findall(r"\b\d{6}(?:\.\d+)?\b", r["violation_codes"]))),
            "violations": [r["violation_codes"]] if r["violation_codes"] else [],
            "high_risk": None,  # no severity field in this era
            "suspension_notes": r["suspension_notes"] or None,
        }
    return biz


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
def name_kind(pset, bset, pjoined, bjoined):
    """-> (kind, similarity ratio); kind None = unrelated."""
    if pset == bset:
        return "exact", 1.0
    if pjoined == bjoined:
        return "compact", 1.0
    if pset <= bset or bset <= pset:
        return "subset", None
    ratio = difflib.SequenceMatcher(None, pjoined, bjoined).ratio()
    shared = {t for t in pset & bset if t not in PLACE}
    if len(shared) >= 2:
        return "overlap", ratio
    if ratio >= FUZZY_RATIO:
        return "fuzzy", ratio
    return None, ratio


def geo_relation(poi, b):
    """-> 'same' | 'near' | 'far' | 'conflict' | 'zip' | None"""
    if poi.get("lat") and b["lat"]:
        d = meters(poi["lat"], poi["lon"], b["lat"], b["lon"])
        if d <= SAME_M:
            return "same"
        if d <= NEAR_M:
            return "near"
        return "conflict" if d > CONFLICT_M else "far"
    if b["postal"]:
        return "zip" if b["postal"] in NB_ZIPS else "conflict"
    return None


def match_poi(poi: dict, index: dict, by_token: dict, by_addr: dict, df: dict) -> tuple:
    """-> (confidence, [business dicts], diagnostics)"""
    ptoks = norm_tokens(poi["name"])
    if not ptoks:
        return "none", [], {"reason": "empty name after normalization"}
    pset, pjoined = set(ptoks), "".join(ptoks)
    paddr = parse_addr(poi.get("addr", ""))

    cand_keys = set(by_token.get(pjoined, set()))  # joined-string hit ("mycanh")
    for t in pset:
        cand_keys |= by_token.get(t, set())
    if paddr:  # so spelling variants at the same address get compared at all
        cand_keys |= by_addr.get(paddr, set())

    accepted, rejected, notes = [], [], []
    for key in sorted(cand_keys):  # deterministic across hash seeds
        b = index[key]
        baddr = parse_addr(b["address"])
        addr = None
        if paddr and baddr:
            addr = "match" if paddr == baddr else "conflict"
        kind, ratio = name_kind(pset, b["_set"], pjoined, b["_joined"])
        if kind is None:
            continue
        strong = kind in ("exact", "compact") or (kind == "fuzzy" and ratio >= FUZZY_STRONG)
        if addr == "match":
            accepted.append((b, kind, "name+address", addr, "n/a"))
            continue

        geo = geo_relation(poi, b)
        if addr == "conflict":
            # OSM and DPH disagree on the street number (1118 vs 1114 Grant) but
            # the coordinates say same building and the name is unambiguous
            if strong and geo == "same":
                accepted.append((b, kind, "name-only", "number-differs", geo))
                notes.append(f'street number differs: OSM {poi.get("addr")!r} vs DPH '
                             f'{b["address"].strip()!r}; coordinates within {SAME_M} m')
            else:
                rejected.append((kind, b["name"], b["address"], "addr-conflict"))
            continue

        ok = False
        if geo == "conflict" or geo == "far":
            ok = False
        elif kind in ("exact", "compact"):
            ok = True  # same / near / zip / no-info
        elif kind == "fuzzy":
            ok = strong and geo == "same"
        elif kind == "subset":
            smaller = pset if pset <= b["_set"] else b["_set"]
            identity = [t for t in smaller if t not in PLACE]
            best_df = min((df[t] for t in identity), default=10 ** 9)
            if geo == "same":
                ok = best_df <= DF_DISTINCT or len(identity) >= 2
            elif geo == "zip":
                ok = best_df <= DF_UNIQUE
        if ok:
            accepted.append((b, kind, "name-only", addr, geo))
        else:
            rejected.append((kind, b["name"], b["address"], geo))

    diag = {"rejected": rejected[:6]}
    if notes:
        diag["address_note"] = "; ".join(sorted(set(notes)))
    if not accepted:
        return "none", [], diag

    with_addr = [a for a in accepted if a[2] == "name+address"]
    pool = with_addr or accepted
    conf = "name+address" if with_addr else "name-only"

    if conf == "name-only":
        # an exact/compact name beats a looser subset one (e.g. "Pyramid Cafe"
        # must not also absorb "Sky Bar at Transamerica Pyramid")
        strict = [a for a in pool if a[1] in ("exact", "compact")]
        pool = strict or pool
        # sibling registrations: same normalized name at the same street address
        # in another era, rejected only because that era lacks coordinates
        ids = {(a[0]["_joined"], parse_addr(a[0]["address"])) for a in pool}
        for key in sorted(cand_keys):
            b = index[key]
            if (b["_joined"], parse_addr(b["address"])) in ids and \
                    all(b is not a[0] for a in pool):
                pool.append((b, "sibling", "name-only", None, "sibling"))
        # several distinct street addresses (chains, second locations): keep the nearest
        groups = defaultdict(list)
        for a in pool:
            groups[parse_addr(a[0]["address"]) or a[0]["address"].strip().upper()].append(a)
        if len(groups) > 1:
            def dist(items):
                ds = [meters(poi["lat"], poi["lon"], a[0]["lat"], a[0]["lon"])
                      for a in items if a[0]["lat"] and poi.get("lat")]
                return min(ds) if ds else float("inf")
            best = min(groups.values(), key=dist)
            if dist(best) < float("inf"):
                diag["other_addresses"] = sorted(
                    {a[0]["address"].strip().upper() for g in groups.values()
                     if g is not best for a in g})
                pool = best
            else:
                diag["multi_address"] = True

    diag["methods"] = sorted({a[1] for a in pool})
    return conf, [a[0] for a in pool], diag


def summarize(businesses: list) -> dict:
    insps = []
    for b in businesses:
        for k, i in b["inspections"].items():
            if i["date"] and i["date"] <= TODAY:
                insps.append(dict(i, dataset=b["dataset"], key=k))
    insps.sort(key=lambda i: (i["date"], i["dataset"], i["key"]))
    out = {"inspections_total": len(insps)}
    if not insps:
        return out
    # A POI can map to several DPH registrations of one address (e.g. "Boudin
    # Bakery & Cafe" + "Boudin Restaurant") inspected the same day; same-day
    # ties are resolved conservatively (worst score/status, most violations).
    last_day = [i for i in insps if i["date"] == insps[-1]["date"]]

    def vcount(i):
        return i["violation_count"] if i["dataset"] == "tvy3-wexg" else len(i["violations"])
    last = max(last_day, key=lambda i: (vcount(i) or 0, i["key"]))
    out["last_inspection_date"] = last["date"]
    out["last_inspection_type"] = last["type"]
    out["last_inspection_dataset"] = last["dataset"]
    out["violation_count_last"] = vcount(last)
    if last["dataset"] == "tvy3-wexg":
        out["last_violation_codes"] = last["violation_codes"]
    out["last_violations"] = [v for i in last_day for v in i["violations"]]
    if len(last_day) > 1:
        out["last_day_inspections"] = len(last_day)

    scored = [i for i in insps if i["score"] is not None]
    if scored:
        last_scored_day = [i for i in scored if i["date"] == scored[-1]["date"]]
        out["last_score"] = min(i["score"] for i in last_scored_day)
        out["last_score_date"] = scored[-1]["date"]
        out["worst_score_all_time"] = min(i["score"] for i in scored)
        out["worst_score_date"] = min(scored, key=lambda i: (i["score"], i["date"]))["date"]
    else:
        out["last_score"] = out["last_score_date"] = out["worst_score_all_time"] = None

    statused = [i for i in insps if i["status"]]
    if statused:
        rank = {"Closure": 0, "Conditional Pass": 1, "Pass": 2}
        last_status_day = [i for i in statused if i["date"] == statused[-1]["date"]]
        out["last_status"] = min(last_status_day,
                                 key=lambda i: rank.get(i["status"], 3))["status"]
        out["last_status_date"] = statused[-1]["date"]
        out["closures_all_time"] = sum(1 for i in statused if i["status"] == "Closure")
        out["conditional_pass_all_time"] = sum(
            1 for i in statused if i["status"] == "Conditional Pass")
    out["high_risk_count_all_time"] = sum(i["high_risk"] or 0 for i in insps)
    out["high_risk_count_basis"] = ("2016-19 'High Risk' + 2020-23 'Major' violations; "
                                    "2024+ has no severity field")
    out["first_inspection_date"] = insps[0]["date"]
    out["eras"] = sorted({i["dataset"] for i in insps})
    return out


def main() -> None:
    verbose = "-v" in sys.argv
    pois = json.loads((ROOT / "data/places.json").read_text())
    biz = load_businesses()
    metas = {ds: json.loads(p[1].read_text()) for ds, p in DATASETS.items()}

    by_token, by_addr, df = defaultdict(set), defaultdict(set), defaultdict(int)
    for key, b in biz.items():
        toks = norm_tokens(b["name"])
        b["_set"], b["_joined"] = set(toks), "".join(toks)
        for t in b["_set"]:
            by_token[t].add(key)
            df[t] += 1
        by_token[b["_joined"]].add(key)  # "MyCanh" must find "MY CANH"
        a = parse_addr(b["address"])
        if a:
            by_addr[a].add(key)

    dmin = min(m["date_min"] for m in metas.values())
    dmax = max(m["date_max_not_after_today"] for m in metas.values())
    result = {"_meta": {
        "as_of": TODAY,
        "source": [SOURCE_URL.format(ds) for ds in DATASETS],
        "datasets": {ds: {"rows": m["rows"], "date_min": m["date_min"],
                          "date_max": m["date_max_not_after_today"],
                          "fetched": m["as_of"]} for ds, m in metas.items()},
        "dataset_range": f"{dmin}..{dmax}",
        "notes": [
            "Numeric scores exist only in 2016-2019 (LIVES); DPH stopped scoring in 2021. Later eras: Pass / Conditional Pass / Closure.",
            "2024+ rows with no violation_count and no violation_codes and status Pass are read as 0 violations; any other missing count is null.",
            "2024+ dataset is two feeds (typed rows loaded 2025-07; untyped rows loaded monthly since); an untyped row is dropped when a typed row for the same permit/date/status/violation_count exists (218 such duplicates).",
            "When several DPH registrations of one POI were inspected on the same day, last_score/last_status/violation_count_last take the worst of that day (last_day_inspections says how many); worst_score_all_time and *_all_time counts span all matched registrations.",
            "2024+ open data is known to lag/miss inspections versus the DPH lookup tool (inspections.myhealthdepartment.com), whose robots.txt forbids automated access; it was not fetched.",
            "match_confidence: name+address = normalized name relates (exact/compact/subset/overlap/fuzzy) AND street number+street agree; name-only = exact/compact name with coordinates or zip corroboration, subset/strong-fuzzy name within SAME_M, or exact name at a differing street number within SAME_M (see address_note); none = no defensible match.",
            f"Thresholds: SAME_M={SAME_M} NEAR_M={NEAR_M} CONFLICT_M={CONFLICT_M} DF_DISTINCT={DF_DISTINCT} DF_UNIQUE={DF_UNIQUE} FUZZY_RATIO={FUZZY_RATIO} FUZZY_STRONG={FUZZY_STRONG}; NB_ZIPS={sorted(NB_ZIPS)}",
        ],
    }}

    counts = defaultdict(int)
    by_cat = defaultdict(lambda: defaultdict(int))
    methods = defaultdict(int)
    for poi in pois:
        conf, matched, diag = match_poi(poi, biz, by_token, by_addr, df)
        counts[conf] += 1
        by_cat[poi["category"]][conf] += 1
        entry = {"match_confidence": conf,
                 "source": "SF DPH via data.sf.gov (see _meta.source)",
                 "dataset_range": result["_meta"]["dataset_range"],
                 "as_of": TODAY}
        if matched:
            entry["match_methods"] = diag["methods"]
            for m in diag["methods"]:
                methods[f"{conf}/{m}"] += 1
            entry["matched_businesses"] = [
                {"dataset": b["dataset"], "id": b["id"], "name": b["name"],
                 "address": b["address"], "inspections": len(b["inspections"])}
                for b in sorted(matched, key=lambda b: (b["dataset"], b["id"]))]
            if diag.get("address_note"):
                entry["address_note"] = diag["address_note"]
            if diag.get("other_addresses"):
                entry["other_locations_not_merged"] = diag["other_addresses"]
            if diag.get("multi_address"):
                entry["multiple_addresses_merged"] = True
            entry.update(summarize(matched))
        result[poi["name"]] = entry
        if verbose and conf != "name+address":
            print(f'{conf:12s} {poi["name"]!r} addr={poi.get("addr")!r} '
                  f'-> {[(b["name"], b["address"]) for b in matched][:3]} '
                  f'{diag.get("methods", "")} rejected={diag["rejected"][:3]}',
                  file=sys.stderr)
        elif verbose and diag["methods"] != ["exact"]:
            print(f'{conf:12s} {poi["name"]!r} via {diag["methods"]} -> '
                  f'{sorted({b["name"] for b in matched})}', file=sys.stderr)

    out = INSP / "poi_inspections.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False))

    n = len(pois)
    print(f"{n} POIs -> {out.relative_to(ROOT)}")
    for conf in ("name+address", "name-only", "none"):
        print(f"  {conf:13s} {counts[conf]:4d}  ({100 * counts[conf] / n:.0f}%)")
    for cat, c in sorted(by_cat.items()):
        print(f"  {cat:10s} " + "  ".join(f"{k}={v}" for k, v in sorted(c.items())))
    print("  methods: " + ", ".join(f"{k}={v}" for k, v in sorted(methods.items())))
    matched = [v for k, v in result.items() if k != "_meta" and v.get("inspections_total")]
    eras = defaultdict(int)
    for v in matched:
        for e in v["eras"]:
            eras[e] += 1
    print("  POIs with >=1 inspection per era: " + ", ".join(f"{k}={v}" for k, v in sorted(eras.items())))
    recent = sum(1 for v in matched if v.get("last_inspection_date", "") >= "2024-01-01")
    scored = sum(1 for v in matched if v.get("last_score") is not None)
    print(f"  last inspection in 2024+: {recent}; have a 2016-19 numeric score: {scored}")


if __name__ == "__main__":
    main()
