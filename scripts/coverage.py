#!/usr/bin/env python3
"""Coverage per neighborhood, as a Markdown table, from the built data/places.json.

Counts places, walk-time range, and how many carry each enrichment layer
(street risk, DPH inspection match, menu file by status). The menu columns
read data/menus/index.json by POI key. Paste the output into
docs/nb-food-coverage-report.md rather than typing numbers by hand.

    python3 scripts/coverage.py
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORDER = ["North Beach", "Chinatown", "Fisherman's Wharf", "Russian Hill",
         "Nob Hill", "Financial District/South Beach"]


def main() -> None:
    places = json.loads((ROOT / "data/places.json").read_text())
    index = {m["name"]: m for m in json.loads((ROOT / "data/menus/index.json").read_text())}
    rows = []
    groups = {}
    for p in places:
        groups.setdefault(p.get("neighborhood") or "(none)", []).append(p)
    names = [n for n in ORDER if n in groups] + sorted(set(groups) - set(ORDER))
    header = ("| neighborhood | places | rest. | cafes | groc. | walk min | street risk | DPH match "
              "| DPH name+addr | menus tried | ok | partial | not_found | skipped |")
    print(header)
    print("|" + "---|" * (header.count("|") - 1))
    tot = Counter()
    for n in names + ["TOTAL"]:
        ps = places if n == "TOTAL" else groups[n]
        cat = Counter(p["category"] for p in ps)
        st = Counter(index[p["key"]]["status"] for p in ps if p["key"] in index)
        tried = sum(st.values())
        insp = sum(1 for p in ps if "inspection" in p)
        insp_addr = sum(1 for p in ps if p.get("inspection", {}).get("match_confidence") == "name+address")
        walk = f"{min(p['walkMin'] for p in ps)}–{max(p['walkMin'] for p in ps)}"
        print(f"| {n} | {len(ps)} | {cat['restaurant']} | {cat['cafe']} | {cat['grocery']} | {walk} | "
              f"{sum(1 for p in ps if 'risk' in p)} | {insp} | {insp_addr} | {tried} | "
              f"{st['ok']} | {st['partial']} | {st['not_found']} | {st['skipped']} |")
    eat = [p for p in places if p["category"] in ("restaurant", "cafe")]
    covered = sum(1 for p in eat if index.get(p["key"], {}).get("status") in ("ok", "partial"))
    print(f"\nRestaurants + cafes: {len(eat)}; with a menu (ok or partial): {covered}; "
          f"attempted: {sum(1 for p in eat if p['key'] in index)}.")
    zero = [p for p in places if p.get("risk", {}).get("total") == 0 and (p['risk'].get('nearest_incident_m') or 0) > 150]
    by = ", ".join(f"{n} {c}" for n, c in Counter(p["neighborhood"] for p in zero).most_common())
    print(f"Street-risk geocoding gaps (total 0, nearest snap point > 150 m): {len(zero)} places ({by}).")


if __name__ == "__main__":
    main()
