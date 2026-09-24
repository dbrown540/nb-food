import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from packages import package_facts  # noqa: E402


class PackageFacts(unittest.TestCase):
    def test_weight_volume_each_count(self):
        self.assertEqual(package_facts("1 Lb"), {"sold_by": "weight", "package_g": 453.6, "package_ml": None, "units": None})
        self.assertEqual(package_facts("16 Oz")["package_g"], 453.6)
        self.assertEqual(package_facts("16 Fl Oz"), {"sold_by": "volume", "package_g": None, "package_ml": 473.2, "units": None})
        self.assertEqual(package_facts("1 Pint")["package_ml"], 473.2)
        self.assertEqual(package_facts("1 Each"), {"sold_by": "each", "package_g": None, "package_ml": None, "units": 1})
        self.assertEqual(package_facts("1 Doz")["units"], 12)
        self.assertEqual(package_facts("20 Bag"), {"sold_by": "count", "package_g": None, "package_ml": None, "units": 20})

    def test_unknown_size_says_nothing(self):
        self.assertEqual(package_facts("assorted"), {"sold_by": None, "package_g": None, "package_ml": None, "units": None})


if __name__ == "__main__":
    unittest.main()
