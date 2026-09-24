#!/usr/bin/env python3
"""Food-attribute tags for every row of data/menu_items.json.

Principle "item-attributes" (spine/stages/menus.json): an item has an
attribute only when its own words say so, lacks it only when its own words
rule it out, and is otherwise unknown.

How it is decided:
  1. Readings (T2). A constrained classifier answers the question battery
     (spine/battery/item-attributes.md + data/attributes.json): per attribute
     yes / no / unknown plus the item words behind the answer. Each item text is
     read `samples` times (spine/bindings.json "item-attributes").
  2. Pins. Every reading is stored in data/tag_pins.jsonl keyed by the item
     text's hash and the basis (model, battery hash, sampling). A text already
     pinned under the current basis is never sent again, so a rebuild never
     re-rolls the model; a new basis (model, battery or sampling change) reads
     every text again.
  3. Route (T1, route_attribute). "yes" needs `agreeYes` readings that quote
     words found in the item; "no" needs `agreeNo` readings; anything else is
     unknown. A "yes" whose quoted words are not in the item counts as unknown.

Output data/item_tags.json is derived from the item table + pins + route and
is never hand-edited (`--check`). Items with no pinned readings under the
current basis are listed in `untagged` with the reason, never guessed.

    python3 scripts/tag_items.py                 # rewrite data/item_tags.json from pins
    python3 scripts/tag_items.py --check         # exit 1 if it is stale
    .venv/bin/python scripts/tag_items.py --run [--kind product|menu] [--limit N] [--ids ID,...] [--sync] [--key-ref REF]
        read every unpinned text (Batches API by default; --sync for a few),
        append the pins, then rewrite data/item_tags.json. The API key comes
        from ANTHROPIC_API_KEY, else from `op read REF` (REF via --key-ref or
        NB_FOOD_KEY_REF); it is never printed or written anywhere.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readings import PinWriter, pin_lines, read_all, read_budgeted, read_cli, sampling_basis  # noqa: E402
from spine_hash import content_hash, json_hash, text_hash  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BATTERY = "spine/battery/item-attributes.md"
VOCAB = "data/attributes.json"
BATTERY_FILES = [BATTERY, VOCAB]
PINS = "data/tag_pins.jsonl"
OUT = "data/item_tags.json"
STATE = "data/.tag_batch.json"  # gitignored: an in-flight batch id, so a rerun resumes it
SCHEMA_VERSION = 1
CODE = {"yes": "y", "no": "n", "unknown": "u"}
ANSWER = {v: k for k, v in CODE.items()}


# ---------------------------------------------------------------- inputs
def cfg(root: Path = ROOT) -> dict:
    return json.loads((root / "spine/bindings.json").read_text())["bindings"]["item-attributes"]


def attributes(root: Path = ROOT) -> list:
    return json.loads((root / VOCAB).read_text())["attributes"]


def system_text(root: Path = ROOT) -> str:
    lines = "\n".join(f"{a['id']}: {a['definition']}" for a in attributes(root))
    return (root / BATTERY).read_text().replace("{attributes}", lines)


def answer_schema(root: Path = ROOT) -> dict:
    one = {"type": "object", "additionalProperties": False, "required": ["answer", "words"],
           "properties": {"answer": {"type": "string", "enum": ["yes", "no", "unknown"]},
                          "words": {"type": "array", "items": {"type": "string"}}}}
    ids = [a["id"] for a in attributes(root)]
    return {"type": "object", "additionalProperties": False, "required": ids, "properties": {i: one for i in ids}}


def item_text(row: dict) -> str:
    parts = []
    if row.get("section"):
        parts.append(f"Section: {row['section']}")
    parts.append(f"Item: {row['name']}")
    if row.get("description"):
        parts.append(f"Description: {row['description']}")
    return "\n".join(parts)


def basis(root: Path = ROOT) -> dict:
    c = cfg(root)
    return {"model": c["model"], "battery": content_hash(root, BATTERY_FILES), "sampling": sampling_basis(c)}


def load_pins(root: Path = ROOT) -> dict:
    f = root / PINS
    if not f.exists():
        return {}
    pins = {}
    for line in f.read_text().splitlines():
        if line.strip():
            p = json.loads(line)
            pins[(p["key"], p["basis"])] = p
    return pins


def items(root: Path = ROOT) -> list:
    return json.loads((root / "data/menu_items.json").read_text())["rows"]


# ---------------------------------------------------------------- route (T1)
def route_attribute(samples: list, text: str, agree_yes: int, agree_no: int) -> tuple:
    """samples: [(answer code, [words]), ...] for one attribute -> (answer, readings behind it, words)."""
    low = text.lower()
    yes = no = 0
    yes_words, no_words = [], []
    for code, words in samples:
        quoted = [w.strip() for w in words if w.strip() and w.strip().lower() in low]
        if code == "y" and quoted:
            yes += 1
            yes_words += quoted
        elif code == "n":
            no += 1
            no_words += quoted
    if yes >= agree_yes:
        return "yes", yes, dedupe(yes_words)
    if no >= agree_no:
        return "no", no, dedupe(no_words)
    return "unknown", len(samples) - yes - no, []


def verbatim(sample: dict, text: str) -> dict:
    """Keep only quoted words that occur in the item's own text, so a pin holds nothing but
    the item's words and closed codes (a quote the item does not contain supports nothing)."""
    if "w" not in sample:
        return sample
    low = text.lower()
    w = {a: [x for x in ws if x.strip() and x.strip().lower() in low] for a, ws in sample["w"].items()}
    w = {a: ws for a, ws in w.items() if ws}
    return {k: v for k, v in sample.items() if k != "w"} | ({"w": w} if w else {})


