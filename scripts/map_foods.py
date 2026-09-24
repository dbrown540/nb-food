#!/usr/bin/env python3
"""Nutrient source for every row of data/menu_items.json.

Principle "food-mapping" (spine/stages/nutrients.json): an item's nutrients come
from its own package label when one is on file, else from the public food
record that is the same food, and are otherwise unknown, never zero.

Cascade, per item:
  1. Label (T0). data/labels/<item id>.json is on file -> kind "label": exact for
     the nutrients the label lists, unknown for the rest.
  2. Closest USDA entry (T2). Candidate search (T1, `candidates`) offers the top
     entries from two pools of data/usda_index.json: single foods (Foundation, SR
     Legacy without its restaurant and fast-food dishes) and mixed dishes as eaten
     (Survey FNDDS). A constrained classifier (spine/battery/food-map.md) answers,
     `samples` times, which candidate is the item itself (or none) and which
     listed portion is one serving (or none). Readings are pinned in
     data/food_map_pins.jsonl keyed by the hash of the exact model input (item +
     candidates) and the basis, so a rebuild never re-rolls the model.
  3. Route (T1, `route_mapping`). A record is taken only when `agreeMap` readings
     name it; a portion only when `agreePortion` of those name it. Anything else
     is unmapped.

Kinds: label | usda-single-food (the record is a plain food: Foundation, SR
Legacy, or a survey entry filed in a plain-food group; its per-100 g values
match the food) | usda-mixed-dish-estimate (a survey entry filed in a dish
group, bindings "dishCategories", standing in for someone's own recipe: an
estimate) | unmapped (nutrients unknown).
`grams` is the product's package weight (basis "package") or, for a menu item,
the chosen USDA portion (basis "estimated portion: ..."), else null.

    python3 scripts/map_foods.py                 # rewrite data/food_map.json from labels + pins
    python3 scripts/map_foods.py --check         # exit 1 if it is stale
    .venv/bin/python scripts/map_foods.py --run [--kind product|menu] [--limit N] [--ids ID,...] [--sync] [--key-ref REF]
        (transport per the binding: readings.py "cli" on the signed-in Claude plan, or "api")
"""
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packages import package_facts  # noqa: E402
from readings import PinWriter, pin_lines, read_all, read_budgeted, read_cli, sampling_basis  # noqa: E402
from spine_hash import content_hash, json_hash, text_hash  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BATTERY = "spine/battery/food-map.md"
PINS = "data/food_map_pins.jsonl"
OUT = "data/food_map.json"
INDEX = "data/usda_index.json"
LABELS = "data/labels"
STATE = "data/.map_batch.json"
SCHEMA_VERSION = 1
KINDS = ("label", "usda-single-food", "usda-mixed-dish-estimate", "unmapped")


def cfg(root: Path = ROOT) -> dict:
    return json.loads((root / "spine/bindings.json").read_text())["bindings"]["food-mapping"]


def items(root: Path = ROOT) -> list:
    return json.loads((root / "data/menu_items.json").read_text())["rows"]


def basis(root: Path = ROOT) -> dict:
    c = cfg(root)
    return {"model": c["model"], "battery": content_hash(root, [BATTERY]), "sampling": sampling_basis(c)}


