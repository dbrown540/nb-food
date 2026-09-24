#!/usr/bin/env python3
"""The spine gate: keeps the registry in spine/ true against the code and data.

Registry: spine/tiers.json (tiers, grains, reject destinations, coverage),
spine/stages/*.json (principles per stage), spine/invariants.json (shared
integrity invariants), spine/bindings.json (bindings and owner rulings),
spine/owner_signers (the owner's public signing key). spine/STORY.md is
generated from them (--write-story) and never edited.

Items (numbering follows the first-principles-spine paradigm):
  G1  implementer file / symbol / data key / case input exists
  G2  every registered path is tracked by git (staged counts)
  G3  an enforcer is called from its calledBy
  G4  a code implementer has a test that names it
  G5  a principle has exactly one decider; an invariant has none
  G6  an implementer's kind matches its tier (cascade: per path; tier = highest path)
  G7  a T3/T4 principle or path has whyNotLower
  G8  a principle or invariant has an enforcer or a stated gap
  G8a an enforcer declares onReject (halt | drop | hold; hold names its queue)
  G9  two or more canonical cases where code implements the entry; every case passes
  G10 inputs name existing entries with the producer's grain; no cycles; consumers too
  G11 ids are unique across the registry
  G12 every stance (a principle's or invariant's statement, grain or scope and
      tier; a whole ruling) has owner consent, or its consent is not yet overdue:
      consent is a commit signed with the owner's key that landed the stance, and
      it is owed `time.consentDays` after the stance first landed. Everything else
      lands on a green gate with no owner action.
  G12a a battery or prompt carries a contentHash equal to its files' hash
  G13 a principle has a grain, an invariant a scope, and not the other's field
  G14 a statement contains no code-shaped token (heuristic)
  G15 a statement contains no number
  G16 a ruling has decidedOn / by / basis / reviewBy and is not past review
  G18 a T2 path has a measurement or a stated gap; a measurement is not expired
  G18a a gap or an interim marker is not past its reviewBy
  G19 a T2-T4 implementer's outputs carry their basis with model identity
  G20 a T2/T3 implementer whose outputs flow on has tracked pins
  G21 (interim, by name pattern) every check_* function is a registered enforcer
  G22 spine/STORY.md equals what the registry renders
  G23 a decider or routing function holds no number other than 0 or 1
      (a subscript index is structure, not a threshold, and is not counted)
Not implemented, with the reason: G2a (nothing here runs outside the build),
G17 (no binding is keyed by data vintage yet; menu freshness is a principle).

Every date check warns from `time.warnDays` before the date and fails after it.

    python3 scripts/spine_gate.py [--pre-commit] [--today YYYY-MM-DD] [--root DIR]
    python3 scripts/spine_gate.py --write-story
"""
import ast
import importlib.util
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from spine_hash import content_hash, json_hash  # noqa: E402


