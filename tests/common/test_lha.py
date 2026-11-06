import tempfile
import unittest
from pathlib import Path

from common import lha
from tests.helpers import make_lha


class LhaTest(unittest.TestCase):
    def test_extract_writes_nested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "a.lha"
            archive.write_bytes(make_lha({"Game/Game.slave": b"slave", "Game/data/level1": b"L" * 5000}))
            out = Path(tmp) / "out"
            written = lha.extract(archive, out)
            self.assertEqual(sorted(written), ["Game/Game.slave", "Game/data/level1"])
            self.assertEqual((out / "Game" / "data" / "level1").read_bytes(), b"L" * 5000)

    def test_iter_files_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "a.lha"
            data = bytearray(make_lha({"f": b"hello"}))
            archive.write_bytes(bytes(data))
            self.assertEqual(list(lha.iter_files(archive)), [("f", b"hello")])
            data[-3] ^= 0xFF
            archive.write_bytes(bytes(data))
            with self.assertRaises(lha.LhaError):
                list(lha.iter_files(archive))


if __name__ == "__main__":
    unittest.main()
