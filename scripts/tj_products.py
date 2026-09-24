#!/usr/bin/env python3
"""Build data/products/trader-joe-s.json from a Trader Joe's product-API pull.

traderjoes.com blocks non-browser clients, so the pull runs in a browser on
traderjoes.com: POST /api/graphql `products` filtered to store_code 19
(San Francisco - North Beach, 401 Bay St), published + available, 100 per
page, saved as JSON {store_code, fetched_at, rows} with rows of
[sku, item_title, retail_price, sales_size, sales_uom_description, category_path].

Only food and drink are kept: a product whose category path starts with a
non-food department (NON_FOOD) is left out. Each product becomes one row:
section = category path without the leading "Food>", price = the store's
retail price, size = pack size as printed, plus what the size means
(scripts/packages.py): sold_by (weight | volume | each | count), package_g for a
weight, package_ml for a volume, units for items sold by the each or by count.
The store's API carries no description.

`--refresh` re-derives those size facts on the committed file without a new pull.

    python3 scripts/tj_products.py PULL.json
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packages import package_facts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/products/trader-joe-s.json"
NON_FOOD = ("Everything Else", "Flowers & Plants", "Bouquets", "Plants")


def clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def size(n, uom) -> str:
    n = f"{n:g}" if isinstance(n, (int, float)) else clean(n)
    return clean(f"{n} {uom or ''}")


def build(pull: dict) -> dict:
    if pull.get("store_code") != "19":
        raise SystemExit(f"expected store_code 19, got {pull.get('store_code')!r}")
    seen, products = set(), []
    for sku, title, price, n, uom, path in pull["rows"]:
        path = clean(path)
        if sku in seen or path.startswith(NON_FOOD):
            continue
        seen.add(sku)
        section = path.removeprefix("Food>") or "Uncategorized"
        sz = size(n, uom)
        products.append({"section": section.replace(">", " / "), "name": clean(title), "description": "",
                         "size": sz, "price": float(price) if price not in (None, "") else None, **package_facts(sz)})
    products.sort(key=lambda p: (p["section"], p["name"], p["size"]))
    as_of = datetime.fromisoformat(pull["fetched_at"].replace("Z", "+00:00")).astimezone().date().isoformat()
    return {
        "name": "Trader Joe's",
        "addr": "401 Bay Street",
        "source_url": "https://www.traderjoes.com/home/products/category/food-8",
        "source": "traderjoes.com product API (store_code 19, San Francisco - North Beach; "
                  "published + available items at store retail price; pulled in a browser session)",
        "as_of": as_of,
        "status": "ok",
        "extraction": {"method": "script", "path": "scripts/tj_products.py", "pulled_at": pull["fetched_at"]},
        "products": products,
    }


def main(argv: list) -> int:
    if argv == ["--refresh"]:
        doc = json.loads(OUT.read_text())
        doc["products"] = [{k: p[k] for k in ("section", "name", "description", "size", "price")} | package_facts(p["size"])
                           for p in doc["products"]]
    elif len(argv) == 1:
        doc = build(json.loads(Path(argv[0]).expanduser().read_text()))
    else:
        raise SystemExit("usage: tj_products.py PULL.json | --refresh")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doc['products'])} products")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
