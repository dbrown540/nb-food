#!/usr/bin/env python3
"""USDA FoodData Central record cache: data/usda/<fdcId>.json.

A record is fetched once, from the API's batch endpoint (POST /v1/foods, up to
20 ids a call), and committed; a lookup then reads the cached file, so a
record never changes silently. The API is called only for an fdcId that has
no cached file.

Each cached record: fdcId, dataType, description, publicationDate (the API's),
fetched_at, nutrients per 100 g (every nutrient the record carries: USDA
nutrient id, number, name, unit, amount) and portions (description, gram
weight).

The API key is read at run time with `op read REF` as the 1Password service
account (readings.op_read); REF comes from --key-ref
or the NB_FOOD_USDA_KEY_REF environment variable, and is kept out of this
repository. The key is sent in a request header, never in a URL, and is never
printed, logged or written.

    python3 scripts/usda.py FDC_ID [FDC_ID ...] [--key-ref REF]   # cache these records
    python3 scripts/usda.py --mapped [--key-ref REF]              # cache every fdcId in data/food_map.json and data/grocery_foods.json
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readings import op_read  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/usda"
API = "https://api.nal.usda.gov/fdc/v1/foods"
PER_CALL = 20
FIELDS = ("fdcId", "dataType", "description", "publicationDate", "fetched_at", "nutrients", "portions")


def cached(fdc_id: int) -> Path:
    return CACHE / f"{int(fdc_id)}.json"


def api_key(ref: str) -> str:
    ref = ref or os.environ.get("NB_FOOD_USDA_KEY_REF", "")
    if not ref:
        raise SystemExit("usda: no --key-ref and no NB_FOOD_USDA_KEY_REF")
    return op_read(ref)


def portion_label(p: dict) -> str:
    unit = (p.get("measureUnit") or {}).get("name", "")
    parts = [str(p.get("amount") or ""), "" if unit == "undetermined" else unit, p.get("modifier") or "",
             p.get("portionDescription") or ""]
    return " ".join(" ".join(x.strip() for x in parts if x and x.strip()).split())


def record(food: dict, fetched_at: str) -> dict:
    nutrients = []
    for n in food.get("foodNutrients", []):
        meta = n.get("nutrient") or {}
        if n.get("amount") is None or not meta.get("id"):
            continue
        nutrients.append({"id": meta["id"], "number": meta.get("number"), "name": meta.get("name"),
                          "unit": meta.get("unitName"), "amount": n["amount"]})
    nutrients.sort(key=lambda n: n["id"])
    fndds = food.get("dataType") == "Survey (FNDDS)"  # its portion modifier is a code, not words
    portions = [{"description": (p.get("portionDescription") or "").strip() if fndds else portion_label(p),
                 "gram_weight": p["gramWeight"]}
                for p in food.get("foodPortions", []) if p.get("gramWeight")]
    return {"fdcId": food["fdcId"], "dataType": food.get("dataType"), "description": food.get("description"),
            "publicationDate": food.get("publicationDate"), "fetched_at": fetched_at,
            "nutrients": nutrients, "portions": portions}


def fetch(ids: list, key_ref: str) -> dict:
    """Cache every id without a cached file. -> {"requests": n, "cached": [...], "missing": [...]}."""
    todo = sorted({int(i) for i in ids if not cached(i).exists()})
    out = {"requests": 0, "cached": [], "missing": []}
    if not todo:
        return out
    key = api_key(key_ref)
    CACHE.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(todo), PER_CALL):
        chunk = todo[start:start + PER_CALL]
        req = urllib.request.Request(API, data=json.dumps({"fdcIds": chunk, "format": "full"}).encode(),
                                     headers={"Content-Type": "application/json", "X-Api-Key": key}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            foods = json.loads(resp.read())
        out["requests"] += 1
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        got = set()
        for food in foods:
            rec = record(food, fetched_at)
            cached(rec["fdcId"]).write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
            got.add(rec["fdcId"])
            out["cached"].append(rec["fdcId"])
        out["missing"] += [i for i in chunk if i not in got]
    return out


def record_problems(name: str, d: dict) -> list:
    if tuple(d) != FIELDS:
        return [f"usda/{name}: fields {list(d)} != {list(FIELDS)}"]
    if name != f"{d['fdcId']}.json" or not d["fetched_at"] or not d["publicationDate"]:
        return [f"usda/{name}: not a dated record of fdcId {name[:-5]}"]
    return []


def check_usda_cache(root: Path) -> list:
    """Enforcer for the cache invariant: every file is a whole, dated record named by its
    fdcId, and every fdcId a mapping uses has a cached record."""
    problems = []
    for f in sorted((root / "data/usda").glob("*.json")):
        problems += record_problems(f.name, json.loads(f.read_text()))
    fm = root / "data/food_map.json"
    if fm.exists():
        for row in json.loads(fm.read_text())["rows"]:
            if row.get("fdcId") and not (root / f"data/usda/{row['fdcId']}.json").exists():
                problems.append(f"{row['id']}: mapped to fdcId {row['fdcId']} with no cached record")
    gf = root / "data/grocery_foods.json"
    if gf.exists():
        for row in json.loads(gf.read_text())["rows"]:
            if not (root / f"data/usda/{row['fdcId']}.json").exists():
                problems.append(f"grocery food {row['food']}: fdcId {row['fdcId']} has no cached record")
    return problems


def record_case(case: dict) -> dict:
    return {"problems": len(record_problems(case["name"], case["record"]))}


def main(argv: list) -> int:
    key_ref, ids, mapped, i = "", [], False, 0
    while i < len(argv):
        a = argv[i]
        if a == "--key-ref" and i + 1 < len(argv):
            key_ref = argv[i + 1]
            i += 1
        elif a == "--mapped":
            mapped = True
        elif a.isdigit():
            ids.append(int(a))
        else:
            raise SystemExit(f"usda: unknown argument {a!r}")
        i += 1
    if mapped:
        ids += [r["fdcId"] for r in json.loads((ROOT / "data/food_map.json").read_text())["rows"] if r.get("fdcId")]
        ids += [r["fdcId"] for r in json.loads((ROOT / "data/grocery_foods.json").read_text())["rows"]]
    out = fetch(ids, key_ref)
    print(f"usda: {out['requests']} request(s); cached {len(out['cached'])}; not returned by the API {out['missing']}")
    return 1 if out["missing"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
