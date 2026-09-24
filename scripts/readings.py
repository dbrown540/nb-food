"""Model readings shared by the pinned classifier steps (tag_items.py, map_foods.py).

read_all() sends every pending text `n` times over one of two transports:

  api   the Anthropic API: the Batches API by default (half price; an in-flight
        batch id is kept in a gitignored state file so a rerun resumes it) or
        directly with --sync for a handful. Billed to the API key.
  cli   Claude Code in headless mode (`claude -p`), one fresh session per
        reading, billed to the signed-in Claude plan. Each call loads nothing
        but the battery: no tools, MCP servers, settings, skills or memory, and
        thinking off. The
        answer is held to the same JSON schema (--json-schema), and the model id
        is the one the CLI reports from the provider's response (modelUsage).
        Readings are handed back as they finish (on_done), so a usage limit
        stops a run without losing what was read.

It returns the parsed readings with the model id each response reports; the
caller pins them.

The API key comes from ANTHROPIC_API_KEY, else from `op read REF` run as the
1Password service account (op_read; REF from the caller's flag or NB_FOOD_KEY_REF).
It is never printed or written.
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


def op_read(ref: str) -> str:
    """Read one secret with the 1Password CLI as the service account, never through the
    desktop app. The service-account token is OP_SERVICE_ACCOUNT_TOKEN, else it is read from
    the macOS keychain item named by NB_FOOD_OP_KEYCHAIN_ITEM. Neither the token nor the
    value read is printed, logged or written; they live only in this process."""
    env = dict(os.environ)
    if not env.get("OP_SERVICE_ACCOUNT_TOKEN"):
        item = env.get("NB_FOOD_OP_KEYCHAIN_ITEM")
        if not item:
            raise SystemExit("set NB_FOOD_OP_KEYCHAIN_ITEM (the keychain item holding the 1Password "
                             "service-account token) or OP_SERVICE_ACCOUNT_TOKEN")
        r = subprocess.run(["security", "find-generic-password", "-s", item, "-w"], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise SystemExit(f"no service-account token in keychain item {item!r}")
        env["OP_SERVICE_ACCOUNT_TOKEN"] = r.stdout.strip()
    r = subprocess.run(["op", "read", ref], capture_output=True, text=True, env=env)
    if r.returncode != 0 or not r.stdout.strip():
        reason = (r.stderr.strip().splitlines() or ["no value returned"])[-1]
        raise SystemExit(f"op read {ref} failed as the service account: {reason}")
    return r.stdout.strip()


def api_key(ref: str) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    ref = ref or os.environ.get("NB_FOOD_KEY_REF")
    if not ref:
        raise SystemExit("no ANTHROPIC_API_KEY and no --key-ref / NB_FOOD_KEY_REF")
    return op_read(ref)


def usage_of(msg) -> dict:
    u = msg.usage
    return {"input": u.input_tokens or 0, "cache_write": u.cache_creation_input_tokens or 0,
            "cache_read": u.cache_read_input_tokens or 0, "output": u.output_tokens or 0}


def add_usage(total: dict, u: dict) -> None:
    for k, v in u.items():
        total[k] = total.get(k, 0) + v


def read_all(todo: dict, n: int, params_fn, parse_fn, sync: bool, key_ref: str, state: Path, basis_hash: str) -> tuple:
    """todo: {key: text}. -> (got {key: {sample index: (sample, model)}}, usage, failures, batched)."""
    import anthropic  # only the reading step needs the SDK
    client = anthropic.Anthropic(api_key=api_key(key_ref), max_retries=6)
    got, usage, failures = {}, {}, []

    def take(key, s, msg):
        add_usage(usage, usage_of(msg))
        sample, model = parse_fn(msg)
        if sample is None:
            failures.append((key, model))
        else:
            got.setdefault(key, {})[s] = (sample, model)

    if sync:
        from concurrent.futures import ThreadPoolExecutor
        jobs = [(k, s) for k in todo for s in range(n)]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for (k, s), msg in zip(jobs, ex.map(lambda j: client.messages.create(**params_fn(todo[j[0]])), jobs)):
                take(k, s, msg)
        return got, usage, failures, False

    st = json.loads(state.read_text()) if state.exists() else {}
    if st.get("basis") == basis_hash and st.get("batch_id"):
        batch_id = st["batch_id"]
        print(f"resuming batch {batch_id}")
    else:
        reqs = [{"custom_id": f"{k}-{s}", "params": params_fn(todo[k])} for k in todo for s in range(n)]
        batch_id = client.messages.batches.create(requests=reqs).id
        state.write_text(json.dumps({"batch_id": batch_id, "basis": basis_hash, "texts": len(todo)}))
        print(f"submitted batch {batch_id}: {len(reqs)} requests")
    while True:
        bt = client.messages.batches.retrieve(batch_id)
        rc = bt.request_counts
        print(f"  {bt.processing_status}: processing {rc.processing}, succeeded {rc.succeeded}, errored {rc.errored}", flush=True)
        if bt.processing_status == "ended":
            break
        time.sleep(60)
    for res in client.messages.batches.results(batch_id):
        k, s = res.custom_id.rsplit("-", 1)
        if res.result.type != "succeeded":
            failures.append((k, res.result.type))
        else:
            take(k, int(s), res.result.message)
    state.unlink(missing_ok=True)
    return got, usage, failures, True


def pin_lines(pins: dict) -> str:
    return "\n".join(json.dumps(pins[k], ensure_ascii=False, sort_keys=True) for k in sorted(pins)) + "\n"


def cli_message(system: str, schema: dict, text: str, model: str):
    """One headless Claude Code reading -> a message-shaped object (content, stop_reason,
    model, usage) so the callers' parsers read it like an API response."""
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    with tempfile.TemporaryDirectory() as tmp:  # an empty working directory: no project context to discover
        mcp = Path(tmp) / "mcp.json"
        mcp.write_text('{"mcpServers": {}}')
        try:
            r = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", "--no-session-persistence",
                            "--tools", "", "--strict-mcp-config", "--mcp-config", str(mcp), "--setting-sources", "",
                            "--disable-slash-commands", "--no-chrome", "--settings", '{"alwaysThinkingEnabled": false}',
                            "--system-prompt", system,
                            "--json-schema", json.dumps(schema), text],
                           capture_output=True, text=True, cwd=tmp, env=env, stdin=subprocess.DEVNULL, timeout=300)
        except subprocess.TimeoutExpired:  # a hung reading is a failed reading, never a crashed run
            return SimpleNamespace(stop_reason="cli timeout", content=[], model=None, usage=None)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return SimpleNamespace(stop_reason=f"cli exit {r.returncode}", content=[], model=None, usage=None,
                               error=(r.stderr.strip().splitlines() or ["no output"])[-1][:200])
    usage = d.get("modelUsage") or {}
    models = sorted(usage)
    u = SimpleNamespace(input_tokens=sum(m.get("inputTokens", 0) for m in usage.values()),
                        cache_creation_input_tokens=sum(m.get("cacheCreationInputTokens", 0) for m in usage.values()),
                        cache_read_input_tokens=sum(m.get("cacheReadInputTokens", 0) for m in usage.values()),
                        output_tokens=sum(m.get("outputTokens", 0) for m in usage.values()))
    ok = not d.get("is_error") and d.get("structured_output") is not None and models == [model]
    reason = "end_turn" if ok else ("wrong model " + ",".join(models) if d.get("structured_output") is not None else
                                    f"cli error: {str(d.get('result'))[:160]}")
    return SimpleNamespace(stop_reason=reason, model=models[0] if len(models) == 1 else ",".join(models), usage=u,
                           content=[SimpleNamespace(type="text", text=json.dumps(d.get("structured_output")))])


