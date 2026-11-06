import time
import tkinter as tk
import unittest
from unittest import mock
from tkinter import ttk

from common import dialogs

from tests.helpers import reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()


def widgets(w):
    for child in w.winfo_children():
        yield child
        yield from widgets(child)


def dialog_windows():
    return [w for w in ROOT.winfo_children() if isinstance(w, dialogs.AmigaDialog)]


def watchdog():
    """A dialog that never gets answered must fail the test, not hang it."""
    ROOT.after(8000, lambda: [w.destroy() for w in dialog_windows()])


def click_later(label, delay=50):
    """Press the button with this label in the open dialog; retries until the dialog exists."""
    def attempt():
        for dlg in dialog_windows():
            for w in widgets(dlg):
                if isinstance(w, ttk.Button) and w.cget("text") == label:
                    w.invoke()
                    return
        ROOT.after(30, attempt)
    ROOT.after(delay, attempt)
    watchdog()


def script(*steps):
    """Run steps one after another, each on the open dialog (for multi-step interaction)."""
    pending, tries = list(steps), [0]

    def run():
        tries[0] += 1
        if not pending or tries[0] > 250:
            return
        dialogs_open = dialog_windows()
        if dialogs_open:
            pending.pop(0)(dialogs_open[0])
        ROOT.after(30, run)
    ROOT.after(50, run)
    watchdog()


def type_into(dlg, text):
    entry = next(w for w in widgets(dlg) if isinstance(w, ttk.Entry))
    entry.delete(0, "end")
    entry.insert(0, text)


def press(dlg, label):
    next(w for w in widgets(dlg) if isinstance(w, ttk.Button) and w.cget("text") == label).invoke()


def close_later(how):
    def attempt():
        for dlg in dialog_windows():
            how(dlg)
            return
        ROOT.after(30, attempt)
    ROOT.after(50, attempt)
    watchdog()


