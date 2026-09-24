import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import inspections  # noqa: E402


def case(name):
    return inspections.match_case(json.loads((ROOT / f"spine/cases/inspection-match/{name}.json").read_text()))


class MatchPoi(unittest.TestCase):
    """match_poi through match_case, on the registered canonical fixtures."""

    def test_name_and_address(self):
        self.assertEqual(case("name-and-address")["confidence"], "name+address")

    def test_name_and_building(self):
        self.assertEqual(case("name-and-building")["confidence"], "name-only")

    def test_far_namesake_is_none(self):
        self.assertEqual(case("far-namesake"), {"confidence": "none", "matched": []})

    def test_thresholds_are_bindings(self):
        b = json.loads((ROOT / "spine/bindings.json").read_text())["bindings"]["inspection-match"]
        self.assertEqual(inspections.SAME_M, b["sameBuildingM"])
        self.assertEqual(inspections.NB_ZIPS, set(b["areaZips"]))


if __name__ == "__main__":
    unittest.main()
