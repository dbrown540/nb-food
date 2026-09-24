#!/usr/bin/env python3
"""Integrity gate on the built data. Each check_* function is an enforcer
registered in the spine (spine/stages/*.json, spine/invariants.json); main()
calls all of them and exits 1 on any failure. Warnings (a date inside its
warning window) print but do not fail.

  check_layer_keys       every layer record belongs to exactly one place (invariant)
  check_menu_extraction  menu / product files have the item shape; files dated on or
                         after the basis cutoff name their extraction basis
  check_derived          derived tables equal what their scripts write (invariant)
  check_menu_freshness   a menu past its kept age fails; inside the window it warns
  check_verdicts         every verdict is an owner ruling with a date, not past review
  check_item_tags        (scripts/tag_items.py) the attribute tags obey their principle
  check_food_map         (scripts/map_foods.py) every item has a nutrient source, or none, with its kind
  check_usda_cache       (scripts/usda.py) cached USDA records are whole, dated and cover every mapping
  check_nutrients        (scripts/usda_nutrients.py) one nutrient row per mapped record, in bounds, witnessed

    python3 scripts/check_data.py [--today YYYY-MM-DD]
"""
import json
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freshness import menu_age  # noqa: E402
from map_foods import check_food_map  # noqa: E402
from tag_items import check_item_tags  # noqa: E402
from usda import check_usda_cache  # noqa: E402
from usda_nutrients import check_nutrients  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"ok", "partial", "not_found", "skipped"}
MENU_ITEM = {"section", "item", "price", "description"}
PRODUCT = {"section", "name", "description", "size", "price", "sold_by", "package_g", "package_ml", "units"}
DERIVED = [("scripts/menus_index.py", "data/menus/index.json"),
           ("scripts/menu_items.py", "data/menu_items.json"),
           ("scripts/tag_items.py", "data/item_tags.json"),
           ("scripts/map_foods.py", "data/food_map.json"),
           ("scripts/usda_nutrients.py", "data/nutrients.json")]


def bindings(root: Path = ROOT) -> dict:
    return json.loads((root / "spine/bindings.json").read_text())


# ---------------------------------------------------------------- invariant: layers keyed to places
def check_layer_keys(data: dict) -> list:
    problems = []
    places, risk, insp = data["places"], data["risk"], data["inspections"]
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
    orphans = sorted(set(risk) - keyset)
    if orphans:
        problems.append(f"{len(orphans)} street-risk entries match no place: {orphans[:5]}")
    missing = sorted(keyset - set(risk))
    if missing:
        problems.append(f"{len(missing)} place(s) without a street-risk entry: {missing[:5]}")
    orphans = sorted(set(insp) - {"_meta"} - keyset)
    if orphans:
        problems.append(f"{len(orphans)} inspection entries match no place: {orphans[:5]}")
    return problems


# ---------------------------------------------------------------- menu extraction
def menu_file_problems(fname: str, d: dict, keyset: set, basis_from: str) -> list:
    problems = []
    if d.get("name") not in keyset:
        problems.append(f"{fname}: name {d.get('name')!r} is not a place key")
    if d.get("status") not in STATUSES:
        problems.append(f"{fname}: status {d.get('status')!r}")
    rows, shape = (d.get("items", []), MENU_ITEM) if "products" not in d else (d["products"], PRODUCT)
    name_field = "item" if shape is MENU_ITEM else "name"
    for i in rows:
        if set(i) != shape or not str(i.get(name_field, "")).strip() \
                or (i.get("price") is not None and not isinstance(i["price"], (int, float))):
            problems.append(f"{fname}: malformed row {str(i)[:80]}")
            break
    if d.get("as_of", "") >= basis_from and rows:
        ex = d.get("extraction") or {}
        if ex.get("method") == "script":
            if not ex.get("path"):
                problems.append(f"{fname}: script extraction without the script's path")
        elif not (ex.get("model") and ex.get("prompt_hash")):
            problems.append(f"{fname}: dated {d.get('as_of')} but no extraction basis (model, prompt_hash)")
    return problems


def check_menu_extraction(root: Path, keyset: set) -> list:
    basis_from = bindings(root)["bindings"]["menu-extraction"]["basisRequiredFrom"]
    problems = []
    for path in sorted((root / "data/menus").glob("*.json")):
        if path.name != "index.json":
            problems += menu_file_problems(f"menus/{path.name}", json.loads(path.read_text()), keyset, basis_from)
    for path in sorted((root / "data/products").glob("*.json")):
        problems += menu_file_problems(f"products/{path.name}", json.loads(path.read_text()), keyset, basis_from)
    return problems


def menu_file_case(case: dict) -> dict:
    p = menu_file_problems("case.json", case["file"], set(case["keys"]), case["basisRequiredFrom"])
    return {"problems": len(p)}


# ---------------------------------------------------------------- invariant: derived, not transcribed
def stale(committed: str, derived: str) -> bool:
    return committed != derived


