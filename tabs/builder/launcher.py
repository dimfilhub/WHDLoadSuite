"""Starting a game in Amiberry from a tab (Builder, Browser) without freezing the window.

The first launch downloads WHDLoad and a few games are prepared first, so the work runs in a background thread; the
tab is told what is happening through callbacks, always on the window thread.
"""
import queue
import threading
from pathlib import Path
from tkinter import messagebox

from common import amiberry, amiberry_runtime
from common.gamepaths import drive_path, game_name

from . import core, launch_screen

NO_AMIBERRY = "Amiberry not found. Put it in the emulator folder or choose it in Settings > Amiberry…."


class GameLauncher:
    def __init__(self, widget, settings, on_status, on_error, on_launched=None, title="Launch"):
        """widget: any Tk widget (its `after` polls for the result); settings: the AppSettings (Amiberry and
        Kickstart locations); on_status(text), on_error(text) and on_launched() report back to the tab; title: the
        title of the question asked before a game is prepared."""
        self.widget, self.settings, self.title = widget, settings, title
        self.on_status, self.on_error, self.on_launched = on_status, on_error, on_launched
        self._results: queue.Queue = queue.Queue()
        self.busy = False

    def launch(self, archive: Path, work_dir: Path, whdload_dir: Path) -> bool:
        """Start the game in the background; False if nothing was started (already busy, no Amiberry, or the user
        declined). The launch screen comes first (unless switched off in the settings); a game that needs a prepared
        drive is announced there, or in a question when the screen is off, because preparing it takes a moment and
        writes the drive into the Whdload folder."""
        if self.busy:
            return False
        exe = self.settings.amiberry_exe()
        if exe is None:
            self.on_error(NO_AMIBERRY)
            return False
        name = game_name(archive)
        drive = drive_path(name, work_dir, whdload_dir)
        kickstarts = self.settings.kickstarts_dir()
        options = self.settings.amiberry_options()          # read here, on the window thread
        first = not amiberry_runtime.has_whdload(amiberry_runtime.home_dir())
        preparing = core.needs_preparing(archive, work_dir, whdload_dir)
        if self._screen_wanted():
            # the launch screen shows the game's picture, lets the user change the options for this launch, and says
            # when the game has to be prepared first, so it replaces the question below
            found = self.settings.game_image(archive.stem)
            options = launch_screen.ask(self.widget, name, options, found[0] if found else None,
                                        found[1] if found else "", preparing, self.settings)
            if options is None:
                return False
        elif preparing and not messagebox.askokcancel(
                self.title,
                f"{name} needs a prepared drive, which does not exist yet.\n\nIt will be prepared now (this takes "
                f"a moment) and then started.\n\nContinue?"):
            return False
        self.on_status(f"{'Preparing and starting' if preparing else 'Starting'} {name}…"
                       + (" First launch: copying your ROMs and downloading WHDLoad." if first else ""))

        def start():
            try:
                core.ensure_prepared(archive, work_dir, whdload_dir)
                amiberry.launch_game(exe, archive, drive, kickstarts, options=options)
                self._results.put((name, None))
            except (RuntimeError, OSError, ValueError) as exc:
                self._results.put((name, str(exc)))

        self.busy = True
        threading.Thread(target=start, daemon=True).start()
        self.widget.after(200, self._poll)
        return True

    def _screen_wanted(self) -> bool:
        """Whether to show the launch screen: the user has not switched it off (settings from tests or the command
        line may not have the option at all)."""
        flag = getattr(self.settings, "launch_screen", None)
        return flag is not None and flag.get() and hasattr(self.settings, "game_image")

    def _poll(self):
        try:
            name, error = self._results.get_nowait()
        except queue.Empty:
            self.widget.after(200, self._poll)
            return
        self.busy = False
        if error:
            self.on_status(f"Could not start {name}.")
            self.on_error(error)
        else:
            if self.on_launched:
                self.on_launched()       # first: the tab may refresh its status line, and the message must win
            self.on_status(f"Launched {name} in Amiberry.")
