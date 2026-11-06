import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from tabs.hdcommander import HdfVolume, betterwb
from tests.helpers import make_adf


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class BetterWbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        zips = {
            "misc3.1": ("Misc3.1", "BetterWB1.zip", {"S/Startup-Sequence": b"better", "S/Startup-Envhandler": b"env",
                                                       "C/Info": b"newinfo", "Libs/icon.library": b"v46"}),
            "tools3.1": ("Tools3.1", "BetterWB2.zip", {"Tools/Extra": b"tool"}),
            "icons3.1": ("Icons3.1", "BetterWB5.zip", {"Prefs.info": b"icon"}),
        }
        self.disks = self.dir / "Disks"
        self.disks.mkdir()
        for vol, (label, name, files) in zips.items():
            content = {name: _zip(files)}
            if vol == "misc3.1":
                content["BetterWB.readme.txt"] = b"readme"
            make_adf(self.disks / f"{label}.adf", label, content)
        (self.disks / "Other.adf").write_bytes(b"not a disk")
        self.vol = HdfVolume.create(str(self.dir / "t.hdf"), 8)
        self.addCleanup(self.vol.close)
        for folder in ("C", "Libs", "S", "Tools", "System"):
            self.vol.makedirs(folder)
        self.vol.put_bytes(b"floppy startup", "S/Startup-Sequence")
        self.vol.put_bytes(b"copy", "C/Copy")
        self.vol.put_bytes(b"calc", "Tools/calculator")
        self.found = betterwb.find_disks(self.disks)

    def test_finds_disks_by_volume_name(self):
        self.assertEqual(sorted(self.found), ["icons3.1", "misc3.1", "tools3.1"])
        self.assertEqual(betterwb.missing(self.found), ((), ("Bonus3.1", "Docs3.1", "Drivers3.1")))

    def test_installs_zips_readme_and_cleans_up(self):
        items = betterwb.install_betterwb(self.vol, self.found)
        self.assertTrue(all(i.status != "failed" for i in items), [(i.name, i.message) for i in items])
        self.assertEqual(self.vol.read("Libs/icon.library"), b"v46")
        self.assertEqual(self.vol.read("Tools/Extra"), b"tool")
        self.assertEqual(self.vol.read("Locale/Help/BetterWB.readme.txt"), b"readme")
        self.assertEqual(self.vol.read("S/Startup-Sequence"), b"better")
        self.assertEqual(self.vol.read("S/Startup-Sequence.old"), b"floppy startup")
        self.assertFalse(self.vol.exists("Tools/calculator"))
        self.assertTrue({e.name: e for e in self.vol.listdir("C")}["Copy"].protect & betterwb.PURE)

    def test_env_handler_startup_is_optional(self):
        betterwb.install_betterwb(self.vol, self.found, env_handler=True)
        self.assertEqual(self.vol.read("S/Startup-Sequence"), b"env")

    def test_needs_workbench_first(self):
        self.vol.delete("S/Startup-Sequence")
        items = betterwb.install_betterwb(self.vol, self.found)
        self.assertEqual([i.status for i in items], ["failed"])
        self.assertIn("Make bootable", items[0].message)

    def test_missing_required_disk_changes_nothing(self):
        found = {k: v for k, v in self.found.items() if k != "misc3.1"}
        items = betterwb.install_betterwb(self.vol, found)
        self.assertEqual([i.status for i in items], ["failed"])
        self.assertFalse(self.vol.exists("Libs/icon.library"))

    def test_reinstalling_is_safe(self):
        betterwb.install_betterwb(self.vol, self.found)
        items = betterwb.install_betterwb(self.vol, self.found)
        self.assertTrue(all(i.status != "failed" for i in items))
        self.assertEqual(self.vol.read("S/Startup-Sequence.old"), b"floppy startup")

    def test_not_enough_space(self):
        small = HdfVolume.create(str(self.dir / "s.hdf"), 1)
        self.addCleanup(small.close)
        for folder in ("C", "Libs", "S"):
            small.makedirs(folder)
        small.put_bytes(b"x", "S/Startup-Sequence")
        big = {"misc3.1": self.found["misc3.1"]}
        make_adf(self.dir / "Big.adf", "Misc3.1", {"BetterWB1.zip": _zip({"Libs/big": bytes(2_000_000)})})
        big["misc3.1"] = self.dir / "Big.adf"
        items = betterwb.install_betterwb(small, big)
        self.assertEqual(items[0].status, "failed")
        self.assertIn("free space", items[0].message)


if __name__ == "__main__":
    unittest.main()
