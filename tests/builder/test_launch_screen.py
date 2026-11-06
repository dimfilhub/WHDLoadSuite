"""The launch screen shown before a game starts from the Browser or the Builder."""
import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from common import amiberry_runtime as rt
from common import gamebase
from tabs.builder import launch_screen
from tabs.builder import launcher as launcher_module
from tabs.builder import tab as builder_tab
from tabs.settings import settings as settings_module
from tabs.settings.settings import AppSettings
from tests.helpers import make_lha, reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()


def make_png(path, size=(320, 256)):
    from PIL import Image
    Image.new("RGB", size, (200, 30, 30)).save(path)
    return path.read_bytes()


class FitSizeTest(unittest.TestCase):
    def test_small_pictures_are_enlarged_by_whole_numbers(self):
        self.assertEqual(launch_screen.fit_size(320, 256, 640, 512), (640, 512, True))
        self.assertEqual(launch_screen.fit_size(320, 256, 1000, 800), (960, 768, True))      # 3x, never 3.1x

    def test_other_pictures_are_fitted_smoothly(self):
        self.assertEqual(launch_screen.fit_size(320, 256, 500, 400), (500, 400, False))      # 1.56x: not a whole number
        self.assertEqual(launch_screen.fit_size(1000, 500, 640, 512), (640, 320, False))     # too big: shrunk
        self.assertEqual(launch_screen.fit_size(500, 1000, 640, 512), (256, 512, False))


@unittest.skipIf(ROOT is None, "no display")
class LaunchScreenTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        patch = mock.patch.object(settings_module, "SETTINGS_FILE", self.dir / "settings.json")
        patch.start()
        self.addCleanup(patch.stop)
        self.settings = AppSettings(ROOT)
        self.options = rt.Options(keyboard="d", window="windowed", look="normal")
        self.picture = self.dir / "shot.png"
        make_png(self.picture)
        self.screens = []

    def screen(self, **kw):
        s = launch_screen.LaunchScreen(ROOT, "Alien_v1.0", self.options, kw.pop("picture", self.picture),
                                       kw.pop("kind", "screenshot"), settings=kw.pop("settings", self.settings), **kw)
        self.screens.append(s)
        self.addCleanup(lambda: s.winfo_exists() and s.destroy())
        return s

    def choose(self, screen, field, value):
        combo, mapping = screen.vars[field]
        text = next(t for t, v in mapping.items() if v == value)
        combo.set(text)

    def test_it_shows_the_picture(self):
        screen = self.screen()
        self.assertIsNotNone(screen.image)
        self.assertGreaterEqual(screen.image.width(), 320)                 # a 320x256 screenshot is enlarged, not shrunk
        self.assertLessEqual(screen.image.width(), launch_screen.MAX_PICTURE[0])
        self.assertAlmostEqual(screen.image.width() / screen.image.height(), 320 / 256, delta=0.01)      # same proportions

    def test_a_missing_picture_is_a_note_not_an_error(self):
        screen = self.screen(picture=None, kind="")
        self.assertIsNone(screen.image)
        screen = self.screen(picture=self.dir / "gone.png")
        self.assertIsNone(screen.image)

    def test_launch_returns_the_options_for_this_launch_only(self):
        screen = self.screen()
        self.choose(screen, "keyboard", "a")
        self.choose(screen, "window", "fullscreen")
        self.choose(screen, "look", "crt")
        screen.launch()
        self.assertEqual(screen.result, rt.Options(keyboard="a", window="fullscreen", look="crt"))
        self.assertEqual(self.settings.keyboard.get(), "d")                 # the saved choices are untouched
        self.assertEqual(self.settings.window.get(), "windowed")

    def test_the_other_options_are_kept(self):
        self.options = rt.Options(keyboard="b", quit_on_exit=True, splash=False)
        screen = self.screen()
        screen.launch()
        self.assertEqual(screen.result, self.options)

    def test_remembering_makes_the_choices_the_defaults(self):
        screen = self.screen()
        self.choose(screen, "keyboard", "c")
        self.choose(screen, "look", "scanlines")
        screen.remember.set(True)
        screen.launch()
        self.assertEqual((self.settings.keyboard.get(), self.settings.window.get(), self.settings.look.get()),
                         ("c", "windowed", "scanlines"))
        self.assertIn('"keyboard": "c"', (self.dir / "settings.json").read_text())

    def test_the_screen_can_be_switched_off_from_itself_even_when_cancelling(self):
        screen = self.screen()
        screen.show_again.set(False)
        screen.cancel()
        self.assertIsNone(screen.result)
        self.assertFalse(self.settings.launch_screen.get())

    def test_it_says_where_to_turn_the_screen_back_on(self):
        self.assertTrue(any("Settings > Amiberry" in t for t in self.texts(self.screen())))
        self.assertFalse(any("Settings > Amiberry" in t for t in self.texts(self.screen(settings=None))))   # no tick, no hint

    @staticmethod
    def texts(w):
        out = [str(w.cget("text"))] if w.winfo_class() in ("TLabel", "Label") else []
        for child in w.winfo_children():
            out += LaunchScreenTest.texts(child)
        return out

    def test_it_says_when_the_game_has_to_be_prepared(self):
        texts = self.texts
        self.assertTrue(any("prepared drive" in t for t in texts(self.screen(preparing=True))))
        self.assertFalse(any("prepared drive" in t for t in texts(self.screen())))