def read_cli(todo: dict, n: int, request_fn, parse_fn, on_done, workers: int, stop_after: int = 6) -> tuple:
    """request_fn(text) -> (system, schema, model). on_done(key, readings) is called as soon
    as a text has all n usable readings. After `stop_after` failed readings in a row (a plan
    limit, an exhausted credit, an outage) no new reading starts and the run returns.
    -> (usage, failures)."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    usage, failures, lock = {}, [], threading.Lock()
    state = {"in_a_row": 0, "stopped": ""}

    def one(key):
        system, schema, model = request_fn(todo[key])
        got = []
        for _ in range(n):
            if state["stopped"]:
                return
            msg = cli_message(system, schema, todo[key], model)
            sample, who = parse_fn(msg) if msg.stop_reason in ("end_turn", "refusal") else (None, msg.stop_reason)
            with lock:
                if msg.usage is not None:
                    add_usage(usage, usage_of(msg))
                if sample is None:
                    failures.append((key, who))
                    state["in_a_row"] += 1
                    if state["in_a_row"] >= stop_after and not state["stopped"]:
                        state["stopped"] = str(who)
                        print(f"stopping: {stop_after} failed readings in a row, last: {who}", flush=True)
                else:
                    state["in_a_row"] = 0
            if sample is None:
                return
            got.append((sample, who))
        with lock:
            on_done(key, got)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, list(todo)))
    return usage, failures


def sampling_basis(c: dict) -> dict:
    """The sampling half of a basis, from a step's bindings (its transport included)."""
    if c.get("transport") == "cli":
        return {"transport": "claude-code-cli", "samples": c["samples"], "thinking": "disabled",
                "answer": "structured output tool", "temperature": "provider default"}
    return {"samples": c["samples"], "effort": c["effort"], "thinking": c["thinking"],
            "maxTokens": c["maxTokens"], "temperature": "provider default"}


