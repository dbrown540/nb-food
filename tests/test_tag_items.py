import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import tag_items as t  # noqa: E402


class RouteAttribute(unittest.TestCase):
    def r(self, samples, text="Item: Fried Calamari with Lemon"):
        return t.route_attribute(samples, text, 2, 3)

    def test_yes_needs_two_quoting_readings(self):
        self.assertEqual(self.r([("y", ["Fried"]), ("y", ["fried calamari"]), ("u", [])]), ("yes", 2, ["Fried", "fried calamari"]))
        self.assertEqual(self.r([("y", ["Fried"]), ("u", []), ("n", [])])[0], "unknown")

    def test_a_yes_that_quotes_nothing_in_the_item_is_unknown(self):
        self.assertEqual(self.r([("y", ["battered"]), ("y", ["crispy"]), ("y", [])]), ("unknown", 3, []))

    def test_no_needs_all_readings(self):
        self.assertEqual(self.r([("n", ["Lemon"]), ("n", []), ("n", [])])[0], "no")
        self.assertEqual(self.r([("n", []), ("n", []), ("u", [])])[0], "unknown")


class CheckItemTags(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("spine/bindings.json", "spine/battery/item-attributes.md", "data/attributes.json"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, self.root / rel)
        row = {"id": "case--fried-calamari", "place": "Case", "kind": "menu", "section": "", "name": "Fried Calamari",
               "description": "", "size": "", "price": 9.0, "source": "case", "as_of": "2026-09-23", "status": "ok"}
        (self.root / "data/menu_items.json").write_text(json.dumps({"schema_version": 1, "rows": [row]}))
        text = t.item_text(row)
        ids = [a["id"] for a in t.attributes(self.root)]
        pin = {"key": t.text_hash(text), "basis": t.json_hash(t.basis(self.root)), "models": ["m"], "at": "2026-09-23",
               "samples": [{"a": "y" + "u" * (len(ids) - 1), "w": {"fried": ["Fried"]}}] * 3}
        (self.root / t.PINS).write_text(json.dumps(pin) + "\n")
        (self.root / t.OUT).write_text(t.render(t.derive(self.root)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_derived_tags_pass(self):
        self.assertEqual(t.check_item_tags(self.root), [])
        doc = json.loads((self.root / t.OUT).read_text())
        self.assertEqual(doc["rows"][0]["tags"]["fried"], {"answer": "yes", "agree": 3, "words": ["Fried"]})

    def test_a_yes_without_the_items_words_is_rejected(self):
        doc = json.loads((self.root / t.OUT).read_text())
        doc["rows"][0]["tags"]["nuts"] = {"answer": "yes", "agree": 3, "words": ["walnut"]}
        (self.root / t.OUT).write_text(json.dumps(doc))
        self.assertTrue(any("nuts: yes without" in p for p in t.check_item_tags(self.root)))

    def test_an_item_neither_tagged_nor_listed_is_rejected(self):
        doc = json.loads((self.root / t.OUT).read_text())
        doc["rows"] = []
        (self.root / t.OUT).write_text(json.dumps(doc))
        self.assertTrue(any("neither tagged" in p for p in t.check_item_tags(self.root)))

    def test_a_new_basis_leaves_items_untagged_not_guessed(self):
        b = json.loads((self.root / "spine/bindings.json").read_text())
        b["bindings"]["item-attributes"]["samples"] = 5
        (self.root / "spine/bindings.json").write_text(json.dumps(b))
        doc = t.derive(self.root)
        self.assertEqual((len(doc["rows"]), len(doc["untagged"])), (0, 1))


if __name__ == "__main__":
    unittest.main()


class Verbatim(unittest.TestCase):
    def test_pins_keep_only_the_items_words(self):
        s = t.verbatim({"a": "yn", "w": {"fried": ["Fried", "battered"], "nuts": ["walnut"]}}, "Item: Fried Calamari")
        self.assertEqual(s, {"a": "yn", "w": {"fried": ["Fried"]}})
