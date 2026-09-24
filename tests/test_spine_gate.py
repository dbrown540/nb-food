"""The spine gate's own negative cases: each test breaks a scratch copy of the
registry the way one gate item guards against and expects that item to fail.
The scratch repo is committed with a throwaway signing key registered as its
owner, so the clean baseline passes every item, G12 included."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from spine_gate import Gate  # noqa: E402

TODAY = "2026-09-23"
COPY = ["spine", "scripts", "tests", "data/attributes.json", "data/tag_pins.jsonl", "data/curated.json",
        "data/menus", "data/products", "data/labels", "data/menu_items.json", "data/usda_index.json",
        "data/food_map_pins.jsonl", "data/usda"]


def git(root, *args, key=None):
    cfg = ["-c", "user.name=case", "-c", "user.email=case@example.org", "-c", "commit.gpgsign=false"]
    if key:
        cfg += ["-c", "gpg.format=ssh", "-c", f"user.signingkey={key}"]
    subprocess.run(["git", *cfg, *args], cwd=root, check=True, capture_output=True)


class GateCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_tmp = tempfile.TemporaryDirectory()
        base = Path(cls.base_tmp.name) / "repo"
        for rel in COPY:
            src, dst = ROOT / rel, base / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy(src, dst)
        cls.key = Path(cls.base_tmp.name) / "owner_key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "case", "-f", str(cls.key)], check=True)
        pub = cls.key.with_suffix(".pub").read_text().split()
        (base / "spine/owner_signers").write_text(f'owner namespaces="git" {pub[0]} {pub[1]}\n')
        git(base, "init", "-q")
        git(base, "add", "-A")
        git(base, "commit", "-q", "-S", "-m", "base", key=cls.key)
        cls.base = base

    @classmethod
    def tearDownClass(cls):
        cls.base_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(self.base, self.root, symlinks=True)

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, pre_commit=True, today=TODAY):
        return Gate(self.root, today, pre_commit).run()

    def codes(self, **kw):
        return {f.split()[0] for f in self.gate(**kw).fails}

    def edit(self, rel, fn):
        p = self.root / rel
        doc = json.loads(p.read_text())
        fn(doc)
        p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")

    def principle(self, doc, pid):
        return next(p for p in doc["principles"] if p["id"] == pid)

    # ---------------------------------------------------------------- baseline
    def test_clean_signed_registry_passes_every_item(self):
        self.assertEqual(self.gate(pre_commit=False).fails, [])

    # ---------------------------------------------------------------- one test per item
    def test_g1_missing_implementer(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness")["implementers"][0].update(path="scripts/gone.py"))
        self.assertIn("G1", self.codes())

    def test_g2_untracked_case_input(self):
        (self.root / "spine/cases/menu-freshness/extra.json").write_text((self.root / "spine/cases/menu-freshness/stale.json").read_text())
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness")["cases"].append(
            {"given": "untracked", "call": "scripts/freshness.py:age_case", "input": "spine/cases/menu-freshness/extra.json", "expect": {"status": "stale"}}))
        self.assertIn("G2", self.codes())

    def test_g3_enforcer_not_called(self):
        self.edit("spine/stages/places.json", lambda d: self.principle(d, "curated-verdict")["implementers"][1].update(calledBy="scripts/freshness.py"))
        self.assertIn("G3", self.codes())

    def test_g4_no_test_names_the_code(self):
        self.edit("spine/stages/places.json", lambda d: self.principle(d, "curated-verdict")["implementers"][1].update(tests="tests/test_freshness.py"))
        self.assertIn("G4", self.codes())

    def test_g5_two_deciders(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness")["implementers"].append(
            dict(self.principle(d, "menu-freshness")["implementers"][0])))
        self.assertIn("G5", self.codes())

    def test_g6_kind_does_not_match_tier(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness").update(tier="T2"))
        self.assertIn("G6", self.codes())

    def test_g7_model_tier_without_why_not_lower(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-extraction").pop("whyNotLower"))
        self.assertIn("G7", self.codes())

    def test_g8_no_enforcer_no_gap(self):
        self.edit("spine/stages/places.json", lambda d: self.principle(d, "inspection-match").pop("gap"))
        self.assertIn("G8", self.codes())

    def test_g8a_reject_destination_outside_the_set(self):
        self.edit("spine/stages/places.json", lambda d: self.principle(d, "curated-verdict")["implementers"][1].update(onReject="repair"))
        self.assertIn("G8a", self.codes())

    def test_g8a_hold_without_queue(self):
        self.edit("spine/stages/places.json", lambda d: self.principle(d, "curated-verdict")["implementers"][1].update(onReject="hold"))
        self.assertIn("G8a", self.codes())

    def test_g9_case_fails_against_the_code(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness")["cases"][2].update(expect={"status": "current"}))
        self.assertIn("G9", self.codes())

    def test_g9_one_case_is_not_enough(self):
        self.edit("spine/invariants.json", lambda d: d["invariants"][0].update(cases=d["invariants"][0]["cases"][:1]))
        self.assertIn("G9", self.codes())

    def test_g10_input_grain_mismatch(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness")["inputs"][0].update(grain="item"))
        self.assertIn("G10", self.codes())

    def test_g10_cycle(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-extraction").update(
            inputs=[{"principle": "menu-freshness", "field": "x", "grain": "menu"}]))
        self.assertIn("G10", self.codes())

    def test_g11_duplicate_id(self):
        self.edit("spine/stages/menus.json", lambda d: d["consumers"][0].update(id="menu-freshness"))
        self.assertIn("G11", self.codes())

    def test_g12_unconsented_stance_warns_in_its_window_then_fails(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness").update(
            statement="A menu older than the kept age is flagged until it is refreshed."))
        git(self.root, "commit", "-q", "-am", "unsigned stance change")
        g = self.gate(pre_commit=False)
        self.assertFalse(any(f.startswith("G12") for f in g.fails))
        self.assertTrue(any(w.startswith("G12 menu-freshness") for w in g.warns))
        self.assertIn("G12", self.codes(pre_commit=False, today="2099-01-01"))

    def test_g12_implementation_change_needs_no_consent(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness")["cases"][0].update(
            given="read a few days ago"))
        git(self.root, "commit", "-q", "-am", "unsigned wording of a case")
        g = self.gate(pre_commit=False, today="2099-01-01")
        self.assertFalse(any(x.startswith("G12") for x in g.fails + g.warns))

    def test_g12_signed_landing_is_consent(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness").update(
            statement="A menu older than the kept age is flagged until it is refreshed."))
        git(self.root, "commit", "-q", "-S", "-am", "signed stance change", key=self.key)
        g = self.gate(pre_commit=False, today="2099-01-01")
        self.assertFalse(any(x.startswith("G12") for x in g.fails + g.warns))

    def test_g12a_battery_changed_under_its_hash(self):
        p = self.root / "spine/battery/item-attributes.md"
        p.write_text(p.read_text() + "\nAnswer generously.\n")
        self.assertIn("G12a", self.codes())

    def test_g13_principle_with_scope(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness").update(scope=["menus"]))
        self.assertIn("G13", self.codes())

    def test_g14_code_token_in_statement(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness").update(statement="A menu past max_age is flagged."))
        self.assertIn("G14", self.codes())

    def test_g15_number_in_statement(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "menu-freshness").update(statement="A menu older than six months (180 days) is flagged."))
        self.assertIn("G15", self.codes())

    def test_g16_ruling_past_review(self):
        self.assertIn("G16", self.codes(today="2027-04-01"))

    def test_g16_ruling_without_basis(self):
        self.edit("spine/bindings.json", lambda d: d["rulings"][0].pop("basis"))
        self.assertIn("G16", self.codes())

    def test_g18_t2_path_without_measurement_or_gap(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "item-attributes")["implementers"][0]["paths"][0].pop("gap"))
        self.assertIn("G18", self.codes())

    def test_g18a_gap_past_review(self):
        self.assertIn("G18a", self.codes(today="2027-01-15"))

    def test_g19_pin_without_model_identity(self):
        p = self.root / "data/tag_pins.jsonl"
        lines = p.read_text().splitlines()
        first = json.loads(lines[0])
        first["models"] = []
        p.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n")
        self.assertIn("G19", self.codes())

    def test_g20_pins_not_tracked(self):
        self.edit("spine/stages/menus.json", lambda d: self.principle(d, "item-attributes")["implementers"][0]["paths"][0].update(pins="data/elsewhere.jsonl"))
        self.assertIn("G20", self.codes())

    def test_g21_unregistered_gate(self):
        p = self.root / "scripts/check_data.py"
        p.write_text(p.read_text() + "\n\ndef check_something_new(root):\n    return []\n")
        self.assertIn("G21", self.codes())

    def test_g22_story_edited_by_hand(self):
        p = self.root / "spine/STORY.md"
        p.write_text(p.read_text() + "\nA sentence nobody generated.\n")
        self.assertIn("G22", self.codes())

    def test_g23_number_in_a_decider(self):
        p = self.root / "scripts/freshness.py"
        p.write_text(p.read_text().replace('    due = date.fromisoformat(as_of)', '    grace = 7\n    due = date.fromisoformat(as_of)'))
        self.assertIn("G23", self.codes())


if __name__ == "__main__":
    unittest.main()
