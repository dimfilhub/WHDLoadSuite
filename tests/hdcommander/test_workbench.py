import tempfile
import unittest
from pathlib import Path

from tabs.hdcommander import HdfVolume, workbench
from tests.helpers import make_adf, workbench_disks


class WorkbenchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.floppies = workbench_disks(self.dir / "Floppies") if (self.dir / "Floppies").mkdir() is None else None
        self.vol = HdfVolume.create(str(self.dir / "t.hdf"), 8)
        self.addCleanup(self.vol.close)
        self.disks = workbench.find_disks(self.floppies)

    def install(self, **kw):
        return workbench.install_workbench(self.vol, self.disks.found, **kw)

    def statuses(self, items):
        return {i.name: i.status for i in items}

    # ----- finding the disks -----

    def test_find_disks_by_volume_name(self):
        self.assertTrue(self.disks.usable)
        self.assertEqual(sorted(self.disks.found), ["extras", "fonts", "install", "locale", "storage", "workbench"])
        self.assertEqual(self.disks.found["workbench"].name, "Workbench.adf")
        self.assertEqual((self.disks.missing_required, self.disks.missing_optional, self.disks.others), ([], [], []))

    def test_find_disks_reports_missing_and_foreign_disks(self):
        (self.floppies / "Install.adf").unlink()
        (self.floppies / "Fonts.adf").unlink()
        make_adf(self.floppies / "Game.adf", "Some Game", {"x": b"y"})
        (self.floppies / "notes.txt").write_text("not a disk")
        found = workbench.find_disks(self.floppies)
        self.assertFalse(found.usable)
        self.assertEqual(found.missing_required, ["Install3.1"])
        self.assertEqual(found.missing_optional, ["Fonts"])
        self.assertEqual(found.others, ["Game.adf (Some Game)"])
        self.assertFalse(workbench.find_disks(self.dir / "nothing here").usable)

    def test_find_disks_looks_one_folder_down(self):
        outer = self.dir / "outer"
        outer.mkdir()
        (self.floppies).rename(outer / "Floppies")
        self.assertTrue(workbench.find_disks(outer).usable)

    # ----- installing -----

    def test_installs_every_disk_where_the_installer_puts_it(self):
        items = self.install()
        self.assertTrue(all(i.status == "ok" for i in items), items)
        v = self.vol
        self.assertEqual(v.read("C/Copy"), b"copy")
        self.assertEqual(v.read("Tools/Calculator"), b"calc")                       # Extras merged into the root
        self.assertEqual(v.read("Locale/Catalogs/deutsch/Sys/workbench.catalog"), b"cat")
        self.assertEqual(v.read("Locale/Countries/germany.country"), b"de")
        self.assertFalse(v.exists("Locale/Disk.info"))                              # the disk icon is not copied
        self.assertEqual(v.read("Fonts/topaz.font"), b"topaz")
        self.assertEqual(v.read("Fonts/topaz/8"), b"8")
        self.assertEqual(v.read("Storage/DOSDrivers/RAD"), b"rad")
        self.assertEqual(v.read("Storage/Monitors/NTSC"), b"ntsc driver")
        self.assertEqual(v.read("Storage/DataTypes.info"), b"dt icon")              # root icons of Storage
        self.assertEqual(v.read("Devs/Keymaps/usa1"), b"usa1")                      # printers and keymaps are active
        self.assertEqual(v.read("Tools/HDToolBox"), b"hdtoolbox")                   # (hd|bru)# only
        self.assertEqual(v.read("Tools/BRU"), b"bru")
        self.assertFalse(v.exists("Tools/drive definitions"))
        self.assertEqual(v.read("S/BRUtab"), b"brutab")
        self.assertEqual(v.read("Libs/68040.library"), b"68040")
        for folder in ("Prefs/Env-Archive/Sys", "Classes/Gadgets", "Devs/DataTypes", "Storage/Printers", "WBStartup"):
            self.assertTrue(v.isdir(folder), folder)

    def test_later_disks_overwrite_earlier_ones_like_the_installer(self):
        self.install()
        v = self.vol
        self.assertEqual(v.read("L/aux-handler"), b"new handler")                   # Extras over Workbench
        self.assertEqual(v.read("Prefs.info"), b"extras prefs icon")
        self.assertEqual(v.read("Disk.info"), b"hard disk icon")                    # Install's Update/Disk.info last
        self.assertEqual(v.read("Devs/Printers/EpsonQ"), b"epson driver")           # real driver over the 0-byte stub
        self.assertEqual(v.read("C/SetPatch"), b"setpatch")                         # Install's C/ is not copied

    def test_hard_disk_startup_replaces_the_floppy_one_and_attributes_are_kept(self):
        self.install()
        self.assertEqual(self.vol.read("S/Startup-Sequence"), b"; hard drive startup\n")
        self.assertEqual(self.vol.meta("S/Startup-Sequence").protect, 0x40)
        self.assertEqual(self.vol.meta("C/Copy").protect, 0x10)

    def test_pal_or_ntsc_monitor_becomes_active(self):
        self.install()
        self.assertEqual(self.vol.read("Devs/Monitors/PAL"), b"pal driver")
        self.assertEqual(self.vol.read("Devs/Monitors/PAL.info"), b"pal icon")
        self.assertFalse(self.vol.exists("Storage/Monitors/PAL"))                   # moved, not copied
        self.assertFalse(self.vol.exists("Devs/Monitors/NTSC"))
        other = HdfVolume.create(str(self.dir / "n.hdf"), 8)
        self.addCleanup(other.close)
        workbench.install_workbench(other, self.disks.found, region="NTSC")
        self.assertEqual(other.read("Devs/Monitors/NTSC"), b"ntsc driver")
        self.assertTrue(other.exists("Storage/Monitors/PAL"))

    def test_optional_disks_can_be_left_out(self):
        items = self.install(include=("extras",))
        names = self.statuses(items)
        self.assertEqual((names["Locale"], names["Fonts"], names["Storage3.1"]), ("skipped",) * 3)
        self.assertTrue(self.vol.exists("Tools/Calculator"))
        self.assertFalse(self.vol.exists("Fonts/topaz.font"))
        self.assertFalse(self.vol.exists("Devs/Monitors/PAL"))                      # no Storage disk: no monitor move
        self.assertTrue(self.vol.exists("S/Startup-Sequence"))                      # the system itself is still complete

    def test_progress_is_reported(self):
        seen = []
        self.install(progress=lambda fraction, text: seen.append(fraction))
        self.assertTrue(seen and seen[0] == 0 and seen == sorted(seen) and seen[-1] < 1)

    # ----- refusing and failing safely -----

    def test_missing_required_disks_fail_without_touching_the_image(self):
        items = workbench.install_workbench(self.vol, {"extras": self.disks.found["extras"]})
        self.assertEqual([i.status for i in items], ["failed"])
        self.assertIn("Workbench3.1", items[0].message)
        self.assertEqual(self.vol.listdir(""), [])

    def test_existing_startup_script_needs_permission_and_is_kept_as_old(self):
        self.vol.makedirs("S")
        self.vol.put_bytes(b"; my own startup\n", "S/Startup-Sequence")
        items = self.install()
        self.assertEqual(items[0].status, "failed")
        self.assertEqual(self.vol.read("S/Startup-Sequence"), b"; my own startup\n")
        self.assertFalse(self.vol.exists("C"))                                       # nothing was copied
        items = self.install(replace_startup=True)
        self.assertTrue(all(i.status == "ok" for i in items), items)
        self.assertEqual(self.vol.read("S/Startup-Sequence"), b"; hard drive startup\n")
        self.assertEqual(self.vol.read("S/Startup-Sequence.old"), b"; my own startup\n")

    def test_not_enough_space(self):
        # a floppy holds under 880 KB, so the two big files come from two disks
        make_adf(self.floppies / "Workbench.adf", "Workbench3.1", {"C/Big": b"x" * 800_000, "S/Startup-Sequence": b"x"})
        make_adf(self.floppies / "Fonts.adf", "Fonts", {"big.font": b"y" * 800_000})
        small = HdfVolume.create(str(self.dir / "small.hdf"), 1)
        self.addCleanup(small.close)
        items = workbench.install_workbench(small, workbench.find_disks(self.floppies).found)
        self.assertEqual(items[0].status, "failed")
        self.assertIn("not enough free space", items[0].message)
        self.assertEqual(small.listdir(""), [])

    def test_reinstalling_is_safe(self):
        self.install()
        again = self.install(replace_startup=True)
        self.assertTrue(all(i.status in ("ok", "skipped") for i in again), again)
        self.assertEqual(self.vol.read("C/Copy"), b"copy")
        self.assertEqual(self.vol.read("Devs/Monitors/PAL"), b"pal driver")
        self.assertFalse(self.vol.exists("Storage/Monitors/PAL"))


if __name__ == "__main__":
    unittest.main()
