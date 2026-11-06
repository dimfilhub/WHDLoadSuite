import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from tabs.hdcommander import HdfVolume
from tabs.hdcommander import tab as gui_tab
from tabs.hdcommander.tab import HdCommanderTab
from tests.helpers import make_adf, make_lha, make_rdb_image, workbench_disks, reset_root, shared_root
from common.settings import Settings

ROOT = shared_root()


def tearDownModule():
    reset_root()


class Answers:
    """Scripted stand-in for dialogs.choose: answers by dialog title and records what was shown.
    A dialog without a scripted answer is accepted, like clicking its first button."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, parent, title, message, buttons, default=0, cancel=None, heading=None, mono=None,
                 footer=None):
        self.calls.append({"title": title, "message": message, "buttons": [b[1] for b in buttons],
                           "heading": heading, "mono": mono, "footer": footer, "default": default})
        return self.answers[title] if title in self.answers else buttons[0][1]


@unittest.skipIf(ROOT is None, "no display")
class GuiTabTest(unittest.TestCase):
    def setUp(self):
        # Registered first, so it runs last: collect this test's Tk objects on the main thread (otherwise the
        # cyclic GC may free their variables later from a worker thread, which Tk reports as an error).
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.src = self.dir / "downloads"
        self.src.mkdir()
        (self.src / "Alien_v1.0_De.lha").write_bytes(make_lha({"Alien/Alien.slave": b"S" * 100}))
        (self.src / "notes.txt").write_bytes(b"hello")
        self.settings = Settings(self.dir / "settings.json")
        self.downloads = tk.StringVar(master=ROOT, value=str(self.src))
        self.tab = HdCommanderTab(ROOT, self.downloads, settings=self.settings)
        self.addCleanup(self.tab.destroy)
        self.dlg = Answers({})          # default: accept every dialog (tests script their own where it matters)
        patch = mock.patch.object(gui_tab.dialogs, "choose", self.dlg)
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_tab_says_it_is_experimental_and_tells_you_to_keep_a_backup(self):
        self.assertEqual(gui_tab.TAB_LABEL, "HDCommander (experimental)")
        self.assertEqual(self.tab.notice.cget("text"), gui_tab.EXPERIMENTAL_NOTICE)
        for needed in ("EXPERIMENTAL", "backup", "copy"):
            self.assertIn(needed, gui_tab.EXPERIMENTAL_NOTICE)
        self.assertEqual(self.tab.notice.winfo_manager(), "pack")           # it is on the tab, above the toolbar
        first = self.tab.pack_slaves()[0]
        self.assertIs(first, self.tab.notice)

    def wait(self):
        deadline = time.time() + 15
        while time.time() < deadline:
            ROOT.update()
            if not self.tab.busy and self.tab.events.empty():
                break
            time.sleep(0.02)
        for worker in list(self.tab._workers):
            worker.join(5)            # let the threads finish before the tab is destroyed
        ROOT.update()

    def select(self, panel, name):
        idx = [e.name for e in panel.entries].index(name)
        panel.tree.selection_set(str(idx))

    def new_image(self, name="t.hdf"):
        path = self.dir / name
        self.tab._set_volume(HdfVolume.create(str(path), 8), str(path))
        return path

    def test_test_image_needs_amiberry(self):
        self.new_image()
        self.tab._emulator = lambda: (None, None, gui_tab.amiberry.Options())
        with mock.patch.object(self.tab, "error") as error, mock.patch.object(gui_tab.amiberry, "launch_hdf") as launch:
            self.tab.test_image()
        launch.assert_not_called()
        self.assertIn("Amiberry not found", error.call_args[0][0])
        self.assertIsNotNone(self.tab.volume)            # the image stays open: nothing was started

    def test_test_image_boots_it_in_amiberry_and_reopens_it_afterwards(self):
        path = self.new_image()
        exe, kickstarts = Path("/x/Amiberry"), self.dir / "Kickstarts"
        options = gui_tab.amiberry.Options(keyboard="b", look="crt")
        self.tab._emulator = lambda: (exe, kickstarts, options)
        proc = mock.Mock()
        proc.poll.return_value = 0                         # the emulator is already closed
        with mock.patch.object(gui_tab.amiberry, "launch_hdf", return_value=proc) as launch:
            self.tab.test_image()
            deadline = time.time() + 10
            while self.tab._emu_proc is not None and time.time() < deadline:
                ROOT.update()
                time.sleep(0.02)
        launch.assert_called_once_with(exe, path, kickstarts, options)       # the user's choices go along
        self.assertIsNone(self.tab._emu_proc)
        self.assertIsNotNone(self.tab.volume)              # reopened once the emulator quit

    def test_starts_in_downloads_without_image(self):
        self.assertEqual(self.tab.host.loc.path, self.src.resolve())
        self.assertIn("Alien_v1.0_De.lha", [e.name for e in self.tab.host.entries])
        self.assertIsNone(self.tab.hdf.loc)
        self.tab.copy()                         # no image: must not crash or start work
        self.assertFalse(self.tab.busy)

    def test_install_lha_and_copy_back(self):
        path = self.new_image()
        self.assertEqual(self.settings.get(gui_tab.SETTING_IMAGE), str(path))
        self.select(self.tab.host, "Alien_v1.0_De.lha")
        self.tab.set_active(self.tab.host)
        self.tab.install_games()
        self.wait()
        self.assertEqual(self.tab.volume.read("Games/A/Alien/Alien.slave"), b"S" * 100)
        self.assertIn("Games", [e.name for e in self.tab.hdf.entries])
        # image -> host
        out = self.dir / "out"
        out.mkdir()
        self.tab.host.set_location(gui_tab.HostLocation(out))
        self.tab.hdf.loc.change_dir("Games")
        self.tab.hdf.reload()
        self.select(self.tab.hdf, "A")
        self.tab.set_active(self.tab.hdf)
        self.tab.copy()
        self.wait()
        self.assertEqual((out / "A" / "Alien" / "Alien.slave").read_bytes(), b"S" * 100)

    def test_click_on_title_bar_selects_pane(self):
        self.tab.set_active(self.tab.host)
        self.tab.hdf.header.event_generate("<Button-1>")
        ROOT.update()
        self.assertIs(self.tab.active, self.tab.hdf)
        self.tab.host.header.event_generate("<Button-1>")
        ROOT.update()
        self.assertIs(self.tab.active, self.tab.host)

    def test_install_whdload_action_and_kickstart_notice(self):
        from tests.helpers import distribution
        self.new_image()
        arc = self.dir / "WHDLoad_usr_small.lha"
        arc.write_bytes(distribution())
        dlg = Answers({"Install WHDLoad": "docs"})
        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=str(arc)), \
                mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.install_whdload()
            self.wait()
        self.assertEqual([c["title"] for c in dlg.calls], ["Install WHDLoad", "WHDLoad installed"])
        self.assertEqual(dlg.calls[0]["buttons"], ["docs", "nodocs", None])
        self.assertIn("documentation", dlg.calls[0]["message"])
        self.assertTrue(self.tab.volume.exists("C/WHDLoad"))
        self.assertTrue(self.tab.volume.exists("S/WHDLoad.prefs"))
        self.assertTrue(self.tab.volume.exists("Help/WHDLoad/History.txt"))     # chose "With documentation"
        self.assertTrue(self.tab.volume.isdir("Devs/Kickstarts"))
        notice = dlg.calls[1]                                                    # Kickstart notice shown
        self.assertIn("Devs:Kickstarts", notice["message"])
        self.assertIn("kick34005.A500", notice["mono"])                          # table in the mono panel
        self.assertIn("copyrighted", notice["footer"])

    def test_install_whdload_without_documentation(self):
        from tests.helpers import distribution
        self.new_image()
        arc = self.dir / "WHDLoad_usr_small.lha"
        arc.write_bytes(distribution())
        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=str(arc)), \
                mock.patch.object(gui_tab.dialogs, "choose", Answers({"Install WHDLoad": "nodocs"})):
            self.tab.install_whdload()
            self.wait()
        self.assertTrue(self.tab.volume.exists("C/WHDLoad"))
        self.assertFalse(self.tab.volume.exists("Help"))

    def _whdload_flow(self, copy_kickstarts):
        """Run Install WHDLoad with a Kickstart folder offered; copy_kickstarts is the user's reply."""
        from tests.helpers import distribution
        ks = self.dir / "ks"
        ks.mkdir(exist_ok=True)
        (ks / "kick34005.A500").write_bytes(b"rom")
        (ks / "notes.txt").write_text("not a rom")
        tab = HdCommanderTab(ROOT, self.downloads, settings=self.settings, kickstart_source=lambda: ks)
        self.addCleanup(tab.destroy)
        self.tab = tab
        self.new_image(f"k{copy_kickstarts}.hdf")
        arc = self.dir / "WHDLoad_usr_small.lha"
        arc.write_bytes(distribution())
        dlg = Answers({"Install WHDLoad": "nodocs", "Kickstart files": copy_kickstarts})
        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=str(arc)), \
                mock.patch.object(gui_tab.dialogs, "choose", dlg):
            tab.install_whdload()
            self.wait()
        return tab, dlg

    def test_user_can_accept_template_kickstarts(self):
        tab, dlg = self._whdload_flow(True)
        self.assertEqual([c["title"] for c in dlg.calls], ["Install WHDLoad", "Kickstart files", "WHDLoad installed"])
        offer = dlg.calls[1]
        self.assertEqual(offer["buttons"], [True, False])
        self.assertIn("kick34005.A500", offer["mono"])
        self.assertNotIn("notes.txt", offer["mono"])
        self.assertEqual(tab.volume.read("Devs/Kickstarts/kick34005.A500"), b"rom")
        self.assertIn("ROM found, .RTB missing", dlg.calls[2]["mono"])           # notice follows the copy

    def test_user_can_decline_template_kickstarts(self):
        tab, dlg = self._whdload_flow(False)
        self.assertEqual([c["title"] for c in dlg.calls], ["Install WHDLoad", "Kickstart files", "WHDLoad installed"])
        self.assertFalse(tab.volume.exists("Devs/Kickstarts/kick34005.A500"))    # nothing copied
        self.assertTrue(tab.volume.isdir("Devs/Kickstarts"))                     # folder still ready
        self.assertNotIn("found", dlg.calls[2]["mono"])                          # notice still shown

    def test_install_whdload_cancel_and_bad_archive(self):
        self.new_image()
        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=""):
            self.tab.install_whdload()                                           # cancelled file dialog
        self.assertFalse(self.tab.busy)
        junk = self.dir / "junk.lha"
        junk.write_bytes(make_lha({"Game/Game.slave": b"s"}))
        dlg = Answers({})
        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=str(junk)), \
                mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.install_whdload()
        self.assertEqual([c["title"] for c in dlg.calls], ["Install WHDLoad"])   # error notice, no question
        self.assertIn("not a WHDLoad distribution", dlg.calls[0]["message"])
        self.assertFalse(self.tab.busy)
        arc = self.dir / "ok.lha"
        from tests.helpers import distribution
        arc.write_bytes(distribution())
        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=str(arc)), \
                mock.patch.object(gui_tab.dialogs, "choose", Answers({"Install WHDLoad": None})):
            self.tab.install_whdload()                                           # Cancel at the docs question
        self.assertFalse(self.tab.volume.exists("C"))

    def test_delete_confirm_defaults_to_cancel_and_can_be_declined(self):
        self.new_image()
        self.tab.volume.mkdir("Keep")
        self.tab.hdf.reload()
        self.select(self.tab.hdf, "Keep")
        self.tab.set_active(self.tab.hdf)
        dlg = Answers({"Delete": False})
        with mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.delete()
        self.assertTrue(self.tab.volume.exists("Keep"))
        self.assertEqual(dlg.calls[0]["buttons"], [True, False])          # Delete / Cancel
        self.assertEqual(dlg.calls[0]["default"], 1)                      # Cancel is the default button

    def test_mkdir_cancelled_creates_nothing(self):
        self.new_image()
        self.tab.set_active(self.tab.hdf)
        with mock.patch.object(gui_tab.dialogs, "ask_text", return_value=None):
            self.tab.mkdir()
        self.assertEqual(self.tab.hdf.entries, [])

    def test_new_image_dialog_asks_size(self):
        path = self.dir / "new.hdf"
        with mock.patch.object(gui_tab.filedialog, "asksaveasfilename", return_value=str(path)), \
                mock.patch.object(gui_tab.dialogs, "ask_integer", return_value=8) as ask:
            self.tab.new_dialog()
        self.assertTrue(path.exists())
        self.assertEqual(self.tab.image_var.get(), str(path))
        self.assertEqual(ask.call_args[0][3:6], (256, 4, gui_tab.MAX_IMAGE_MB))   # default, min, max
        other = self.dir / "other.hdf"
        with mock.patch.object(gui_tab.filedialog, "asksaveasfilename", return_value=str(other)), \
                mock.patch.object(gui_tab.dialogs, "ask_integer", return_value=None):
            self.tab.new_dialog()                                                 # size prompt cancelled
        self.assertFalse(other.exists())

    def test_errors_and_notices_use_amiga_dialogs(self):
        bad = self.dir / "bad.hdf"
        bad.write_bytes(b"this is not an amiga disk image" * 100)
        dlg = Answers({})
        with mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.open_image(str(bad))
            self.tab.copy()                                                      # no image open
        self.assertIsNone(self.tab.volume)
        self.assertEqual([c["heading"] for c in dlg.calls], ["Error", "No image"])
        self.assertIn("Open or create an image", dlg.calls[1]["message"])

    def _make_bootable(self, answers=None, folder=None):
        self.new_image()
        floppies = workbench_disks(self.dir / "Floppies") if (self.dir / "Floppies").mkdir() is None else None
        dlg = Answers(answers or {})
        with mock.patch.object(gui_tab.filedialog, "askdirectory",
                               return_value=str(folder if folder is not None else floppies)), \
                mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.make_bootable()
            self.wait()
        return dlg, floppies

    def test_make_bootable_installs_workbench(self):
        dlg, floppies = self._make_bootable()
        self.assertEqual([c["title"] for c in dlg.calls], ["Make bootable", "Workbench installed"])
        question = dlg.calls[0]
        self.assertEqual(question["buttons"], ["PAL", "NTSC", None])
        for disk in ("Workbench3.1", "Install3.1", "Extras3.1", "Locale", "Fonts", "Storage3.1"):
            self.assertIn(disk, question["mono"])                             # the disks it found
        v = self.tab.volume
        self.assertEqual(v.read("S/Startup-Sequence"), b"; hard drive startup\n")
        self.assertEqual(v.read("Devs/Monitors/PAL"), b"pal driver")
        self.assertEqual(self.settings.get(gui_tab.SETTING_DISKS), str(floppies))   # the folder is remembered
        self.assertIn("Install WHDLoad", dlg.calls[1]["footer"])                    # points to the next step
        self.assertIn("C", [e.name for e in self.tab.hdf.entries])                  # the image pane shows it

    def test_make_bootable_ntsc_and_cancel(self):
        self._make_bootable({"Make bootable": "NTSC"})
        self.assertEqual(self.tab.volume.read("Devs/Monitors/NTSC"), b"ntsc driver")
        self.assertFalse(self.tab.volume.exists("Devs/Monitors/PAL"))

    def test_make_bootable_can_be_cancelled(self):
        dlg, _ = self._make_bootable({"Make bootable": None})
        self.assertEqual([c["title"] for c in dlg.calls], ["Make bootable"])        # no "installed" notice
        self.assertEqual(self.tab.volume.listdir(""), [])
        self.assertFalse(self.tab.busy)
        self.new_image("again.hdf")
        with mock.patch.object(gui_tab.filedialog, "askdirectory", return_value=""):
            self.tab.make_bootable()                                                # folder dialog cancelled
        self.assertEqual(self.tab.volume.listdir(""), [])

    def test_make_bootable_explains_missing_disks(self):
        empty = self.dir / "Empty"
        empty.mkdir()
        make_adf(empty / "Extras.adf", "Extras3.1", {"Tools/Calculator": b"calc"})
        dlg, _ = self._make_bootable(folder=empty)
        self.assertEqual(len(dlg.calls), 1)
        self.assertEqual(dlg.calls[0]["heading"], "Disks not found")
        self.assertIn("Workbench3.1", dlg.calls[0]["message"])
        self.assertIn("Install3.1", dlg.calls[0]["message"])
        self.assertEqual(self.tab.volume.listdir(""), [])

    def test_make_bootable_warns_when_replacing_a_startup_script(self):
        self.new_image()
        self.tab.volume.makedirs("S")
        self.tab.volume.put_bytes(b"; mine\n", "S/Startup-Sequence")
        floppies = workbench_disks(self.dir / "Floppies") if (self.dir / "Floppies").mkdir() is None else None
        dlg = Answers({})
        with mock.patch.object(gui_tab.filedialog, "askdirectory", return_value=str(floppies)), \
                mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.make_bootable()
            self.wait()
        self.assertIn("already has a startup script", dlg.calls[0]["message"])
        self.assertEqual(self.tab.volume.read("S/Startup-Sequence.old"), b"; mine\n")
        self.assertEqual(self.tab.volume.read("S/Startup-Sequence"), b"; hard drive startup\n")

    def test_reports_are_answered_before_the_next_dialog_opens(self):
        """After a run that skipped something, the report must be modal: the Kickstart question and the notice
        that follow grab the mouse, which made the report's Close button dead."""
        from tests.helpers import distribution
        ks = self.dir / "ks"
        ks.mkdir(exist_ok=True)
        (ks / "kick34005.A500").write_bytes(b"rom")
        tab = HdCommanderTab(ROOT, self.downloads, settings=self.settings, kickstart_source=lambda: ks)
        self.addCleanup(tab.destroy)
        self.tab = tab
        self.new_image("report.hdf")
        arc = self.dir / "WHDLoad_usr_small.lha"
        arc.write_bytes(distribution())
        order = []

        class Recorder(Answers):
            def __call__(self, parent, title, *args, **kw):
                order.append("dialog: " + title)
                return super().__call__(parent, title, *args, **kw)

        def fake_report(parent, title, text, modal=False):
            order.append(f"report(modal={modal}): {title}")

        with mock.patch.object(gui_tab.filedialog, "askopenfilename", return_value=str(arc)), \
                mock.patch.object(gui_tab.dialogs, "choose", Recorder({"Install WHDLoad": "nodocs"})), \
                mock.patch.object(gui_tab, "show_text", fake_report):
            tab.install_whdload()                    # first run: everything is new, no report
            self.wait()
            order.clear()
            tab.install_whdload()                    # second run: everything is skipped -> a report
            self.wait()
        reports = [o for o in order if o.startswith("report")]
        self.assertEqual(len(reports), 2, order)     # one for WHDLoad, one for the Kickstart files already there
        self.assertTrue(all("modal=True" in r for r in reports), reports)
        self.assertLess(order.index(reports[0]), order.index("dialog: Kickstart files"))

    def test_progress_bar_stays_full_until_the_results_window_is_closed(self):
        self.new_image()
        (self.src / ("x" * 31)).write_bytes(b"1")                  # cannot be copied: a results window opens
        self.tab.host.reload()
        self.select(self.tab.host, "x" * 31)
        self.tab.set_active(self.tab.host)
        seen = {}

        def results_window(parent, title, text, modal=False):
            seen["while_open"] = float(self.tab.progress.cget("value"))
            seen["modal"] = modal

        with mock.patch.object(gui_tab, "show_text", results_window):
            self.tab.copy()
            self.wait()
        self.assertEqual(seen["while_open"], 100.0)               # full while the results are on screen
        self.assertTrue(seen["modal"])
        self.assertEqual(float(self.tab.progress.cget("value")), 0.0)    # empty once Close was pressed

    def test_progress_bar_stays_full_after_a_clean_run_until_the_next_one(self):
        self.new_image()
        self.select(self.tab.host, "notes.txt")
        self.tab.set_active(self.tab.host)
        self.tab.copy()                                            # all ok: no results window
        self.wait()
        self.assertEqual(float(self.tab.progress.cget("value")), 100.0)
        self.select(self.tab.host, "Alien_v1.0_De.lha")
        with mock.patch.object(gui_tab.dialogs, "confirm", return_value=False):
            self.tab.copy()                                        # declined: nothing starts, bar is untouched
        self.assertEqual(float(self.tab.progress.cget("value")), 100.0)
        self.tab.volume.delete("notes.txt")
        self.select(self.tab.host, "notes.txt")
        self.tab._run("Copy", lambda progress: [])                 # a new run starts from empty
        self.assertEqual(float(self.tab.progress.cget("value")), 0.0)
        self.wait()

    def test_action_buttons_are_centered(self):
        self.tab.pack(fill="both", expand=True)
        ROOT.geometry("1000x600")
        ROOT.deiconify()                  # Windows only lays out a window that is actually shown
        self.addCleanup(ROOT.withdraw)
        ROOT.update()
        row, bar = self.tab.button_row, self.tab.button_row.master
        self.assertGreater(bar.winfo_width(), 900)
        left_gap = row.winfo_x()
        right_gap = bar.winfo_width() - (row.winfo_x() + row.winfo_width())
        self.assertLessEqual(abs(left_gap - right_gap), 2, (left_gap, right_gap))     # equal space on both sides
        self.assertEqual([b.cget("text") for b in self.tab.buttons][:3], ["View (F3)", "Install Game (F4)", "Copy (F5)"])
        self.tab.pack_forget()

    def test_opening_a_pfs3_image_explains_why_it_cannot_be_used(self):
        pfs = self.dir / "pfs.hdf"
        make_rdb_image(pfs, "PFS3")
        dlg = Answers({})
        with mock.patch.object(gui_tab.dialogs, "choose", dlg):
            self.tab.open_image(str(pfs))
        self.assertIsNone(self.tab.volume)
        self.assertEqual(len(dlg.calls), 1)
        self.assertEqual(dlg.calls[0]["heading"], "PFS3 images are not supported")
        self.assertIn("OFS and FFS", dlg.calls[0]["message"])
        self.assertIn("New", dlg.calls[0]["message"])

    def test_reopening_a_pfs3_image_at_startup_only_sets_the_status(self):
        pfs = self.dir / "pfs.hdf"
        make_rdb_image(pfs, "PFS3")
        self.settings.set(gui_tab.SETTING_IMAGE, str(pfs))
        dlg = Answers({})
        with mock.patch.object(gui_tab.dialogs, "choose", dlg):
            tab = HdCommanderTab(ROOT, self.downloads, settings=self.settings)
            self.addCleanup(tab.destroy)
        self.assertEqual(dlg.calls, [])                              # no dialog while starting up
        self.assertIsNone(tab.volume)
        self.assertIn("PFS3 file system", tab.status.get())
        self.assertIn("OFS/FFS", tab.status.get())

    def test_install_game_only_from_host_pane(self):
        self.new_image()
        self.tab.set_active(self.tab.hdf)
        self.tab.install_games()                       # image pane active: nothing happens
        self.assertFalse(self.tab.busy)
        self.assertFalse(self.tab.volume.exists("Games"))

    def test_copy_as_file_keeps_archive(self):
        self.new_image()
        self.select(self.tab.host, "Alien_v1.0_De.lha")
        self.tab.set_active(self.tab.host)
        self.tab.copy()
        self.wait()
        self.assertEqual(self.tab.volume.read("Alien_v1.0_De.lha"), (self.src / "Alien_v1.0_De.lha").read_bytes())
        self.assertFalse(self.tab.volume.exists("Games"))

    def test_mkdir_delete_navigation(self):
        self.new_image()
        self.tab.set_active(self.tab.hdf)
        with mock.patch.object(gui_tab.dialogs, "ask_text", return_value="Docs"):
            self.tab.mkdir()
        self.assertTrue(self.tab.volume.isdir("Docs"))
        self.tab.hdf.loc.change_dir("Docs")
        self.tab.hdf.reload()
        self.assertEqual([e.name for e in self.tab.hdf.entries], [".."])
        self.tab.hdf.up()
        self.assertEqual(self.tab.hdf.loc.path, "")
        self.select(self.tab.hdf, "Docs")
        self.tab.delete()
        self.assertFalse(self.tab.volume.exists("Docs"))

    def test_reopen_last_image_and_close(self):
        path = self.new_image()
        self.tab.volume.mkdir("Keep")
        self.tab.close_image()
        self.assertIsNone(self.tab.volume)
        self.assertEqual(self.settings.get(gui_tab.SETTING_IMAGE), "")
        self.settings.set(gui_tab.SETTING_IMAGE, str(path))
        tab2 = HdCommanderTab(ROOT, self.downloads, settings=self.settings)
        self.addCleanup(tab2.destroy)
        self.assertIn("Keep", [e.name for e in tab2.hdf.entries])

    def test_downloads_follow_unless_navigated(self):
        other = self.dir / "other"
        other.mkdir()
        self.downloads.set(str(other))
        self.tab.downloads_changed()
        self.assertEqual(self.tab.host.loc.path, other.resolve())
        self.tab.host.loc.change_dir("..")             # user navigates away
        elsewhere = self.tab.host.loc.path
        self.downloads.set(str(self.src))
        self.tab.downloads_changed()
        self.assertEqual(self.tab.host.loc.path, elsewhere)

    def test_failed_items_show_report(self):
        self.new_image()
        (self.src / ("x" * 31)).write_bytes(b"1")        # name too long for the Amiga
        self.tab.host.reload()
        self.select(self.tab.host, "x" * 31)
        self.tab.set_active(self.tab.host)
        with mock.patch.object(gui_tab, "show_text") as show:
            self.tab.copy()
            self.wait()
        self.assertTrue(show.called)
        self.assertIn("FAIL", show.call_args[0][2])


if __name__ == "__main__":
    unittest.main()