@unittest.skipIf(ROOT is None, "no display")
class LauncherUsesTheScreenTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "downloads").mkdir()
        patch = mock.patch.object(settings_module, "SETTINGS_FILE", self.dir / "settings.json")
        patch.start()
        self.addCleanup(patch.stop)
        (self.dir / "downloads" / "Alien_v1.0.lha").write_bytes(make_lha({"Alien/Alien.slave": b"S" * 50}))
        self.settings = AppSettings(ROOT)
        self.settings.downloads.set(str(self.dir / "downloads"))
        self.settings.work_dir.set(str(self.dir))
        self.settings.whdload_dir.set(str(self.dir / "Whdload"))
        self.settings.exe_dir.set(str(self.dir / "Executables"))
        self.assertTrue(self.settings.launch_screen.get())                 # on unless the user turns it off
        self.tab = builder_tab.BuilderTab(ROOT, self.settings)
        self.addCleanup(self.tab.destroy)
        self.tab.refresh()
        self.tab.set_checked(["0"], True)
        for module, name in ((builder_tab, "messagebox"), (launcher_module, "messagebox")):
            patch = mock.patch.object(module, name)
            patch.start()
            self.addCleanup(patch.stop)

    def finish(self):
        deadline = time.time() + 10
        while self.tab.launcher.busy and time.time() < deadline:
            ROOT.update()
            time.sleep(0.02)
        self.assertFalse(self.tab.launcher.busy)

    def run_launch(self, answer):
        with mock.patch.object(self.settings, "amiberry_exe", lambda: Path("/x/Amiberry")), \
                mock.patch.object(launcher_module.launch_screen, "ask", return_value=answer) as ask, \
                mock.patch.object(launcher_module.amiberry, "launch_game") as launch:
            self.tab.launch()
            self.finish()
        return ask, launch

    def test_the_game_starts_with_the_options_chosen_on_the_screen(self):
        chosen = rt.Options(keyboard="a", window="fullscreen", look="crt")
        ask, launch = self.run_launch(chosen)
        self.assertEqual(launch.call_args.kwargs["options"], chosen)
        self.assertEqual(ask.call_args.args[1], "Alien_v1.0")
        self.assertEqual(ask.call_args.args[2], self.settings.amiberry_options())      # it starts from the saved choices

    def test_cancelling_the_screen_starts_nothing(self):
        ask, launch = self.run_launch(None)
        launch.assert_not_called()
        self.assertFalse(self.tab.launcher.busy)

    def test_the_picture_comes_from_the_chosen_gamebase_folder(self):
        data = self.dir / "gb" / "data"
        (data / "screenshots" / "A").mkdir(parents=True)
        make_png(data / "screenshots" / "A" / "Alien.png")
        self.settings.gamebase_dir.set(str(data))
        self.addCleanup(gamebase.forget)
        with mock.patch.object(gamebase, "load_map", lambda: {"Alien": {"s": "screenshots/A/Alien.png"}}):
            ask, _ = self.run_launch(self.settings.amiberry_options())
        picture, kind = ask.call_args.args[3:5]
        self.assertEqual((picture.name, kind), ("Alien.png", "screenshot"))

    def test_without_a_folder_there_is_no_picture_but_the_screen_still_comes(self):
        ask, _ = self.run_launch(self.settings.amiberry_options())
        self.assertEqual(ask.call_args.args[3:5], (None, ""))

    def test_a_game_that_needs_preparing_is_announced_by_the_screen_not_by_a_second_question(self):
        with mock.patch.object(builder_tab.core, "needs_preparing", return_value=True), \
                mock.patch.object(builder_tab.core, "ensure_prepared"):
            ask, launch = self.run_launch(self.settings.amiberry_options())
        self.assertTrue(ask.call_args.args[5])                              # preparing
        launcher_module.messagebox.askokcancel.assert_not_called()
        launch.assert_called_once()

    def test_switched_off_there_is_no_screen_and_the_saved_options_are_used(self):
        self.settings.launch_screen.set(False)
        ask, launch = self.run_launch("never used")
        ask.assert_not_called()
        self.assertEqual(launch.call_args.kwargs["options"], self.settings.amiberry_options())


if __name__ == "__main__":
    unittest.main()
