import tempfile
import unittest
from pathlib import Path

from tabs.hdcommander import HdfVolume
from tabs.hdcommander.installer import install, INSTALLED, SKIPPED, FAILED
from tests.helpers import make_lha


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.vol = HdfVolume.create(str(self.dir / "t.hdf"), 8)
        self.addCleanup(self.vol.close)

    def archive(self, name, files):
        p = self.dir / name
        p.write_bytes(make_lha(files))
        return p

    def test_install_game_folder_and_icon(self):
        a = self.archive("Alien_v1.0.lha", {"Alien/Alien.slave": b"S" * 3000,
                                              "Alien/data": b"D" * 5000, "Alien.info": b"I" * 100})
        seen = []
        res = install(self.vol, a, lambda d, t, p: seen.append((d, t)))
        self.assertEqual((res.status, res.folder, res.files), (INSTALLED, "Games/A/Alien", 3))
        self.assertEqual(self.vol.read("Games/A/Alien/Alien.slave"), b"S" * 3000)
        self.assertEqual(self.vol.read("Games/A/Alien.info"), b"I" * 100)
        self.assertEqual(seen[-1][0], seen[-1][1])

    def test_skip_and_overwrite(self):
        a = self.archive("Zork.lha", {"Zork/Zork.slave": b"1"})
        self.assertEqual(install(self.vol, a).status, INSTALLED)
        self.assertEqual(install(self.vol, a).status, SKIPPED)
        self.assertEqual(install(self.vol, a, overwrite=True).status, INSTALLED)

    def test_digit_group_and_slave_at_root(self):
        a = self.archive("1942_v1.0.lha", {"1942.slave": b"x", "readme": b"y"})
        res = install(self.vol, a)
        self.assertEqual(res.folder, "Games/0-9/1942_v1.0")
        self.assertEqual(self.vol.read("Games/0-9/1942_v1.0/readme"), b"y")

    def test_failures_leave_image_clean(self):
        for files in ({"Foo/Foo.slave": b"x", "Foo/" + "n" * 31: b"x"},   # name too long
                      {"Foo/Foo.slave": b"x", "Foo/A": b"1", "Foo/a": b"2"},   # case clash
                      {"Foo/Foo.slave": b"x" * (9 * 1024 * 1024)}):       # too big
            res = install(self.vol, self.archive("Foo.lha", files))
            self.assertEqual(res.status, FAILED, files.keys())
            self.assertFalse(self.vol.exists("Games/F/Foo"))

    def test_archive_without_slave_is_not_a_game(self):
        res = install(self.vol, self.archive("Docs.lha", {"Docs/readme": b"x"}))
        self.assertEqual(res.status, "not_whdload")
        self.assertFalse(self.vol.exists("Games"))

    def test_corrupt_archive(self):
        p = self.archive("Bad.lha", {"Bad/Bad.slave": b"abc"})
        raw = bytearray(p.read_bytes())
        raw[-3] ^= 0xFF           # damage the data -> CRC mismatch
        p.write_bytes(bytes(raw))
        self.assertEqual(install(self.vol, p).status, FAILED)


if __name__ == "__main__":
    unittest.main()
