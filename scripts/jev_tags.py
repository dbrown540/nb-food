#!/usr/bin/env python3
"""Ask Jev (TypeSafe's System One classifier) the attribute battery for a set of
items and compare its answers with the pinned Opus tags in data/item_tags.json.

An evaluation, not a registered decider: its output is a research record
(docs/research/<date>-jev-vs-opus-attributes.json) that says how often the two
agree, so the owner can decide whether Jev may carry the principle.

One call per item: the item is the state (section, item, description), and each
attribute is one Choice question (yes / no / unknown) whose criteria carry the
definition from data/attributes.json. The key is read with op as the 1Password
service account (readings.op_read); it is never printed or written.

    python3 scripts/jev_tags.py --ids ID,ID,... --key-ref REF [--out PATH]
"""
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readings import op_read  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
PRICE_PER_INPUT_TOKEN = 0.042 / 1e6  # USD, from the vendor's published price; output is free


def questions(attrs: list) -> dict:
    q = {}
    for a in attrs:
        q[a["id"]] = {
            "type": "choice",
            "instructions": f"Judging only from this menu item's own section, name and description: does the item have "
                            f"the attribute '{a['id']}'? The attribute means: {a['definition']}",
            "criteria": {
                "yes": f"The item's words say it has it. {a['definition']}",
                "no": "The item's words rule it out: a single plain food whose nature excludes it, or a description "
                      "that lists what the item is made of with nothing that has it.",
                "unknown": "The words do not settle it: the dish's parts are not listed, or it could be made either "
                           "way. An item that simply does not mention the attribute is unknown.",
            },
        }
    return q


def ask(key: str, row: dict, qs: dict) -> dict:
    state = {"section": row["section"], "item": row["name"], "description": row["description"]}
    body = json.dumps({"model": MODEL, "state": json.dumps(state, ensure_ascii=False), "questions": qs}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read())
    out["_ms"] = round((time.time() - t0) * 1000)
    return out


def main(argv: list) -> int:
    args = dict(zip(argv[::2], argv[1::2]))
    unknown_flags = set(args) - {"--ids", "--key-ref", "--out"}
    if unknown_flags or "--ids" not in args or "--key-ref" not in args:
        raise SystemExit("usage: jev_tags.py --ids ID,... --key-ref REF [--out PATH]")
    ids = args["--ids"].split(",")
    rows = {r["id"]: r for r in json.loads((ROOT / "data/menu_items.json").read_text())["rows"]}
    tags = {r["id"]: r["tags"] for r in json.loads((ROOT / "data/item_tags.json").read_text())["rows"]}
    attrs = json.loads((ROOT / "data/attributes.json").read_text())["attributes"]
    qs = questions(attrs)
    key = op_read(args["--key-ref"])
    results, tokens = [], 0
    for i in ids:
        resp = ask(key, rows[i], qs)
        tokens += (resp.get("usage") or {}).get("input_tokens", 0)
        answers = resp.get("answers") or {}
        results.append({"id": i, "name": rows[i]["name"], "description": rows[i]["description"],
                        "model": resp.get("model"), "ms": resp["_ms"],
                        "attributes": {a["id"]: {"opus": tags[i][a["id"]]["answer"] if i in tags else None,
                                                 "opus_agree": tags[i][a["id"]]["agree"] if i in tags else None,
                                                 "jev": (answers.get(a["id"]) or {}).get("choice"),
                                                 "jev_confidence": (answers.get(a["id"]) or {}).get("confidence")}
                                       for a in attrs}})
    out = {"date": date.today().isoformat(), "jev_model_requested": MODEL,
           "opus_basis": json.loads((ROOT / "data/item_tags.json").read_text())["basis"],
           "questions": qs, "input_tokens": tokens, "cost_usd": round(tokens * PRICE_PER_INPUT_TOKEN, 5),
           "results": results}
    path = Path(args.get("--out", ROOT / f"docs/research/{out['date']}-jev-vs-opus-attributes.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"jev: {len(results)} items, {tokens} input tokens, ${out['cost_usd']}; wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