def check_derived(root: Path) -> list:
    problems = []
    for script, out in DERIVED:
        r = subprocess.run([sys.executable, str(root / script), "--check"], capture_output=True, text=True, cwd=root)
        if r.returncode != 0:
            problems.append(f"{out} is stale or hand-edited (run {script})")
    return problems


def derived_case(case: dict) -> dict:
    return {"stale": stale(case["committed"], case["derived"])}


# ---------------------------------------------------------------- menu freshness
def check_menu_freshness(root: Path, today: str) -> tuple:
    b = bindings(root)
    max_age = b["bindings"]["menu-freshness"]["maxAgeDays"]
    warn = b["bindings"]["time"]["warnDays"]
    ext = {r["menu"]: r["until"] for r in b["rulings"] if r.get("kind") == "menu-extension"}
    fails, warns = [], []
    files = [p for p in sorted((root / "data/menus").glob("*.json")) if p.name != "index.json"]
    files += sorted((root / "data/products").glob("*.json"))
    for path in files:
        d = json.loads(path.read_text())
        if not (d.get("items") or d.get("products")):
            continue  # nothing is presented from a menu that was not found
        age = menu_age(d["as_of"], today, max_age, warn)
        slug = path.stem
        if age["status"] == "stale" and ext.get(slug, "") >= today:
            age = {"status": "due-soon", "due": ext[slug]}
        if age["status"] == "stale":
            fails.append(f"{path.parent.name}/{path.name}: as of {d['as_of']}, due {age['due']}; refresh it or rule an extension")
        elif age["status"] == "due-soon":
            warns.append(f"{path.parent.name}/{path.name}: due {age['due']}")
    return fails, warns


# ---------------------------------------------------------------- curated verdicts
def verdict_problems(name: str, entry: dict, today: str, cfg: dict, warn_days: int) -> tuple:
    if "verdict" not in entry:
        return [], []
    if entry["verdict"] not in cfg["verdicts"]:
        return [f"{name}: verdict {entry['verdict']!r} not in {cfg['verdicts']}"], []
    try:
        decided = date.fromisoformat(entry.get("verified", ""))
    except ValueError:
        until = cfg.get("undatedUntil", {}).get(name, "")
        if until and today <= until:  # a recorded, dated exemption while the owner supplies the date
            return [], [f"{name}: verdict has no ruling date; exemption ends {until}"]
        return [f"{name}: verdict without the date it was ruled (verified)"], []
    due = decided + timedelta(days=cfg["reviewAfterDays"])
    t = date.fromisoformat(today)
    if t > due:
        return [f"{name}: verdict ruled {decided}, review was due {due}"], []
    if t >= due - timedelta(days=warn_days):
        return [], [f"{name}: verdict review due {due}"]
    return [], []


def check_verdicts(root: Path, today: str) -> tuple:
    b = bindings(root)
    cfg, warn = b["bindings"]["curated-verdict"], b["bindings"]["time"]["warnDays"]
    curated = json.loads((root / "data/curated.json").read_text())
    entries = list(curated["overrides"].items()) + [(e["name"], e) for e in curated["extras"]]
    fails, warns = [], []
    for name, e in entries:
        f, w = verdict_problems(name, e, today, cfg, warn)
        fails += f
        warns += w
    # a verdict in the built index must have come from a ruling: it travels with its date
    undated = {k.lower() for k, v in cfg.get("undatedUntil", {}).items() if today <= v}
    for p in json.loads((root / "data/places.json").read_text()):
        if p.get("verdict") and not p.get("verified") and p["key"].lower() not in undated:
            fails.append(f"places.json {p['key']}: verdict without a dated ruling")
    return fails, warns


def verdict_case(case: dict) -> dict:
    f, w = verdict_problems("case", case["entry"], case["today"], case["cfg"], case["warnDays"])
    return {"fails": len(f), "warns": len(w)}


# ---------------------------------------------------------------- main
def main(argv: list) -> int:
    today = date.today().isoformat()
    if argv[:1] == ["--today"] and len(argv) == 2:
        today = argv[1]
    elif argv:
        raise SystemExit(f"check_data: unknown argument(s) {argv}")
    places = json.loads((ROOT / "data/places.json").read_text())
    risk = json.loads((ROOT / "data/crime/poi_street_risk.json").read_text())["pois"]
    insp = json.loads((ROOT / "data/inspections/poi_inspections.json").read_text())
    keyset = {p.get("key") for p in places}

    fails = check_layer_keys({"places": places, "risk": risk, "inspections": insp})
    fails += check_menu_extraction(ROOT, keyset)
    fails += check_derived(ROOT)
    f, warns = check_menu_freshness(ROOT, today)
    fails += f
    f, w = check_verdicts(ROOT, today)
    fails += f
    warns += w
    fails += check_item_tags(ROOT)
    fails += check_food_map(ROOT)
    fails += check_usda_cache(ROOT)
    fails += check_nutrients(ROOT)

    for w in warns:
        print("WARN", w)
    for p in fails:
        print("FAIL", p)
    print(f"check_data: {len(fails)} problem(s), {len(warns)} warning(s); {len(places)} places, {len(risk)} risk, "
          f"{len(insp) - 1} inspections")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
