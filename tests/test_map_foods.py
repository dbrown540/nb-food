import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import map_foods as m  # noqa: E402
from usda import check_usda_cache, record_problems  # noqa: E402


class RouteMapping(unittest.TestCase):
    def test_all_readings_on_one_record(self):
        self.assertEqual(m.route_mapping([("c2", "p1")] * 3, 16, 3, 2), (2, 1, 3, ""))

    def test_below_the_bar_is_unmapped(self):
        k, _, _, reason = m.route_mapping([("c2", "p1"), ("c2", "p1"), ("none", "none")], 16, 3, 2)
        self.assertIsNone(k)
        self.assertEqual(reason, "readings do not agree on one record")

    def test_all_none(self):
        self.assertEqual(m.route_mapping([("none", "none")] * 3, 16, 3, 2), (None, None, 3, "no candidate is the same food"))

    def test_off_list_and_refused_readings_count_for_nothing(self):
        self.assertIsNone(m.route_mapping([("c99", "p1"), ("refused", "none"), ("c1", "p1")], 16, 3, 2)[0])

    def test_portion_needs_its_own_agreement(self):
        self.assertEqual(m.route_mapping([("c1", "p1"), ("c1", "p2"), ("c1", "none")], 16, 3, 2)[1], None)


class KindOf(unittest.TestCase):
    def test_kind_follows_what_the_record_is_not_which_list_it_is_on(self):
        dishes = ["Pizza"]
        self.assertEqual(m.kind_of({"dataType": "Survey (FNDDS)", "category": "Dried fruits"}, dishes), "usda-single-food")
        self.assertEqual(m.kind_of({"dataType": "Survey (FNDDS)", "category": "Pizza"}, dishes), "usda-mixed-dish-estimate")
        self.assertEqual(m.kind_of({"dataType": "SR Legacy", "category": "Pizza"}, dishes), "usda-single-food")


class PackageGrams(unittest.TestCase):
    def test_mass_units_convert_and_others_do_not(self):
        self.assertEqual(m.package_grams("16 Oz"), 453.6)
        self.assertEqual(m.package_grams("1 Lb"), 453.6)
        self.assertIsNone(m.package_grams("16 Fl Oz"))
        self.assertIsNone(m.package_grams("1 Each"))


class CheckFoodMap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        (self.root / "spine").mkdir()
        (self.root / "spine/bindings.json").write_text(json.dumps({"bindings": {"food-mapping": {"dishCategories": ["Pizza"]}}}))
        rows = [{"id": "a", "kind": "product"}, {"id": "b", "kind": "menu"}, {"id": "c", "kind": "menu"}]
        (self.root / "data/menu_items.json").write_text(json.dumps({"rows": rows}))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rows, unread=()):
        (self.root / m.OUT).write_text(json.dumps({"rows": rows, "unread": list(unread)}))

    def test_check_food_map_accepts_each_kind(self):
        self.write([{"id": "a", "kind": "usda-single-food", "estimate": False, "fdcId": 1, "dataType": "SR Legacy"},
                    {"id": "b", "kind": "unmapped", "reason": "no candidate is the same food"}],
                   [{"id": "c", "reason": "no pinned readings"}])
        self.assertEqual(m.check_food_map(self.root), [])

    def test_check_food_map_rejects(self):
        self.write([{"id": "a", "kind": "usda-mixed-dish-estimate", "fdcId": 1, "dataType": "Survey (FNDDS)", "category": "Dried fruits"},
                    {"id": "b", "kind": "unmapped", "reason": "x", "grams": 0},
                    {"id": "z", "kind": "label", "label": "data/labels/z.json"}])
        p = m.check_food_map(self.root)
        self.assertEqual(len(p), 6, p)  # wrong group, no estimate flag, unmapped with weight, missing label, c unaccounted, z unknown


class UsdaCache(unittest.TestCase):
    def test_check_usda_cache_on_the_repo(self):
        self.assertEqual(check_usda_cache(ROOT), [])

    def test_record_problems(self):
        rec = json.loads((ROOT / "spine/cases/usda-records/whole-dated.json").read_text())["record"]
        self.assertEqual(record_problems("1.json", rec), [])
        self.assertEqual(len(record_problems("1.json", {**rec, "publicationDate": None})), 1)


if __name__ == "__main__":
    unittest.main()


class Determinism(unittest.TestCase):
    def test_candidates_do_not_depend_on_the_hash_seed(self):
        import subprocess
        code = ("import sys; sys.path.insert(0, 'scripts'); import map_foods as m, hashlib; idx = m.Index(m.ROOT); "
                "h = hashlib.sha256(); [h.update(m.message(r, idx.candidates(r), 4).encode()) for r in m.items()[:400]]; "
                "print(h.hexdigest())")
        outs = {subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                               env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}).stdout for seed in ("1", "2")}
        self.assertEqual(len(outs), 1)
