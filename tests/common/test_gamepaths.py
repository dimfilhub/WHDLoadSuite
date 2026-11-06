import tempfile
import unittest
from pathlib import Path
from unittest import mock

from common import gamepaths


class GamePathsTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(gamepaths.game_name(Path("x/Game_v1.5_2489.lha")), "Game_v1.5_2489")
        self.assertEqual(gamepaths.base_name("Game_v1.5_2489"), "Game")
        self.assertEqual(gamepaths.base_name("Game"), "Game")
        self.assertEqual(gamepaths.base_name("_v1.0"), "_v1.0")              # never an empty name

    def test_group_dir(self):
        self.assertEqual(gamepaths.group_dir("alien"), "A")
        self.assertEqual(gamepaths.group_dir("1942"), "0-9")
        self.assertEqual(gamepaths.group_dir("_x"), "#")
        self.assertEqual(gamepaths.group_dir(""), "#")

    def test_drive_path(self):
        work = Path("/w")
        self.assertEqual(gamepaths.drive_path("Alien_v1", work), work / "Whdload" / "A" / "Alien_v1")
        self.assertEqual(gamepaths.drive_path("Alien_v1", work, Path("/d")), Path("/d/A/Alien_v1"))

    def test_executable_path_depends_on_platform(self):
        work = Path("/w")
        for platform, suffix in (("darwin", ".app"), ("win32", ".exe"), ("linux", "")):
            with mock.patch.object(gamepaths.sys, "platform", platform):
                path = gamepaths.executable_path("Alien", work, Path("/e"))
            self.assertEqual(path.name, "Alien" + suffix)
            self.assertEqual(path.parent.name, "A")


if __name__ == "__main__":
    unittest.main()


class BuildStateTest(unittest.TestCase):
    """The colours of the Builder and Browser lists: only games that need a prepared drive are coloured by it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.exes = self.work / "Executables"

    def state(self, name):
        return gamepaths.build_state(name, self.work, exe_dir=self.exes)

    def make_drive(self, name):
        gamepaths.drive_path(name, self.work).mkdir(parents=True)

    def make_executable(self, name):
        path = gamepaths.executable_path(name, self.work, self.exes)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.mkdir() if path.suffix == ".app" else path.write_text("x")

    def test_a_game_that_runs_from_its_lha_has_no_colour_even_with_a_drive(self):
        self.assertEqual(self.state("Rockford_v1.0"), "")
        self.make_drive("Rockford_v1.0")
        self.assertEqual(self.state("Rockford_v1.0"), "")

    def test_a_drive_game_is_orange_until_it_is_prepared_then_green(self):
        self.assertEqual(self.state("RocketAttack_v1.0"), "needs_prep")
        self.make_drive("RocketAttack_v1.0")
        self.assertEqual(self.state("RocketAttack_v1.0"), "prepared")

    def test_icon_is_the_app_icon_unless_the_game_has_its_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "Icons").mkdir()
            (work / "Icons" / "default.png").write_bytes(b"d")
            app = work / "app.png"
            app.write_bytes(b"a")
            with mock.patch.object(gamepaths, "APP_ICON", app):
                self.assertEqual(gamepaths.find_icon("Game_v1.0", work), app)     # beats Icons/default
                (work / "Icons" / "Game.png").write_bytes(b"g")
                self.assertEqual(gamepaths.find_icon("Game_v1.0", work), work / "Icons" / "Game.png")
            with mock.patch.object(gamepaths, "APP_ICON", work / "missing.png"):
                self.assertEqual(gamepaths.find_icon("Other_v1.0", work), work / "Icons" / "default.png")

    def test_a_built_executable_is_blue_for_every_kind_of_game(self):
        self.make_executable("RocketAttack_v1.0")
        self.make_executable("Rockford_v1.0")
        self.assertEqual(self.state("RocketAttack_v1.0"), "executable")       # with no drive left, still blue
        self.make_drive("RocketAttack_v1.0")
        self.assertEqual(self.state("RocketAttack_v1.0"), "executable")
        self.assertEqual(self.state("Rockford_v1.0"), "executable")

