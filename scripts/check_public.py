#!/usr/bin/env python3
"""Publish gate: exit 1 if any tracked file mentions a personal-context term.

The repo is public and describes restaurants, public datasets and sources —
nothing about who uses the index. Two pattern groups:

  OWNER  personal identifiers (full name, domain, personal email) — checked
         in EVERY tracked file, no exemptions.
  TOPIC  wellness / regimen wording, and the owner's first name alone —
         checked everywhere except verbatim public data, where the words
         belong to the city or to other businesses: data/inspections/** (DPH
         text), data/sf.db + data/sf_places.json (OSM names/tags), and store
         product lists data/products/** (names as the store prints them,
         written by a pull script). The OSM shop value `health_food` and soda
         product names are exempt by pattern. Derived tables that hold only
         words copied from those sources are exempt too, because their own
         --check gates refuse any content the derivation did not write:
         data/menu_items.json (menu_items.py --check) and data/item_tags.json
         (tag_items.py --check: every quoted word must occur in the item),
         data/tag_pins.jsonl (check_item_tags: a pin holds only its item's
         own words and closed answer codes) and data/food_map.json
         (map_foods.py --check).
         USDA FoodData Central text (data/usda/**, data/usda_index.json,
         data/nutrients.json) is
         public data written by scripts, like the OSM and DPH text.

Build outputs (data/places.json, docs/index.html) are checked like sources,
so a stray term in the curated overlay or the viewer template fails here.

    python3 scripts/check_public.py            # gate over `git ls-files`
    python3 scripts/check_public.py PATH ...   # gate over the given paths
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNER = [  # everywhere, no exemptions
    (r"\bdanny brown\b", "owner full name"),
    (r"therenthacker", "owner domain"),
    (r"\b[a-z0-9._-]+@(gmail|icloud|me|hotmail|yahoo|outlook|proton)\.\w+\b", "personal email"),
]
OWNER_NAME = [  # first name alone: everywhere except verbatim public data (other businesses carry it)
    (r"\bdanny\b", "owner name"),
]
TOPIC = [
    (r"\bhealth(?!_food\b)", "health"),
    (r"\bhealthy\b", "healthy"),
    (r"\bdiet(ary|s)?\b(?!\s+(coke|pepsi|dr\b|soda|sprite|7up|mountain|ginger|root))", "diet"),
    (r"\bnutrition(al)?\b", "nutrition"),
    (r"\bcalorie", "calorie"),
    (r"\ballerg", "allergen"),
    (r"\bmedical\b", "medical"),
    (r"\bmacros\b|\bpre-?gym\b|\bworkout\b", "regimen"),
]
TOPIC_EXEMPT = ("data/inspections/", "data/sf.db", "data/sf_places.json", "data/sf_osm_raw.json", "data/products/",
                "data/menu_items.json", "data/item_tags.json", "data/food_map.json", "data/tag_pins.jsonl",
                "data/usda/", "data/usda_index.json", "data/nutrients.json")
SELF = "scripts/check_public.py"  # holds the pattern table; not scanned


def tracked() -> list:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / f for f in out.split("\n") if f]


def scan(path: Path) -> list:
    rel = str(path.relative_to(ROOT))
    try:
        text = path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_text(rel, text)


def scan_text(rel: str, text: str) -> list:
    if rel == SELF:  # the gate's own pattern table
        return []
    pats = list(OWNER) + ([] if rel.startswith(TOPIC_EXEMPT) else list(OWNER_NAME) + list(TOPIC))
    hits = []
    for pat, label in pats:
        for m in re.finditer(pat, text, re.IGNORECASE):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{rel}:{line}: {label} -> {text[max(0, m.start() - 30):m.end() + 30]!r}")
    return hits


def scan_case(case: dict) -> dict:
    """Canonical-case entry. The text is stored in parts so a case that must trip
    the gate does not trip it as a tracked file."""
    return {"hits": len(scan_text(case["path"], "".join(case["text_parts"])))}


def main() -> int:
    paths = [Path(a).resolve() for a in sys.argv[1:]] or tracked()
    hits = [h for p in paths if p.is_file() for h in scan(p)]
    for h in hits[:60]:
        print(h)
    if len(hits) > 60:
        print(f"... {len(hits) - 60} more")
    print(f"check_public: {len(hits)} hit(s) in {len(paths)} file(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
