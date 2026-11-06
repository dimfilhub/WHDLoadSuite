import gzip
import tempfile
import unittest
from pathlib import Path

from tabs.hdcommander.adf import AdfDisk
from tabs.hdcommander.volume import HdfError
from tests.helpers import make_adf


class AdfDiskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "disk.adf"
        make_adf(self.path, "Workbench3.1", {"S/Startup-Sequence": (b"; hello\n", 0x40),
                                             "C/Copy": b"copy" * 500, "Disk.info": b"icon"})

    def test_volume_name_entries_and_contents(self):
        with AdfDisk(self.path) as disk:
            self.assertEqual(disk.name, "Workbench3.1")
            by_path = {e.path: e for e in disk.entries()}
            self.assertEqual(sorted(by_path), ["C", "C/Copy", "Disk.info", "S", "S/Startup-Sequence"])
            self.assertTrue(by_path["C"].is_dir and not by_path["C/Copy"].is_dir)
            self.assertEqual(by_path["C/Copy"].size, 2000)
            self.assertEqual(disk.read(by_path["C/Copy"]), b"copy" * 500)
            self.assertEqual(disk.meta(by_path["S/Startup-Sequence"]).protect, 0x40)     # attributes are readable

    def test_adz_is_a_gzipped_adf(self):
        adz = self.dir / "disk.adz"
        adz.write_bytes(gzip.compress(self.path.read_bytes()))
        with AdfDisk(adz) as disk:
            self.assertEqual(disk.name, "Workbench3.1")
            self.assertEqual(len(disk.entries()), 5)
            temp = disk._temp
        self.assertFalse(Path(temp).exists())                       # the unpacked copy is removed on close

    def test_unsupported_and_broken_files(self):
        for name, content in (("a.dms", b"DMS!"), ("junk.adf", b"x" * 901120), ("small.adf", b"x" * 10)):
            path = self.dir / name
            path.write_bytes(content)
            with self.assertRaises(HdfError, msg=name):
                AdfDisk(path)
        big = self.dir / "big.adf"
        big.write_bytes(b"\0" * 2_000_000)
        with self.assertRaises(HdfError):
            AdfDisk(big)


if __name__ == "__main__":
    unittest.main()
