import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import usda_nutrients as u  # noqa: E402

FIELDS = {"energy_kcal": [1008, 2047, 2048], "sugars_g": [2000, 1063], "carbohydrate_g": [1005]}


class NutrientRow(unittest.TestCase):
    def test_first_id_the_record_carries_wins_and_absent_is_null(self):
        food = {"fdcId": 1, "dataType": "Foundation", "description": "case"}
        r = u.nutrient_row(food, {2048: "40", 2047: "38.5", 1063: "2"}, FIELDS)
        self.assertEqual(r["per_100g"], {"energy_kcal": 38.5, "sugars_g": 2.0, "carbohydrate_g": None})
        self.assertEqual(r["nutrient_ids"], {"energy_kcal": 2047, "sugars_g": 1063, "carbohydrate_g": None})

    def test_a_reported_zero_stays_zero(self):
        r = u.nutrient_row({"fdcId": 1, "dataType": "SR Legacy", "description": "c"}, {1005: "0"}, FIELDS)
        self.assertEqual(r["per_100g"]["carbohydrate_g"], 0.0)


class SurveyNumbers(unittest.TestCase):
    """The survey release writes nutrient numbers (208) where the others write ids (1008)."""

    def test_numbers_map_to_ids_and_shared_numbers_take_the_first_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            bulk = Path(tmp)
            for rel, (bulk_type, _) in u.RELEASES.items():
                d = bulk / rel / "csv"
                d.mkdir(parents=True)
                survey = bulk_type == "survey_fndds_food"
                w = lambda name, head, rows: csv.writer(open(d / name, "w", newline="")).writerows([head] + rows)
                w("nutrient.csv", ["id", "name", "unit_name", "nutrient_nbr"],
                  [["1008", "Energy", "KCAL", "208"], ["2000", "Total Sugars", "G", "269"],
                   ["1063", "Sugars, Total NLEA", "G", "269"], ["1005", "Carbohydrate", "G", "205"],
                   ["1050", "Carbohydrate, by summation", "G", "205"]])
                w("food.csv", ["fdc_id", "data_type", "description"], [["7", bulk_type, "case food"]] if survey else [])
                w("food_nutrient.csv", ["id", "fdc_id", "nutrient_id", "amount"],
                  [["1", "7", "208", "150"], ["2", "7", "269", "4.5"], ["3", "7", "205", "20"]] if survey else [])
            old = u.BULK
            u.BULK = bulk
            try:
                foods, amounts, _ = u.read_bulk({7}, FIELDS)
            finally:
                u.BULK = old
        self.assertEqual(amounts[7], {1008: "150", 2000: "4.5", 1005: "20"})


class CheckNutrients(unittest.TestCase):
    def test_check_nutrients_on_the_repo(self):
        notes = []
        self.assertEqual(u.check_nutrients(u.ROOT, notes), [])

    def test_bounds(self):
        b = {"per_field": {"fat_g": [0, 100]}, "sum_fields": ["protein_g", "fat_g"], "sum_max": 105}
        self.assertEqual(u.bounds_problems({"fdcId": 1, "per_100g": {"protein_g": 20, "fat_g": 50}}, b), [])
        self.assertEqual(len(u.bounds_problems({"fdcId": 1, "per_100g": {"protein_g": 20, "fat_g": 101}}, b)), 2)

    def test_printed_precision(self):
        self.assertGreaterEqual(u.printed_precision(1.63), abs(1.626 - 1.63))
        self.assertGreaterEqual(u.printed_precision(1620.0), abs(1625 - 1620))
        self.assertLess(u.printed_precision(22.5), abs(22.6 - 22.5))


if __name__ == "__main__":
    unittest.main()
