#!/usr/bin/env python3
"""Integrity gate on the built data: exit 1 on any of

  - a `key` that is missing, duplicated, or whose place has no neighborhood
  - a street-risk / inspection layer entry whose key matches no place
  - a place without a street-risk entry (the layer is meant to be complete)
  - a menu file whose `name` is not a place key, or whose status is unknown
  - a menus index that differs from what menus_index.py would write
  - a menu item without the four fields, or with a non-numeric price

    python3 scripts/check_data.py
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"ok", "partial", "not_found", "skipped"}


def main() -> int:
    problems = []
    places = json.loads((ROOT / "data/places.json").read_text())
    keys = [p.get("key") for p in places]
    if None in keys:
        problems.append(f"{keys.count(None)} place(s) without a key")
    dup = [k for k, n in Counter(keys).items() if n > 1]
    if dup:
        problems.append(f"duplicate keys: {dup[:5]}")
    nn = [p["name"] for p in places if not p.get("neighborhood")]
    if nn:
        problems.append(f"{len(nn)} place(s) without a neighborhood: {nn[:5]}")
    keyset = set(keys)

    risk = json.loads((ROOT / "data/crime/poi_street_risk.json").read_text())["pois"]
    orphans = sorted(set(risk) - keyset)
    if orphans:
        problems.append(f"{len(orphans)} street-risk entries match no place: {orphans[:5]}")
    missing = sorted(keyset - set(risk))
    if missing:
        problems.append(f"{len(missing)} place(s) without a street-risk entry: {missing[:5]}")

    insp = json.loads((ROOT / "data/inspections/poi_inspections.json").read_text())
    orphans = sorted(set(insp) - {"_meta"} - keyset)
    if orphans:
        problems.append(f"{len(orphans)} inspection entries match no place: {orphans[:5]}")

    menus_dir = ROOT / "data/menus"
    index_path = menus_dir / "index.json"
    for path in sorted(menus_dir.glob("*.json")):
        if path == index_path:
            continue
        d = json.loads(path.read_text())
        if d.get("name") not in keyset:
            problems.append(f"{path.name}: name {d.get('name')!r} is not a place key")
        if d.get("status") not in STATUSES:
            problems.append(f"{path.name}: status {d.get('status')!r}")
        for i in d.get("items", []):
            if set(i) != {"section", "item", "price", "description"} or not str(i.get("item", "")).strip() \
                    or (i.get("price") is not None and not isinstance(i["price"], (int, float))):
                problems.append(f"{path.name}: malformed item {str(i)[:80]}")
                break
    r = subprocess.run([sys.executable, str(ROOT / "scripts/menus_index.py"), "--check"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        problems.append("data/menus/index.json is stale (run scripts/menus_index.py)")

    for p in problems:
        print("FAIL", p)
    print(f"check_data: {len(problems)} problem(s); {len(places)} places, {len(risk)} risk, "
          f"{len(insp) - 1} inspections, {len(list(menus_dir.glob('*.json'))) - 1} menu files")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
