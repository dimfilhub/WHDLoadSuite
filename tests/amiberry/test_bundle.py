import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tabs.builder import bundle
from tests.amiberry.fake import write_db


class StageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = self.root / "Amiberry.app" / "Contents" / "MacOS" / "Amiberry"
        self.exe.parent.mkdir(parents=True)
        self.exe.write_text("x")
        self.home = self.root / "home"
        write_db(self.home, [])
        (self.home / "WHDBoot" / "WHDLoad").write_text("w")
        (self.home / "WHDBoot" / "tmp").mkdir()
        self.kick = self.root / "Kickstarts"
        self.kick.mkdir()
        (self.kick / "Kickstart v3.1 (A1200).rom").write_bytes(b"rom31")
        (self.kick / "Kickstart v1.3.rom").write_bytes(b"rom13")
        self.archive = self.root / "Alien_v1.0.lha"
        self.archive.write_bytes(b"lha")

    def stage(self, **kw):
        staging = self.root / "stage"
        manifest = bundle.stage(self.archive, staging, self.exe, self.home, self.kick, **kw)
        return staging, manifest

    def test_autoload_bundle_holds_the_archive_under_its_own_name_whdload_and_roms(self):
        staging, m = self.stage(overrides={"Alien_v1.0": {"hardware": {"z3_ram": 16}}})
        self.assertEqual((m["mode"], m["archive"], m["hardware"]), ("autoload", "Alien_v1.0.lha", {"z3_ram": 16}))
        self.assertEqual(m["exe"], "Amiberry.app/Contents/MacOS/Amiberry")
        self.assertTrue((staging / "Alien_v1.0.lha").is_file())
        self.assertTrue((staging / "WHDBoot" / "WHDLoad").is_file())
        self.assertFalse((staging / "WHDBoot" / "tmp").exists())
        self.assertEqual(sorted(p.name for p in (staging / "ROMs").iterdir()), ["Kickstart v1.3.rom", "Kickstart v3.1 (A1200).rom"])
        self.assertEqual(json.loads((staging / "manifest.json").read_text()), m)

    def test_drive_bundle_holds_the_drive_and_the_a1200_rom_only(self):
        drive = self.root / "drive"
        (drive / "S").mkdir(parents=True)
        (drive / "S" / "Startup-Sequence").write_text("x")
        staging, m = self.stage(drive=drive, overrides={"Alien_v1.0": {"mode": "drive"}})
        self.assertEqual(m["mode"], "drive")
        self.assertTrue((staging / "game" / "S" / "Startup-Sequence").is_file())
        self.assertEqual((staging / "kick.rom").read_bytes(), b"rom31")
        self.assertFalse((staging / "WHDBoot").exists())

    def make_picture(self, size=(320, 256)):
        from PIL import Image
        path = self.root / "shot.png"
        Image.new("RGB", size, (200, 30, 30)).save(path)
        return path

    def test_a_launch_screen_puts_the_picture_in_as_a_small_png(self):
        from PIL import Image
        staging, m = self.stage(overrides={}, launch={"picture": self.make_picture(), "kind": "screenshot"})
        self.assertEqual(m["launch"], {"image": "launch.png", "kind": "screenshot"})
        with Image.open(staging / "launch.png") as image:
            self.assertEqual(image.size, (640, 512))                       # a 320x256 screenshot, doubled
        self.assertEqual(json.loads((staging / "manifest.json").read_text())["launch"], m["launch"])

    def test_a_launch_screen_without_a_picture_has_no_image(self):
        staging, m = self.stage(overrides={}, launch={"picture": None})
        self.assertEqual(m["launch"], {"image": None, "kind": ""})
        self.assertFalse((staging / "launch.png").exists())
        shutil.rmtree(staging)
        staging, m = self.stage(overrides={}, launch={"picture": self.root / "not-a-picture.png", "kind": "cover"})
        self.assertEqual(m["launch"], {"image": None, "kind": ""})          # unreadable: the same as none

    def test_without_a_launch_screen_nothing_is_added(self):
        staging, m = self.stage(overrides={})
        self.assertNotIn("launch", m)
        self.assertFalse((staging / "launch.png").exists())

    def test_clear_errors(self):
        with self.assertRaisesRegex(RuntimeError, "prepare it first"):
            self.stage(overrides={"Alien_v1.0": {"mode": "drive"}})
        (self.home / "WHDBoot" / "WHDLoad").unlink()
        with self.assertRaisesRegex(RuntimeError, "WHDLoad is not installed"):
            self.stage(overrides={})