def dedupe(words: list) -> list:
    """Case-insensitive unique words, first spelling kept, in sorted order."""
    first = {}
    for w in words:
        first.setdefault(w.lower(), w)
    return [first[k] for k in sorted(first)]


def decide(text: str, pin: dict, c: dict, attr_ids: list) -> dict:
    tags = {}
    for i, a in enumerate(attr_ids):
        samples = []
        for s in pin["samples"]:
            if "a" in s:
                samples.append((s["a"][i], s.get("w", {}).get(a, [])))
            else:  # a refused reading answers nothing
                samples.append(("u", []))
        ans, agree, words = route_attribute(samples, text, c["agreeYes"], c["agreeNo"])
        tags[a] = {"answer": ans, "agree": agree, **({"words": words} if words else {})}
    return tags


# ---------------------------------------------------------------- derive / check
def derive(root: Path = ROOT) -> dict:
    c, b = cfg(root), basis(root)
    bh = json_hash(b)
    ids = [a["id"] for a in attributes(root)]
    pins = load_pins(root)
    rows, untagged = [], []
    for r in items(root):
        text = item_text(r)
        th = text_hash(text)
        pin = pins.get((th, bh))
        if pin is None:
            untagged.append({"id": r["id"], "text_hash": th, "reason": "no pinned readings for this text under the current basis"})
            continue
        rows.append({"id": r["id"], "text_hash": th, "tags": decide(text, pin, c, ids)})
    return {"schema_version": SCHEMA_VERSION, "basis": {**b, "hash": bh}, "attributes": ids,
            "rule": {"agreeYes": c["agreeYes"], "agreeNo": c["agreeNo"], "samples": c["samples"]},
            "rows": rows, "untagged": untagged}


def render(doc: dict) -> str:
    head = {k: v for k, v in doc.items() if k not in ("rows", "untagged")}
    rows = ",\n".join(json.dumps(r, ensure_ascii=False) for r in doc["rows"])
    unt = ",\n".join(json.dumps(r, ensure_ascii=False) for r in doc["untagged"])
    head_txt = json.dumps(head, ensure_ascii=False, indent=1)[:-2]
    return f'{head_txt},\n "rows": [\n{rows}\n],\n "untagged": [\n{unt}\n]}}\n'