@unittest.skipIf(ROOT is None, "no display")
class DialogsTest(unittest.TestCase):
    def tearDown(self):
        for w in list(ROOT.winfo_children()):
            w.destroy()

    def test_choose_returns_clicked_button_value(self):
        click_later("Without documentation")
        result = dialogs.choose(ROOT, "T", "msg", [("With documentation", "docs"),
                                                   ("Without documentation", "nodocs"), ("Cancel", None)])
        self.assertEqual(result, "nodocs")
        self.assertEqual(dialog_windows(), [])                     # closed after answering

    def test_a_dialog_answered_while_it_is_still_being_shown_is_not_waited_for(self):
        """On a slow machine the answer can arrive during the dialog's own update(); waiting for the destroyed window
        used to raise 'bad window path name'."""
        slow_update = dialogs.AmigaDialog.update

        def slow(dialog):
            time.sleep(0.3)
            slow_update(dialog)
        click_later("Yes", delay=10)
        with mock.patch.object(dialogs.AmigaDialog, "update", slow):
            self.assertIs(dialogs.confirm(ROOT, "T", "sure?"), True)

    def test_closing_the_window_gives_the_cancel_value(self):
        close_later(lambda d: d.protocol("WM_DELETE_WINDOW") and d.tk.call(d.protocol("WM_DELETE_WINDOW")))
        self.assertEqual(dialogs.choose(ROOT, "T", "msg", [("Yes", True), ("No", False)], cancel=False), False)

    def test_return_picks_default_and_escape_cancels(self):
        close_later(lambda d: d.on_return())
        self.assertEqual(dialogs.choose(ROOT, "T", "m", [("A", "a"), ("B", "b")], default=1), "b")
        close_later(lambda d: d.on_escape())
        self.assertEqual(dialogs.choose(ROOT, "T", "m", [("A", "a"), ("B", "b")], cancel="esc"), "esc")

    def test_amiga_look_and_content(self):
        seen = {}

        def inspect(dlg):
            seen["bg"] = dlg.cget("background")
            seen["texts"] = [w.cget("text") for w in widgets(dlg) if isinstance(w, (ttk.Label, tk.Label))]
            seen["transient"] = bool(dlg.wm_transient())
            for w in widgets(dlg):
                if isinstance(w, ttk.Button):
                    w.invoke()
                    break

        close_later(inspect)
        dialogs.message(ROOT, "Title", "the message", heading="Heading", mono="a  b\nc  d", footer="the footer")
        self.assertEqual(seen["bg"], "#0055aa")                    # Workbench blue, like About/Filters
        self.assertTrue(seen["transient"])
        for text in ("Heading", "the message", "a  b\nc  d", "the footer"):
            self.assertIn(text, seen["texts"])

    def test_confirm(self):
        click_later("Delete")
        self.assertIs(dialogs.confirm(ROOT, "T", "sure?", yes="Delete", no="Cancel"), True)
        click_later("Cancel")
        self.assertIs(dialogs.confirm(ROOT, "T", "sure?", yes="Delete", no="Cancel"), False)
        close_later(lambda d: d.on_escape())                      # Esc means No
        self.assertIs(dialogs.confirm(ROOT, "T", "sure?"), False)
        close_later(lambda d: d.on_return())                      # Return picks the default
        self.assertIs(dialogs.confirm(ROOT, "T", "sure?", default_yes=False), False)

    def test_ask_text_validates_and_cancels(self):
        seen = {}
        script(lambda d: (type_into(d, "   "), press(d, "OK")),             # blank is refused, dialog stays
               lambda d: seen.update(error=d.error_var.get()),
               lambda d: (type_into(d, " Docs "), press(d, "OK")))
        self.assertEqual(dialogs.ask_text(ROOT, "T", "Name?"), "Docs")        # trimmed
        self.assertIn("enter a name", seen["error"].lower())
        script(lambda d: press(d, "Cancel"))
        self.assertIsNone(dialogs.ask_text(ROOT, "T", "Name?"))
        script(lambda d: (type_into(d, "keep"), d.on_escape()))
        self.assertIsNone(dialogs.ask_text(ROOT, "T", "Name?", initial="x"))

    def test_ask_text_shows_initial_text(self):
        seen = {}
        script(lambda d: seen.update(text=d.entry_var.get()), lambda d: press(d, "OK"))
        self.assertEqual(dialogs.ask_text(ROOT, "T", "Name?", initial="DH0"), "DH0")
        self.assertEqual(seen["text"], "DH0")

    def test_ask_integer_range_and_errors(self):
        errors = []
        script(lambda d: (type_into(d, "abc"), press(d, "OK")),
               lambda d: errors.append(d.error_var.get()),
               lambda d: (type_into(d, "5000"), press(d, "OK")),
               lambda d: errors.append(d.error_var.get()),
               lambda d: (type_into(d, " 50 "), press(d, "OK")))
        self.assertEqual(dialogs.ask_integer(ROOT, "T", "MB?", 256, 4, 4000), 50)
        self.assertIn("whole number", errors[0])
        self.assertIn("4 to 4000", errors[1])
        script(lambda d: press(d, "Cancel"))
        self.assertIsNone(dialogs.ask_integer(ROOT, "T", "MB?", 256, 4, 4000))

    def test_modal_report_window_holds_the_grab_until_closed(self):
        """A report that is followed by another dialog must be answered first: otherwise the next dialog's grab
        makes its Close button dead."""
        state = {}

        def close_it():
            win = next(w for w in ROOT.winfo_children() if isinstance(w, tk.Toplevel))
            state["grab"] = win.grab_current()
            state["win"] = win
            next(w for w in widgets(win) if isinstance(w, ttk.Button) and w.cget("text") == "Close").invoke()

        ROOT.after(100, close_it)
        ROOT.after(8000, lambda: [w.destroy() for w in ROOT.winfo_children() if isinstance(w, tk.Toplevel)])
        win = dialogs.show_text(ROOT, "Report", "SKIP x  already exists", modal=True)    # returns once closed
        self.assertIs(state["grab"], state["win"])                    # it held the input grab while open
        self.assertFalse(win.winfo_exists())                          # and Close really closed it

    def test_plain_text_window_does_not_block(self):
        win = dialogs.show_text(ROOT, "Viewer", "text")               # the F3 viewer stays non-modal
        self.assertTrue(win.winfo_exists())
        win.destroy()

    def test_show_text_window(self):
        win = dialogs.show_text(ROOT, "Report", "FAIL x  boom")
        ROOT.update()
        boxes = [w for w in widgets(win) if isinstance(w, tk.Text)]
        self.assertEqual(boxes[0].get("1.0", "end").strip(), "FAIL x  boom")
        self.assertEqual(str(boxes[0].cget("state")), "disabled")      # read-only
        self.assertEqual(win.cget("background"), "#0055aa")
        win.destroy()


if __name__ == "__main__":
    unittest.main()
