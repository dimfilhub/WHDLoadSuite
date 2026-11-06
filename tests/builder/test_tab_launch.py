"""The Builder tab's Launch to test button: runs the game through the Amiberry module."""
import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from common import gamepaths
from tabs.builder import launcher as launcher_module
from tabs.builder import tab as builder_tab
from tabs.settings import settings as settings_module
from tabs.settings.settings import AppSettings
from tests.helpers import make_lha, reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()


@unittest.skipIf(ROOT is None, "no display")
class LaunchButtonTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "downloads").mkdir()
        # the tabs save their folder choices: keep that away from the real settings file of the project
        patch = mock.patch.object(settings_module, "SETTINGS_FILE", self.dir / "settings.json")
        patch.start()
        self.addCleanup(patch.stop)
        (self.dir / "downloads" / "Alien_v1.0.lha").write_bytes(make_lha({"Alien/Alien.slave": b"S" * 50}))
        self.settings = AppSettings(ROOT)
        self.settings.launch_screen.set(False)       # the launch screen is tested in test_launch_screen.py
        self.settings.downloads.set(str(self.dir / "downloads"))
        self.settings.work_dir.set(str(self.dir))
        self.settings.whdload_dir.set(str(self.dir / "Whdload"))
        self.settings.exe_dir.set(str(self.dir / "Executables"))
        self.tab = builder_tab.BuilderTab(ROOT, self.settings)
        self.addCleanup(self.tab.destroy)
        self.tab.refresh()
        self.tab.set_checked(["0"], True)
        self.box = mock.patch.object(builder_tab, "messagebox")
        self.messagebox = self.box.start()
        self.addCleanup(self.box.stop)
        ask = mock.patch.object(launcher_module, "messagebox")       # the question before preparing a game
        self.ask = ask.start().askokcancel
        self.addCleanup(ask.stop)

    def finish(self):
        deadline = time.time() + 10
        while self.tab.launcher.busy and time.time() < deadline:
            ROOT.update()
            time.sleep(0.02)
        self.assertFalse(self.tab.launcher.busy)

    def test_launches_the_selected_archive_with_its_prepared_drive_path(self):
        exe = Path("/x/Amiberry")
        with mock.patch.object(self.settings, "amiberry_exe", lambda: exe), \
                mock.patch.object(launcher_module.amiberry, "launch_game") as launch:
            self.tab.launch()
            self.finish()
        (got_exe, archive, drive, kickstarts), _ = launch.call_args
        self.assertEqual((got_exe, archive.name), (exe, "Alien_v1.0.lha"))
        self.assertEqual(drive, self.dir / "Whdload" / "A" / "Alien_v1.0")
        self.assertEqual(kickstarts, self.settings.kickstarts_dir())
        self.assertEqual(self.tab.status.get(), "Launched Alien_v1.0 in Amiberry.")
        self.messagebox.showerror.assert_not_called()

    def test_a_reason_for_not_starting_is_shown(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(launcher_module.amiberry, "launch_game", side_effect=RuntimeError("prepare it first")):
            self.tab.launch()
            self.finish()
        self.messagebox.showerror.assert_called_once_with("Launch", "prepare it first")
        self.assertIn("Could not start", self.tab.status.get())

    def test_no_amiberry_is_explained_without_starting_anything(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: None), \
                mock.patch.object(launcher_module.amiberry, "launch_game") as launch:
            self.tab.launch()
        launch.assert_not_called()
        self.assertIn("Amiberry not found", self.messagebox.showerror.call_args[0][1])
        self.assertFalse(self.tab.launcher.busy)

    def test_the_status_says_when_the_first_launch_has_more_to_do(self):
        home = self.dir / "WHDLoadSuite" / "Amiberry"
        with mock.patch.object(launcher_module.amiberry_runtime, "home_dir", lambda: home), \
                mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(launcher_module.amiberry, "launch_game"):
            self.tab.launch()
            first = self.tab.status.get()
            self.finish()
            (home / "WHDBoot").mkdir(parents=True)
            (home / "WHDBoot" / "WHDLoad").write_text("w")      # WHDLoad is there from now on
            self.tab.launch()
            later = self.tab.status.get()
            self.finish()
        self.assertIn("downloading WHDLoad", first)
        self.assertNotIn("downloading", later)

    def wait_for_worker(self):
        deadline = time.time() + 10
        while time.time() < deadline:
            ROOT.update()
            if self.tab.worker is not None and not self.tab.worker.is_alive() and self.tab.events.empty():
                break
            time.sleep(0.02)
        ROOT.update()

    def test_build_makes_an_executable_with_amiberry_from_the_archive(self):
        exe = Path("/x/Amiberry")
        built = Path("/out/Alien_v1.0.app")
        with mock.patch.object(self.settings, "amiberry_exe", lambda: exe), \
                mock.patch.object(builder_tab.bundle, "create_executable", return_value=built) as create:
            self.tab.start_bundle()
            self.wait_for_worker()
        (archive, work_dir, exe_dir, whdload_dir), kwargs = create.call_args
        self.assertEqual((archive.name, work_dir, whdload_dir), ("Alien_v1.0.lha", self.dir, self.dir / "Whdload"))
        self.assertEqual((kwargs["exe"], kwargs["kickstarts"]), (exe, self.settings.kickstarts_dir()))
        self.assertEqual(kwargs["options"], self.settings.amiberry_options())             # built with the user's choices
        self.assertIn(f"Alien_v1.0.lha: ok: {built}", self.tab.log.get("1.0", "end"))
        self.assertEqual(self.tab.status.get(), "Done.")

    def test_build_gives_the_executable_the_launch_screen_and_the_games_picture(self):
        picture = (Path("/gb/shot.png"), "screenshot")
        for switch, expected in ((True, (True, picture)), (False, (False, None))):
            self.settings.launch_screen.set(switch)
            with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                    mock.patch.object(self.settings, "game_image", lambda stem: picture), \
                    mock.patch.object(builder_tab.bundle, "create_executable", return_value=Path("/o/A.app")) as create:
                self.tab.start_bundle()
                self.wait_for_worker()
            kwargs = create.call_args.kwargs
            self.assertEqual((kwargs["launch_screen"], kwargs["picture"]), expected)

    def test_a_failed_build_is_logged_and_counted(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(builder_tab.bundle, "create_executable", side_effect=RuntimeError("PyInstaller is not installed")):
            self.tab.start_bundle()
            self.wait_for_worker()
        self.assertIn("FAILED: PyInstaller is not installed", self.tab.log.get("1.0", "end"))
        self.assertEqual(self.tab.status.get(), "Done with 1 failure(s).")

    def test_build_without_amiberry_is_explained_and_starts_nothing(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: None), \
                mock.patch.object(builder_tab.bundle, "create_executable") as create:
            self.tab.start_bundle()
        create.assert_not_called()
        self.assertIn("Amiberry not found", self.messagebox.showerror.call_args[0][1])
        self.assertIsNone(self.tab.worker)

    def test_launch_prepares_a_drive_game_first_then_starts_it(self):
        order = []
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(builder_tab.core, "needs_preparing", return_value=True), \
                mock.patch.object(builder_tab.core, "ensure_prepared",
                                  side_effect=lambda *a: order.append(("prepare", a[0].name, a[1], a[2]))), \
                mock.patch.object(launcher_module.amiberry, "launch_game",
                                  side_effect=lambda *a, **k: order.append(("launch", a[1].name, k["options"]))):
            self.tab.launch()
            self.assertIn("Preparing and starting Alien_v1.0", self.tab.status.get())
            self.finish()
        self.assertEqual(order, [("prepare", "Alien_v1.0.lha", self.dir, self.dir / "Whdload"),
                                 ("launch", "Alien_v1.0.lha", self.settings.amiberry_options())])
        self.assertEqual(self.tab.status.get(), "Launched Alien_v1.0 in Amiberry.")

    def test_a_game_that_cannot_be_prepared_is_not_launched_and_says_why(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(builder_tab.core, "ensure_prepared", side_effect=RuntimeError("no Template_WHDLoad")), \
                mock.patch.object(launcher_module.amiberry, "launch_game") as launch:
            self.tab.launch()
            self.finish()
        launch.assert_not_called()
        self.messagebox.showerror.assert_called_once_with("Launch", "no Template_WHDLoad")

    def test_build_prepares_drive_games_first_and_logs_it(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(builder_tab.core, "ensure_prepared", return_value="ok: drive") as prepare, \
                mock.patch.object(builder_tab.bundle, "create_executable", return_value=Path("/out/A.app")):
            self.tab.start_bundle()
            self.wait_for_worker()
        prepare.assert_called_once()
        log = self.tab.log.get("1.0", "end")
        self.assertIn("Alien_v1.0.lha: prepared its drive first", log)
        self.assertIn("Alien_v1.0.lha: ok: %s" % Path("/out/A.app"), log)

    def test_colours_show_which_games_need_preparing_and_how_far_they_are(self):
        downloads = self.dir / "downloads"
        (downloads / "RocketAttack_v1.0.lha").write_bytes(make_lha({"RocketAttack/RocketAttack.slave": b"S"}))
        self.tab.refresh()
        ids = {Path(a).stem: str(i) for i, a in enumerate(self.tab.archives)}   # Alien_v1.0 needs nothing

        def colour(name):
            self.tab.refresh_prepared()
            return tuple(t for t in self.tab.tree.item(ids[name], "tags") if t in ("needs_prep", "prepared", "executable"))

        self.assertEqual(colour("RocketAttack_v1.0"), ("needs_prep",))        # orange: needs a drive, has none
        self.assertEqual(colour("Alien_v1.0"), ())                             # runs from its .lha: no colour
        gamepaths.drive_path("RocketAttack_v1.0", self.dir).mkdir(parents=True)
        gamepaths.drive_path("Alien_v1.0", self.dir).mkdir(parents=True)       # a drive it does not need
        self.assertEqual(colour("RocketAttack_v1.0"), ("prepared",))           # green
        self.assertEqual(colour("Alien_v1.0"), ())                             # still nothing
        exe = gamepaths.executable_path("RocketAttack_v1.0", self.dir, self.dir / "Executables")
        exe.parent.mkdir(parents=True)
        exe.mkdir() if exe.suffix == ".app" else exe.write_text("x")
        self.assertEqual(colour("RocketAttack_v1.0"), ("executable",))         # blue, one tag whatever Tk's precedence
        self.assertEqual(self.tab.tree.item(ids["RocketAttack_v1.0"], "tags").count("executable"), 1)

    def test_each_state_has_its_own_colour_and_the_legend_uses_the_same_ones(self):
        colours = {tag: str(self.tab.tree.tag_configure(tag, "foreground")) for tag in ("needs_prep", "prepared", "executable")}
        self.assertEqual(colours, {"needs_prep": gamepaths.NEEDS_PREP_COLOUR, "prepared": gamepaths.PREPARED_COLOUR,
                                   "executable": gamepaths.EXECUTABLE_COLOUR})
        self.assertEqual(len(set(colours.values())), 3)
        self.assertEqual(gamepaths.NEEDS_PREP_COLOUR, "#e65c00")      # orange

    def test_the_legend_explains_all_three_colours(self):
        texts = []
        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "Label":
                    texts.append(child.cget("text"))
                walk(child)
        walk(self.tab)
        for wanted in ("Needs preparation", "Prepared", "Executable built"):
            self.assertIn(f"■ {wanted}", texts)

    def test_launch_to_test_asks_before_preparing_and_can_be_cancelled(self):
        (self.dir / "downloads" / "RocketAttack_v1.0.lha").write_bytes(make_lha({"RocketAttack/RocketAttack.slave": b"S"}))
        self.tab.refresh()
        index = [Path(a).stem for a in self.tab.archives].index("RocketAttack_v1.0")
        self.tab.set_checked([str(index)], True)
        self.tab.set_checked(["0"], False)
        self.ask.return_value = False
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(builder_tab.core, "ensure_prepared") as prepare, \
                mock.patch.object(launcher_module.amiberry, "launch_game") as launch:
            self.tab.launch()
        prepare.assert_not_called()
        launch.assert_not_called()
        self.assertFalse(self.tab.launcher.busy)
        title, question = self.ask.call_args[0][:2]
        self.assertEqual(title, "Launch")
        self.assertIn("RocketAttack_v1.0 needs a prepared drive", question)

    def test_a_game_that_needs_nothing_is_not_asked_about(self):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(launcher_module.amiberry, "launch_game"):
            self.tab.launch()                                # Alien_v1.0 runs straight from its .lha
            self.finish()
        self.ask.assert_not_called()

    def test_there_is_no_prepare_button_any_more(self):
        self.assertFalse(hasattr(self.tab, "prepare_btn"))
        self.assertFalse(hasattr(self.tab, "start_prepare"))
        self.assertFalse(hasattr(self.tab, "force"))

    def test_one_game_at_a_time(self):
        self.tab.set_checked(["0"], True)
        self.tab.clear_selection()
        self.tab.launch()                                   # nothing selected: a message, no launch
        self.messagebox.showinfo.assert_called_once()


if __name__ == "__main__":
    unittest.main()
