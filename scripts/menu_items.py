#!/usr/bin/env python3
"""Derive data/menu_items.json, one flat row per menu item or store product.

Sources: every data/menus/<slug>.json (restaurant and cafe menus) and every
data/products/<slug>.json (a store's packaged products). The output is
derived, never hand-edited; `--check` exits 1 when the committed file differs
from what this script would write (run by check_data.py and the pre-commit
hook). The row schema and its version are the interface consumers pin; see
README "Item table".

Row id = slug(place key) + "--" + slug(item name). Names that repeat within a
place get "-2", "-3", ... in the order (section, description, size, price,
name), so the same menu yields the same ids however its file is ordered.

    python3 scripts/menu_items.py          # rewrite data/menu_items.json
    python3 scripts/menu_items.py --check  # exit 1 if it is stale
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/menu_items.json"
SCHEMA_VERSION = 1
FIELDS = ("id", "place", "kind", "section", "name", "description", "size", "price", "source", "as_of", "status")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def source_rows() -> list:
    rows = []
    for path in sorted((ROOT / "data/menus").glob("*.json")):
        if path.name == "index.json":
            continue
        d = json.loads(path.read_text())
        for it in d.get("items", []):
            rows.append({"place": d["name"], "kind": "menu", "section": it["section"] or "", "name": it["item"],
                         "description": it["description"] or "", "size": "", "price": it["price"],
                         "source": d["source"], "as_of": d["as_of"], "status": d["status"]})
    for path in sorted((ROOT / "data/products").glob("*.json")):
        d = json.loads(path.read_text())
        for p in d["products"]:
            rows.append({"place": d["name"], "kind": "product", "section": p["section"] or "", "name": p["name"],
                         "description": p.get("description") or "", "size": p.get("size") or "", "price": p["price"],
                         "source": d["source"], "as_of": d["as_of"], "status": d["status"]})
    return rows


def with_ids(rows: list) -> list:
    order = lambda r: (r["section"], r["description"], r["size"], r["price"] if r["price"] is not None else -1, r["name"])
    groups = {}
    for r in rows:
        groups.setdefault(f"{slug(r['place'])}--{slug(r['name'])}", []).append(r)
    out = []
    for base, grp in groups.items():
        for n, r in enumerate(sorted(grp, key=order), start=1):
            out.append({"id": base if n == 1 else f"{base}-{n}", **r})
    ids = [r["id"] for r in out]
    if len(ids) != len(set(ids)):  # a "-2" suffix can collide with a name that itself ends in "-2"
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise SystemExit(f"menu_items: id collision {dup[:5]}")
    return sorted(out, key=lambda r: r["id"])


def render(rows: list) -> str:
    lines = [json.dumps({k: r[k] for k in FIELDS}, ensure_ascii=False) for r in rows]
    return '{"schema_version": %d,\n "rows": [\n%s\n]}\n' % (SCHEMA_VERSION, ",\n".join(lines))


def main(argv: list) -> int:
    unknown = [a for a in argv if a != "--check"]
    if unknown:
        raise SystemExit(f"menu_items: unknown argument(s) {unknown}")
    rows = with_ids(source_rows())
    text = render(rows)
    if "--check" in argv:
        if OUT.exists() and OUT.read_text() == text:
            print(f"menu_items.json is current ({len(rows)} rows)")
            return 0
        print("menu_items.json is STALE; run scripts/menu_items.py", file=sys.stderr)
        return 1
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows "
          f"({sum(r['kind'] == 'menu' for r in rows)} menu, {sum(r['kind'] == 'product' for r in rows)} product)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