# ---------------------------------------------------------------- candidate search (T1)
def stem(t: str) -> str:
    """Plural to singular, roughly: 'pizzas' -> 'pizza', 'tomatoes' -> 'tomato'."""
    if len(t) > 4 and t.endswith("es") and not t.endswith("ses"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokens(s: str, prefix_len: int) -> list:
    """Stems, plus a prefix key ("~linguin") so spelling variants still meet."""
    out = []
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()  # "jalapeño" -> "jalapeno"
    for t in re.findall(r"[a-z]+", s.lower()):
        if len(t) > 2:
            out.append(stem(t))
            if len(t) >= prefix_len:
                out.append("~" + t[:prefix_len])
    return out


class Index:
    def __init__(self, root: Path):
        self.c = cfg(root)
        doc = json.loads((root / INDEX).read_text())
        excl = set(self.c["singlePoolExclude"])
        self.foods = [f for f in doc["foods"] if not (f["dataType"] != "Survey (FNDDS)" and f["category"] in excl)]
        self.by_id = {f["fdcId"]: f for f in self.foods}
        self.plen = self.c["prefixLength"]
        self.df = Counter(t for f in self.foods for t in set(tokens(f["description"], self.plen)))
        self.inv = defaultdict(set)
        for i, f in enumerate(self.foods):
            for t in set(tokens(f["description"], self.plen)):
                self.inv[t].add(i)

    def candidates(self, row: dict) -> list:
        c = self.c
        weights = defaultdict(float)
        for field, w in (("name", c["nameWeight"]), ("description", c["descriptionWeight"]), ("section", c["sectionWeight"])):
            text = row.get(field) or ""
            # a menu word USDA spells differently brings USDA's words along (bindings: aliases)
            text += " " + " ".join(c["aliases"].get(t, "") for t in tokens(text, self.plen))
            for t in set(tokens(text, self.plen)):
                weights[t] = max(weights[t], w * (c["prefixWeight"] if t.startswith("~") else 1))
        n = len(self.foods)
        score = defaultdict(float)
        for t in sorted(weights):  # fixed order: float sums, and so ties, must not depend on hash seeds
            for i in sorted(self.inv.get(t, ())):
                score[i] += weights[t] * math.log(n / self.df[t])
        ranked = sorted(score, key=lambda i: (-score[i], self.foods[i]["fdcId"]))
        single = [i for i in ranked if self.foods[i]["dataType"] != "Survey (FNDDS)"][:c["candidatesPerPool"]]
        dish = [i for i in ranked if self.foods[i]["dataType"] == "Survey (FNDDS)"][:c["candidatesPerPool"]]
        return [self.foods[i] for i in single + dish]


def item_lines(row: dict) -> list:
    lines = []
    if row.get("section"):
        lines.append(f"Section: {row['section']}")
    lines.append(f"Item: {row['name']}")
    if row.get("description"):
        lines.append(f"Description: {row['description']}")
    if row.get("size"):
        lines.append(f"Package: {row['size']}")
    lines.append(f"Kind: {'packaged store product' if row['kind'] == 'product' else 'restaurant or cafe menu item'}")
    return lines


def message(row: dict, cands: list, max_portions: int) -> str:
    lines = item_lines(row) + ["", "Candidates:"]
    for n, f in enumerate(cands, 1):
        tag = "DISH" if f["dataType"] == "Survey (FNDDS)" else "FOOD"
        ports = "; ".join(f"p{k} {d} ({g:g} g)" for k, (d, g) in enumerate(f["portions"][:max_portions], 1))
        lines.append(f"c{n} [{tag}] {f['description']}" + (f" | portions: {ports}" if ports else ""))
    return "\n".join(lines)


def package_grams(size: str):
    return package_facts(size)["package_g"]


# ---------------------------------------------------------------- route (T1)
def route_mapping(samples: list, n_cands: int, agree_map: int, agree_portion: int) -> tuple:
    """samples: [(choice, portion), ...] as "cN"/"none" and "pN"/"none".
    -> (candidate number or None, portion number or None, readings behind the choice, reason)."""
    votes = Counter()
    for choice, _ in samples:
        k = int(choice[1:]) if re.fullmatch(r"c\d+", choice or "") else None
        if k is not None and 1 <= k <= n_cands:
            votes[k] += 1
    none = sum(1 for c, _ in samples if c == "none")
    if votes:
        k, agree = votes.most_common(1)[0]
        if agree >= agree_map:
            ports = Counter(int(p[1:]) for c, p in samples if c == f"c{k}" and re.fullmatch(r"p\d+", p or ""))
            portion = None
            if ports:
                pk, pn = ports.most_common(1)[0]
                portion = pk if pn >= agree_portion else None
            return k, portion, agree, ""
    if none == len(samples):
        return None, None, none, "no candidate is the same food"
    return None, None, max(list(votes.values()) + [none]), "readings do not agree on one record"


# ---------------------------------------------------------------- derive / check
def load_pins(root: Path = ROOT) -> dict:
    f = root / PINS
    pins = {}
    for line in (f.read_text().splitlines() if f.exists() else []):
        if line.strip():
            p = json.loads(line)
            pins[(p["key"], p["basis"])] = p
    return pins


def kind_of(food: dict, dish_categories: list) -> str:
    """What the matched record is: a survey (FNDDS) entry filed in a dish food group stands in for
    someone's recipe (an estimate); any other record, survey entries for plain foods included, is a
    single food."""
    if food["dataType"] == "Survey (FNDDS)" and food["category"] in dish_categories:
        return "usda-mixed-dish-estimate"
    return "usda-single-food"


def label_of(root: Path, item_id: str):
    f = root / LABELS / f"{item_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


def decide(row: dict, idx: Index, pins: dict, bh: str, root: Path, label=None) -> dict:
    """label: the item's label document when one is on file (label_of)."""
    c = idx.c
    out = {"id": row["id"]}
    grams_pkg = package_grams(row.get("size", "")) if row["kind"] == "product" else None
    if label is not None:
        return {**out, "kind": "label", "estimate": False, "label": f"{LABELS}/{row['id']}.json", "grams": label["serving_g"],
                "grams_basis": "label serving"}
    cands = idx.candidates(row)
    msg = message(row, cands, c["maxPortions"])
    key = text_hash(msg)
    out["key"] = key
    if not cands:
        return {**out, "kind": "unmapped", "reason": "no candidate shares a word with the item", "agree": 0}
    pin = pins.get((key, bh))
    if pin is None:
        return {**out, "kind": None}
    samples = [(s.get("c", "none"), s.get("p", "none")) if "c" in s else ("refused", "none") for s in pin["samples"]]
    k, portion, agree, reason = route_mapping(samples, len(cands), c["agreeMap"], c["agreePortion"])
    if k is None:
        return {**out, "kind": "unmapped", "reason": reason, "agree": agree}
    f = cands[k - 1]
    kind = kind_of(f, c["dishCategories"])
    # a menu item is someone else's recipe and portion, so its numbers are an estimate whatever the record is
    row_out = {**out, "kind": kind, "estimate": kind == "usda-mixed-dish-estimate" or row["kind"] == "menu",
               "fdcId": f["fdcId"], "dataType": f["dataType"], "category": f["category"],
               "description": f["description"], "agree": agree}
    if grams_pkg:
        row_out.update(grams=grams_pkg, grams_basis="package")
    elif portion and row["kind"] == "menu":
        d, g = f["portions"][portion - 1]
        row_out.update(grams=g, grams_basis=f"estimated portion: {d}")
    return row_out


def derive(root: Path = ROOT) -> dict:
    c, b = cfg(root), basis(root)
    bh = json_hash(b)
    idx, pins = Index(root), load_pins(root)
    rows, unread = [], []
    for r in items(root):
        d = decide(r, idx, pins, bh, root, label_of(root, r["id"]))
        if d["kind"] is None:
            unread.append({"id": r["id"], "key": d["key"], "reason": "no pinned readings for this input under the current basis"})
        else:
            rows.append(d)
    return {"schema_version": SCHEMA_VERSION, "basis": {**b, "hash": bh}, "index": json.loads((root / INDEX).read_text())["releases"],
            "rule": {k: c[k] for k in ("samples", "agreeMap", "agreePortion", "candidatesPerPool")},
            "rows": rows, "unread": unread}


def render(doc: dict) -> str:
    head = json.dumps({k: v for k, v in doc.items() if k not in ("rows", "unread")}, ensure_ascii=False, indent=1)[:-2]
    rows = ",\n".join(json.dumps(r, ensure_ascii=False) for r in doc["rows"])
    unread = ",\n".join(json.dumps(r, ensure_ascii=False) for r in doc["unread"])
    return f'{head},\n "rows": [\n{rows}\n],\n "unread": [\n{unread}\n]}}\n'


def check_food_map(root: Path = ROOT) -> list:
    """Enforcer for food-mapping: every item is mapped, unmapped with a reason, or listed
    unread; a label mapping has its label file; a USDA mapping names a record whose data
    type fits its kind; an unmapped item carries no record and no weight."""
    f = root / OUT
    if not f.exists():
        return [f"{OUT} missing"]
    doc = json.loads(f.read_text())
    problems, seen = [], set()
    ids_kind = {r["id"]: r.get("kind") for r in items(root)}
    ids = set(ids_kind)
    dishes = cfg(root)["dishCategories"]
    for r in doc["rows"]:
        seen.add(r["id"])
        k = r.get("kind")
        if k not in KINDS:
            problems.append(f"{r['id']}: kind {k!r}")
        elif k == "label" and not (root / r.get("label", "-")).exists():
            problems.append(f"{r['id']}: label mapping without its label file")
        elif k == "unmapped" and (r.get("fdcId") or r.get("grams") or not r.get("reason")):
            problems.append(f"{r['id']}: unmapped must carry a reason and no record or weight")
        elif k in ("usda-single-food", "usda-mixed-dish-estimate") and \
                k != kind_of({"dataType": r.get("dataType"), "category": r.get("category")}, dishes):
            problems.append(f"{r['id']}: kind {k} does not fit a {r.get('dataType')} record filed under {r.get('category')!r}")
        if k != "unmapped" and r.get("estimate") is not (k == "usda-mixed-dish-estimate" or ids_kind.get(r["id"]) == "menu") \
                and k != "label":
            problems.append(f"{r['id']}: estimate flag {r.get('estimate')!r} does not fit its kind and item")
        if r.get("grams") is not None and not r["grams"] > 0:
            problems.append(f"{r['id']}: grams {r['grams']!r}")
    for u in doc["unread"]:
        seen.add(u["id"])
        if not u.get("reason"):
            problems.append(f"{u['id']}: unread without a reason")
    missing = sorted(ids - seen)
    if missing:
        problems.append(f"{len(missing)} item(s) neither mapped nor listed unread: {missing[:3]}")
    extra = sorted(seen - ids)
    if extra:
        problems.append(f"{len(extra)} mapping(s) for items not in the table: {extra[:3]}")
    return problems


# ---------------------------------------------------------------- canonical-case entries
def decide_case(case: dict) -> dict:
    d = decide(case["row"], Index(ROOT), load_pins(ROOT), json_hash(basis(ROOT)), ROOT, case.get("label"))
    return {k: d[k] for k in ("kind", "fdcId", "grams_basis", "reason") if k in d}


def route_case(case: dict) -> dict:
    k, portion, agree, reason = route_mapping([tuple(s) for s in case["samples"]], case["n"],
                                              case["agreeMap"], case["agreePortion"])
    return {"candidate": k, "portion": portion, "agree": agree}


# ---------------------------------------------------------------- readings (network)
def parse_reading(msg):
    if msg.stop_reason == "refusal":
        return {"refusal": True}, msg.model
    if msg.stop_reason != "end_turn":
        return None, f"stop_reason {msg.stop_reason}"
    try:
        data = json.loads(next(b.text for b in msg.content if b.type == "text"))
        return {"c": str(data["choice"]).strip(), "p": str(data["portion"]).strip()}, msg.model
    except (StopIteration, ValueError, KeyError, TypeError) as e:
        return None, f"unparseable reading: {e!r}"


def request_params(root: Path, text: str) -> dict:
    c = cfg(root)
    schema = SCHEMA
    return {"model": c["model"], "max_tokens": c["maxTokens"], "thinking": {"type": c["thinking"]},
            "output_config": {"effort": c["effort"], "format": {"type": "json_schema", "schema": schema}},
            "system": [{"type": "text", "text": (root / BATTERY).read_text(), "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": text}]}


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["choice", "portion"],
          "properties": {"choice": {"type": "string"}, "portion": {"type": "string"}}}


