#!/usr/bin/env python3
"""Publish gate for the enrichment layers and reports: exit 1 if any owned file
mentions a personal-context term. The repo is public; the layers describe
restaurants, public datasets and sources — nothing about who uses the index.

Checks the paths in OWNED (whole files) for the PATTERNS below. The OSM shop
value `health_food` and the DPH dataset ids are exempt by construction.

    python3 scripts/check_public.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNED = ["data/menus", "data/neighborhoods.geojson", "docs/nb-food-coverage-report.md",
         "scripts/menus_index.py", "scripts/fetch_neighborhoods.py", "scripts/check_public.py"]
PATTERNS = [
    (r"\bhealth(?!_food\b)", "health"),  # health_food is an OSM shop tag
    (r"\bhealthy\b", "healthy"),
    (r"\bdiet(ary|s)?\b(?!\s+(coke|pepsi|dr\b|soda|sprite|7up|mountain|ginger|root))", "diet"),  # "Diet Coke" is a product
    (r"\bnutrition(al)?\b", "nutrition"),
    (r"\bcalorie", "calorie"),
    (r"\ballerg", "allergen"),
    (r"\bmedical\b", "medical"),
    (r"\bdanny\b", "owner name"),
    (r"therenthacker", "owner domain"),
    (r"@[a-z0-9.-]+\.(com|net|org)\b", "email address"),
]


def main() -> int:
    hits = []
    for rel in OWNED:
        p = ROOT / rel
        files = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in files:
            if not f.is_file():
                continue
            text = f.read_text(errors="replace")
            for pat, label in PATTERNS:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    if rel == "scripts/check_public.py" and m.start() < text.index("def main"):
                        continue  # the pattern table itself
                    line = text.count("\n", 0, m.start()) + 1
                    hits.append(f"{f.relative_to(ROOT)}:{line}: {label} -> {text[max(0, m.start() - 30):m.end() + 30]!r}")
    for h in hits:
        print(h)
    print(f"check_public: {len(hits)} hit(s) in {len(OWNED)} owned path(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
