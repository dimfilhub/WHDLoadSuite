"""The Browser tab's row colours come from the same build_state as the Builder tab's."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from common import gamepaths
from tabs.browser.tab import BrowserTab


class RowStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.folders = (self.work, self.work / "Whdload", self.work / "Executables")

    def tags(self, name, ticked=()):
        game = SimpleNamespace(path=Path(f"/dl/{name}.lha"))
        return BrowserTab._state(game, self.folders, ticked)

    def test_orange_green_and_nothing(self):
        self.assertEqual(self.tags("RocketAttack_v1.0"), ("needs_prep",))
        self.assertEqual(self.tags("Rockford_v1.0"), ())
        gamepaths.drive_path("RocketAttack_v1.0", self.work).mkdir(parents=True)
        gamepaths.drive_path("Rockford_v1.0", self.work).mkdir(parents=True)
        self.assertEqual(self.tags("RocketAttack_v1.0"), ("prepared",))
        self.assertEqual(self.tags("Rockford_v1.0"), ())                # a drive it does not need is not shown

    def test_blue_when_built_and_gold_when_ticked_in_the_builder(self):
        exe = gamepaths.executable_path("RocketAttack_v1.0", self.work, self.folders[2])
        exe.parent.mkdir(parents=True)
        exe.mkdir() if exe.suffix == ".app" else exe.write_text("x")
        self.assertEqual(self.tags("RocketAttack_v1.0"), ("executable",))
        self.assertEqual(self.tags("RocketAttack_v1.0", ticked={Path("/dl/RocketAttack_v1.0.lha")}), ("ticked",))

    def test_no_folders_means_no_colour(self):
        game = SimpleNamespace(path=Path("/dl/RocketAttack_v1.0.lha"))
        self.assertEqual(BrowserTab._state(game, None, ()), ())


if __name__ == "__main__":
    unittest.main()