def check_item_tags(root: Path = ROOT) -> list:
    """Enforcer for item-attributes: every item is tagged or listed untagged with its
    reason; every tag is yes/no/unknown for every attribute; every yes quotes words
    that occur in the item; every row is keyed to the item's current text and basis."""
    f = root / OUT
    if not f.exists():
        return [f"{OUT} missing"]
    doc = json.loads(f.read_text())
    problems = []
    ids = [a["id"] for a in attributes(root)]
    bh = json_hash(basis(root))
    if doc.get("basis", {}).get("hash") != bh:
        problems.append(f"{OUT}: basis {doc.get('basis', {}).get('hash')} is not the current basis {bh}")
    by_id = {r["id"]: r for r in items(root)}
    seen = set()
    for row in doc["rows"]:
        r = by_id.get(row["id"])
        if r is None:
            problems.append(f"{row['id']}: tagged but not in the item table")
            continue
        seen.add(row["id"])
        text = item_text(r)
        if row["text_hash"] != text_hash(text):
            problems.append(f"{row['id']}: tags were read from other text")
        if sorted(row["tags"]) != sorted(ids):
            problems.append(f"{row['id']}: attributes {sorted(row['tags'])} != vocabulary")
        for a, t in row["tags"].items():
            if t["answer"] not in CODE:
                problems.append(f"{row['id']}.{a}: answer {t['answer']!r}")
            if t["answer"] == "yes" and (not t.get("words") or any(w.lower() not in text.lower() for w in t["words"])):
                problems.append(f"{row['id']}.{a}: yes without the item's own words")
    for u in doc["untagged"]:
        if not u.get("reason"):
            problems.append(f"{u['id']}: untagged without a reason")
        seen.add(u["id"])
    missing = sorted(set(by_id) - seen)
    if missing:
        problems.append(f"{len(missing)} item(s) neither tagged nor listed untagged: {missing[:3]}")
    texts = {text_hash(item_text(r)): item_text(r).lower() for r in by_id.values()}
    for (key, _), pin in load_pins(root).items():
        low = texts.get(key)
        words = [w for s in pin["samples"] for ws in s.get("w", {}).values() for w in ws]
        if low is not None and any(w.lower() not in low for w in words):
            problems.append(f"pin {key}: holds words its item does not contain")
    return problems


# ---------------------------------------------------------------- canonical-case entries
def decide_case(case: dict) -> dict:
    """One item row -> its tags from the tracked pins (no model call)."""
    root = ROOT
    text = item_text(case["row"])
    pin = load_pins(root).get((text_hash(text), json_hash(basis(root))))
    if pin is None:
        return {"tagged": False}
    tags = decide(text, pin, cfg(root), [a["id"] for a in attributes(root)])
    return {"tagged": True, "answers": {a: t["answer"] for a, t in tags.items()},
            "words": {a: t["words"] for a, t in tags.items() if "words" in t}}


def route_case(case: dict) -> dict:
    ans, agree, words = route_attribute([(s[0], s[1]) for s in case["samples"]], case["text"],
                                        case["agreeYes"], case["agreeNo"])
    return {"answer": ans, "agree": agree, "words": words}


# ---------------------------------------------------------------- model readings (network)
def parse_reading(msg, attr_ids: list):
    """-> (sample dict, model id) or (None, reason) when the reading is unusable."""
    if msg.stop_reason == "refusal":
        return {"refusal": True}, msg.model
    if msg.stop_reason != "end_turn":
        return None, f"stop_reason {msg.stop_reason}"
    try:
        data = json.loads(next(b.text for b in msg.content if b.type == "text"))
        a = "".join(CODE[data[i]["answer"]] for i in attr_ids)
    except (StopIteration, ValueError, KeyError, TypeError) as e:
        return None, f"unparseable reading: {e!r}"
    w = {i: [x for x in data[i]["words"] if x.strip()] for i in attr_ids
         if data[i]["answer"] != "unknown" and any(x.strip() for x in data[i]["words"])}
    return {"a": a, **({"w": w} if w else {})}, msg.model


def request_params(root: Path, text: str) -> dict:
    c = cfg(root)
    return {"model": c["model"], "max_tokens": c["maxTokens"],
            "thinking": {"type": c["thinking"]},
            "output_config": {"effort": c["effort"], "format": {"type": "json_schema", "schema": answer_schema(root)}},
            "system": [{"type": "text", "text": system_text(root), "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": text}]}


def write_pins(root: Path, new: list) -> None:
    pins = load_pins(root)
    for p in new:
        pins[(p["key"], p["basis"])] = p
    (root / PINS).write_text(pin_lines(pins))


def pending(root: Path, limit: int, only_ids: set, kind: str = "") -> dict:
    bh = json_hash(basis(root))
    pins = load_pins(root)
    todo = {}
    for r in items(root):
        if (only_ids and r["id"] not in only_ids) or (kind and r["kind"] != kind):
            continue
        text = item_text(r)
        th = text_hash(text)
        if (th, bh) not in pins:
            todo.setdefault(th, text)
    keys = sorted(todo)[:limit] if limit else sorted(todo)
    return {k: todo[k] for k in keys}


