"""Whole-app check that does not care how the code is organised into folders: the main window builds all
five tabs. (The command line is tested in tests/amigaexec/test_cli.py.)"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


WINDOW_SCRIPT = """
import json, sys, tkinter as tk
sys.path.insert(0, sys.argv[1])
import gui
out = {}
def fake_mainloop(root):
    notebook = next(w for w in root.winfo_children() if w.winfo_class() == "TNotebook")
    out["tabs"] = [notebook.tab(i, "text") for i in range(notebook.index("end"))]
    out["selected"] = notebook.tab(notebook.select(), "text")
    out["title"] = root.title()
    out["menu"] = bool(root.cget("menu"))
    out["minsize"] = list(root.minsize())
    menubar = root.nametowidget(root.cget("menu"))
    out["menus"] = [menubar.entrycget(i, "label") for i in range(menubar.index("end") + 1)]
    settings_menu = root.nametowidget(menubar.entrycget(0, "menu"))
    out["settings_items"] = [settings_menu.entrycget(i, "label") for i in range(settings_menu.index("end") + 1)]
    for index in (0, 0, 1, 2):                                 # Browser… twice: still a single window
        settings_menu.invoke(index)
    root.update()
    out["settings_windows"] = sorted(w.title() for w in root.winfo_children() if w.winfo_class() == "Toplevel")
    for w in [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"]:
        w.destroy()
    gui.show_help(root)
    gui.show_about(root)
    root.update()
    helps = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel" and w.title().endswith("Help")]
    out["help_pages"] = len(helps[0].pages)
    out["help_map"] = gui.HELP_PAGES

    def texts(widget):
        for child in widget.winfo_children():
            if isinstance(child, tk.Text):
                yield child.get("1.0", "end")
            yield from texts(child)
    out["help_and_about"] = "\\n".join(texts(root))
    root.destroy()
tk.Tk.mainloop = fake_mainloop
gui.main()
print(json.dumps(out))
"""


class MainWindowTest(unittest.TestCase):
    def test_builds_all_tabs_in_order(self):
        """Runs gui.main() in a fresh process: on macOS, creating a throw-away Tk window first (as a
        display check) crashes the real one, and a fresh process also keeps this test isolated."""
        with tempfile.TemporaryDirectory() as home:
            # keep the per-user settings (last image, FTP login...) out of the test
            env = {**os.environ, "HOME": home, "XDG_CONFIG_HOME": home, "APPDATA": home}
            result = subprocess.run([sys.executable, "-c", WINDOW_SCRIPT, str(ROOT)], env=env, cwd=home,
                                    capture_output=True, text=True, timeout=120)
        if "couldn't connect to display" in result.stderr or "no display name" in result.stderr:
            self.skipTest("no display available")
        self.assertEqual(result.returncode, 0, result.stderr)
        seen = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(seen["tabs"], ["Browser", "Builder", "Downloader", "HDCommander (experimental)"])
        self.assertEqual(set(seen["help_map"]), set(seen["tabs"]))     # F1 knows the Help page of every tab
        self.assertEqual(seen["menus"], ["Settings", "Help"])
        self.assertEqual(seen["settings_items"], ["Browser…", "Builder…", "Amiberry…"])
        self.assertEqual(seen["settings_windows"], ["Amiberry settings", "Browser settings", "Builder settings"])
        self.assertEqual(seen["selected"], "Browser")            # the app starts on the Browser tab
        self.assertTrue(seen["title"].startswith("WHDLoadSuite v"))
        self.assertTrue(seen["menu"])
        self.assertGreaterEqual(seen["minsize"][0], 640)    # at least the base width; the Browser adds what its button row needs (its own tests check that)
        self.assertLess(seen["minsize"][0], 1000)           # ...but not the single 1600-point row it used to need
        text = seen["help_and_about"]
        self.assertIn("Welcome to WHDLoadSuite", text)                 # the Help opens on its first page
        self.assertIn("WHDLoadSuite runs WHDLoad", text)               # and the About window opened too
        self.assertEqual(seen["help_pages"], 25)                       # the contents tree is filled in


if __name__ == "__main__":
    unittest.main()
