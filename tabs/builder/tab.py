"""Builder tab: test-launch and build standalone executables of the games found in the downloads folder."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk

from common.gamepaths import EXECUTABLE_COLOUR, NEEDS_PREP_COLOUR, PREPARED_COLOUR, build_state, game_name
from tabs.settings.settings import KIND

from . import bundle, core
from .launcher import GameLauncher

APP_NAME = "Builder"
UNCHECKED, CHECKED, PARTIAL = "☐", "☑", "⊟"


class BuilderTab(ttk.Frame):
    def __init__(self, master, settings):
        """settings: the app's AppSettings, which owns the folder choices."""
        super().__init__(master, padding=12)
        self.settings = settings
        self.work_dir, self.whdload_dir, self.exe_dir = settings.work_dir, settings.whdload_dir, settings.exe_dir
        self.downloads = settings.downloads
        self.events: queue.Queue = queue.Queue()
        self.worker = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        opts = ttk.Frame(self)
        opts.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        self.count = tk.StringVar()
        self.status = tk.StringVar(value="Ready.")
        self.launcher = GameLauncher(self, settings, self.status.set, self._launch_failed, self.refresh_prepared,
                                     title="Launch")
        self.picked = tk.StringVar()
        ttk.Label(opts, textvariable=self.count).pack(side="left", padx=(0, 8))
        ttk.Label(opts, textvariable=self.picked).pack(side="left", padx=(0, 16))
        self.select_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Select all", variable=self.select_all,
                        command=self.toggle_all).pack(side="left")
        self._button(opts, "Refresh list", self.refresh).pack(side="right")
        self._button(opts, "Clear selection", self.clear_selection).pack(side="right", padx=(0, 8))

        box = ttk.LabelFrame(self, text="Archives (select the ones to launch or build)")
        box.grid(row=1, column=0, columnspan=3, sticky="nsew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(box, selectmode="none", style="Archives.Treeview")
        self.tree.heading("#0", text="Name")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self.on_tree_click)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold  # keep a reference so the font is not garbage collected
        self.tree.tag_configure("checked", font=bold)
        self.tree.tag_configure("needs_prep", foreground=NEEDS_PREP_COLOUR)
        self.tree.tag_configure("prepared", foreground=PREPARED_COLOUR)
        self.tree.tag_configure("executable", foreground=EXECUTABLE_COLOUR)
        sb = ttk.Scrollbar(box, command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.config(yscrollcommand=sb.set)

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 2))
        log_head = ttk.Frame(self)
        log_head.grid(row=3, column=0, columnspan=3, sticky="ew")
        ttk.Label(log_head, text="Log").pack(side="left")
        ttk.Label(log_head, textvariable=self.status).pack(side="left", padx=(16, 0))
        legend = tk.Frame(log_head, background="white")  # white so green/blue read on the blue window
        legend.pack(side="right")
        for text, color in (("Needs preparation", NEEDS_PREP_COLOUR), ("Prepared", PREPARED_COLOUR),
                            ("Executable built", EXECUTABLE_COLOUR)):
            tk.Label(legend, text=f"■ {text}", foreground=color, background="white").pack(side="left", padx=4)

        self.log = tk.Text(self, height=14, state="disabled", wrap="word")
        self.log.grid(row=4, column=0, columnspan=3, sticky="ew", pady=4)

        btns = ttk.Frame(self)
        btns.grid(row=5, column=0, columnspan=3, pady=(20, 12))  # equal gap to the log (+4) and the window edge (+12)
        self.launch_btn = self._button(btns, "Launch to test", self.launch)
        self.launch_btn.pack(side="left")
        self.exe_btn = self._button(btns, f"Build {KIND}", self.start_bundle)
        self.exe_btn.pack(side="left", padx=6)
        self.clear_btn = self._button(btns, "Clear Prepared", self.clear, style="clear.TButton")
        self.clear_btn.pack(side="left", padx=(18, 0))
        self._button(btns, "Quit", self.quit_app).pack(side="left", padx=(12, 0))

        self.archives: list[Path] = []
        self.refresh()
        self.after(100, self.poll)

    @staticmethod
    def _button(parent, text, command, **extra):
        return ttk.Button(parent, text=text, command=command, width=21, **extra)

    def save_settings(self):
        self.settings.save_settings()

    def refresh(self):
        """Re-scan the downloads folder: the ticked archives and open letter groups survive."""
        old = self.archives
        ticked = {old[int(i)] for i in self.tree.selection()}
        opened = {self.tree.item(g, "text")[2:] for g in self.tree.get_children() if self.tree.item(g, "open")}
        src = Path(self.downloads.get())
        self.archives = sorted(src.rglob("*.lha"), key=lambda p: p.name.lower()) if src.is_dir() else []
        self.tree.delete(*self.tree.get_children())
        self.select_all.set(False)
        self.picked.set("0 selected.")
        groups = {}
        for i, a in enumerate(self.archives):
            first = a.name[0].upper()
            key = first if first.isalpha() else "0-9"
            if key not in groups:
                groups[key] = self.tree.insert("", "end", text=f"{UNCHECKED} {key}", open=key in opened)
            self.tree.insert(groups[key], "end", iid=str(i), text=f"{UNCHECKED} {a.name}")
            self._tag(str(i))
        self.count.set(f"{len(self.archives)} archive(s) found." if self.archives else "No .lha archives found.")
        self.progress.config(value=0)
        self.set_checked([str(i) for i, a in enumerate(self.archives) if a in ticked], True)

    def on_tree_click(self, event):
        """Click a row to tick/untick it (a letter toggles all its games); the arrow expands/collapses."""
        item = self.tree.identify_row(event.y)
        if not item or self.tree.identify_element(event.x, event.y) == "Treeitem.indicator":
            return None
        children = self.tree.get_children(item)
        if not children:
            self.set_checked([item], item not in self.tree.selection())
        else:
            self.set_checked(children, not all(c in self.tree.selection() for c in children))
        return "break"

    def select_paths(self, paths):
        """Add these archives to the selection and expand their letter groups.
        Returns how many were not in the list (e.g. not .lha)."""
        self.refresh()
        wanted = set(paths)
        found = [str(i) for i, a in enumerate(self.archives) if a in wanted]
        self.set_checked(found, True)
        for group in {self.tree.parent(i) for i in found}:
            self.tree.item(group, open=True)
        if found:
            self.tree.see(found[0])
        return len(wanted) - len(found)

    def toggle_all(self):
        self.set_checked([i for g in self.tree.get_children() for i in self.tree.get_children(g)],
                         self.select_all.get())

    def clear_selection(self):
        self.set_checked(list(self.tree.selection()), False)

    def _box(self, item, box):
        self.tree.item(item, text=f"{box} {self.tree.item(item, 'text')[2:]}")

    def _tag(self, item, bold=None):
        """Bold when ticked (a letter: all its games ticked), plus one colour tag from build_state: blue (executable
        built), green (prepared), orange (needs a prepared drive, has none), none (needs nothing). One colour
        tag only (like the Browser), so the result never depends on tag precedence."""
        tags = []
        if bold is None:
            bold = item in self.tree.selection()
        if bold:
            tags.append("checked")
        if not self.tree.get_children(item):
            name = game_name(self.archives[int(item)])
            work = Path(self.work_dir.get())
            state = build_state(name, work, Path(self.whdload_dir.get()), Path(self.exe_dir.get()))
            if state:
                tags.append(state)
        self.tree.item(item, tags=tags)

    def refresh_prepared(self):
        """Re-evaluate which games are prepared, keeping the current ticks."""
        for group in self.tree.get_children():
            for item in self.tree.get_children(group):
                self._tag(item)

    def set_checked(self, items, checked):
        for it in items:
            (self.tree.selection_add if checked else self.tree.selection_remove)(it)
            self._box(it, CHECKED if checked else UNCHECKED)
            self._tag(it, checked)
        for group in {self.tree.parent(it) for it in items}:
            kids = self.tree.get_children(group)
            full = all(k in self.tree.selection() for k in kids)
            some = any(k in self.tree.selection() for k in kids)
            self._box(group, CHECKED if full else PARTIAL if some else UNCHECKED)
            self._tag(group, full)
        self.select_all.set(bool(self.archives) and len(self.tree.selection()) == len(self.archives))
        self.picked.set(f"{len(self.tree.selection())} selected.")

    def ticked_paths(self):
        return {self.archives[int(i)] for i in self.tree.selection()}

    def selected_indices(self):
        return sorted(int(i) for i in self.tree.selection())

    def need_selection(self, title):
        """True if something is selected; otherwise tell the user to select items first."""
        if self.tree.selection():
            return True
        messagebox.showinfo(title, "Select one or more items in the list first.")
        return False

    def launch(self):
        if self.launcher.busy or not self.need_selection("Launch"):
            return
        sel = self.selected_indices()
        if len(sel) != 1:
            messagebox.showinfo("Launch", "Select exactly one game in the list to launch.")
            return
        self.launcher.launch(self.archives[sel[0]], Path(self.work_dir.get()), Path(self.whdload_dir.get()))

    def _launch_failed(self, error):
        messagebox.showerror("Launch", error)

    def clear(self):
        work_dir = Path(self.work_dir.get())
        targets = f"  • the prepared game folders (A–Z, 0-9, #) in {self.whdload_dir.get()}"
        if not messagebox.askokcancel(
                "Clear work folder",
                f"WARNING: the following folders and everything inside them will be permanently deleted:\n\n"
                f"{targets}\n\nThe prepared drives are lost. The few games that need one are prepared again, "
                f"automatically, the next time you launch or build them. Your downloads and executables are not "
                f"touched. This cannot be undone.\n\nContinue?",
                icon="warning", default="cancel"):
            return
        try:
            removed = core.clear_work_dir(work_dir, Path(self.whdload_dir.get()))
        except (RuntimeError, OSError) as exc:
            messagebox.showerror("Clear Prepared", str(exc))
            return
        self.write_log("Cleared: " + (", ".join(p.name for p in removed) or "nothing to delete"))
        self.refresh()
        self.status.set("Work folder cleared.")

    def quit_app(self):
        self.save_settings()
        if self.worker and self.worker.is_alive() and not messagebox.askokcancel(
                "Quit", "A job is still running. Quit anyway?", icon="warning", default="cancel"):
            return
        self.winfo_toplevel().destroy()

    def downloader_folder_changed(self, _path=None):
        """The downloader's download folder is the shared downloads folder: keep them in step."""
        self.save_settings()
        self.refresh()
        if self.settings.on_downloads_changed:
            self.settings.on_downloads_changed()

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def write_log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def start_bundle(self):
        if not self.need_selection(f"Build {KIND}"):
            return
        exe = self.settings.amiberry_exe()
        if exe is None:
            messagebox.showerror(f"Build {KIND}", "Amiberry not found. Put it in the emulator folder or choose it "
                                                  "in Settings > Amiberry….")
            return
        self.clear_log()
        todo = [self.archives[i] for i in self.selected_indices()]
        self.save_settings()
        self.set_busy(True)
        self.progress.config(value=0, maximum=len(todo))
        screen = self.settings.launch_screen.get()             # read here, on the window thread
        pictures = {a: self.settings.game_image(a.stem) for a in todo} if screen else {}
        self.worker = threading.Thread(target=self.run, args=(todo, Path(self.work_dir.get()),
                                                         Path(self.whdload_dir.get()), Path(self.exe_dir.get()), exe,
                                                         self.settings.amiberry_options(), screen, pictures), daemon=True)
        self.worker.start()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for b in (self.clear_btn, self.exe_btn, self.launch_btn):
            b.config(state=state)

    def run(self, todo, work_dir, whdload_dir, exe_dir, exe, options, launch_screen=False, pictures=None):
        failed = 0
        for n, archive in enumerate(todo):
            self.events.put(("status", f"Building {archive.name} ({n + 1}/{len(todo)})…"))
            try:
                prepared = core.ensure_prepared(archive, work_dir, whdload_dir)   # only games that need a drive
                if prepared:
                    self.events.put(("log", f"{archive.name}: prepared its drive first"))
                app = bundle.create_executable(archive, work_dir, exe_dir, whdload_dir, exe=exe,
                                               kickstarts=self.settings.kickstarts_dir(), options=options,
                                               launch_screen=launch_screen, picture=(pictures or {}).get(archive))
                result = f"ok: {app}"
            except Exception as exc:
                failed += 1
                result = f"FAILED: {exc}"
            self.events.put(("log", f"{archive.name}: {result}"))
            self.events.put(("progress", n + 1))
        self.events.put(("done", failed))

    def poll(self):
        try:
            while True:
                kind, val = self.events.get_nowait()
                if kind == "status":
                    self.status.set(val)
                elif kind == "log":
                    self.write_log(val)
                elif kind == "progress":
                    self.progress.config(value=val)
                elif kind == "done":
                    self.status.set("Done." if not val else f"Done with {val} failure(s).")
                    self.set_busy(False)
                    self.refresh_prepared()
        except queue.Empty:
            pass
        self.after(100, self.poll)
