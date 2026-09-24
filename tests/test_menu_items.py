import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from menu_items import with_ids, slug  # noqa: E402


def row(name, section="Mains", description="", price=9.0):
    return {"place": "Case Cafe", "kind": "menu", "section": section, "name": name, "description": description,
            "size": "", "price": price, "source": "case", "as_of": "2026-09-23", "status": "ok"}


class Ids(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slug("Bob's Crème Brûlée"), "bob-s-creme-brulee")

    def test_repeated_names_get_stable_suffixes_whatever_the_file_order(self):
        rows = [row("Soup", "Lunch", "tomato"), row("Soup", "Dinner", "onion"), row("Salad")]
        a = {r["id"]: r["section"] for r in with_ids(rows)}
        b = {r["id"]: r["section"] for r in with_ids(list(reversed(rows)))}
        self.assertEqual(a, b)
        self.assertEqual(a, {"case-cafe--soup": "Dinner", "case-cafe--soup-2": "Lunch", "case-cafe--salad": "Mains"})


if __name__ == "__main__":
    unittest.main()
