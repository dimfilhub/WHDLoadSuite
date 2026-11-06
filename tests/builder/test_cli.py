"""The Builder tab's command line (builder.py): prepare games from .lha archives."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.amiberry.fake import make_fake, requires_posix
from tests.helpers import make_lha

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, str(ROOT / "builder.py"), *args],
                          capture_output=True, text=True, timeout=120, cwd=ROOT, env=env)


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / "Template_WHDLoad" / "S").mkdir(parents=True)
        (self.work / "Template_WHDLoad" / "C").mkdir()
        (self.work / "Template_WHDLoad" / "C" / "WHDLoad").write_bytes(b"whdload")
        (self.work / "Template_WHDLoad" / "S" / "Startup-Sequence").write_text("cd SYS:Old\nWHDLoad Old.slave PRELOAD\n")
        (self.work / "downloads").mkdir()
        (self.work / "downloads" / "Alien_v1.0.lha").write_bytes(make_lha({"Alien/Alien.slave": b"S" * 50, "Alien/data": b"D"}))

    def test_bundle_passes_the_launch_screen_choices_and_the_picture_on(self):
        from unittest import mock
        from common import amiberry
        from tabs.builder import core
        calls = []

        def fake_create(archive, work_dir, **kw):
            calls.append(kw)
            return Path("/out/Alien_v1.0.app")

        with mock.patch.object(core, "load_launch_screen", return_value=(True, "/gb", "cover")), \
                mock.patch.object(core.gamebase, "find_image", return_value=(Path("/gb/a.jpg"), "cover")) as find, \
                mock.patch.object(amiberry, "find", return_value=Path("/x/Amiberry")):
            self.assertEqual(core.bundle_games(["Alien"], self.work, create=fake_create), 0)
        find.assert_called_once_with("/gb", "Alien_v1.0", "cover")
        self.assertEqual((calls[0]["launch_screen"], calls[0]["picture"]), (True, (Path("/gb/a.jpg"), "cover")))
        calls.clear()
        with mock.patch.object(core, "load_launch_screen", return_value=(False, "/gb", "best")), \
                mock.patch.object(core.gamebase, "find_image") as find, \
                mock.patch.object(amiberry, "find", return_value=Path("/x/Amiberry")):
            core.bundle_games(["Alien"], self.work, create=fake_create)
        find.assert_not_called()
        self.assertEqual((calls[0]["launch_screen"], calls[0]["picture"]), (False, None))

    def test_help(self):
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--work-dir", result.stdout)

    def test_prepares_a_game_and_skips_it_the_second_time(self):
        result = run_cli("Alien", "--work-dir", str(self.work))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        drive = self.work / "Whdload" / "A" / "Alien_v1.0"
        self.assertEqual((drive / "Alien" / "Alien.slave").read_bytes(), b"S" * 50)
        self.assertEqual((drive / "C" / "WHDLoad").read_bytes(), b"whdload")             # template copied
        self.assertEqual((drive / "S" / "Startup-Sequence").read_text(), "cd SYS:Alien\nWHDLoad Alien.slave PRELOAD\n")
        self.assertFalse((self.work / "Configurations").exists())                       # no emulator config any more
        again = run_cli("Alien", "--work-dir", str(self.work))
        self.assertIn("skipped", again.stdout)
        forced = run_cli("Alien", "--work-dir", str(self.work), "--force")
        self.assertIn("ok:", forced.stdout)

    def test_nothing_to_do(self):
        (self.work / "downloads" / "Alien_v1.0.lha").unlink()
        result = run_cli("--work-dir", str(self.work))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no .lha archives", result.stderr)

    def isolated_env(self, home):
        """A user home of its own, so a test launch never touches the real Amiberry folder."""
        return {**os.environ, "HOME": str(home), "XDG_DATA_HOME": str(home), "APPDATA": str(home),
                "FAKE_ARGS": str(home / "args.txt")}

    def test_bundle_needs_a_game_name_and_a_known_one(self):
        result = run_cli("--bundle", "--work-dir", str(self.work))
        self.assertEqual(result.returncode, 1)
        self.assertIn("--bundle needs", result.stderr)
        result = run_cli("--bundle", "Nothing", "--work-dir", str(self.work))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no archives match", result.stderr)

    def test_launch_needs_exactly_one_known_game(self):
        self.assertEqual(run_cli("--launch", "--work-dir", str(self.work)).returncode, 1)
        result = run_cli("--launch", "Nothing", "--work-dir", str(self.work))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no such archive", result.stderr)

    @requires_posix
    def test_launch_runs_the_archive_in_amiberry(self):
        home = self.work / "userhome"
        home.mkdir()
        fake_dir = self.work / "amiberry-folder"
        fake_dir.mkdir()
        make_fake(fake_dir)
        result = run_cli("--launch", "Alien", "--work-dir", str(self.work), "--amiberry-dir", str(fake_dir),
                         env=self.isolated_env(home))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args_file = home / "args.txt"
        deadline = time.time() + 15
        while not args_file.exists() and time.time() < deadline:   # the emulator is started, not waited for
            time.sleep(0.1)
        args = args_file.read_text().splitlines()
        self.assertEqual(args[-2], "--autoload")
        self.assertTrue(args[-1].endswith("Alien_v1.0.lha"))


if __name__ == "__main__":
    unittest.main()
