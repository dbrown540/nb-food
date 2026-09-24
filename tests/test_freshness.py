import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from freshness import menu_age  # noqa: E402


class MenuAge(unittest.TestCase):
    def test_current_due_soon_stale(self):
        self.assertEqual(menu_age("2026-09-22", "2026-10-01", 180, 30)["status"], "current")
        self.assertEqual(menu_age("2026-09-22", "2027-02-19", 180, 30)["status"], "due-soon")  # due - warn
        self.assertEqual(menu_age("2026-09-22", "2027-03-21", 180, 30)["status"], "due-soon")  # the due day itself
        self.assertEqual(menu_age("2026-09-22", "2027-03-22", 180, 30)["status"], "stale")

    def test_due_date(self):
        self.assertEqual(menu_age("2026-09-22", "2026-09-22", 180, 30)["due"], "2027-03-21")


if __name__ == "__main__":
    unittest.main()