def run(root: Path, limit: int, only_ids: set, sync: bool, key_ref: str, kind: str = "", budget: float = 0.0) -> None:
    todo = pending(root, limit, only_ids, kind)
    c, b = cfg(root), basis(root)
    bh = json_hash(b)
    n = c["samples"]
    attr_ids = [a["id"] for a in attributes(root)]
    transport = c.get("transport", "api")
    print(f"{len(todo)} text(s) to read x {n} readings; basis {bh} ({b['model']} over {transport})", flush=True)
    if not todo:
        return
    today = date.today().isoformat()
    parse = lambda msg: parse_reading(msg, attr_ids)
    if transport == "cli":
        writer = PinWriter(root / PINS, lambda: load_pins(root), c["cliFlushEvery"])
        system, schema = system_text(root), answer_schema(root)
        try:
            usage, failures = read_cli(todo, n, lambda text: (system, schema, c["model"]), parse,
                                       lambda k, got: writer.add({"key": k, "basis": bh, "at": today, "transport": "claude-code-cli",
                                                                  "models": sorted({m for _, m in got}),
                                                                  "samples": [verbatim(s, todo[k]) for s, _ in got]}),
                                       c["cliWorkers"])
        finally:
            writer.flush()
        pinned, batch_note = len(writer.new), False
    elif budget and not sync:
        def pin_chunk(got):
            write_pins(root, [{"key": th, "basis": bh, "at": today, "batch": True,
                               "models": sorted({m for _, m in samples.values()}),
                               "samples": [verbatim(samples[s][0], todo[th]) for s in range(n)]}
                              for th, samples in got.items() if len(samples) == n])
        spent, done, left = read_budgeted(todo, n, lambda text: request_params(root, text), parse, key_ref,
                                          root / STATE, bh, c["model"], budget, c["batchChunk"], pin_chunk)
        print(f"read {done} text(s) for ${spent:.2f}; {left} left for a later budget")
        usage, failures, pinned, batch_note = {"usd": round(spent, 4)}, [], done, True
    else:
        got, usage, failures, batch_note = read_all(todo, n, lambda text: request_params(root, text), parse,
                                                    sync, key_ref, root / STATE, bh)
        new = [{"key": th, "basis": bh, "at": today, "batch": batch_note,
                "models": sorted({m for _, m in samples.values()}),
                "samples": [verbatim(samples[s][0], todo[th]) for s in range(n)]}
               for th, samples in got.items() if len(samples) == n]  # a text is pinned only with all its readings
        write_pins(root, new)
        pinned = len(new)
    print(f"pinned {pinned} text(s); {len(failures)} unusable reading(s); usage {usage}")
    log = root / "data/.tag_runs.jsonl"  # gitignored run log (operational report, not a record)
    with log.open("a") as fh:
        fh.write(json.dumps({"at": today, "basis": bh, "texts": len(todo), "pinned": pinned, "transport": transport,
                             "failures": len(failures), "usage": usage, "batch": batch_note}) + "\n")


# ---------------------------------------------------------------- main
def main(argv: list) -> int:
    flags = {"--run", "--sync", "--check"}
    opts, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            opts[a] = True
        elif a in ("--limit", "--ids", "--key-ref", "--kind", "--budget") and i + 1 < len(argv):
            opts[a] = argv[i + 1]
            i += 1
        else:
            raise SystemExit(f"tag_items: unknown argument {a!r}")
        i += 1
    if "--run" in opts:
        run(ROOT, int(opts.get("--limit", 0)), set(filter(None, opts.get("--ids", "").split(","))),
            "--sync" in opts, opts.get("--key-ref", ""), opts.get("--kind", ""), float(opts.get("--budget", 0)))
    doc = derive(ROOT)
    text = render(doc)
    if "--check" in opts:
        cur = (ROOT / OUT).read_text() if (ROOT / OUT).exists() else ""
        if cur == text:
            print(f"item_tags.json is current ({len(doc['rows'])} tagged, {len(doc['untagged'])} untagged)")
            return 0
        print("item_tags.json is STALE; run scripts/tag_items.py", file=sys.stderr)
        return 1
    (ROOT / OUT).write_text(text)
    print(f"wrote {OUT}: {len(doc['rows'])} tagged, {len(doc['untagged'])} untagged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
