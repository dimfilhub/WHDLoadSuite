"""AppSettings: the folder choices shared by the tabs."""
import gc
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from common.amiberry_runtime import Options
from common.paths import DEFAULT_WORK_DIR
from tabs.settings import settings as settings_module
from tabs.settings.settings import AppSettings

from tests.helpers import reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()


@unittest.skipIf(ROOT is None, "no display")
class AppSettingsTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.file = self.dir / "settings.json"
        patch = mock.patch.object(settings_module, "SETTINGS_FILE", self.file)   # never the project's real file
        patch.start()
        self.addCleanup(patch.stop)

    def test_defaults_when_nothing_is_saved(self):
        s = AppSettings(ROOT)
        self.assertEqual(s.work_dir.get(), str(DEFAULT_WORK_DIR))
        self.assertEqual(s.whdload_dir.get(), str(DEFAULT_WORK_DIR / "Whdload"))
        self.assertEqual(s.exe_dir.get(), str(DEFAULT_WORK_DIR / "Executables"))
        self.assertEqual(s.downloads.get(), str(DEFAULT_WORK_DIR / "downloads"))
        self.assertEqual(s.amiberry_dir.get(), "")

    def test_the_launch_screen_choices_are_remembered(self):
        (self.dir / "gb").mkdir()
        s = AppSettings(ROOT)
        self.assertEqual((s.launch_screen.get(), s.launch_image.get(), s.gamebase_dir.get()), (True, "best", ""))
        s.launch_screen.set(False)
        s.launch_image.set("cover")
        s.gamebase_dir.set(str(self.dir / "gb"))
        s.save_settings()
        again = AppSettings(ROOT)
        self.assertEqual((again.launch_screen.get(), again.launch_image.get(), again.gamebase_dir.get()),
                         (False, "cover", str(self.dir / "gb")))

    def test_a_bad_picture_choice_or_a_vanished_gamebase_folder_falls_back(self):
        self.file.write_text(json.dumps({"launch_image": "poster", "gamebase_dir": str(self.dir / "gone")}))
        s = AppSettings(ROOT)
        self.assertEqual((s.launch_image.get(), s.gamebase_dir.get()), ("best", ""))

    def test_saved_folders_are_loaded_and_missing_ones_are_dropped(self):
        (self.dir / "mine").mkdir()
        self.file.write_text(json.dumps({"downloads": str(self.dir / "mine"), "exe_dir": str(self.dir / "gone")}))
        s = AppSettings(ROOT)
        self.assertEqual(s.downloads.get(), str(self.dir / "mine"))
        self.assertEqual(s.exe_dir.get(), str(DEFAULT_WORK_DIR / "Executables"))      # the folder no longer exists

    def test_an_old_sources_setting_is_still_read_as_the_downloads_folder(self):
        (self.dir / "old").mkdir()
        self.file.write_text(json.dumps({"sources": str(self.dir / "old")}))
        self.assertEqual(AppSettings(ROOT).downloads.get(), str(self.dir / "old"))

    def test_changing_downloads_saves_it_and_tells_the_tabs(self):
        s = AppSettings(ROOT)
        told = []
        s.on_downloads_changed = lambda: told.append(1)
        s.set_downloads(self.dir / "new")
        self.assertEqual(s.downloads.get(), str(self.dir / "new"))
        self.assertEqual(json.loads(self.file.read_text())["downloads"], str(self.dir / "new"))
        self.assertEqual(told, [1])

    def test_the_work_folder_takes_the_default_subfolders_along_but_not_customised_ones(self):
        s = AppSettings(ROOT)
        told = []
        s.on_folders_changed = lambda: told.append(1)
        old = Path(s.work_dir.get())
        s.exe_dir.set(str(self.dir / "my-executables"))              # customised: must stay
        s.set_work_dir(self.dir / "work2")
        self.assertEqual(s.work_dir.get(), str(self.dir / "work2"))
        self.assertEqual(s.whdload_dir.get(), str(self.dir / "work2" / "Whdload"))   # was at its default: follows
        self.assertEqual(s.exe_dir.get(), str(self.dir / "my-executables"))
        self.assertEqual(told, [1])
        self.assertNotEqual(old, self.dir / "work2")

    def test_another_folder_is_saved_and_announced(self):
        s = AppSettings(ROOT)
        told = []
        s.on_folders_changed = lambda: told.append(1)
        s.set_folder(s.whdload_dir, self.dir / "drives")
        self.assertEqual(json.loads(self.file.read_text())["whdload_dir"], str(self.dir / "drives"))
        self.assertEqual(told, [1])

    def test_the_amiberry_choices_default_to_how_the_app_always_behaved(self):
        self.assertEqual(AppSettings(ROOT).amiberry_options(), Options("d", "windowed", "normal", False, True))

    def test_a_choice_is_saved_the_moment_it_is_made_and_comes_back(self):
        s = AppSettings(ROOT)
        s.keyboard.set("b")
        s.look.set("crt")
        s.window.set("fullscreen")
        s.quit_on_exit.set(True)
        s.splash.set(False)
        saved = json.loads(self.file.read_text())["amiberry_options"]
        self.assertEqual(saved, {"keyboard": "b", "window": "fullscreen", "look": "crt", "quit_on_exit": True, "splash": False})
        again = AppSettings(ROOT)
        self.assertEqual(again.amiberry_options(), Options("b", "fullscreen", "crt", True, False))
        self.assertEqual(settings_module.load_options(), Options("b", "fullscreen", "crt", True, False))   # the CLI reads it too

    def test_no_keyboard_is_a_real_choice_that_survives(self):
        s = AppSettings(ROOT)
        s.keyboard.set("")
        self.assertEqual(AppSettings(ROOT).amiberry_options().keyboard, "")

    def test_nonsense_in_the_saved_file_falls_back_to_the_defaults(self):
        for bad in ({"amiberry_options": {"keyboard": "q", "look": "sepia"}}, {"amiberry_options": "oops"},
                    {"amiberry_options": None}, ["not", "a", "dict"]):
            self.file.write_text(json.dumps(bad))
            self.assertEqual(AppSettings(ROOT).amiberry_options(), Options(), bad)
            self.assertEqual(settings_module.load_options(), Options())

    def test_the_folder_settings_survive_having_the_options_in_the_same_file(self):
        (self.dir / "mine").mkdir()
        self.file.write_text(json.dumps({"downloads": str(self.dir / "mine"), "amiberry_options": {"keyboard": "a"}}))
        s = AppSettings(ROOT)
        self.assertEqual((s.downloads.get(), s.keyboard.get()), (str(self.dir / "mine"), "a"))

    def test_amiberry_comes_from_the_chosen_folder_or_the_usual_places(self):
        s = AppSettings(ROOT)
        with mock.patch.object(settings_module.amiberry, "find", return_value=Path("/x/Amiberry")) as find:
            self.assertEqual(s.amiberry_exe(), Path("/x/Amiberry"))
            find.assert_called_with(None)                          # nothing chosen: the usual places
            s.amiberry_dir.set("/chosen")
            s.amiberry_exe()
            find.assert_called_with("/chosen")
        self.assertEqual(s.kickstarts_dir().name, "Kickstarts")


if __name__ == "__main__":
    unittest.main()
