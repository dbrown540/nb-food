import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_data as cd  # noqa: E402


def write(root, rel, obj):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy(ROOT / "spine/bindings.json", self.root / "bindings.json")
        write(self.root, "spine/bindings.json", (self.root / "bindings.json").read_text())
        (self.root / "data/menus").mkdir(parents=True)
        (self.root / "data/products").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def menu(self, slug, **kw):
        doc = {"name": "Case Cafe", "addr": "", "menu_url": None, "source": "case", "as_of": "2026-09-22", "status": "ok",
               "items": [{"section": "Mains", "item": "Soup", "price": 9.0, "description": ""}]}
        doc.update(kw)
        write(self.root, f"data/menus/{slug}.json", doc)


class LayerKeys(unittest.TestCase):
    def test_check_layer_keys(self):
        places = [{"key": "A", "name": "A", "neighborhood": "North Beach"}]
        self.assertEqual(cd.check_layer_keys({"places": places, "risk": {"A": {}}, "inspections": {"_meta": {}}}), [])
        self.assertEqual(len(cd.check_layer_keys({"places": places, "risk": {}, "inspections": {"_meta": {}, "Z": {}}})), 2)


class MenuExtraction(Fixture):
    def test_check_menu_extraction(self):
        self.menu("old")  # before the basis cutoff: no basis needed
        self.assertEqual(cd.check_menu_extraction(self.root, {"Case Cafe"}), [])
        self.menu("new", as_of="2026-10-01")
        self.assertEqual(len(cd.check_menu_extraction(self.root, {"Case Cafe"})), 1)
        self.menu("new", as_of="2026-10-01", extraction={"method": "model", "model": "m", "prompt_hash": "sha256:x"})
        self.assertEqual(cd.check_menu_extraction(self.root, {"Case Cafe"}), [])
        self.assertEqual(len(cd.check_menu_extraction(self.root, {"Other"})), 2)


class Freshness(Fixture):
    def test_check_menu_freshness(self):
        self.menu("cafe")
        self.assertEqual(cd.check_menu_freshness(self.root, "2026-10-01"), ([], []))
        f, w = cd.check_menu_freshness(self.root, "2027-03-01")
        self.assertEqual((len(f), len(w)), (0, 1))
        f, w = cd.check_menu_freshness(self.root, "2027-04-01")
        self.assertEqual((len(f), len(w)), (1, 0))

    def test_extension_ruling_holds_until_its_date(self):
        self.menu("cafe")
        b = json.loads((self.root / "spine/bindings.json").read_text())
        b["rulings"].append({"id": "extend-cafe", "kind": "menu-extension", "menu": "cafe", "until": "2027-05-01"})
        write(self.root, "spine/bindings.json", b)
        self.assertEqual(len(cd.check_menu_freshness(self.root, "2027-04-01")[0]), 0)
        self.assertEqual(len(cd.check_menu_freshness(self.root, "2027-05-02")[0]), 1)

    def test_a_menu_that_was_not_found_is_not_aged(self):
        self.menu("gone", status="not_found", items=[])
        self.assertEqual(cd.check_menu_freshness(self.root, "2030-01-01"), ([], []))


class Verdicts(Fixture):
    def test_check_verdicts(self):
        write(self.root, "data/curated.json", {"overrides": {"a": {"verdict": "pick", "verified": "2026-08-31"}}, "extras": []})
        write(self.root, "data/places.json", [{"key": "A", "verdict": "pick", "verified": "2026-08-31"}])
        self.assertEqual(cd.check_verdicts(self.root, "2026-10-01"), ([], []))
        write(self.root, "data/places.json", [{"key": "B", "verdict": "pick"}])
        self.assertEqual(len(cd.check_verdicts(self.root, "2026-10-01")[0]), 1)
        write(self.root, "data/curated.json", {"overrides": {"a": {"verdict": "great"}}, "extras": []})
        self.assertEqual(len(cd.check_verdicts(self.root, "2026-10-01")[0]), 2)


class Derived(unittest.TestCase):
    def test_check_derived_on_the_repo(self):
        self.assertEqual(cd.check_derived(ROOT), [])
        self.assertTrue(cd.stale("a", "b"))


if __name__ == "__main__":
    unittest.main()
