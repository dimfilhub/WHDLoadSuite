"""The Browser tab's Launch in Amiberry button."""
import contextlib
import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from common import amiberry_runtime as rt
from common import gamepaths
from tabs.browser import tab as browser_tab
from tabs.browser.tab import BrowserTab
from tabs.builder import launcher as launcher_module

from tests.helpers import reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()

NAMES = ("Alien_v1.0", "RocketAttack_v1.0", "Rockford_v1.0")      # RocketAttack runs from a prepared drive


@unittest.skipIf(ROOT is None, "no display")
class LaunchButtonTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "downloads").mkdir()
        for name in NAMES:
            (self.dir / "downloads" / f"{name}.lha").write_bytes(b"x")
        self.downloads = tk.StringVar(master=ROOT, value=str(self.dir / "downloads"))
        self.folders = tuple(tk.StringVar(master=ROOT, value=str(self.dir / sub)) for sub in ("", "Whdload", "Executables"))
        self.options = rt.Options(keyboard="c", window="fullscreen", look="crt")
        self.settings = SimpleNamespace(amiberry_exe=lambda: Path("/x/Amiberry"), kickstarts_dir=lambda: Path("/k"),
                                        amiberry_options=lambda: self.options)
        box = mock.patch.object(browser_tab, "messagebox")
        self.messagebox = box.start()
        self.addCleanup(box.stop)
        ask = mock.patch.object(launcher_module, "messagebox")      # the question before preparing a game
        self.ask = ask.start().askokcancel
        self.addCleanup(ask.stop)
        self.tab = BrowserTab(ROOT, self.downloads, self.folders, settings=self.settings)
        self.addCleanup(self.tab.destroy)
        deadline = time.time() + 10
        while len(self.tab.rows) < len(NAMES) and time.time() < deadline:
            ROOT.update()
            time.sleep(0.02)
        self.assertEqual(len(self.tab.rows), len(NAMES))

    def click(self, index, shift=False, add=False):
        """A click on the row at `index` (the tree is not on screen in tests, so what it would find is faked)."""
        tree = self.tab.tree
        with mock.patch.object(tree, "identify_region", return_value="cell"), \
                mock.patch.object(tree, "identify_element", return_value="text"), \
                mock.patch.object(tree, "identify_row", return_value=str(index)), \
                mock.patch.object(self.tab, "restyle"), mock.patch.object(tree, "focus"):
            self.tab.toggle(SimpleNamespace(x=1, y=1, state=(0x1 if shift else 0) | (browser_tab.ADD_KEY if add else 0)))

    def test_a_click_selects_only_that_row(self):
        paths = [g.path for g in self.tab.rows]
        self.click(0)
        self.click(1)
        self.assertEqual(self.tab.picked, {paths[1]})              # the click moved the selection, it did not add
        self.click(2)
        self.assertEqual(self.tab.picked, {paths[2]})

    def test_clicking_the_selected_row_again_unselects_it(self):
        self.click(1)
        self.click(1)
        self.assertEqual(self.tab.picked, set())

    def test_cmd_click_adds_and_removes_single_rows(self):
        paths = [g.path for g in self.tab.rows]
        self.click(0)
        self.click(2, add=True)
        self.assertEqual(self.tab.picked, {paths[0], paths[2]})
        self.click(0, add=True)                                     # again: that row leaves the selection
        self.assertEqual(self.tab.picked, {paths[2]})
        self.click(1, add=True)
        self.click(0, shift=True)                                   # the range starts at the last Cmd+clicked row
        self.assertEqual(self.tab.picked, set(paths))
        self.click(1)                                               # a plain click is back to one row
        self.assertEqual(self.tab.picked, {paths[1]})

    def test_shift_click_still_selects_a_range(self):
        paths = [g.path for g in self.tab.rows]
        self.click(0)
        self.click(2, shift=True)
        self.assertEqual(self.tab.picked, set(paths[:3]))
        self.click(1)                                              # a plain click starts again with one row
        self.assertEqual(self.tab.picked, {paths[1]})

    def pick(self, *names):
        self.tab.picked = {self.dir / "downloads" / f"{n}.lha" for n in names}

    def finish(self):
        deadline = time.time() + 10
        while self.tab.launcher.busy and time.time() < deadline:
            ROOT.update()
            time.sleep(0.02)
        self.assertFalse(self.tab.launcher.busy)

    @contextlib.contextmanager
    def backend(self):
        """Amiberry and the preparation replaced; yields the list of what was done, in order."""
        done = []
        with mock.patch.object(launcher_module.core, "ensure_prepared", side_effect=lambda *a, **k: done.append("prepare")), \
                mock.patch.object(launcher_module.amiberry, "launch_game", side_effect=lambda *a, **k: done.append("launch")) as launch:
            self.launch_game = launch
            yield done

    def test_exactly_one_game_must_be_selected(self):
        with self.backend() as done:
            self.tab.launch()                                  # none selected
            self.pick("Alien_v1.0", "Rockford_v1.0")
            self.tab.launch()                                  # two selected
        self.assertEqual(done, [])
        self.assertEqual(self.messagebox.showinfo.call_count, 2)
        self.assertIn("exactly one", self.messagebox.showinfo.call_args[0][1])

    def test_a_normal_game_is_launched_without_any_question(self):
        self.pick("Rockford_v1.0")
        with self.backend() as done:
            self.tab.launch()
            self.finish()
        self.ask.assert_not_called()
        self.assertEqual(done, ["prepare", "launch"])               # prepare is a no-op for this game
        self.assertEqual(self.launch_game.call_args[0][1].name, "Rockford_v1.0.lha")
        self.assertEqual(self.launch_game.call_args.kwargs["options"], self.options)        # the user's choices go along
        self.assertEqual(self.launch_game.call_args[0][2], self.dir / "Whdload" / "R" / "Rockford_v1.0")

    def test_a_game_that_needs_preparing_asks_first_and_can_be_cancelled(self):
        self.pick("RocketAttack_v1.0")
        self.ask.return_value = False
        with self.backend() as done:
            self.tab.launch()
        self.assertEqual(done, [])                                  # neither prepared nor started
        self.assertFalse(self.tab.launcher.busy)
        title, question = self.ask.call_args[0][:2]
        self.assertEqual(title, "Launch in Amiberry")
        self.assertIn("RocketAttack_v1.0 needs a prepared drive", question)
        self.assertIn("prepared now", question)

    def test_a_confirmed_game_is_prepared_then_started_and_reported_in_the_status_line(self):
        self.pick("RocketAttack_v1.0")
        self.ask.return_value = True
        with self.backend() as done:
            self.tab.launch()
            self.assertIn("Preparing and starting RocketAttack_v1.0", self.tab.status.cget("text"))
            self.finish()
        self.assertEqual(done, ["prepare", "launch"])
        exe, archive, drive, kickstarts = self.launch_game.call_args[0]
        self.assertEqual((exe, archive.name, kickstarts), (Path("/x/Amiberry"), "RocketAttack_v1.0.lha", Path("/k")))
        self.assertEqual(drive, self.dir / "Whdload" / "R" / "RocketAttack_v1.0")
        self.assertEqual(self.tab.status.cget("text"), "Launched RocketAttack_v1.0 in Amiberry.")

    def test_no_question_once_the_drive_exists(self):
        gamepaths.drive_path("RocketAttack_v1.0", self.dir).mkdir(parents=True)
        self.pick("RocketAttack_v1.0")
        with self.backend() as done:
            self.tab.launch()
            self.finish()
        self.ask.assert_not_called()
        self.assertIn("launch", done)

    def test_a_failure_is_shown(self):
        self.pick("Rockford_v1.0")
        with mock.patch.object(launcher_module.amiberry, "launch_game", side_effect=RuntimeError("No Kickstart ROM")):
            self.tab.launch()
            self.finish()
        self.messagebox.showerror.assert_called_once_with("Launch in Amiberry", "No Kickstart ROM")
        self.assertIn("Could not start Rockford_v1.0", self.tab.status.cget("text"))

    def test_no_amiberry_is_explained(self):
        self.pick("Rockford_v1.0")
        self.settings.amiberry_exe = lambda: None
        with self.backend() as done:
            self.tab.launch()
        self.assertEqual(done, [])
        self.assertIn("Amiberry not found", self.messagebox.showerror.call_args[0][1])

    def test_the_button_is_in_the_top_bar_next_to_send_to_builder(self):
        top = self.tab.launch_btn.master
        self.assertEqual(top.pack_info()["side"], "top")                         # the button row, not the bottom bar
        labels = [w.cget("text") for w in top.pack_slaves() if w.winfo_class() in ("TButton", "Button")]
        self.assertEqual(set(labels), {"Launch in Amiberry", "Review selection", "Clear selection", "Refresh"})
        self.assertNotIn("Export CSV…", labels)                                  # that button is gone
        self.assertEqual(self.tab.launch_btn.pack_info()["side"], "right")
        sent = BrowserTab(ROOT, self.downloads, self.folders, on_send=lambda paths: None, settings=self.settings)
        self.addCleanup(sent.destroy)
        order = [w.cget("text") for w in sent.launch_btn.master.pack_slaves() if w.winfo_class() == "TButton" and w.pack_info()["side"] == "right"]
        self.assertEqual(order[:2], ["Send to Builder", "Launch in Amiberry"])   # packed right: Send first, Launch to its left
        self.assertNotIn("Launch in Amiberry", [w.cget("text") for w in sent.status.master.pack_slaves() if w.winfo_class() == "TButton"])

    def test_the_filters_and_the_buttons_have_a_row_each_and_the_window_may_not_get_narrower_than_either(self):
        filters, buttons = self.tab._bars
        self.assertNotEqual(filters, buttons)
        self.assertIn("Clear filters", [w.cget("text") for w in filters.pack_slaves() if w.winfo_class() == "TButton"])
        ROOT.update_idletasks()
        self.assertGreaterEqual(self.tab.min_width(), max(filters.winfo_reqwidth(), buttons.winfo_reqwidth()))
        self.assertLess(self.tab.min_width(), 1000)           # far less than the single row it replaced (about 1600)

    def test_facets_without_values_get_no_empty_frame(self):
        frames = [w for w in self.tab.side.winfo_children() if w.winfo_class() == "TLabelframe"]
        shown = [f.cget("text") for f in frames]
        self.assertIn("Language", shown)
        self.assertEqual(len(frames), len(shown))
        for empty in ("Platform", "Memory", "Media", "Other tags (≥2)"):         # none of the three test games has any
            self.assertNotIn(empty, shown)
        self.assertEqual(self.tab.vars["platform"], {})                           # the facet itself still exists

    def test_there_is_no_export_any_more(self):
        self.assertFalse(hasattr(self.tab, "export"))

    def test_the_button_exists_only_when_the_tab_can_launch(self):
        self.assertTrue(hasattr(self.tab, "launch_btn"))
        plain = BrowserTab(ROOT, self.downloads, self.folders)
        self.addCleanup(plain.destroy)
        self.assertFalse(hasattr(plain, "launch_btn"))


if __name__ == "__main__":
    unittest.main()
