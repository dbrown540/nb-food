#!/usr/bin/env python3
"""Build data/usda_index.json: the USDA FoodData Central entries a menu item or
product can be mapped to, with their household portions.

Sources are USDA's public bulk downloads (gitignored under data/usda_bulk/):
Foundation and SR Legacy (single foods) and Survey FNDDS (mixed dishes as
eaten). Only descriptions and portion weights are kept here: this index is
what candidate search reads. Nutrient values come from the API and are cached
per record by scripts/usda.py.

    python3 scripts/usda_index.py --fetch   # download the bulk releases, then build
    python3 scripts/usda_index.py           # build from the downloaded releases
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BULK = ROOT / "data/usda_bulk"
OUT = ROOT / "data/usda_index.json"
BASE = "https://fdc.nal.usda.gov/fdc-datasets/"
RELEASES = {  # release folder -> (bulk data_type, API dataType)
    "FoodData_Central_foundation_food_csv_2025-04-24": ("foundation_food", "Foundation"),
    "FoodData_Central_sr_legacy_food_csv_2018-04": ("sr_legacy_food", "SR Legacy"),
    "FoodData_Central_survey_food_csv_2024-10-31": ("survey_fndds_food", "Survey (FNDDS)"),
}


def table(release: str, name: str) -> list:
    path = next((BULK / release).rglob(name))
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch() -> None:
    BULK.mkdir(parents=True, exist_ok=True)
    for rel in RELEASES:
        z = BULK / f"{rel}.zip"
        subprocess.run(["curl", "-sf", "-m", "300", "-o", str(z), BASE + z.name], check=True)
        subprocess.run(["unzip", "-q", "-o", str(z), "-d", str(BULK / rel)], check=True)


def portion_label(row: dict, units: dict) -> str:
    """'1 cup', '2 tbsp chopped', '1 ring': amount, unit (when determined), modifier, description."""
    unit = units.get(row["measure_unit_id"], "")
    parts = [row["amount"], "" if unit == "undetermined" else unit, row["modifier"], row["portion_description"]]
    return " ".join(" ".join(p.strip() for p in parts if p and p.strip()).split())


def build() -> dict:
    foods = []
    for rel, (bulk_type, api_type) in RELEASES.items():
        units = {r["id"]: r["name"] for r in table(rel, "measure_unit.csv")}
        if api_type == "Survey (FNDDS)":
            cats = {r["wweia_food_category"]: r["wweia_food_category_description"] for r in table(rel, "wweia_food_category.csv")}
        else:
            cats = {r["id"]: r["description"] for r in table(rel, "food_category.csv")}
        rows = [r for r in table(rel, "food.csv") if r["data_type"] == bulk_type]
        ids = {r["fdc_id"] for r in rows}
        portions = {}
        for p in table(rel, "food_portion.csv"):
            if p["fdc_id"] in ids and p["gram_weight"]:
                label = portion_label(p, units)
                if api_type == "Survey (FNDDS)":
                    label = p["portion_description"].strip() or label
                portions.setdefault(p["fdc_id"], []).append([label, round(float(p["gram_weight"]), 1)])
        for r in rows:
            foods.append({"fdcId": int(r["fdc_id"]), "dataType": api_type, "description": r["description"],
                          "category": cats.get(r["food_category_id"], ""), "portions": portions.get(r["fdc_id"], [])})
    foods.sort(key=lambda f: f["fdcId"])
    return {"schema_version": 1, "releases": sorted(RELEASES), "foods": foods}


def main(argv: list) -> int:
    if argv not in ([], ["--fetch"]):
        raise SystemExit(f"usda_index: unknown argument(s) {argv}")
    if argv == ["--fetch"]:
        fetch()
    doc = build()
    rows = ",\n".join(json.dumps(f, ensure_ascii=False) for f in doc["foods"])
    OUT.write_text('{"schema_version": 1,\n "releases": %s,\n "foods": [\n%s\n]}\n' % (json.dumps(doc["releases"]), rows))
    by = {}
    for f in doc["foods"]:
        by[f["dataType"]] = by.get(f["dataType"], 0) + 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doc['foods'])} foods {by}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
