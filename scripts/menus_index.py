#!/usr/bin/env python3
"""Regenerate data/menus/index.json from the per-place files data/menus/<slug>.json.

The index is derived, never hand-edited: one entry per file, sorted by slug,
carrying name / slug / status / menu_url / items_count / source / as_of. A
file whose `name` is not a POI key in data/places.json is reported (the build
merges the menus layer by that key), as is a status outside the four allowed.

    python3 scripts/menus_index.py          # rewrite the index
    python3 scripts/menus_index.py --check  # exit 1 if the committed index is stale
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MENUS = ROOT / "data/menus"
INDEX = MENUS / "index.json"
STATUSES = {"ok", "partial", "not_found", "skipped"}


def build_index() -> list:
    entries = []
    for path in sorted(MENUS.glob("*.json")):
        if path == INDEX:
            continue
        doc = json.loads(path.read_text())
        if doc.get("status") not in STATUSES:
            raise SystemExit(f"{path.name}: status {doc.get('status')!r} not in {sorted(STATUSES)}")
        for k in ("name", "source", "as_of", "items"):
            if not doc.get(k) and k != "items":
                raise SystemExit(f"{path.name}: missing {k}")
        entries.append({"name": doc["name"], "slug": path.stem, "status": doc["status"],
                        "menu_url": doc.get("menu_url"), "items_count": len(doc.get("items", [])),
                        "source": doc["source"], "as_of": doc["as_of"]})
    return entries


def main() -> int:
    entries = build_index()
    places = ROOT / "data/places.json"
    if places.exists():
        keys = {p.get("key", p["name"]) for p in json.loads(places.read_text())}
        orphans = [e["name"] for e in entries if e["name"] not in keys]
        if orphans:
            print(f"WARN {len(orphans)} menu file(s) whose name is not a POI key: {orphans}", file=sys.stderr)
    text = json.dumps(entries, indent=1, ensure_ascii=False)
    if "--check" in sys.argv:
        if INDEX.exists() and INDEX.read_text() == text:
            print(f"index.json is current ({len(entries)} entries)")
            return 0
        print("index.json is STALE; run scripts/menus_index.py", file=sys.stderr)
        return 1
    INDEX.write_text(text)
    by = {}
    for e in entries:
        by[e["status"]] = by.get(e["status"], 0) + 1
    print(f"wrote {INDEX.relative_to(ROOT)}: {len(entries)} entries " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
