import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from readings import PinWriter, sampling_basis  # noqa: E402


class Basis(unittest.TestCase):
    def test_transport_is_part_of_the_basis(self):
        api = {"samples": 3, "effort": "low", "thinking": "disabled", "maxTokens": 64}
        cli = {**api, "transport": "cli"}
        self.assertNotEqual(sampling_basis(api), sampling_basis(cli))
        self.assertEqual(sampling_basis(cli)["transport"], "claude-code-cli")


class Pins(unittest.TestCase):
    def test_writer_keeps_what_was_read_before_an_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pins.jsonl"
            load = lambda: {(json.loads(l)["key"], json.loads(l)["basis"]): json.loads(l)
                            for l in (path.read_text().splitlines() if path.exists() else []) if l}
            w = PinWriter(path, load, 2)
            w.add({"key": "a", "basis": "b"})
            self.assertFalse(path.exists())
            w.add({"key": "c", "basis": "b"})
            self.assertEqual(len(load()), 2)  # flushed at the second pin, before any close


if __name__ == "__main__":
    unittest.main()
