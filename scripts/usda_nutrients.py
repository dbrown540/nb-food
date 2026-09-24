#!/usr/bin/env python3
"""Build data/nutrients.json: per-100 g nutrients for every USDA record that
data/food_map.json and data/grocery_foods.json reference.

Principle "food-nutrients" (spine/stages/nutrients.json): a food's nutrients
are the public record's own values per 100 g, read by nutrient identity with a
fixed fallback order (spine/bindings.json "food-nutrients"), and a nutrient the
record does not carry is unknown (null), never zero.

Source: USDA FoodData Central bulk releases in data/usda_bulk/ (gitignored;
`python3 scripts/usda_index.py --fetch`). The Survey (FNDDS) release writes the
nutrient NUMBER (208 = energy) in food_nutrient.nutrient_id where the other
releases write the nutrient id (1008); each release's nutrient.csv maps one to
the other, and ids (four digits) and numbers (three) never collide.

Output is derived, never hand-edited, and deterministic (rows sorted by fdcId,
values as USDA prints them). `--check`: with the bulk releases present, the
file must equal what this script writes; without them (a clean checkout), every
value is checked against the committed per-record copies in data/usda/, which
were fetched from the FoodData Central API independently of the bulk files.

    python3 scripts/usda_nutrients.py            # rewrite data/nutrients.json
    python3 scripts/usda_nutrients.py --check
"""
import csv
import glob
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usda_index import RELEASES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BULK = ROOT / "data/usda_bulk"
OUT = ROOT / "data/nutrients.json"
SCHEMA_VERSION = 1


def cfg(root: Path = ROOT) -> dict:
    return json.loads((root / "spine/bindings.json").read_text())["bindings"]["food-nutrients"]


def mapped_ids(root: Path = ROOT) -> list:
    """Every fdcId a mapping uses: the menu food map's and the grocery foods'."""
    ids = {r["fdcId"] for r in json.loads((root / "data/food_map.json").read_text())["rows"] if r.get("fdcId")}
    grocery = root / "data/grocery_foods.json"
    if grocery.exists():
        ids |= {r["fdcId"] for r in json.loads(grocery.read_text())["rows"]}
    return sorted(ids)


def nutrient_row(food: dict, amounts: dict, fields: dict) -> dict:
    """food: {fdcId, dataType, description}; amounts: {nutrient id: amount string as USDA prints it};
    fields: {field: [nutrient ids in fallback order]} -> one row. The first id the record carries
    gives the value; a field no id covers is null."""
    per, used = {}, {}
    for field, ids in fields.items():
        hit = next((i for i in ids if amounts.get(i) not in (None, "")), None)
        per[field] = float(amounts[hit]) if hit is not None else None
        used[field] = hit
    return {"fdcId": food["fdcId"], "dataType": food["dataType"], "description": food["description"],
            "per_100g": per, "nutrient_ids": used}


def row_case(case: dict) -> dict:
    """Canonical-case entry: a record's own CSV rows (as extracted) -> its row."""
    amounts = {int(k): v for k, v in case["amounts"].items()}
    return nutrient_row(case["food"], amounts, case.get("fields") or cfg()["fields"])


