import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tabs.builder import core
from tests.helpers import make_lha


class StartupTest(unittest.TestCase):
    def test_rewrite_startup_points_at_the_game_and_keeps_options(self):
        template = "; comment\ncd SYS:Old\nWHDLoad Old.slave PRELOAD CUSTOM1=1\n"
        out = core.rewrite_startup(template, "Alien/Disk1", "Alien.slave")
        self.assertEqual(out, "; comment\ncd SYS:Alien/Disk1\nWHDLoad Alien.slave PRELOAD CUSTOM1=1\n")


class ClearWorkDirTest(unittest.TestCase):
    def make_work(self, root):
        for d in ("Template_WHDLoad", "Whdload/A/Alien", "Whdload/0-9/1942", "Whdload/#/Odd", "Whdload/Keep"):
            (root / d).mkdir(parents=True)

    def test_removes_prepared_groups_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_work(root)
            removed = core.clear_work_dir(root, root / "Whdload")
            self.assertEqual({p.name for p in removed}, {"A", "0-9", "#"})
            self.assertTrue((root / "Template_WHDLoad").is_dir())
            self.assertTrue((root / "Whdload" / "Keep").is_dir())      # not a game group: left alone
            self.assertEqual([p.name for p in (root / "Whdload").iterdir()], ["Keep"])

    def test_removes_the_emptied_whdload_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Template_WHDLoad").mkdir()
            (root / "Whdload" / "B" / "Game").mkdir(parents=True)
            core.clear_work_dir(root)
            self.assertFalse((root / "Whdload").exists())

    def test_refuses_a_folder_that_is_not_a_work_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                core.clear_work_dir(Path(tmp))


class EnsurePreparedTest(unittest.TestCase):
    """Games that run from a prepared drive get it made automatically, the others are left alone."""
    OVERRIDES = {"Alien_v1.0": {"mode": "drive"}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.archive = self.work / "downloads" / "Alien_v1.0.lha"
        self.archive.parent.mkdir()
        self.archive.write_bytes(make_lha({"Alien/Alien.slave": b"S" * 50, "Alien/data": b"D"}))
        self.other = self.work / "downloads" / "Zool_v1.0.lha"
        self.other.write_bytes(make_lha({"Zool/Zool.slave": b"S"}))

    def make_template(self):
        (self.work / "Template_WHDLoad" / "S").mkdir(parents=True)
        (self.work / "Template_WHDLoad" / "S" / "Startup-Sequence").write_text("cd SYS:Old\nWHDLoad Old.slave PRELOAD\n")

    def test_a_normal_game_needs_nothing(self):
        self.assertFalse(core.needs_preparing(self.other, self.work, overrides=self.OVERRIDES))
        self.assertIsNone(core.ensure_prepared(self.other, self.work, overrides=self.OVERRIDES))
        self.assertFalse((self.work / "Whdload").exists())

    def test_a_drive_game_is_prepared_once(self):
        self.make_template()
        self.assertTrue(core.needs_preparing(self.archive, self.work, overrides=self.OVERRIDES))
        message = core.ensure_prepared(self.archive, self.work, overrides=self.OVERRIDES)
        self.assertIn("ok:", message)
        drive = self.work / "Whdload" / "A" / "Alien_v1.0"
        self.assertEqual((drive / "S" / "Startup-Sequence").read_text(), "cd SYS:Alien\nWHDLoad Alien.slave PRELOAD\n")
        self.assertFalse(core.needs_preparing(self.archive, self.work, overrides=self.OVERRIDES))
        (drive / "save.dat").write_text("keep")
        self.assertIsNone(core.ensure_prepared(self.archive, self.work, overrides=self.OVERRIDES))   # not redone
        self.assertEqual((drive / "save.dat").read_text(), "keep")

    def test_a_custom_prepared_folder_is_honoured(self):
        self.make_template()
        elsewhere = self.work / "elsewhere"
        core.ensure_prepared(self.archive, self.work, elsewhere, self.OVERRIDES)
        self.assertTrue((elsewhere / "A" / "Alien_v1.0" / "Alien" / "Alien.slave").is_file())
        self.assertFalse((self.work / "Whdload").exists())

    def test_a_missing_template_gives_a_readable_error(self):
        with self.assertRaisesRegex(RuntimeError, "no Template_WHDLoad"):
            core.ensure_prepared(self.archive, self.work, overrides=self.OVERRIDES)

    def test_the_shipped_overrides_cover_the_known_drive_games(self):
        for name in ("RocketAttack_v1.0", "UpScope_v1.01_Arcadia"):
            self.assertTrue(core.needs_preparing(self.work / f"{name}.lha", self.work), name)
        self.assertFalse(core.needs_preparing(self.work / "Rockford_v1.0.lha", self.work))


class SelectArchivesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / "downloads" / "A").mkdir(parents=True)
        for name in ("Alien_v1.0.lha", "Alien_v1.1_AGA.lha", "Zool_v1.0.lha"):
            (self.work / "downloads" / "A" / name).write_bytes(b"x")

    def names(self, *wanted):
        return [a.stem for a in core.select_archives(self.work, wanted)]

    def test_all_when_no_names_are_given(self):
        self.assertEqual(self.names(), ["Alien_v1.0", "Alien_v1.1_AGA", "Zool_v1.0"])

    def test_matches_the_full_name_or_the_name_without_its_version_ignoring_case(self):
        self.assertEqual(self.names("alien"), ["Alien_v1.0", "Alien_v1.1_AGA"])
        self.assertEqual(self.names("Alien_v1.1_AGA"), ["Alien_v1.1_AGA"])
        self.assertEqual(self.names("Nothing"), [])


