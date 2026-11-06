"""The settings windows, opened from the Settings menu: one for the Browser, one for the Builder, one for Amiberry.

Each window shows the folder choices of its part of the app (kept in AppSettings) with a note on what each is.
A window that is already open is brought to the front instead of opening a second copy.
"""
import queue
import re
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from common import amiberry, amiberry_runtime, gamebase
from common.amiberry_runtime import KEYBOARD_CHOICES, LOOK_CHOICES, WINDOW_CHOICES
from common.dialogs import DARK_BLUE
from common.theme import WB_BLUE
from common.utils import human

from .settings import KIND

SECTIONS = ("browser", "builder", "amiberry")
TITLES = {"browser": "Browser settings", "builder": "Builder settings", "amiberry": "Amiberry settings"}
NOTE_COLOUR = "#ff8800"
NO_AMIBERRY = "Amiberry not found. Put it in the emulator folder or choose it in the Amiberry folder row above."

IMAGE_CHOICES = (("best", "Screenshot, else front cover"), ("screenshot", "Screenshot only"),
                 ("cover", "Front cover only"))


def rom_status_text(report) -> str:
    """What the Kickstart ROM panel says: which ROMs Amiberry recognised and which files it ignores."""
    if not report.scanned:
        return ("Amiberry has not listed the ROMs yet. Launch a game once (it copies your ROMs and scans them), then "
                "press Refresh.")
    lines = []
    for description, filename, exists in report.known:
        name = re.sub(r"\s*\[[^\]]*\]|\s*\(\d+k\)", "", description).replace("KS ROM", "Kickstart")
        lines.append(f"✔ {name}   {filename}" if exists else f"✘ {name}   {filename} (the file is missing)")
    for filename in report.unknown:
        lines.append(f"✘ {filename}   not a known Kickstart dump: Amiberry ignores it")
    if not report.has_a600:
        lines.append("")
        lines.append("No Kickstart 3.1 for the A500/A600: games that prefer one run as an A1200 instead "
                     "(most still work).")
    return "\n".join(lines) if lines else "Amiberry found no Kickstart ROMs."


