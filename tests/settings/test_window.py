"""The settings windows opened from the Settings menu: Browser, Builder and Amiberry."""
import gc
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

import time

from common import amiberry
from common import amiberry_runtime as rt
from common.amiberry import RomReport
from tabs.settings import settings as settings_module
from tabs.settings import window as window_module
from tabs.settings.settings import KIND, AppSettings
from tabs.settings.window import SettingsWindow, rom_status_text

from tests.helpers import reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()


def label_texts(widget):
    texts = []
    for child in widget.winfo_children():
        if child.winfo_class() in ("TLabel", "Label"):
            texts.append(str(child.cget("text")))
        texts += label_texts(child)
    return texts


@unittest.skipIf(ROOT is None, "no display")
class SettingsWindowTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.home = self.dir / "WHDLoadSuite" / "Amiberry"
        for patch in (mock.patch.object(settings_module, "SETTINGS_FILE", self.dir / "settings.json"),
                      mock.patch.object(rt, "home_dir", lambda: self.home)):
            patch.start()
            self.addCleanup(patch.stop)
        self.games = self.dir / "WHDLoadSuite" / "Games"
        games_patch = mock.patch.object(rt, "games_dir", lambda: self.games)      # never the user's real saved games
        games_patch.start()
        self.addCleanup(games_patch.stop)
        from common import gamebase
        app_data = mock.patch.object(gamebase, "extracted_dir", lambda: self.dir / "no-app-data" / "Gamebase")
        app_data.start()                    # never the real extracted pictures in the user's application data
        self.addCleanup(app_data.stop)
        self.addCleanup(gamebase.forget)
        box = mock.patch.object(window_module, "messagebox")
        self.box = box.start()
        self.addCleanup(box.stop)
        self.close_all()                                   # a window left open by another test would be shown again
        self.settings = AppSettings(ROOT)
        self.settings.amiberry_exe = lambda: None          # these tests never run the real Amiberry
        self.windows = []
        self.addCleanup(self.close_all)

    def close_all(self):
        for w in list(SettingsWindow._open.values()):
            w.close()
        SettingsWindow._open.clear()

    def open(self, section):
        window = SettingsWindow.show(ROOT, self.settings, section)
        self.windows.append(window)
        return window

    def make_home(self):
        (self.home / "WHDBoot").mkdir(parents=True)
        (self.home / "WHDBoot" / "WHDLoad").write_bytes(b"x" * 2048)

    # --- what each window shows --------------------------------------------------------------------------

    def test_each_part_of_the_app_has_its_own_window_with_its_own_rows(self):
        shown = {s: [t for t in label_texts(self.open(s)) if t.endswith(":")] for s in ("browser", "builder", "amiberry")}
        self.assertEqual(shown["browser"], ["Downloads folder:"])
        self.assertEqual(shown["builder"], ["Work folder:", "Prepared (Whdload) folder:", f"{KIND} folder:"])
        self.assertEqual(shown["amiberry"], ["Amiberry folder:", "Amiberry data:", "Saved games:", "Kickstart ROMs:", "WHDLoad games:",
                                             "Keyboard joystick:", "Window:", "Screen look:", "Picture:",
                                             "GamebaseAmiga folder:"])      # left column, then right column
        self.assertEqual([self.open(s).title() for s in ("browser", "builder", "amiberry")],
                         ["Browser settings", "Builder settings", "Amiberry settings"])

    def test_an_unknown_section_is_refused(self):
        with self.assertRaises(ValueError):
            SettingsWindow(ROOT, self.settings, "nothing")

    def test_asking_again_shows_the_same_window_and_closing_allows_a_new_one(self):
        first = self.open("builder")
        self.assertIs(self.open("builder"), first)
        self.assertEqual(len(SettingsWindow._open), 1)
        first.close()
        self.assertFalse(first.winfo_exists())
        self.assertIsNot(self.open("builder"), first)

    def test_the_windows_are_independent(self):
        a, b = self.open("browser"), self.open("amiberry")
        self.assertIsNot(a, b)
        a.close()
        self.assertTrue(b.winfo_exists())

    # --- choosing folders --------------------------------------------------------------------------------

    def test_browsing_for_the_downloads_folder_changes_saves_and_announces_it(self):
        told = []
        self.settings.on_downloads_changed = lambda: told.append(1)
        window = self.open("browser")
        with mock.patch.object(window_module.filedialog, "askdirectory", return_value=str(self.dir / "dl")) as ask:
            window.pick_downloads()
        self.assertEqual(self.settings.downloads.get(), str(self.dir / "dl"))
        self.assertEqual((told, ask.call_args.kwargs["parent"]), ([1], window))
        self.assertTrue((self.dir / "settings.json").is_file())

    def test_cancelling_the_folder_dialog_changes_nothing(self):
        before = self.settings.downloads.get()
        window = self.open("browser")
        with mock.patch.object(window_module.filedialog, "askdirectory", return_value=""):
            window.pick_downloads()
        self.assertEqual(self.settings.downloads.get(), before)
        self.assertFalse((self.dir / "settings.json").exists())

    def test_the_builder_window_changes_the_work_folder_and_the_default_folders_follow(self):
        window = self.open("builder")
        with mock.patch.object(window_module.filedialog, "askdirectory", return_value=str(self.dir / "w")):
            window.pick_work_dir()
        self.assertEqual(self.settings.work_dir.get(), str(self.dir / "w"))
        self.assertEqual(self.settings.exe_dir.get(), str(self.dir / "w" / "Executables"))

    def test_the_other_builder_folders_are_chosen_the_same_way(self):
        told = []
        self.settings.on_folders_changed = lambda: told.append(1)
        window = self.open("builder")
        with mock.patch.object(window_module.filedialog, "askdirectory", return_value=str(self.dir / "x")):
            window._pick(self.settings.exe_dir, "title")
        self.assertEqual((self.settings.exe_dir.get(), told), (str(self.dir / "x"), [1]))

    def make_data_folder(self):
        data = self.dir / "gb" / "data"
        (data / "screenshots" / "A").mkdir(parents=True)
        (data / "extras" / "Cover Scans" / "A").mkdir(parents=True)
        (data / "screenshots" / "A" / "Alien.png").write_bytes(b"x")
        (data / "extras" / "Cover Scans" / "A" / "Alien_Front.jpg").write_bytes(b"x")
        return data

    def test_the_gamebase_folder_is_browsed_saved_and_described(self):
        data = self.make_data_folder()
        window = self.open("amiberry")
        self.assertIn("Optional", window.gamebase_note.get())
        with mock.patch.object(window_module.filedialog, "askdirectory", return_value=str(data)):
            window.pick_gamebase()
        self.assertEqual(self.settings.gamebase_dir.get(), str(data))
        self.assertIn("1 screenshots and 1 cover scans", window.gamebase_note.get())
        self.assertIn("gamebase_dir", (self.dir / "settings.json").read_text())
        self.settings.gamebase_dir.set(str(self.dir))
        window.refresh_gamebase()
        self.assertIn("No screenshots or cover scans here", window.gamebase_note.get())

    def make_source(self):
        source = self.dir / "gbsource"
        source.mkdir()
        for name in ("Screenshots.rar", "Extras.rar"):
            (source / name).write_bytes(b"rar")
        return source

    def wait_for(self, condition):
        deadline = time.time() + 10
        while not condition() and time.time() < deadline:
            ROOT.update()
            time.sleep(0.02)

    def test_the_gamebase_source_offers_to_extract_its_pictures(self):
        window = self.open("amiberry")
        self.assertFalse(window.extract_button.grid_info())                   # no folder: nothing to extract
        self.settings.gamebase_dir.set(str(self.make_source()))
        window.refresh_gamebase()
        self.assertIn("Gamebase source found", window.gamebase_note.get())
        self.assertTrue(window.extract_button.grid_info())                    # shown now
        self.settings.gamebase_dir.set(str(self.make_data_folder()))
        window.refresh_gamebase()
        self.assertFalse(window.extract_button.grid_info())                   # a data folder needs no extracting

    def test_extracting_asks_first_runs_in_the_background_and_reports_success(self):
        from common import gamebase
        source, dest = self.make_source(), self.dir / "extracted"
        self.settings.gamebase_dir.set(str(source))
        window = self.open("amiberry")

        def fake_extract(folder, where, progress=None):
            progress("Extracting screenshots… 5 of 10 files")
            dest.mkdir()
            return "Extracted 2 screenshots and 1 cover scans."

        with mock.patch.object(gamebase, "extracted_dir", lambda: dest), \
                mock.patch.object(gamebase, "extract", fake_extract):
            self.box.askokcancel.return_value = True
            window.extract_gamebase()
            self.assertIn(str(dest), self.box.askokcancel.call_args[0][1])      # says where it goes
            self.wait_for(lambda: not window._extracting)
        self.box.showinfo.assert_called_once()
        self.assertIn("Extracted 2 screenshots", self.box.showinfo.call_args[0][1])
        self.assertEqual(str(window.extract_button.cget("state")), "normal")

    def extracted(self):
        dest = self.dir / "extracted"
        (dest / "Screenshots").mkdir(parents=True)
        (dest / "Screenshots" / "a.png").write_bytes(b"x" * 2048)
        return dest

    def test_the_delete_button_is_there_only_when_there_are_extracted_pictures(self):
        from common import gamebase
        dest = self.dir / "extracted"
        with mock.patch.object(gamebase, "extracted_dir", lambda: dest):
            window = self.open("amiberry")
            self.assertFalse(window.delete_button.grid_info())
            self.extracted()
            window.refresh_gamebase()
            self.assertTrue(window.delete_button.grid_info())

    def test_deleting_asks_first_then_removes_only_the_extracted_pictures(self):
        from common import gamebase
        dest = self.extracted()
        source = self.make_source()
        self.settings.gamebase_dir.set(str(source))
        with mock.patch.object(gamebase, "extracted_dir", lambda: dest):
            window = self.open("amiberry")
            self.box.askokcancel.return_value = False
            window.delete_gamebase()
            self.assertTrue(dest.exists())                                    # declined: nothing deleted
            self.box.askokcancel.return_value = True
            window.delete_gamebase()
            question = self.box.askokcancel.call_args[0][1]
            self.assertIn(str(dest), question)
            self.assertIn("2.0 KB", question)
            self.assertFalse(dest.exists())
            self.assertTrue((source / "Screenshots.rar").is_file())          # the source folder is untouched
            self.assertIn("Deleted 2.0 KB", self.box.showinfo.call_args[0][1])
            self.assertIn("Gamebase source found", window.gamebase_note.get())   # offers to extract again
            self.assertFalse(window.delete_button.grid_info())

    def test_a_deletion_that_fails_says_why(self):
        from common import gamebase
        dest = self.extracted()
        with mock.patch.object(gamebase, "extracted_dir", lambda: dest):
            window = self.open("amiberry")
            self.box.askokcancel.return_value = True
            with mock.patch.object(gamebase.shutil, "rmtree", side_effect=OSError("in use")):
                window.delete_gamebase()
        self.assertIn("in use", self.box.showerror.call_args[0][1])

    def test_declining_the_question_extracts_nothing(self):
        from common import gamebase
        self.settings.gamebase_dir.set(str(self.make_source()))
        window = self.open("amiberry")
        self.box.askokcancel.return_value = False
        with mock.patch.object(gamebase, "extract") as extract:
            window.extract_gamebase()
        extract.assert_not_called()
        self.assertFalse(window._extracting)

    def test_a_failed_extraction_says_why(self):
        from common import gamebase
        self.settings.gamebase_dir.set(str(self.make_source()))
        window = self.open("amiberry")
        self.box.askokcancel.return_value = True
        with mock.patch.object(gamebase, "extract", side_effect=gamebase.ExtractError(gamebase.NO_UNAR)):
            window.extract_gamebase()
            self.wait_for(lambda: not window._extracting)
        self.assertIn("unar not found", self.box.showerror.call_args[0][1])
        self.assertEqual(str(window.extract_button.cget("state")), "normal")

    def test_choosing_amiberry_is_remembered_without_refreshing_the_tabs(self):
        told = []
        self.settings.on_folders_changed = lambda: told.append(1)
        window = self.open("amiberry")
        with mock.patch.object(window_module.filedialog, "askdirectory", return_value=str(self.dir / "ami")):
            window._pick(self.settings.amiberry_dir, "title", changed=False)
        self.assertEqual((self.settings.amiberry_dir.get(), told), (str(self.dir / "ami"), []))
        self.assertIn("amiberry_dir", (self.dir / "settings.json").read_text())

    # --- the Amiberry data row ---------------------------------------------------------------------------

    def test_shows_where_the_amiberry_data_lives_and_that_it_has_not_been_created_yet(self):
        window = self.open("amiberry")
        self.assertEqual(window.amiberry_data.get(), str(self.home))
        note = window.amiberry_note.get()
        self.assertIn("not created yet", note)
        self.assertIn("Reset deletes it", note)
        self.assertIn("Saved games are kept", note)                    # saved games are said to be kept

    def test_the_note_shows_the_size_once_there_is_data(self):
        self.make_home()
        window = self.open("amiberry")
        self.assertIn("2.0 KB used", window.amiberry_note.get())

    def make_games(self):
        (self.games / "RocketAttack_v1.0" / "S").mkdir(parents=True)
        (self.games / "RocketAttack_v1.0" / "S" / "save.dat").write_bytes(b"x" * 2048)

    def test_the_saved_games_row_shows_what_is_there(self):
        window = self.open("amiberry")
        self.assertEqual(window.games_path.get(), str(self.games))
        self.assertIn("none yet", window.games_note.get())
        self.make_games()
        window.refresh_games_note()
        self.assertIn("1 game, 2.0 KB", window.games_note.get())

    def test_deleting_saved_games_asks_first_and_keeps_the_amiberry_data(self):
        self.make_games()
        self.make_home()
        window = self.open("amiberry")
        self.box.askokcancel.return_value = False
        window.delete_games()
        self.assertTrue(self.games.exists())                                # declined: nothing deleted
        self.box.askokcancel.return_value = True
        window.delete_games()
        question = self.box.askokcancel.call_args[0][1]
        self.assertIn(str(self.games), question)
        self.assertIn("saves and high scores", question)
        self.assertFalse(self.games.exists())
        self.assertTrue((self.home / "WHDBoot" / "WHDLoad").is_file())
        self.assertIn("Deleted 2.0 KB", self.box.showinfo.call_args[0][1])
        self.assertIn("none yet", window.games_note.get())

    def test_deleting_with_no_saved_games_says_so_and_a_running_game_stops_it(self):
        window = self.open("amiberry")
        window.delete_games()
        self.assertIn("no saved games", self.box.showinfo.call_args[0][1])
        self.box.askokcancel.assert_not_called()
        self.make_games()
        with mock.patch.object(window_module.amiberry, "running", lambda: True):
            window.delete_games()
        self.assertIn("running game", self.box.showinfo.call_args[0][1])
        self.assertTrue(self.games.exists())

    def test_reset_asks_first_then_deletes_and_updates_the_note(self):
        self.make_home()
        window = self.open("amiberry")
        self.box.askokcancel.return_value = True
        window.reset_amiberry_data()
        question = self.box.askokcancel.call_args[0][1]
        self.assertIn(str(self.home), question)
        self.assertIn("emulator/Kickstarts", question)         # the user's own ROMs are said to be safe
        self.assertFalse(self.home.exists())
        self.assertIn("not created yet", window.amiberry_note.get())
        self.assertIn("Deleted 2.0 KB", self.box.showinfo.call_args[0][1])
        self.assertIs(self.box.askokcancel.call_args.kwargs["parent"], window)    # the dialog belongs to this window

    def test_declining_keeps_everything(self):
        self.make_home()
        window = self.open("amiberry")
        self.box.askokcancel.return_value = False
        window.reset_amiberry_data()
        self.assertTrue((self.home / "WHDBoot" / "WHDLoad").is_file())

    def test_nothing_to_reset(self):
        window = self.open("amiberry")
        window.reset_amiberry_data()
        self.box.askokcancel.assert_not_called()
        self.assertIn("nothing to reset", self.box.showinfo.call_args[0][1])

    def test_not_while_a_game_is_running(self):
        self.make_home()
        window = self.open("amiberry")
        with mock.patch.object(window_module.amiberry, "running", lambda: True):
            window.reset_amiberry_data()
        self.box.askokcancel.assert_not_called()
        self.assertTrue(self.home.exists())
        self.assertIn("running game", self.box.showinfo.call_args[0][1])

    def test_open_shows_the_folder(self):
        window = self.open("amiberry")
        with mock.patch.object(window_module.amiberry, "open_folder") as opened:
            window.open_amiberry_data()
        opened.assert_called_once_with(self.home)


    # --- the Amiberry choices ----------------------------------------------------------------------------

    def pick(self, window, name, text):
        """Choose `text` in the drop-down called `name`, like the user does."""
        box = window.boxes[name]
        box.set(text)
        box.event_generate("<<ComboboxSelected>>")
        ROOT.update()

    def checkbutton(self, window, text):
        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "TCheckbutton" and child.cget("text") == text:
                    return child
                found = walk(child)
                if found:
                    return found
        return walk(window)

    def test_the_drop_downs_show_the_saved_choices_in_readable_words(self):
        self.settings.keyboard.set("b")
        self.settings.look.set("crt")
        window = self.open("amiberry")
        self.assertEqual(window.boxes["keyboard"].get(), "Layout B: cursor keys, Right Ctrl or Alt = fire")
        self.assertEqual(window.boxes["window"].get(), "Windowed")
        self.assertTrue(window.boxes["look"].get().startswith("CRT monitor"))

    def test_choosing_in_a_drop_down_changes_the_setting_and_saves_it(self):
        window = self.open("amiberry")
        self.pick(window, "keyboard", "None")
        self.pick(window, "window", "Fullscreen (borderless window)")
        self.pick(window, "look", "Scanlines")
        self.assertEqual(self.settings.amiberry_options(), rt.Options("", "fullscreen", "scanlines", False, True))
        self.assertIn('"look": "scanlines"', (self.dir / "settings.json").read_text())

    def test_the_two_checkboxes_change_their_settings(self):
        window = self.open("amiberry")
        self.checkbutton(window, "Close Amiberry when the game exits").invoke()
        self.checkbutton(window, "Show the WHDLoad splash screen").invoke()
        options = self.settings.amiberry_options()
        self.assertEqual((options.quit_on_exit, options.splash), (True, False))

    def test_a_change_made_elsewhere_is_shown(self):
        window = self.open("amiberry")
        self.settings.look.set("scanlines")
        self.assertEqual(window.boxes["look"].get(), "Scanlines")

    def test_the_note_says_which_choices_only_apply_to_lha_games(self):
        texts = label_texts(self.open("amiberry"))
        self.assertTrue([t for t in texts if "only apply to games that start from their .lha" in t])

    def test_looking_at_the_window_creates_nothing(self):
        self.settings.amiberry_exe = lambda: Path("/some/Amiberry")      # even with an Amiberry to ask
        self.open("amiberry")
        self.assertFalse(self.home.exists())
        self.assertFalse(self.home.parent.exists())

    # --- the Kickstart ROM panel -------------------------------------------------------------------------

    def test_the_rom_text_lists_known_roms_missing_files_and_ignored_files(self):
        report = RomReport(scanned=True, has_a600=False,
                           known=[("KS ROM v1.3 (A500,A1000,A2000) rev 34.5 (256k) [315093-02]", "k13.rom", True),
                                  ("KS ROM v3.1 (A1200) rev 40.68 (512k) [391773-01/391774-01]", "k31.rom", False)],
                           unknown=["Bad dump.rom"])
        text = rom_status_text(report)
        self.assertIn("✔ Kickstart v1.3 (A500,A1000,A2000) rev 34.5   k13.rom", text)
        self.assertIn("✘ Kickstart v3.1 (A1200) rev 40.68   k31.rom (the file is missing)", text)
        self.assertIn("✘ Bad dump.rom   not a known Kickstart dump: Amiberry ignores it", text)
        self.assertIn("No Kickstart 3.1 for the A500/A600", text)

    def test_the_kickstarts_readme_quotes_what_the_panel_really_says(self):
        readme = (Path(__file__).resolve().parents[2] / "emulator" / "Kickstarts" / "README.md").read_text(encoding="utf-8")
        panel = rom_status_text(RomReport(scanned=True, known=[("KS ROM v1.3 (A500,A1000,A2000) rev 34.5", "a.rom", False)],
                                          unknown=["b.rom"]))
        for phrase in ("not a known Kickstart dump: Amiberry ignores it", "(the file is missing)",
                       "No Kickstart 3.1 for the A500/A600", "✔ Kickstart v1.3 (A500,A1000,A2000) rev 34.5"):
            self.assertIn(phrase, readme)
        for phrase in ("not a known Kickstart dump: Amiberry ignores it", "(the file is missing)",
                       "No Kickstart 3.1 for the A500/A600", "Kickstart v1.3 (A500,A1000,A2000) rev 34.5"):
            self.assertIn(phrase, panel)                             # the panel really says what the README quotes
        for control in ("Kickstart ROMs", "Refresh", "Reset…", "Amiberry data"):
            self.assertIn(control, readme)                           # and the controls it tells you to use exist
        self.assertIn("launch a game", readme)

    def test_the_rom_text_without_the_a600_hint_and_before_any_scan(self):
        ok = RomReport(scanned=True, has_a600=True, known=[("KS ROM v3.1 (A500,A600,A2000) rev 40.63 (512k)", "a.rom", True)])
        self.assertNotIn("No Kickstart 3.1", rom_status_text(ok))
        self.assertIn("Launch a game once", rom_status_text(RomReport()))
        self.assertEqual(rom_status_text(RomReport(scanned=True, has_a600=True)), "Amiberry found no Kickstart ROMs.")

    def test_the_window_shows_the_report_and_refresh_asks_again(self):
        self.settings.amiberry_exe = lambda: Path("/x/Amiberry")
        reports = [RomReport(), RomReport(scanned=True, has_a600=True, known=[("KS ROM v1.3 (A500) rev 34.5", "k.rom", True)])]
        with mock.patch.object(window_module.amiberry, "rom_report", side_effect=lambda exe: reports.pop(0)):
            window = self.open("amiberry")
            self.assertIn("Launch a game once", window.rom_status.cget("text"))
            window.refresh_roms()
        self.assertIn("✔ Kickstart v1.3 (A500) rev 34.5", window.rom_status.cget("text"))

    def test_the_rom_panel_says_so_when_there_is_no_amiberry(self):
        window = self.open("amiberry")                       # setUp: no Amiberry
        self.assertIn("Amiberry not found", window.rom_status.cget("text"))

    # --- the game database and the update ----------------------------------------------------------------

    def write_database(self, games=11255):
        db = self.home / "WHDBoot" / "game-data" / "whdload_db.json"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_text('{"generated": "2026-11-04T15:49:50Z", "game_count": %d, "games": []}' % games)

    def wait_for_update(self, window):
        deadline = time.time() + 10
        while window._updating and time.time() < deadline:
            ROOT.update()
            time.sleep(0.02)
        self.assertFalse(window._updating)

    def test_the_database_line_says_when_there_is_none_and_what_there_is(self):
        self.assertIn("not downloaded yet", self.open("amiberry").database_info.get())
        self.write_database()
        window = SettingsWindow(ROOT, self.settings, "amiberry")
        self.windows.append(window)
        self.assertEqual(window.database_info.get(), "11,255 games, database of 2026-11-04")

    def test_an_update_runs_in_the_background_then_reports_what_changed(self):
        self.write_database(11000)
        self.settings.amiberry_exe = lambda: Path("/x/Amiberry")
        window = self.open("amiberry")

        def fake_update(exe, home=None):
            self.write_database(11255)
            return True, ""
        with mock.patch.object(window_module.amiberry, "update_whdboot", side_effect=fake_update) as update:
            window.update_whdboot()
            self.assertEqual(str(window.update_button.cget("state")), "disabled")      # no second click while it runs
            self.assertEqual(window.database_info.get(), "Updating…")
            self.wait_for_update(window)
        update.assert_called_once()
        self.assertEqual(str(window.update_button.cget("state")), "normal")
        self.assertEqual(window.database_info.get(), "11,255 games, database of 2026-11-04")
        self.assertEqual(self.box.showinfo.call_args[0][1], "Up to date: 11,255 games (it was 11,000).")

    def test_a_failed_update_shows_amiberrys_own_words(self):
        self.settings.amiberry_exe = lambda: Path("/x/Amiberry")
        window = self.open("amiberry")
        with mock.patch.object(window_module.amiberry, "update_whdboot", return_value=(False, "line1\nno network")):
            window.update_whdboot()
            self.wait_for_update(window)
        self.assertIn("no network", self.box.showerror.call_args[0][1])
        self.assertEqual(str(window.update_button.cget("state")), "normal")

    def test_no_update_without_amiberry_or_while_a_game_runs(self):
        window = self.open("amiberry")
        with mock.patch.object(window_module.amiberry, "update_whdboot") as update:
            window.update_whdboot()                                     # no Amiberry
            self.assertIn("Amiberry not found", self.box.showerror.call_args[0][1])
            self.settings.amiberry_exe = lambda: Path("/x/Amiberry")
            with mock.patch.object(window_module.amiberry, "running", lambda: True):
                window.update_whdboot()                                 # a game is open
            self.assertIn("running game", self.box.showinfo.call_args[0][1])
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