class BundleGamesTest(unittest.TestCase):
    """The command line --bundle logic, with the PyInstaller build replaced."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / "downloads").mkdir()
        for name in ("Alien_v1.0.lha", "Alien_v1.1.lha", "Zool_v1.0.lha"):
            (self.work / "downloads" / name).write_bytes(b"x")
        patch = mock.patch.object(core.amiberry, "find", lambda chosen=None: Path("/x/Amiberry"))
        patch.start()
        self.addCleanup(patch.stop)
        quiet = contextlib.redirect_stdout(io.StringIO())      # bundle_games prints one line per game
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def test_builds_every_matching_game_and_reports_success(self):
        built = []
        code = core.bundle_games(["Alien"], self.work, create=lambda archive, work, **kw: built.append((archive.stem, kw["exe"])) or Path("/out") / archive.stem)
        self.assertEqual(code, 0)
        self.assertEqual(built, [("Alien_v1.0", Path("/x/Amiberry")), ("Alien_v1.1", Path("/x/Amiberry"))])

    def test_a_failure_is_reported_and_the_rest_still_build(self):
        def create(archive, work, **kw):
            if archive.stem == "Alien_v1.0":
                raise RuntimeError("PyInstaller failed")
            return Path("/out") / archive.stem
        self.assertEqual(core.bundle_games(["Alien"], self.work, create=create), 1)

    def test_the_saved_amiberry_choices_are_used(self):
        chosen = core.load_options.__globals__["Options"]("b", "fullscreen", "scanlines", True, False)
        seen = []
        with mock.patch.object(core, "load_options", return_value=chosen):
            core.bundle_games(["Zool"], self.work, create=lambda archive, work, **kw: seen.append(kw["options"]) or Path("/out"))
        self.assertEqual(seen, [chosen])

    def test_a_game_that_needs_a_drive_is_prepared_before_it_is_built(self):
        order = []
        with mock.patch.object(core, "ensure_prepared", side_effect=lambda archive, work: order.append(("prepare", archive.stem))):
            code = core.bundle_games(["Zool"], self.work,
                                     create=lambda archive, work, **kw: order.append(("build", archive.stem)) or Path("/out"))
        self.assertEqual((code, order), (0, [("prepare", "Zool_v1.0"), ("build", "Zool_v1.0")]))

    def test_a_game_that_cannot_be_prepared_fails_without_being_built(self):
        create = mock.Mock()
        with mock.patch.object(core, "ensure_prepared", side_effect=RuntimeError("no Template_WHDLoad")):
            self.assertEqual(core.bundle_games(["Zool"], self.work, create=create), 1)
        create.assert_not_called()

    def test_no_match_and_no_amiberry_are_errors(self):
        self.assertEqual(core.bundle_games(["Nothing"], self.work, create=mock.Mock()), 1)
        with mock.patch.object(core.amiberry, "find", lambda chosen=None: None):
            create = mock.Mock()
            self.assertEqual(core.bundle_games(["Alien"], self.work, create=create), 1)
        create.assert_not_called()


class FindSlaveTest(unittest.TestCase):
    def test_picks_the_shallowest_slave_and_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(core.find_slave(root))
            (root / "Game" / "Sub").mkdir(parents=True)
            (root / "Game" / "Sub" / "Deep.slave").write_bytes(b"x")
            (root / "Game" / "Main.SLAVE").write_bytes(b"x")          # extension is case-insensitive
            (root / "Game" / "readme").write_bytes(b"x")
            self.assertEqual(core.find_slave(root), root / "Game" / "Main.SLAVE")


if __name__ == "__main__":
    unittest.main()
