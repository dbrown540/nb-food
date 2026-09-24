#!/usr/bin/env python3
"""Run the registered batteries (attribute tags and food mapping) on another
model for a set of items and compare its routed answers with the pinned ones.

An evaluation, not a decider: nothing is pinned. The other model's readings go
through the same request builder, parser and route as the registered path;
only the model id changes (and `effort`, which some models reject). The result
is a research record, docs/research/<date>-<label>.json.

    .venv/bin/python scripts/compare_models.py --model claude-haiku-4-5 --ids ID,... --key-ref REF --label NAME
"""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import map_foods as mf  # noqa: E402
import tag_items as ti  # noqa: E402
from readings import add_usage, api_key, cli_message, usage_of  # noqa: E402

ROOT = ti.ROOT
NO_EFFORT = ("claude-haiku-4-5",)  # models that reject output_config.effort


def with_model(params: dict, model: str) -> dict:
    p = {**params, "model": model}
    if model in NO_EFFORT:
        p["output_config"] = {k: v for k, v in p["output_config"].items() if k != "effort"}
    return p


def read(client, params: dict, n: int, parse, usage: dict) -> list:
    if client is None:  # the Claude Code transport, on the signed-in plan
        system = params["system"][0]["text"]
        schema = params["output_config"]["format"]["schema"]
        msgs = [cli_message(system, schema, params["messages"][0]["content"], params["model"]) for _ in range(n)]
    else:
        msgs = [client.messages.create(**params) for _ in range(n)]
    for m in msgs:
        add_usage(usage, usage_of(m))
    return [parse(m) for m in msgs]


def main(argv: list) -> int:
    import anthropic
    args = dict(zip(argv[::2], argv[1::2]))
    if set(args) - {"--model", "--ids", "--key-ref", "--label", "--transport", "--tags-only"} or not {"--model", "--ids", "--label"} <= set(args):
        raise SystemExit("usage: compare_models.py --model M --ids ID,... --label NAME [--transport api|cli] [--key-ref REF] [--tags-only yes]")
    model, ids = args["--model"], args["--ids"].split(",")
    cli = args.get("--transport", "api") == "cli"
    client = None if cli else anthropic.Anthropic(api_key=api_key(args["--key-ref"]), max_retries=6)
    rows = {r["id"]: r for r in ti.items()}
    attr_ids = [a["id"] for a in ti.attributes()]
    tc, mc = ti.cfg(), mf.cfg()
    pinned_tags = {r["id"]: r["tags"] for r in json.loads((ROOT / ti.OUT).read_text())["rows"]}
    pinned_map = {r["id"]: r for r in json.loads((ROOT / mf.OUT).read_text())["rows"]}
    idx = mf.Index(ROOT)
    usage = {"tags": {}, "map": {}}

    def one(i):
        row = rows[i]
        text = ti.item_text(row)
        tag_reads = read(client, with_model(ti.request_params(ROOT, text), model), tc["samples"],
                         lambda m: ti.parse_reading(m, attr_ids), usage["tags"])
        pin = {"samples": [s for s, _ in tag_reads if s is not None]}
        tags = ti.decide(text, pin, tc, attr_ids) if len(pin["samples"]) == tc["samples"] else None
        cands = idx.candidates(row)
        mapping = {"kind": "unmapped", "reason": "no candidate shares a word with the item"}
        if cands and "--tags-only" not in args:
            msg = mf.message(row, cands, mc["maxPortions"])
            map_reads = read(client, with_model(mf.request_params(ROOT, msg), model), mc["samples"], mf.parse_reading, usage["map"])
            samples = [(s.get("c", "none"), s.get("p", "none")) if s and "c" in s else ("refused", "none") for s, _ in map_reads]
            k, portion, agree, reason = mf.route_mapping(samples, len(cands), mc["agreeMap"], mc["agreePortion"])
            mapping = ({"kind": "usda-mixed-dish-estimate" if cands[k - 1]["dataType"] == "Survey (FNDDS)" else "usda-single-food",
                        "fdcId": cands[k - 1]["fdcId"], "description": cands[k - 1]["description"], "agree": agree}
                       if k else {"kind": "unmapped", "reason": reason, "agree": agree})
        return i, tags, mapping

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(one, ids))

    out, tag_agree, tag_total, cm = [], 0, 0, Counter()
    map_same = 0
    for i, tags, mapping in results:
        rec = {"id": i, "name": rows[i]["name"], "tags": {}, "map": {"pinned": pinned_map.get(i), "other": mapping}}
        for a in attr_ids:
            p = pinned_tags[i][a]["answer"]
            o = tags[a]["answer"] if tags else None
            rec["tags"][a] = {"pinned": p, "other": o}
            tag_total += 1
            tag_agree += p == o
            cm[(p, o)] += 1
        pm = pinned_map.get(i) or {}
        same = pm.get("kind") == mapping["kind"] and pm.get("fdcId") == mapping.get("fdcId")
        rec["map"]["same"] = same
        map_same += same
        out.append(rec)
    doc = {"date": date.today().isoformat(), "pinned_model": tc["model"], "other_model": model,
           "tag_agreement": f"{tag_agree}/{tag_total}", "tag_confusion_pinned_to_other": {f"{a}->{b}": n for (a, b), n in sorted(cm.items(), key=str)},
           "map_agreement": f"{map_same}/{len(results)}", "usage": usage, "results": out}
    path = ROOT / f"docs/research/{doc['date']}-{args['--label']}.json"
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"tags {doc['tag_agreement']}, map {doc['map_agreement']}; usage {usage}; wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