class Gate:
    def __init__(self, root: Path, today: str, pre_commit: bool):
        self.root, self.today, self.pre_commit = root, today, pre_commit
        self.fails, self.warns = [], []
        rd = lambda p: json.loads((root / p).read_text())
        self.tiers = rd("spine/tiers.json")
        self.stages = [rd(str(p.relative_to(root))) for p in sorted((root / "spine/stages").glob("*.json"))]
        self.invariants = rd("spine/invariants.json")["invariants"]
        self.bindings = rd("spine/bindings.json")
        self.warn_days = self.bindings["bindings"]["time"]["warnDays"]
        self._tracked = None

    # ---------------------------------------------------------------- helpers
    def fail(self, item, msg):
        self.fails.append(f"{item} {msg}")

    def warn(self, item, msg):
        self.warns.append(f"{item} {msg}")

    def principles(self):
        for s in self.stages:
            for p in s["principles"]:
                yield s["stage"], p

    def entries(self):
        for _, p in self.principles():
            yield "principle", p
        for i in self.invariants:
            yield "invariant", i

    def impls(self, e):
        """Every implementer of an entry, cascade routes and paths flattened."""
        for im in e.get("implementers", []):
            if im.get("kind") == "cascade":
                yield {**im["route"], "role": "route", "kind": "code"}
                for p in im["paths"]:
                    yield {**p, "role": "path"}
            else:
                yield im

    def tracked(self) -> set:
        if self._tracked is None:
            r = subprocess.run(["git", "ls-files"], cwd=self.root, capture_output=True, text=True)
            self._tracked = set(r.stdout.split("\n")) if r.returncode == 0 else set()
        return self._tracked

    def is_tracked(self, path: str) -> bool:
        t = self.tracked()
        return path in t or any(x.startswith(path.rstrip("/") + "/") for x in t)

    def date_check(self, item, what, due: str):
        try:
            d = date.fromisoformat(due)
        except (TypeError, ValueError):
            return self.fail(item, f"{what}: no valid date ({due!r})")
        t = date.fromisoformat(self.today)
        if t > d:
            self.fail(item, f"{what}: past {due}")
        elif t >= d - timedelta(days=self.warn_days):
            self.warn(item, f"{what}: due {due}")

    def binding(self, ref: str):
        key, _, field = ref.partition(".")
        return self.bindings["bindings"][key][field]

    def load_module(self, path: str):
        name = "spine_case_" + re.sub(r"\W", "_", str(self.root / path))
        if name in sys.modules:
            return sys.modules[name]
        if str(self.root / "scripts") not in sys.path:
            sys.path.insert(0, str(self.root / "scripts"))
        spec = importlib.util.spec_from_file_location(name, self.root / path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    # ---------------------------------------------------------------- items
    def g1_exists(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                path = im.get("path")
                if not path:
                    continue
                f = self.root / path
                if not f.exists():
                    self.fail("G1", f"{e['id']}: {path} does not exist")
                    continue
                if im.get("symbol") and f.is_file() and not re.search(rf"^def {re.escape(im['symbol'])}\(", f.read_text(), re.M):
                    self.fail("G1", f"{e['id']}: {path} has no function {im['symbol']}")
                if im.get("key") and f.suffix == ".json" and im["key"] not in json.loads(f.read_text()):
                    self.fail("G1", f"{e['id']}: {path} has no key {im['key']}")
            for b in e.get("bindings", []):
                f = self.root / b["path"]
                if not f.exists():
                    self.fail("G1", f"{e['id']}: binding file {b['path']} does not exist")
                else:
                    d = json.loads(f.read_text())
                    if b["key"] not in d and b["key"] not in d.get("bindings", {}):
                        self.fail("G1", f"{e['id']}: binding {b['path']}#{b['key']} does not exist")
            for c in e.get("cases", []):
                if not (self.root / c["input"]).exists():
                    self.fail("G1", f"{e['id']}: case input {c['input']} does not exist")

    def g2_tracked(self):
        if not self.tracked():
            return self.fail("G2", "not a git checkout; tracked paths cannot be verified")
        paths = {"spine/tiers.json", "spine/invariants.json", "spine/bindings.json", "spine/owner_signers", "spine/STORY.md"}
        for kind, e in self.entries():
            for im in self.impls(e):
                for k in ("path", "tests", "calledBy", "pins"):
                    if im.get(k):
                        paths.add(im[k])
                paths.update(im.get("hashes", []))
            paths.update(c["input"] for c in e.get("cases", []))
            paths.update(b["path"] for b in e.get("bindings", []))
        for p in sorted(paths):
            if not self.is_tracked(p):
                self.fail("G2", f"{p} is not tracked by git")

    def g3_called(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                if im.get("role") != "enforces":
                    continue
                cb = self.root / im.get("calledBy", "")
                if not im.get("calledBy") or not cb.is_file() or f"{im['symbol']}(" not in cb.read_text():
                    self.fail("G3", f"{e['id']}: {im.get('symbol')} is not called from {im.get('calledBy')}")

    def g4_tests(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                if im.get("kind") != "code" or im.get("role") == "path":
                    continue
                t = self.root / im.get("tests", "")
                if not im.get("tests") or not t.is_file() or im["symbol"] not in t.read_text():
                    self.fail("G4", f"{e['id']}: no test names {im.get('symbol')}")

    def g5_deciders(self):
        for kind, e in self.entries():
            n = sum(1 for im in e.get("implementers", []) if im["role"] == "decides")
            if kind == "principle" and n != 1:
                self.fail("G5", f"{e['id']}: {n} deciders (one required)")
            if kind == "invariant" and n:
                self.fail("G5", f"{e['id']}: an invariant has a decider")

    def g6_kind_tier(self):
        order = self.tiers["order"]
        for _, p in self.principles():
            for im in p.get("implementers", []):
                if im["role"] != "decides":
                    continue
                if im["kind"] == "cascade":
                    top = max((pt["tier"] for pt in im["paths"]), key=order.index)
                    if p["tier"] != top:
                        self.fail("G6", f"{p['id']}: tier {p['tier']} but highest path is {top}")
                    for pt in im["paths"]:
                        if pt["kind"] not in self.tiers["tiers"][pt["tier"]]["kinds"]:
                            self.fail("G6", f"{p['id']}: path kind {pt['kind']} does not match {pt['tier']}")
                elif im["kind"] not in self.tiers["tiers"][p["tier"]]["kinds"]:
                    self.fail("G6", f"{p['id']}: decider kind {im['kind']} does not match {p['tier']}")

    def g7_why_not_lower(self):
        for _, p in self.principles():
            if p["tier"] in ("T3", "T4") and not p.get("whyNotLower"):
                cascade = any(im.get("kind") == "cascade" for im in p["implementers"])
                if not cascade:
                    self.fail("G7", f"{p['id']}: {p['tier']} without whyNotLower")
            for im in self.impls(p):
                if im.get("role") == "path" and im["tier"] in ("T3", "T4") and not im.get("whyNotLower"):
                    self.fail("G7", f"{p['id']}: {im['tier']} path '{im.get('label')}' without whyNotLower")

    def g8_enforced(self):
        for kind, e in self.entries():
            enforcers = [im for im in e.get("implementers", []) if im["role"] == "enforces"]
            if not enforcers and not e.get("gap"):
                self.fail("G8", f"{e['id']}: no enforcer and no stated gap")
            for im in enforcers:
                r = im.get("onReject")
                if r not in self.tiers["onReject"]:
                    self.fail("G8a", f"{e['id']}: onReject {r!r} not in {self.tiers['onReject']}")
                if r == "hold":
                    q = im.get("holdQueue") or {}
                    if not (q.get("path") and q.get("raisedBy") and self.is_tracked(q["path"])):
                        self.fail("G8a", f"{e['id']}: a hold without a tracked queue and what raises it")

    def g9_cases(self):
        for kind, e in self.entries():
            code = any(im.get("kind") in ("code", "cascade") for im in e.get("implementers", []))
            cases = e.get("cases", [])
            if code and len(cases) < 2:
                self.fail("G9", f"{e['id']}: {len(cases)} canonical case(s); two or more required")
            for c in cases:
                try:
                    path, sym = c["call"].split(":")
                    got = getattr(self.load_module(path), sym)(json.loads((self.root / c["input"]).read_text()))
                    if isinstance(got, list):
                        got = {"problems": len(got)}
                except Exception as ex:  # a case that cannot run is a failing case
                    self.fail("G9", f"{e['id']}: case '{c['given']}' raised {ex!r}")
                    continue
                if not subset(c["expect"], got):
                    self.fail("G9", f"{e['id']}: case '{c['given']}' expected {c['expect']}, got {got}")

    def g10_inputs(self):
        grains = self.tiers["grains"]
        grain_of = {p["id"]: p.get("grain") for _, p in self.principles()}
        edges = {}
        consumers = [c for s in self.stages for c in s.get("consumers", [])]
        for owner in [p for _, p in self.principles()] + consumers:
            for i in owner.get("inputs", []):
                src = i["principle"]
                if src not in grain_of:
                    self.fail("G10", f"{owner['id']}: input names missing entry {src}")
                    continue
                if i.get("grain") not in grains or i["grain"] != grain_of[src]:
                    self.fail("G10", f"{owner['id']}: input grain {i.get('grain')!r} != {src}'s grain {grain_of[src]!r}")
                edges.setdefault(owner["id"], set()).add(src)
        seen, stack = set(), set()

        def visit(n):
            if n in stack:
                self.fail("G10", f"input cycle through {n}")
                return
            if n in seen:
                return
            seen.add(n)
            stack.add(n)
            for m in edges.get(n, ()):
                visit(m)
            stack.discard(n)
        for n in list(edges):
            visit(n)

    def g11_unique(self):
        ids = [e["id"] for _, e in self.entries()] + [r["id"] for r in self.bindings["rulings"]]
        ids += [c["id"] for s in self.stages for c in s.get("consumers", [])]
        for i in sorted({i for i in ids if ids.count(i) > 1}):
            self.fail("G11", f"id {i} appears more than once")

    def g12_review(self):
        """Owner consent to stances. A stance is what tests 1, 3 and 4 judge: a principle's or
        invariant's statement, grain or scope and tier, or a whole ruling. Implementation,
        prompt wording and data land on a green gate with no owner action. A stance may land
        before consent; consent is owed `time.consentDays` after the stance first landed (an
        uncommitted stance counts from today) and the usual window applies: warn, then fail.
        Consent is a commit signed with the owner's key (spine/owner_signers) that landed the
        stance; the gate checks the signature, never a field an agent wrote."""
        days = self.bindings["bindings"]["time"]["consentDays"]
        signers = self.root / "spine/owner_signers"
        files = [str(p.relative_to(self.root)) for p in sorted((self.root / "spine/stages").glob("*.json"))]
        files += ["spine/invariants.json", "spine/bindings.json"]
        for f in files:
            current = stances_in(json.loads((self.root / f).read_text()))
            log = git(self.root, "log", "--format=%H %cs", "--", f).split("\n")
            versions = []
            for line in filter(None, log):
                c, day = line.split()
                show = git(self.root, "show", f"{c}:{f}")
                versions.append((c, day, stances_in(json.loads(show)) if show else {}))
            for eid, h in sorted(current.items()):
                intro, landed = None, self.today
                for c, day, ents in versions:
                    if ents.get(eid) != h:
                        break
                    intro, landed = c, day
                if intro and signers.exists():
                    status = git(self.root, "-c", f"gpg.ssh.allowedSignersFile={signers}", "log", "-1", "--format=%G?", intro).strip()
                    if status == "G":
                        continue
                due = (date.fromisoformat(landed) + timedelta(days=days)).isoformat()
                self.date_check("G12", f"{eid}: owner consent to its stance (landed {'uncommitted' if not intro else intro[:10]})", due)

    def g12a_hashes(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                if im.get("kind") in ("battery", "prompt"):
                    files = im.get("hashes") or [im["path"]]
                    if not im.get("contentHash"):
                        self.fail("G12a", f"{e['id']}: {im['path']} has no contentHash")
                    elif all((self.root / f).exists() for f in files) and content_hash(self.root, files) != im["contentHash"]:
                        self.fail("G12a", f"{e['id']}: {im['path']} changed since its hash was pinned (review and re-measure)")

    def g13_grain_scope(self):
        stages = {s["stage"] for s in self.stages}
        for kind, e in self.entries():
            if kind == "principle":
                if e.get("grain") not in self.tiers["grains"] or "scope" in e:
                    self.fail("G13", f"{e['id']}: a principle needs a grain from the vocabulary and no scope")
            else:
                if not e.get("scope") or "grain" in e or not set(e["scope"]) <= stages:
                    self.fail("G13", f"{e['id']}: an invariant needs a scope of stage names and no grain")

    CODE_TOKEN = re.compile(r"`|\b\w+\.(py|json|md|js|csv|html|txt)\b|/\w|\b[a-z]+[A-Z]\w*|\b[a-z]+_[a-z_]+\b|\b\w+\.\w+\.\w+|\b\w+\(")

    def g14_g15_statements(self):
        for kind, e in self.entries():
            s = e.get("statement", "")
            if self.CODE_TOKEN.search(s):
                self.fail("G14", f"{e['id']}: statement has a code-shaped token: {self.CODE_TOKEN.search(s).group(0)!r}")
            if re.search(r"\d", s):
                self.fail("G15", f"{e['id']}: statement has a number")

    def g16_rulings(self):
        for r in self.bindings["rulings"]:
            missing = [k for k in ("decidedOn", "by", "basis", "reviewBy") if not r.get(k)]
            if missing:
                self.fail("G16", f"ruling {r['id']}: missing {missing}")
            else:
                self.date_check("G16", f"ruling {r['id']} review", r["reviewBy"])

    def g18_measured(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                if im.get("role") == "path" and im.get("tier") == "T2":
                    m = im.get("measurement")
                    if not m and not im.get("gap"):
                        self.fail("G18", f"{e['id']}: T2 path without a measurement or a stated gap")
                    if m:
                        self.date_check("G18", f"{e['id']} measurement", m.get("expires"))

    def g18a_gaps(self):
        for kind, e in self.entries():
            for obj in [e] + list(self.impls(e)):
                if obj.get("gap"):
                    self.date_check("G18a", f"{e['id']} gap", obj["gap"].get("reviewBy"))
        cov = self.tiers.get("coverage", {})
        if cov.get("interim"):
            self.date_check("G18a", "interim coverage check", cov.get("reviewBy"))

    def g19_basis(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                out = im.get("outputs")
                if not out:
                    continue
                if out["format"] == "pins":
                    f = self.root / out["path"]
                    for n, line in enumerate(f.read_text().splitlines() if f.exists() else [], 1):
                        p = json.loads(line)
                        if not (p.get("basis") and p.get("models") and p.get("samples")):
                            self.fail("G19", f"{e['id']}: {out['path']} line {n} has no basis with model identity")
                            break
                elif out["format"] == "menu-files":
                    since = self.binding(out["requiredFrom"])
                    for d in out["paths"]:
                        for f in sorted((self.root / d).glob("*.json")):
                            doc = json.loads(f.read_text())
                            if f.name == "index.json" or not isinstance(doc, dict) or doc.get("as_of", "") < since:
                                continue
                            ex = doc.get("extraction") or {}
                            if not ((ex.get("model") and ex.get("prompt_hash")) or (ex.get("method") == "script" and ex.get("path"))):
                                self.fail("G19", f"{e['id']}: {d}/{f.name} carries no extraction basis")

    def g20_pins(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                tier = im.get("tier") or (e.get("tier") if im.get("role") == "decides" else None)
                if tier in ("T2", "T3") and im.get("kind") in ("battery", "prompt"):
                    if not im.get("pins") or not self.is_tracked(im["pins"]):
                        self.fail("G20", f"{e['id']}: outputs flow on but pins {im.get('pins')!r} are not tracked")

    def g21_coverage(self):
        cov = self.tiers.get("coverage", {})
        registered = {im.get("symbol") for _, e in self.entries() for im in self.impls(e) if im.get("role") == "enforces"}
        for f in cov.get("files", []):
            for m in re.finditer(cov["pattern"], (self.root / f).read_text(), re.M):
                if m.group(1) not in registered:
                    self.fail("G21", f"{f}: {m.group(1)} is an unregistered gate")

    def g22_story(self):
        f = self.root / "spine/STORY.md"
        if not f.exists() or f.read_text() != render_story(self):
            self.fail("G22", "spine/STORY.md differs from the registry (run scripts/spine_gate.py --write-story)")

    def g23_literals(self):
        for kind, e in self.entries():
            for im in self.impls(e):
                if im.get("kind") != "code" or im.get("role") not in ("decides", "route", "path") or not im.get("symbol"):
                    continue
                f = self.root / im["path"]
                if not f.exists():
                    continue
                fn = next((n for n in ast.walk(ast.parse(f.read_text())) if isinstance(n, ast.FunctionDef) and n.name == im["symbol"]), None)
                if fn is None:
                    continue
                index_consts = {id(n.slice) for n in ast.walk(fn) if isinstance(n, ast.Subscript)}
                for n in ast.walk(fn):
                    if isinstance(n, ast.Constant) and type(n.value) in (int, float) and n.value not in (0, 1) \
                            and id(n) not in index_consts:
                        self.fail("G23", f"{e['id']}: {im['symbol']} holds the number {n.value} (line {n.lineno}); make it a binding")

    def run(self):
        for item in (self.g1_exists, self.g2_tracked, self.g3_called, self.g4_tests, self.g5_deciders,
                     self.g6_kind_tier, self.g7_why_not_lower, self.g8_enforced, self.g9_cases, self.g10_inputs,
                     self.g11_unique, self.g12_review, self.g12a_hashes, self.g13_grain_scope,
                     self.g14_g15_statements, self.g16_rulings, self.g18_measured, self.g18a_gaps,
                     self.g19_basis, self.g20_pins, self.g21_coverage, self.g22_story, self.g23_literals):
            item()
        return self


# -------------------------------------------------------------------- shared
def subset(exp, got) -> bool:
    if isinstance(exp, dict):
        return isinstance(got, dict) and all(k in got and subset(v, got[k]) for k, v in exp.items())
    return exp == got


def git(root: Path, *args) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


STANCE_FIELDS = ("statement", "grain", "scope", "tier")


def stances_in(doc: dict) -> dict:
    """id -> hash of the stance of every principle, invariant and ruling in a registry file:
    the statement, grain or scope and tier of an entry; the whole of a ruling."""
    out = {}
    for key in ("principles", "invariants"):
        for e in doc.get(key, []):
            out[e["id"]] = json_hash({k: e.get(k) for k in STANCE_FIELDS}, 64)
    for r in doc.get("rulings", []):
        out[r["id"]] = json_hash(r, 64)
    return out


def render_story(g: Gate) -> str:
    L = ["# How nb-food decides", "",
         "_Generated from spine/ by `python3 scripts/spine_gate.py --write-story`. Do not edit._", ""]

    def impl_line(im):
        where = im.get("path", "")
        if im.get("symbol"):
            where += f" `{im['symbol']}`"
        if im.get("key"):
            where += f" `#{im['key']}`"
        return where

    for s in g.stages:
        L += [f"## Stage: {s['stage']}", "", s["story"], ""]
        for p in s["principles"]:
            L += [f"### {p['id']}", "", f"> {p['statement']}", "", f"- grain: {p['grain']}; tier: {p['tier']}"]
            for im in p["implementers"]:
                if im["kind"] == "cascade":
                    L.append(f"- decided by a cascade routed by {impl_line(im['route'])}:")
                    for pt in im["paths"]:
                        L.append(f"  - {pt['tier']}: {pt['label']} ({impl_line(pt)})")
                        if pt.get("gap"):
                            L.append(f"    - known gap, review by {pt['gap']['reviewBy']}: {pt['gap']['text']}")
                elif im["role"] == "decides":
                    L.append(f"- decided by: {im['kind']} {impl_line(im)}")
                else:
                    L.append(f"- enforced by: {impl_line(im)}, on reject: {im['onReject']}")
            if p.get("whyNotLower"):
                L.append(f"- why not lower: {p['whyNotLower']}")
            if p.get("gap"):
                L.append(f"- known gap, review by {p['gap']['reviewBy']}: {p['gap']['text']}")
            for b in p.get("bindings", []):
                L.append(f"- binding: {b['path']} `{b['key']}`")
            for i in p.get("inputs", []):
                L.append(f"- reads: {i['principle']} ({i['field']}, per {i['grain']})")
            L.append("- cases:")
            L += [f"  - {c['given']}: expect {json.dumps(c['expect'])}" for c in p.get("cases", [])]
            L.append("")
        if s.get("consumers"):
            L.append("Consumers:")
            L += [f"- {c['id']} ({c['path']}) reads " + ", ".join(i["principle"] for i in c["inputs"]) for c in s["consumers"]]
            L.append("")
    L += ["## Integrity invariants", ""]
    for i in g.invariants:
        L += [f"### {i['id']}", "", f"> {i['statement']}", "", f"- scope: {', '.join(i['scope'])}"]
        for im in i["implementers"]:
            L.append(f"- enforced by: {impl_line(im)}, on reject: {im['onReject']}")
        L.append("- cases:")
        L += [f"  - {c['given']}: expect {json.dumps(c['expect'])}" for c in i.get("cases", [])]
        L.append("")
    L += ["## Rulings", ""]
    for r in g.bindings["rulings"]:
        L.append(f"- **{r.get('id')}** ({r.get('path') or r.get('binding')}): by {r.get('by')} on {r.get('decidedOn')}, "
                 f"review by {r.get('reviewBy')}. {r.get('basis', '(no basis recorded)')}")
    L.append("")
    return "\n".join(L)


def main(argv: list) -> int:
    root, today, pre, write = HERE.parent, date.today().isoformat(), False, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--pre-commit":
            pre = True
        elif a == "--write-story":
            write = True
        elif a in ("--today", "--root") and i + 1 < len(argv):
            if a == "--today":
                today = argv[i + 1]
            else:
                root = Path(argv[i + 1]).resolve()
            i += 1
        else:
            raise SystemExit(f"spine_gate: unknown argument {a!r}")
        i += 1
    g = Gate(root, today, pre)
    if write:
        (root / "spine/STORY.md").write_text(render_story(g))
        print("wrote spine/STORY.md")
        return 0
    g.run()
    for w in g.warns:
        print("WARN", w)
    for f in g.fails:
        print("FAIL", f)
    n = sum(1 for _ in g.entries())
    print(f"spine_gate: {len(g.fails)} failure(s), {len(g.warns)} warning(s); {n} entries, {len(g.bindings['rulings'])} rulings")
    return 1 if g.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