def run(root: Path, limit: int, only_ids: set, sync: bool, key_ref: str, kind: str = "", budget: float = 0.0) -> None:
    c, b = cfg(root), basis(root)
    bh = json_hash(b)
    idx, pins = Index(root), load_pins(root)
    todo, cand_ids = {}, {}
    for r in items(root):
        if (only_ids and r["id"] not in only_ids) or (kind and r["kind"] != kind) or label_of(root, r["id"]) is not None:
            continue
        cands = idx.candidates(r)
        if not cands:
            continue
        msg = message(r, cands, c["maxPortions"])
        key = text_hash(msg)
        if (key, bh) not in pins:
            todo.setdefault(key, msg)
            cand_ids[key] = [f["fdcId"] for f in cands]
    keys = sorted(todo)[:limit] if limit else sorted(todo)
    todo = {k: todo[k] for k in keys}
    n, transport = c["samples"], c.get("transport", "api")
    print(f"{len(todo)} input(s) to read x {n} readings; basis {bh} ({b['model']} over {transport})", flush=True)
    if not todo:
        return
    today = date.today().isoformat()
    pin = lambda k, got, batched: {"key": k, "basis": bh, "at": today, "candidates": cand_ids[k],
                                   **({"transport": "claude-code-cli"} if transport == "cli" else {"batch": batched}),
                                   "models": sorted({m for _, m in got}), "samples": [s for s, _ in got]}
    if transport == "cli":
        writer = PinWriter(root / PINS, lambda: load_pins(root), c["cliFlushEvery"])
        system = (root / BATTERY).read_text()
        try:
            usage, failures = read_cli(todo, n, lambda text: (system, SCHEMA, c["model"]), parse_reading,
                                       lambda k, got: writer.add(pin(k, got, False)), c["cliWorkers"])
        finally:
            writer.flush()
        pinned, batched = len(writer.new), False
    elif budget and not sync:
        def pin_chunk(got):
            now = load_pins(root)
            for k, s in got.items():
                if len(s) == n:
                    p = pin(k, [s[i] for i in range(n)], True)
                    now[(p["key"], p["basis"])] = p
            (root / PINS).write_text(pin_lines(now))
        spent, done, left = read_budgeted(todo, n, lambda t: request_params(root, t), parse_reading, key_ref,
                                          root / STATE, bh, c["model"], budget, c["batchChunk"], pin_chunk)
        print(f"read {done} input(s) for ${spent:.2f}; {left} left for a later budget")
        usage, failures, pinned, batched = {"usd": round(spent, 4)}, [], done, True
    else:
        got, usage, failures, batched = read_all(todo, n, lambda t: request_params(root, t), parse_reading,
                                                 sync, key_ref, root / STATE, bh)
        new = [pin(k, [s[i] for i in range(n)], batched) for k, s in got.items() if len(s) == n]
        for p in new:
            pins[(p["key"], p["basis"])] = p
        (root / PINS).write_text(pin_lines(pins))
        pinned = len(new)
    print(f"pinned {pinned} input(s); {len(failures)} unusable reading(s); usage {usage}")
    with (root / "data/.map_runs.jsonl").open("a") as fh:
        fh.write(json.dumps({"at": today, "basis": bh, "inputs": len(todo), "pinned": pinned, "transport": transport,
                             "failures": len(failures), "usage": usage, "batch": batched}) + "\n")


def main(argv: list) -> int:
    opts, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a in ("--run", "--sync", "--check"):
            opts[a] = True
        elif a in ("--limit", "--ids", "--key-ref", "--kind", "--budget") and i + 1 < len(argv):
            opts[a] = argv[i + 1]
            i += 1
        else:
            raise SystemExit(f"map_foods: unknown argument {a!r}")
        i += 1
    if "--run" in opts:
        run(ROOT, int(opts.get("--limit", 0)), set(filter(None, opts.get("--ids", "").split(","))),
            "--sync" in opts, opts.get("--key-ref", ""), opts.get("--kind", ""), float(opts.get("--budget", 0)))
    doc = derive(ROOT)
    text = render(doc)
    if "--check" in opts:
        if (ROOT / OUT).exists() and (ROOT / OUT).read_text() == text:
            print(f"food_map.json is current ({len(doc['rows'])} decided, {len(doc['unread'])} unread)")
            return 0
        print("food_map.json is STALE; run scripts/map_foods.py", file=sys.stderr)
        return 1
    (ROOT / OUT).write_text(text)
    kinds = Counter(r["kind"] for r in doc["rows"])
    print(f"wrote {OUT}: {dict(kinds)}, {len(doc['unread'])} unread")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