class PinWriter:
    """Collects finished readings and rewrites the pin file every `every` texts and at close,
    so an interrupted run keeps what it read."""

    def __init__(self, path: Path, load, every: int):
        self.path, self.load, self.every, self.new, self.lock = path, load, every, [], __import__("threading").Lock()

    def add(self, pin: dict):
        with self.lock:
            self.new.append(pin)
            if len(self.new) % self.every == 0:
                self.flush()

    def flush(self):
        pins = self.load()
        for p in self.new:
            pins[(p["key"], p["basis"])] = p
        self.path.write_text(pin_lines(pins))


# USD per million tokens (Anthropic list prices; the Batches API bills half). Used only to keep a
# run under the budget its caller sets; the record of cost is the API's own usage figures.
PRICES = {"claude-opus-5": (5.0, 25.0), "claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5": (2.0, 10.0)}
BATCH_DISCOUNT = 0.5


def batch_cost(usage: dict, model: str) -> float:
    pin, pout = PRICES[model]
    full = (usage.get("input", 0) * pin + usage.get("cache_write", 0) * pin * 1.25
            + usage.get("cache_read", 0) * pin * 0.1 + usage.get("output", 0) * pout) / 1e6
    return full * BATCH_DISCOUNT


def read_budgeted(todo: dict, n: int, params_fn, parse_fn, key_ref: str, state: Path, basis_hash: str,
                  model: str, budget: float, chunk: int, on_chunk) -> tuple:
    """Batches of `chunk` texts, one after another; before each, the cost per text measured so far
    projects the chunk, and the run stops when that would pass `budget` (USD). on_chunk(got) pins
    each chunk as it lands. -> (spent, texts read, texts left)."""
    keys, spent, done, per_text = sorted(todo), 0.0, 0, None
    while done < len(keys):
        size = chunk if per_text is not None else min(chunk, 50)  # the first chunk measures, so it stays small
        part = {k: todo[k] for k in keys[done:done + size]}
        if per_text is not None and spent + per_text * len(part) > budget:
            break
        got, usage, failures, _ = read_all(part, n, params_fn, parse_fn, False, key_ref, state, basis_hash)
        cost = batch_cost(usage, model)
        spent += cost
        done += len(part)
        per_text = spent / done
        on_chunk(got)
        print(f"  chunk of {len(part)}: ${cost:.2f} (${spent:.2f} of ${budget:.2f}); {len(failures)} unusable", flush=True)
    return spent, done, len(keys) - done
