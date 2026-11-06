"""The app's settings: the folder choices shared by the tabs, remembered between runs.

AppSettings holds them (as Tk variables, so the tabs can follow changes); the windows in window.py let the user
change them, from the Settings menu.
"""
import json
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from dataclasses import asdict

from common import amiberry, gamebase
from common.amiberry_runtime import Options
from common.paths import DEFAULT_WORK_DIR, EMULATOR_DIR, SETTINGS_FILE

KIND = "App" if sys.platform == "darwin" else "Exe"  # macOS builds .app bundles


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_options() -> Options:
    """The Amiberry choices saved by the app (Settings > Amiberry…), for the command line, which has no window."""
    return Options.from_dict(load_settings().get("amiberry_options"))


def load_launch_screen():
    """(show a launch screen, GamebaseAmiga folder, which picture) as saved by the app, for the command line."""
    raw = load_settings()
    image = raw.get("launch_image")
    return (bool(raw.get("launch_screen", True)), str(raw.get("gamebase_dir") or ""),
            image if image in gamebase.MODES else "best")


class AppSettings:
    """Owns the folder variables; the Browser, Builder, Downloader and HDCommander tabs share them."""

    def __init__(self, master):
        raw = load_settings()
        saved = {k: v for k, v in raw.items() if isinstance(v, str) and v and Path(v).is_dir()}  # drop stale paths
        self.work_dir = tk.StringVar(master, value=saved.get("work_dir", str(DEFAULT_WORK_DIR)))
        # a saved folder that no longer exists falls back to its default inside the work folder
        self.whdload_dir = tk.StringVar(master, value=saved.get("whdload_dir", str(Path(self.work_dir.get()) / "Whdload")))
        self.exe_dir = tk.StringVar(master, value=saved.get("exe_dir", str(Path(self.work_dir.get()) / "Executables")))
        self.downloads = tk.StringVar(master, value=saved.get("downloads", saved.get("sources", str(DEFAULT_WORK_DIR / "downloads"))))
        self.amiberry_dir = tk.StringVar(master, value=saved.get("amiberry_dir", ""))   # empty = emulator/ folder, then usual spots
        self.gamebase_dir = tk.StringVar(master, value=saved.get("gamebase_dir", ""))   # GamebaseAmiga data folder (pictures)
        self.launch_screen = tk.BooleanVar(master, value=bool(raw.get("launch_screen", True)))
        image = raw.get("launch_image")
        self.launch_image = tk.StringVar(master, value=image if image in gamebase.MODES else "best")
        for var in (self.launch_screen, self.launch_image):
            var.trace_add("write", lambda *_: self.save_settings())
        options = Options.from_dict(raw.get("amiberry_options"))
        self.keyboard = tk.StringVar(master, value=options.keyboard)       # "a".."d", or "" for none
        self.window = tk.StringVar(master, value=options.window)           # "windowed" / "fullscreen"
        self.look = tk.StringVar(master, value=options.look)               # "normal" / "scanlines" / "crt"
        self.quit_on_exit = tk.BooleanVar(master, value=options.quit_on_exit)
        self.splash = tk.BooleanVar(master, value=options.splash)
        for var in (self.keyboard, self.window, self.look, self.quit_on_exit, self.splash):
            var.trace_add("write", lambda *_: self.save_settings())        # a choice is kept the moment it is made
        self.on_downloads_changed: Callable[[], None] | None = None   # set by main(): refreshes the other tabs
        self.on_folders_changed: Callable[[], None] | None = None   # set by main(): the prepared/executable markers

    def save_settings(self):
        try:
            SETTINGS_FILE.write_text(json.dumps({"work_dir": self.work_dir.get(), "downloads": self.downloads.get(),
                                                 "whdload_dir": self.whdload_dir.get(), "exe_dir": self.exe_dir.get(),
                                                 "amiberry_dir": self.amiberry_dir.get(),
                                                 "gamebase_dir": self.gamebase_dir.get(),
                                                 "launch_screen": self.launch_screen.get(),
                                                 "launch_image": self.launch_image.get(),
                                                 "amiberry_options": asdict(self.amiberry_options())}))
        except OSError:
            pass

    def amiberry_options(self) -> Options:
        """What the user chose in Settings > Amiberry…: used for every game launched and executable built."""
        return Options.from_dict({"keyboard": self.keyboard.get(), "window": self.window.get(), "look": self.look.get(),
                                  "quit_on_exit": self.quit_on_exit.get(), "splash": self.splash.get()})

    def game_image(self, archive_stem: str):
        """(file, "screenshot"/"cover") of the game's picture in the chosen GamebaseAmiga folder, or None."""
        return gamebase.find_image(self.gamebase_dir.get(), archive_stem, self.launch_image.get())

    def amiberry_exe(self):
        """The Amiberry binary: the chosen folder or app if it holds one, else the usual places; None if not found."""
        return amiberry.find(self.amiberry_dir.get().strip() or None)

    def kickstarts_dir(self) -> Path:
        """Where the user's Kickstart ROMs live; Amiberry gets copies of them in its own folder."""
        return EMULATOR_DIR / "Kickstarts"

    # --- changing a folder: remember it and tell the tabs ------------------------------------------------

    def set_downloads(self, path):
        self.downloads.set(str(path))
        self.save_settings()
        if self.on_downloads_changed:
            self.on_downloads_changed()

    def set_work_dir(self, path):
        old = Path(self.work_dir.get())
        for var, sub in ((self.whdload_dir, "Whdload"), (self.exe_dir, "Executables")):
            if Path(var.get()) == old / sub:   # still the default: follow the work folder
                var.set(str(Path(path) / sub))
        self.work_dir.set(str(path))
        self.save_settings()
        if self.on_folders_changed:
            self.on_folders_changed()

    def set_folder(self, var: tk.StringVar, path):
        var.set(str(path))
        self.save_settings()
        if self.on_folders_changed:
            self.on_folders_changed()