class SettingsWindow(tk.Toplevel):
    _open: dict = {}            # section -> its window, so a second request shows the first

    @classmethod
    def show(cls, parent, settings, section):
        """Open the window for `section`, or bring the one that is already open to the front."""
        window = cls._open.get(section)
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            window.focus_set()
            return window
        cls._open[section] = window = cls(parent, settings, section)
        return window

    def __init__(self, parent, settings, section):
        super().__init__(parent)
        self.withdraw()              # stay hidden until built and centred, or it shows for a moment in the corner
        if section not in SECTIONS:
            raise ValueError(f"unknown settings section: {section}")
        self.settings, self.section = settings, section
        self.title(TITLES[section])
        self.configure(background=WB_BLUE)
        self.transient(parent.winfo_toplevel())
        self.minsize(880, 0)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        self.body = body
        self._notes = []        # the explanatory labels: they wrap to the width of the entry above them
        self._row = 0
        getattr(self, f"_build_{section}")()
        ttk.Button(body, text="Close", command=self.close).grid(row=self._row, column=0, columnspan=3, pady=(18, 0))
        if section != "amiberry":          # its two columns keep fixed note widths: wrapping to the entry would widen them
            self.first_entry.bind("<Configure>",
                                  lambda e: [n.configure(wraplength=max(200, e.width - 8)) for n in self._notes])
        self._centre(parent)
        self.deiconify()

    def close(self):
        SettingsWindow._open.pop(self.section, None)
        self.destroy()

    def _centre(self, parent):
        self.update_idletasks()
        top = parent.winfo_toplevel()
        shift = 32 * SECTIONS.index(self.section)        # cascade: windows open together never hide each other
        x = top.winfo_rootx() + max((top.winfo_width() - self.winfo_reqwidth()) // 2, 0) + shift
        y = top.winfo_rooty() + max((top.winfo_height() - self.winfo_reqheight()) // 3, 0) + shift
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # --- the rows ----------------------------------------------------------------------------------------

    def _add_note(self, text=None, variable=None):
        note = ttk.Label(self.body, text=text or "", textvariable=variable, wraplength=400, justify="left",
                         foreground=NOTE_COLOUR)
        note.grid(row=self._row + 1, column=1, sticky="w", padx=6)
        self._notes.append(note)
        return note

    def _folder_row(self, label, var, command, note):
        ttk.Label(self.body, text=label).grid(row=self._row, column=0, sticky="w", pady=(10, 0))
        entry = ttk.Entry(self.body, textvariable=var)
        entry.grid(row=self._row, column=1, sticky="ew", padx=6, pady=(10, 0))
        ttk.Button(self.body, text="Browse…", command=command).grid(row=self._row, column=2, pady=(10, 0))
        self._add_note(note)
        self.first_entry = getattr(self, "first_entry", None) or entry
        self._row += 2

    def _build_browser(self):
        s = self.settings
        self._folder_row("Downloads folder:", s.downloads, self.pick_downloads,
                         "Where the WHDLoad .lha archives are kept: the Browser lists this folder, and the Builder "
                         "and HDCommander use it too. It is also the Downloader's download folder: changing one "
                         "changes the other.")

    def _build_builder(self):
        s = self.settings
        self._folder_row("Work folder:", s.work_dir, self.pick_work_dir,
                         "The folder with the template for prepared games (Template_WHDLoad) and the Icons. The "
                         "prepared and executable folders follow it while they are still at their defaults.")
        self._folder_row("Prepared (Whdload) folder:", s.whdload_dir,
                         lambda: self._pick(s.whdload_dir, "Select folder for prepared games"),
                         "Where the few games that need a prepared drive get it (A–Z, 0-9, #).")
        self._folder_row(f"{KIND} folder:", s.exe_dir,
                         lambda: self._pick(s.exe_dir, f"Select folder for the {KIND.lower()} files"),
                         f"Where Build {KIND} saves the standalone {KIND.lower()} files.")

    def _build_amiberry(self):
        """Two columns, so the window is not taller than a screen: where Amiberry and its data are, the ROMs and the
        game database on the left; what a launch looks like and the launch screen on the right."""
        s = self.settings
        main = self.body
        main.columnconfigure((0, 1), weight=1, uniform="columns")
        main.columnconfigure(2, weight=0)
        left, right = ttk.Frame(main), ttk.Frame(main)
        left.grid(row=0, column=0, sticky="new", padx=(0, 14))
        right.grid(row=0, column=1, sticky="new", padx=(14, 0))
        for frame in (left, right):
            frame.columnconfigure(1, weight=1)
        self.boxes = {}
        self.body, self._row = left, 0
        self._folder_row("Amiberry folder:", s.amiberry_dir,
                         lambda: self._pick(s.amiberry_dir, "Select Amiberry (the app or the folder containing it)",
                                            changed=False),
                         "The emulator. Empty = the emulator/ folder, then the usual install places. "
                         "Your Kickstart ROMs go in emulator/Kickstarts.")
        self._build_data()
        self._build_games()
        self._build_roms()
        self._build_database()
        self.body, self._row = right, 0
        self._build_choices()
        self._build_launch_screen()
        self.body, self._row = main, 1

    def _choice_row(self, label, var, choices, name):
        """A drop-down for a setting kept as a short value: it shows the readable text of the choices."""
        ttk.Label(self.body, text=label).grid(row=self._row, column=0, sticky="w", pady=(8, 0))
        names = [text for _, text in choices]
        by_text = {text: value for value, text in choices}
        box = ttk.Combobox(self.body, values=names, state="readonly", width=40)
        box.grid(row=self._row, column=1, sticky="w", padx=6, pady=(8, 0))
        box.set(dict(choices).get(var.get(), names[0]))
        box.bind("<<ComboboxSelected>>", lambda _e: var.set(by_text[box.get()]))
        var.trace_add("write", lambda *_: box.winfo_exists() and box.set(dict(choices).get(var.get(), names[0])))
        self.boxes[name] = box
        self._row += 1

    def _check_row(self, text, var):
        ttk.Checkbutton(self.body, text=text, variable=var).grid(row=self._row, column=1, sticky="w", padx=6, pady=(6, 0))
        self._row += 1

    def _build_choices(self):
        s = self.settings
        self._choice_row("Keyboard joystick:", s.keyboard, KEYBOARD_CHOICES, "keyboard")
        self._choice_row("Window:", s.window, WINDOW_CHOICES, "window")
        self._choice_row("Screen look:", s.look, LOOK_CHOICES, "look")
        self._check_row("Close Amiberry when the game exits", s.quit_on_exit)
        self._check_row("Show the WHDLoad splash screen", s.splash)
        self._add_note("Used for games you launch, and executables you build, from now on. The last two only apply "
                       "to games that start from their .lha.")
        self._row += 2

    def _build_launch_screen(self):
        s = self.settings
        ttk.Separator(self.body).grid(row=self._row, column=0, columnspan=3, sticky="ew", pady=(14, 2))
        self._row += 1
        self._check_row("Show a launch screen before a game starts", s.launch_screen)
        self._choice_row("Picture:", s.launch_image, IMAGE_CHOICES, "launch_image")
        ttk.Label(self.body, text="GamebaseAmiga folder:").grid(row=self._row, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(self.body, textvariable=s.gamebase_dir).grid(row=self._row, column=1, sticky="ew", padx=6, pady=(10, 0))
        ttk.Button(self.body, text="Browse…", command=self.pick_gamebase).grid(row=self._row, column=2, pady=(10, 0))
        self.gamebase_note = tk.StringVar(self)
        self._add_note(variable=self.gamebase_note)
        buttons = ttk.Frame(self.body)
        buttons.grid(row=self._row + 1, column=2, sticky="n")
        self.extract_button = ttk.Button(buttons, text="Extract pictures…", command=self.extract_gamebase)
        self.extract_button.grid(row=0, column=0, sticky="ew")
        self.delete_button = ttk.Button(buttons, text="Delete extracted…", command=self.delete_gamebase)
        self.delete_button.grid(row=1, column=0, sticky="ew")
        self._row += 2
        self._extracting = False
        self._extract_events = queue.Queue()
        self._gamebase_job = None
        s.gamebase_dir.trace_add("write", lambda *_: self._later_refresh_gamebase())
        self.refresh_gamebase()

    def pick_gamebase(self):
        start = self.settings.gamebase_dir.get()
        d = filedialog.askdirectory(parent=self, initialdir=start if Path(start).is_dir() else str(Path.home()),
                                    title="Select the GamebaseAmiga data folder (the one with screenshots and extras)")
        if d:
            self.settings.gamebase_dir.set(d)
            self.settings.save_settings()
            self.refresh_gamebase()

    def _later_refresh_gamebase(self):
        """A path typed into the box is looked at once the typing pauses: reading the folder takes a moment."""
        if self._gamebase_job is not None:
            self.after_cancel(self._gamebase_job)
        self._gamebase_job = self.after(500, self.refresh_gamebase)

    def refresh_gamebase(self):
        self._gamebase_job = None
        if not self.winfo_exists() or self._extracting:
            return
        folder = self.settings.gamebase_dir.get().strip()
        gamebase.forget()                      # the folder may have changed on disk
        library = gamebase.library(folder)
        source = gamebase.source_archives(folder)
        if library is not None and source and library.root == gamebase.extracted_dir():
            text = f"Using the pictures extracted from it: {library.describe()}."
        elif source:
            text = "Gamebase source found. Extract its screenshots and front covers (about 330 MB) to use them."
        elif not folder:
            text = ("Optional: the GamebaseAmiga data folder, or the Gamebase source (Screenshots.rar, Extras.rar), "
                    "for the launch screen's pictures. Your folder is only read.")
        elif library is None:
            text = "No screenshots or cover scans here: choose the GamebaseAmiga data folder."
        else:
            text = f"Found {library.describe()}" + (f" in {library.root}." if str(library.root) != folder else ".")
        self.gamebase_note.set(text)
        if source:
            self.extract_button.grid()
        else:
            self.extract_button.grid_remove()
        if gamebase.extracted_size():          # shown whenever there is something to delete, so the space can be got back
            self.delete_button.grid()
        else:
            self.delete_button.grid_remove()

    def delete_gamebase(self):
        """Delete the pictures extracted from the Gamebase source (never the source folder itself)."""
        if self._extracting:
            return
        size = gamebase.extracted_size()
        if not size:
            self.refresh_gamebase()
            return
        folder = gamebase.extracted_dir()
        if not messagebox.askokcancel(
                "Delete extracted pictures",
                f"This deletes {folder} ({human(size)}): the screenshots and front covers extracted from the Gamebase "
                f"source. The source folder is not touched; you can extract them again.\n\nContinue?",
                icon="warning", default="cancel", parent=self):
            return
        try:
            freed = gamebase.delete_extracted()
        except gamebase.ExtractError as exc:
            messagebox.showerror("Delete extracted pictures", str(exc), parent=self)
            return
        self.refresh_gamebase()
        messagebox.showinfo("Delete extracted pictures", f"Deleted {human(freed)}.", parent=self)

    def extract_gamebase(self):
        """Unpack the pictures from the Gamebase source into the app's own data folder, in the background."""
        if self._extracting:
            return
        folder = self.settings.gamebase_dir.get().strip()
        if not gamebase.source_archives(folder):
            return
        dest = gamebase.extracted_dir()
        if not messagebox.askokcancel(
                "Extract pictures",
                f"This unpacks the screenshots and front covers (about 330 MB, a few seconds) from the Gamebase source "
                f"into:\n\n{dest}\n\nThe source folder is not changed. Pictures extracted before are replaced.",
                parent=self):
            return
        self._extracting = True
        self.extract_button.config(state="disabled")
        self.delete_button.config(state="disabled")
        self.gamebase_note.set("Extracting…")

        def work():
            try:
                done = gamebase.extract(folder, dest, progress=lambda text: self._extract_events.put(("progress", text)))
                self._extract_events.put(("done", done))
            except gamebase.ExtractError as exc:
                self._extract_events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_extract)

    def _poll_extract(self):
        if not self.winfo_exists():
            return
        finished = None
        try:
            while True:
                kind, text = self._extract_events.get_nowait()
                if kind == "progress":
                    self.gamebase_note.set(text)
                else:
                    finished = (kind, text)
        except queue.Empty:
            pass
        if finished is None:
            self.after(200, self._poll_extract)
            return
        self._extracting = False
        self.extract_button.config(state="normal")
        self.delete_button.config(state="normal")
        self.refresh_gamebase()
        kind, text = finished
        if kind == "done":
            messagebox.showinfo("Extract pictures", text, parent=self)
        else:
            messagebox.showerror("Extract pictures", text, parent=self)

    def _build_roms(self):
        ttk.Label(self.body, text="Kickstart ROMs:").grid(row=self._row, column=0, sticky="nw", pady=(12, 0))
        self.rom_status = tk.Label(self.body, justify="left", anchor="w", background=DARK_BLUE, foreground="white",
                                   font=tkfont.nametofont("TkFixedFont"), padx=10, pady=8, wraplength=430)
        self.rom_status.grid(row=self._row, column=1, sticky="ew", padx=6, pady=(12, 0))
        self._notes.append(self.rom_status)
        ttk.Button(self.body, text="Refresh", command=self.refresh_roms).grid(row=self._row, column=2, sticky="n",
                                                                              pady=(12, 0))
        self._add_note("Only original, unmodified dumps count; any other file is ignored.")
        self._row += 2
        self.refresh_roms()

    def refresh_roms(self):
        exe = self.settings.amiberry_exe()
        if exe is None:
            self.rom_status.config(text=NO_AMIBERRY)
            return
        self.rom_status.config(text=rom_status_text(amiberry.rom_report(exe)))

    def _build_database(self):
        ttk.Label(self.body, text="WHDLoad games:").grid(row=self._row, column=0, sticky="w", pady=(12, 0))
        self.database_info = tk.StringVar(self)
        ttk.Label(self.body, textvariable=self.database_info).grid(row=self._row, column=1, sticky="w", padx=6, pady=(12, 0))
        self.update_button = ttk.Button(self.body, text="Update now", command=self.update_whdboot)
        self.update_button.grid(row=self._row, column=2, pady=(12, 0))
        self._add_note("The database Amiberry uses to set up each game. Update fetches the newest WHDLoad and database "
                       "(a few seconds).")
        self._row += 2
        self._updates = queue.Queue()
        self._updating = False
        self.refresh_database()

    def refresh_database(self):
        info = amiberry.database_info()
        self.database_info.set(f"{info['games']:,} games, database of {info['generated']}" if info else
                               "not downloaded yet (it is fetched the first time a game is launched)")

    def update_whdboot(self):
        if self._updating:
            return
        exe = self.settings.amiberry_exe()
        if exe is None:
            messagebox.showerror("Update WHDLoad", NO_AMIBERRY, parent=self)
            return
        if amiberry.running():
            messagebox.showinfo("Update WHDLoad", "Close the running game first.", parent=self)
            return
        before = amiberry.database_info()
        self._updating = True
        self.update_button.config(state="disabled")
        self.database_info.set("Updating…")

        def work():
            self._updates.put((*amiberry.update_whdboot(exe), before))

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_update)

    def _poll_update(self):
        if not self.winfo_exists():
            return
        try:
            ok, output, before = self._updates.get_nowait()
        except queue.Empty:
            self.after(200, self._poll_update)
            return
        self._updating = False
        self.update_button.config(state="normal")
        self.refresh_database()
        if ok:
            now = amiberry.database_info()
            was = f" (it was {before['games']:,})" if before and before["games"] != now["games"] else ""
            messagebox.showinfo("Update WHDLoad", f"Up to date: {now['games']:,} games{was}.", parent=self)
        else:
            tail = "\n".join(output.splitlines()[-6:]) or "no output"
            messagebox.showerror("Update WHDLoad", f"The update did not work:\n\n{tail}", parent=self)

    def _build_data(self):
        row = self._row
        ttk.Label(self.body, text="Amiberry data:").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.amiberry_data = tk.StringVar(self, value=str(amiberry_runtime.home_dir()))
        ttk.Entry(self.body, textvariable=self.amiberry_data, state="readonly").grid(
            row=row, column=1, sticky="ew", padx=6, pady=(10, 0))
        ttk.Button(self.body, text="Open", command=self.open_amiberry_data).grid(row=row, column=2, pady=(10, 0))
        ttk.Button(self.body, text="Reset…", command=self.reset_amiberry_data).grid(row=row + 1, column=2, sticky="n")
        self.amiberry_note = tk.StringVar(self)
        self._add_note(variable=self.amiberry_note)
        self._row += 2
        self.refresh_amiberry_note()

    def _build_games(self):
        row = self._row
        ttk.Label(self.body, text="Saved games:").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.games_path = tk.StringVar(self, value=str(amiberry_runtime.games_dir()))
        ttk.Entry(self.body, textvariable=self.games_path, state="readonly").grid(
            row=row, column=1, sticky="ew", padx=6, pady=(10, 0))
        ttk.Button(self.body, text="Open", command=self.open_games).grid(row=row, column=2, pady=(10, 0))
        ttk.Button(self.body, text="Delete…", command=self.delete_games).grid(row=row + 1, column=2, sticky="n")
        self.games_note = tk.StringVar(self)
        self._add_note(variable=self.games_note)
        self._row += 2
        self.refresh_games_note()

    def refresh_games_note(self):
        games = amiberry_runtime.games_dir()
        found = [p for p in games.iterdir() if p.is_dir()] if games.is_dir() else []
        what = (f"{len(found)} game{'s' if len(found) != 1 else ''}, {human(amiberry.folder_size(games))}"
                if found else "none yet")
        self.games_note.set(f"The standalone executables' own copies of their games, with their saves ({what}). "
                            f"Each is made again the next time its executable runs.")

    def open_games(self):
        try:
            amiberry.open_folder(amiberry_runtime.games_dir())
        except OSError as exc:
            messagebox.showerror("Saved games", str(exc), parent=self)

    def delete_games(self):
        games = amiberry_runtime.games_dir()
        if not games.is_dir() or not any(games.iterdir()):
            messagebox.showinfo("Delete saved games", "There are no saved games.", parent=self)
            return
        if amiberry.running():
            messagebox.showinfo("Delete saved games", "Close the running game first.", parent=self)
            return
        if not messagebox.askokcancel(
                "Delete saved games",
                f"This deletes {games} ({human(amiberry.folder_size(games))}): the copy each standalone executable made "
                f"of its game, with its saves and high scores. They cannot be brought back; an executable makes a new "
                f"copy the next time it runs.\n\nClose any standalone executable that is running first.\n\nContinue?",
                icon="warning", default="cancel", parent=self):
            return
        try:
            freed = amiberry.delete_games(games)
        except (RuntimeError, OSError, ValueError) as exc:
            messagebox.showerror("Delete saved games", str(exc), parent=self)
            return
        self.refresh_games_note()
        messagebox.showinfo("Delete saved games", f"Deleted {human(freed)}.", parent=self)

    # --- choosing folders --------------------------------------------------------------------------------

    def _pick(self, var, title, changed=True):
        d = filedialog.askdirectory(parent=self, initialdir=var.get() if Path(var.get()).is_dir() else
                                    self.settings.work_dir.get(), title=title)
        if d:
            if changed:
                self.settings.set_folder(var, d)
            else:                        # Amiberry: nothing for the tabs to refresh
                var.set(d)
                self.settings.save_settings()

    def pick_downloads(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.settings.downloads.get(), title="Select downloads folder")
        if d:
            self.settings.set_downloads(d)

    def pick_work_dir(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.settings.work_dir.get(), title="Select work folder")
        if d:
            self.settings.set_work_dir(d)

    # --- Amiberry's own data -----------------------------------------------------------------------------

    def refresh_amiberry_note(self):
        home = amiberry_runtime.home_dir()
        size = f"{human(amiberry.folder_size(home))} used" if home.exists() else "not created yet"
        self.amiberry_note.set(
            f"This app's own Amiberry settings, ROM copies and WHDLoad, apart from any Amiberry of yours ({size}). "
            f"Reset deletes it; the next launch sets it up again. Saved games are kept.")

    def open_amiberry_data(self):
        try:
            amiberry.open_folder(amiberry_runtime.home_dir())
        except OSError as exc:
            messagebox.showerror("Amiberry data", str(exc), parent=self)

    def reset_amiberry_data(self):
        home = amiberry_runtime.home_dir()
        if not home.exists():
            messagebox.showinfo("Reset Amiberry data", "There is nothing to reset: the folder has not been created yet.",
                                parent=self)
            return
        if amiberry.running():
            messagebox.showinfo("Reset Amiberry data", "Close the running game first.", parent=self)
            return
        if not messagebox.askokcancel(
                "Reset Amiberry data",
                f"This deletes {home} ({human(amiberry.folder_size(home))}): Amiberry's settings, the copies of your "
                f"Kickstart ROMs and the downloaded WHDLoad.\n\nIt is set up again the next time you launch a game "
                f"(WHDLoad is downloaded again). Your own Kickstart files in emulator/Kickstarts, your games and the "
                f"saved games of standalone executables are not touched.\n\nContinue?",
                icon="warning", default="cancel", parent=self):
            return
        try:
            freed = amiberry.reset_home(home)
        except (RuntimeError, OSError, ValueError) as exc:
            messagebox.showerror("Reset Amiberry data", str(exc), parent=self)
            return
        self.refresh_amiberry_note()
        messagebox.showinfo("Reset Amiberry data", f"Deleted {human(freed)}.", parent=self)
