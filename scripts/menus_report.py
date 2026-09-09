#!/usr/bin/env python3
"""Coverage report for the menus layer (data/menus/).

Prints counts by status, item totals, price-level distribution, and the
list of places with no reliable menu source. Stdlib only.

    python3 scripts/menus_report.py
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENUS = os.path.join(ROOT, "data", "menus")
INDEX = os.path.join(MENUS, "index.json")


def main():
    if not os.path.exists(INDEX):
        print("no data/menus/index.json — nothing to report", file=sys.stderr)
        return 1
    index = json.load(open(INDEX))
    by_status = Counter(e["status"] for e in index)
    items_total = sum(e["items_count"] for e in index)
    priced = 0
    levels = Counter()
    for e in index:
        path = os.path.join(MENUS, e["slug"] + ".json")
        if not os.path.exists(path):
            print(f"WARN missing file for {e['slug']}", file=sys.stderr)
            continue
        doc = json.load(open(path))
        priced += sum(1 for i in doc["items"] if i.get("price") is not None)
        if doc.get("price_level_estimate"):
            levels[doc["price_level_estimate"]] += 1

    print(f"menus layer: {len(index)} places indexed (as_of "
          f"{min(e['as_of'] for e in index)} .. {max(e['as_of'] for e in index)})")
    print()
    print("by status:")
    for status in ("ok", "partial", "not_found", "skipped"):
        print(f"  {status:<10} {by_status.get(status, 0):>3}")
    print()
    print(f"items: {items_total} total, {priced} with a price")
    print("price_level_estimate:", ", ".join(f"L{k}={v}" for k, v in sorted(levels.items())) or "n/a")
    print()

    nf = [e for e in index if e["status"] == "not_found"]
    print(f"not_found ({len(nf)}):")
    for e in sorted(nf, key=lambda x: x["name"].lower()):
        print(f"  - {e['name']}" + (f"  [{e['menu_url']}]" if e.get("menu_url") else ""))

    other = [e for e in index if e["status"] in ("partial", "skipped")]
    if other:
        print()
        print("partial / skipped:")
        for e in sorted(other, key=lambda x: (x["status"], x["name"].lower())):
            print(f"  - {e['status']:<8} {e['name']} ({e['items_count']} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
