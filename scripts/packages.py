"""Package size -> weight, volume or count, from the size a store prints ("16 Oz", "1 Each").

One statement of the conversion, used by the product pull (scripts/tj_products.py) and the
food map (scripts/map_foods.py). Unit factors are definitions, not judgments.
"""
import re

GRAMS = {"oz": 28.349523125, "lb": 453.59237, "g": 1.0, "kg": 1000.0}
MILLILITRES = {"fl oz": 29.5735295625, "ml": 1.0, "l": 1000.0, "pint": 473.176473, "qt": 946.352946}
UNITS = {"each": 1, "doz": 12, "bag": 1}


def package_facts(size: str) -> dict:
    """-> {sold_by: weight | volume | each | count | None, package_g, package_ml, units}."""
    out = {"sold_by": None, "package_g": None, "package_ml": None, "units": None}
    m = re.match(r"^\s*([\d.]+)\s*([a-z ]+?)\s*$", size or "", re.I)
    if not m:
        return out
    n, unit = float(m.group(1)), m.group(2).lower()
    if unit in GRAMS:
        out.update(sold_by="weight", package_g=round(n * GRAMS[unit], 1))
    elif unit in MILLILITRES:
        out.update(sold_by="volume", package_ml=round(n * MILLILITRES[unit], 1))
    elif unit in UNITS:
        out.update(sold_by="each" if unit == "each" else "count", units=int(round(n * UNITS[unit])))
    return out
