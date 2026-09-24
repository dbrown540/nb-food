import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_public import scan_text  # noqa: E402


class ScanText(unittest.TestCase):
    def test_menu_words_pass(self):
        self.assertEqual(scan_text("data/menus/x.json", "Soup of the day, tomato and basil"), [])

    def test_topic_word_fails_outside_verbatim_data(self):
        word = "work" + "out"  # assembled so this tracked file does not trip the gate itself
        self.assertEqual(len(scan_text("data/menus/x.json", f"a {word} note")), 1)

    def test_store_product_names_are_verbatim_data(self):
        word = "Nutri" + "tional Yeast"
        self.assertEqual(scan_text("data/products/x.json", word), [])
        self.assertEqual(len(scan_text("data/curated.json", word)), 1)


if __name__ == "__main__":
    unittest.main()