class CreateExecutableTest(unittest.TestCase):
    """The PyInstaller command line, with PyInstaller itself replaced."""

    def test_a_launch_screen_brings_tk_along(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Amiberry.app" / "Contents" / "MacOS" / "Amiberry"
            exe.parent.mkdir(parents=True)
            exe.write_text("x")
            home = root / "home"
            write_db(home, [])
            (home / "WHDBoot" / "WHDLoad").write_text("w")
            kick = root / "Kickstarts"
            kick.mkdir()
            (kick / "k (A1200).rom").write_bytes(b"r")
            archive = root / "Alien_v1.0.lha"
            archive.write_bytes(b"lha")
            seen = {}

            def fake_run(cmd, **kw):
                seen["cmd"] = cmd
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with mock.patch.object(bundle.subprocess, "run", fake_run):
                bundle.create_executable(archive, root / "work", exe=exe, kickstarts=kick, home=home, overrides={},
                                         launch_screen=True)
            cmd = seen["cmd"]
            self.assertEqual([cmd[i + 1] for i, c in enumerate(cmd) if c == "--exclude-module"], ["PIL"])

    def test_command_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Amiberry.app" / "Contents" / "MacOS" / "Amiberry"
            exe.parent.mkdir(parents=True)
            exe.write_text("x")
            home = root / "home"
            write_db(home, [])
            (home / "WHDBoot" / "WHDLoad").write_text("w")
            kick = root / "Kickstarts"
            kick.mkdir()
            (kick / "k (A1200).rom").write_bytes(b"r")
            archive = root / "Alien_v1.0.lha"
            archive.write_bytes(b"lha")
            work = root / "work"
            (work / "Icons").mkdir(parents=True)
            seen = {}

            def fake_run(cmd, **kw):
                seen["cmd"] = cmd
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with mock.patch.object(bundle.subprocess, "run", fake_run):
                out = bundle.create_executable(archive, work, exe=exe, kickstarts=kick, home=home, overrides={})
            cmd = seen["cmd"]
            self.assertEqual(cmd[:3], [sys.executable, "-m", "PyInstaller"])
            self.assertIn("--onefile", cmd)
            self.assertEqual(cmd[cmd.index("--name") + 1], "Alien_v1.0")
            excluded = [cmd[i + 1] for i, c in enumerate(cmd) if c == "--exclude-module"]
            self.assertEqual(sorted(excluded), ["PIL", "tkinter"])           # no launch screen: no Tk, so it stays small
            self.assertTrue(Path(cmd[cmd.index("--paths") + 1]).match("*/common"))
            adds = [cmd[i + 1].rsplit(os.pathsep, 1)[1] for i, c in enumerate(cmd) if c == "--add-data"]
            self.assertIn("emulator/Amiberry.app", adds)
            for wanted in ("WHDBoot", "ROMs", "."):
                self.assertIn(wanted, adds)
            self.assertEqual(out.name, "Alien_v1.0.app" if sys.platform == "darwin" else "Alien_v1.0" + (".exe" if sys.platform == "win32" else ""))
            self.assertEqual(out.parent.name, "A")

    def test_no_emulator_is_a_clear_error(self):
        with mock.patch.object(bundle.amiberry, "find", lambda *_: None):
            with self.assertRaisesRegex(RuntimeError, "Amiberry not found"):
                bundle.create_executable(Path("x.lha"), Path("."))


if __name__ == "__main__":
    unittest.main()