def read_bulk(ids: set, fields: dict) -> tuple:
    """-> (foods {fdcId: food}, amounts {fdcId: {nutrient id: amount}}, extracted rows for the input hash)."""
    wanted_ids = {i for ids_ in fields.values() for i in ids_}
    rank = {i: pos for ids_ in fields.values() for pos, i in enumerate(ids_)}
    foods, amounts, extracted = {}, {}, []
    for rel, (bulk_type, api_type) in RELEASES.items():
        base = BULK / rel
        path = lambda name: glob.glob(str(base / "**" / name), recursive=True)[0]
        # several ids can share a number (205: carbohydrate by difference and by summation; 269: total
        # sugars and total sugars NLEA); a number stands for the wanted id earliest in its field's fallback
        nbr_to_id = {}
        with open(path("nutrient.csv"), newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                nid = int(r["id"])
                if r.get("nutrient_nbr") and nid in rank:
                    nbr = str(int(float(r["nutrient_nbr"])))
                    if nbr not in nbr_to_id or rank[nid] < rank[nbr_to_id[nbr]]:
                        nbr_to_id[nbr] = nid
        with open(path("food.csv"), newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                i = int(r["fdc_id"])
                if i in ids and r["data_type"] == bulk_type:
                    foods[i] = {"fdcId": i, "dataType": api_type, "description": r["description"]}
                    extracted.append(["food", rel, r["fdc_id"], r["data_type"], r["description"]])
        with open(path("food_nutrient.csv"), newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                i = int(r["fdc_id"])
                if i not in ids:
                    continue
                code = str(int(float(r["nutrient_id"])))
                nid = int(code) if len(code) >= 4 else nbr_to_id.get(code)
                if nid in wanted_ids:
                    amounts.setdefault(i, {})[nid] = r["amount"]
                    extracted.append(["amount", rel, r["fdc_id"], str(nid), r["amount"]])
    return foods, amounts, sorted(extracted)


def build(root: Path = ROOT) -> dict:
    c = cfg(root)
    fields = {k: [int(x) for x in v] for k, v in c["fields"].items()}
    ids = mapped_ids(root)
    foods, amounts, extracted = read_bulk(set(ids), fields)
    missing = [i for i in ids if i not in foods]
    if missing:
        raise SystemExit(f"usda_nutrients: {len(missing)} mapped fdcId(s) not in the bulk releases: {missing[:5]}")
    h = hashlib.sha256(json.dumps({"fields": fields, "rows": extracted}, ensure_ascii=False).encode()).hexdigest()
    return {"schema_version": SCHEMA_VERSION,
            "basis": {"releases": [{"name": rel, "date": rel.rsplit("_", 1)[-1]} for rel in sorted(RELEASES)],
                      "script": "scripts/usda_nutrients.py", "inputs_sha256": h,
                      "fields": {k: v for k, v in fields.items()}},
            "rows": [nutrient_row(foods[i], amounts.get(i, {}), fields) for i in ids]}


def render(doc: dict) -> str:
    head = json.dumps({k: v for k, v in doc.items() if k != "rows"}, ensure_ascii=False, indent=1)[:-2]
    rows = ",\n".join(json.dumps(r, ensure_ascii=False) for r in doc["rows"])
    return f'{head},\n "rows": [\n{rows}\n]}}\n'


def bounds_problems(row: dict, b: dict) -> list:
    p, out = row["per_100g"], []
    for field, (lo, hi) in b["per_field"].items():
        v = p.get(field)
        if v is not None and not lo <= v <= hi:
            out.append(f"{row['fdcId']}: {field} {v} outside {lo}..{hi}")
    parts = [p.get(f) for f in b["sum_fields"]]
    if all(v is not None for v in parts) and sum(parts) > b["sum_max"]:
        out.append(f"{row['fdcId']}: {' + '.join(b['sum_fields'])} = {sum(parts):.1f} over {b['sum_max']}")
    return out


def bounds_case(case: dict) -> dict:
    return {"problems": len(bounds_problems(case["row"], case["bounds"]))}


def printed_precision(x) -> float:
    """How far a record-copy value may sit from the bulk value it was printed from: half a unit
    in its last printed decimal, or in its third significant figure, whichever is wider (the API
    prints some survey values rounded: 1.63 for 1.626, 1620 for 1625)."""
    x = float(x)
    text = repr(x)
    places = len(text.split(".")[1].rstrip("0")) if "." in text else 0
    sig3 = 0.5 * 10 ** (math.floor(math.log10(abs(x))) - 2) if x else 0.0
    return max(0.5 * 10 ** -places, sig3) + 1e-9


def check_nutrients(root: Path = ROOT, notes: list = None) -> list:
    """Enforcer for food-nutrients: exactly one row per fdcId the food map references; every
    value inside its physical bounds; every value equal to the committed per-record copy of the
    same record (data/usda) within its printed precision. A null where the copy carries a value
    is the bulk release lacking it (the table reads the bulk release); it is appended to
    `notes`, not rejected."""
    f = root / "data/nutrients.json"
    if not f.exists():
        return ["data/nutrients.json missing"]
    doc = json.loads(f.read_text())
    c = cfg(root)
    rows = {r["fdcId"]: r for r in doc["rows"]}
    problems = []
    ids = set(mapped_ids(root))
    if set(rows) != ids:
        problems.append(f"nutrients rows != mapped fdcIds: missing {sorted(ids - set(rows))[:5]}, extra {sorted(set(rows) - ids)[:5]}")
    for i, r in sorted(rows.items()):
        problems += bounds_problems(r, c["bounds"])
        rec_f = root / f"data/usda/{i}.json"
        if not rec_f.exists():
            continue  # check_usda_cache reports a mapping without its record
        rec = {n["id"]: n["amount"] for n in json.loads(rec_f.read_text())["nutrients"]}
        for field, ids_ in c["fields"].items():
            v, used = r["per_100g"][field], r["nutrient_ids"][field]
            first = next((int(x) for x in ids_ if int(x) in rec), None)
            if v is None and first is not None:
                if notes is not None:
                    notes.append(f"{i}: {field} null in the bulk release; the API copy carries nutrient {first}")
            elif v is not None and (used not in rec or abs(float(rec[used]) - v) > printed_precision(rec[used])):
                problems.append(f"{i}: {field} {v} (nutrient {used}) differs from the record copy {rec.get(used)}")
    return problems


def main(argv: list) -> int:
    if argv not in ([], ["--check"]):
        raise SystemExit(f"usda_nutrients: unknown argument(s) {argv}")
    have_bulk = all((BULK / rel).exists() for rel in RELEASES)
    if argv == ["--check"]:
        if have_bulk:
            if OUT.exists() and OUT.read_text() == render(build()):
                print(f"nutrients.json is current ({len(json.loads(OUT.read_text())['rows'])} rows)")
                return 0
            print("nutrients.json is STALE; run scripts/usda_nutrients.py", file=sys.stderr)
            return 1
        notes = []
        problems = check_nutrients(notes=notes)
        for p in problems[:20]:
            print(p, file=sys.stderr)
        for n in notes:
            print("note:", n)
        print(f"nutrients.json: bulk releases absent; checked against data/usda record copies: {len(problems)} problem(s)")
        return 1 if problems else 0
    if not have_bulk:
        raise SystemExit("usda_nutrients: bulk releases missing; run scripts/usda_index.py --fetch")
    doc = build()
    OUT.write_text(render(doc))
    nulls = {k: sum(1 for r in doc["rows"] if r["per_100g"][k] is None) for k in doc["basis"]["fields"]}
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doc['rows'])} rows; nulls per field {nulls}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
