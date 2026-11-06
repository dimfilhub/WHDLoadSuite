import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from collections import Counter
from pathlib import Path
from tkinter import messagebox, ttk

from common import whdparse
from common.gamepaths import (EXECUTABLE_COLOUR, NEEDS_PREP_COLOUR, PREPARED_COLOUR, build_state, game_name)
from common.utils import bind_wheel, unbind_wheel
from tabs.builder.launcher import GameLauncher

APP_NAME = "Browser"
COLUMNS = [  # (key, heading, width)
    ("title", "Title", 260), ("version", "Version", 70), ("lang", "Language", 110),
    ("platform", "Platform", 100), ("memory", "Memory", 90), ("media", "Media", 80),
    ("other", "Other tags", 130), ("ids", "ID", 90), ("filename", "File", 280),
]
FACETS = ("lang", "platform", "memory", "media", "other")


_vkey = whdparse.version_key


# Tk's modifier bit for "add to the selection": Command on macOS, Control elsewhere (Mod1 is NumLock on Windows)
ADD_KEY = 0x8 if sys.platform == "darwin" else 0x4


class BrowserTab(ttk.Frame):
    """Browse and filter the WHDLoad archives in the downloads folder.

    The folder is the StringVar shared with the other tabs; call reload() when its contents change.
    """

    def __init__(self, master, downloads_var, folder_vars=None, on_quit=None, on_send=None, ticked=None,
                 settings=None):
        """settings: the AppSettings; with it (and folder_vars) the tab can launch a game in Amiberry."""
        super().__init__(master)
        self.downloads = downloads_var
        self.folders = folder_vars  # (work, prepared, executables) StringVars
        self._on_quit = on_quit
        self._on_send = on_send
        self._ticked = ticked  # callable -> set of archive Paths ticked in the Builder tab
        self._settings = settings
        self.games, self.rows = [], []
        self._status_base = ""
        self._anchor = None  # row index of the last plain click, start of a Shift+click range
        self.picked = set()  # archive Paths selected by click; survive refreshes
        self.sort_key, self.sort_rev = "title", False
        self.vars = {}  # facet -> {value: BooleanVar}
        self._scan_gen = 0
        self._scans = queue.Queue()
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.refresh())
        self.group_latest = tk.BooleanVar(value=False)
        self.review = tk.BooleanVar(value=False)  # show only the selected archives, ignoring the filters
        self.noid = tk.BooleanVar(value=False)
        self.noid.trace_add("write", lambda *_: self.refresh())
        self._build()
        self.after(100, self._poll)
        self.reload()

    def _build(self):
        # Two rows: the filters, and the buttons. All on one row they needed more width than a normal window has,
        # and when the window was made narrower Tk squeezed the last buttons into thin slivers.
        filters = ttk.Frame(self, padding=(6, 6, 6, 0))
        filters.pack(fill="x")
        ttk.Label(filters, text="Search:").pack(side="left")
        ttk.Entry(filters, textvariable=self.search, width=28).pack(side="left", padx=4)
        ttk.Checkbutton(filters, text="Latest version only", variable=self.group_latest,
                        command=self.refresh).pack(side="left", padx=10)
        ttk.Checkbutton(filters, text="Only entries without ID", variable=self.noid).pack(side="left")
        ttk.Button(filters, text="Clear filters", command=self.clear).pack(side="left", padx=10)
        top = ttk.Frame(self, padding=(6, 4, 6, 6))
        top.pack(fill="x")
        self._bars = (filters, top)
        if self._on_quit:
            ttk.Button(top, text="Quit", style="quit.TButton", command=self._on_quit).pack(side="right", padx=(4, 0))
        if self._on_send:
            ttk.Button(top, text="Send to Builder", command=self.send).pack(side="right", padx=4)
        if self._settings is not None and self.folders:
            self.launch_btn = ttk.Button(top, text="Launch in Amiberry", command=self.launch)
            self.launch_btn.pack(side="right", padx=4)
            self.launcher = GameLauncher(self, self._settings, lambda text: self.status.config(text=text),
                                         self._launch_failed, self.restyle, title="Launch in Amiberry")
        self.review_btn = ttk.Button(top, text="Review selection", command=self.toggle_review)
        self.review_btn.pack(side="right", padx=4)
        ttk.Button(top, text="Clear selection",
                   command=self.clear_selection).pack(side="right")
        ttk.Button(top, text="Refresh", command=self.reload).pack(side="right", padx=4)

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x")
        legend = tk.Frame(bottom, background="white")
        legend.pack(side="right", padx=4)
        for text, color in (("Needs preparation", NEEDS_PREP_COLOUR), ("Prepared", PREPARED_COLOUR),
                            ("Executable built", EXECUTABLE_COLOUR), ("Selected in Builder", "#c8a000")):
            tk.Label(legend, text=f"■ {text}", foreground=color, background="white").pack(side="left", padx=4)
        self.status = ttk.Label(bottom, anchor="w", padding=4)
        self.status.pack(side="left", fill="x", expand=True)
        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        body.add(left, weight=0)
        canvas = tk.Canvas(left, width=270, highlightthickness=0, background="#0055aa")
        vsb = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.side = ttk.Frame(canvas, padding=4)
        win = canvas.create_window((0, 0), window=self.side, anchor="nw")
        self.side.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.bind("<Enter>", lambda _e: self._bind_wheel(canvas))
        canvas.bind("<Leave>", lambda _e: self._unbind_wheel(canvas))

        right = ttk.Frame(body)
        body.add(right, weight=1)
        self.tree = ttk.Treeview(right, columns=[c[0] for c in COLUMNS], show="tree headings", selectmode="none")
        self.tree.column("#0", width=90, stretch=False)  # group rows (0-9, A-Z) hold the expand arrow
        self.tree.heading("#0", text="Group")
        for key, head, w in COLUMNS:
            self.tree.heading(key, text=head, command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=w, anchor="w")
        sb = ttk.Scrollbar(right, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Button-1>", self.toggle)
        self.tree.bind("<Double-1>", self.reveal)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold  # keep a reference so it is not garbage collected
        self.tree.tag_configure("picked", font=bold)
        self.tree.tag_configure("needs_prep", foreground=NEEDS_PREP_COLOUR)
        self.tree.tag_configure("prepared", foreground=PREPARED_COLOUR)
        self.tree.tag_configure("executable", foreground=EXECUTABLE_COLOUR)
        self.tree.tag_configure("ticked", foreground="#c8a000")

    def _bind_wheel(self, canvas):
        bind_wheel(canvas, canvas)

    def _unbind_wheel(self, canvas):
        unbind_wheel(canvas)

    # ---------- data ----------
    def reload(self, _path=None):
        """Rescan the downloads folder in the background, then rebuild filters and list."""
        self._scan_gen += 1
        gen, root = self._scan_gen, Path(self.downloads.get())
        self.status.config(text=f"Scanning {root}…")

        def work():
            try:
                games = whdparse.scan(root) if root.is_dir() else []
            except OSError:
                games = []
            self._scans.put((gen, root, games))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                gen, root, games = self._scans.get_nowait()
                if gen == self._scan_gen:
                    self.root_dir, self.games = root, games
                    self.build_filters()
                    self.refresh()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _selected(self, facet):
        return {k for k, v in self.vars.get(facet, {}).items() if v.get()}

    def build_filters(self):
        keep = {f: self._selected(f) for f in FACETS}  # survive a rescan
        for w in self.side.winfo_children():
            w.destroy()
        g = self.games
        langs = Counter()
        for x in g:
            langs.update(x.languages or [whdparse.DEFAULT_LANGUAGE])
        other = Counter(o for x in g for o in x.other)
        self._facet_panel("lang", "Language", langs, keep, lambda c: whdparse.LANGUAGES.get(c, c))
        self._facet_panel("platform", "Platform", Counter(p for x in g for p in x.platforms), keep)
        self._facet_panel("memory", "Memory", Counter(m for x in g for m in x.memory), keep)
        self._facet_panel("media", "Media", Counter(m for x in g for m in x.media), keep)
        self._facet_panel("other", "Other tags (≥2)",
                          Counter({k: v for k, v in other.items() if v >= 2}), keep)

    def min_width(self) -> int:
        """The width the filter and button rows need; the window must not be made narrower than this."""
        return max(bar.winfo_reqwidth() for bar in self._bars)

    def _facet_panel(self, facet, label, counter, keep, display=lambda v: v):
        self.vars[facet] = {}
        if not counter:
            return          # nothing to choose from: no empty frame (it was drawn as a thin line)
        lf = ttk.LabelFrame(self.side, text=label, padding=4)
        lf.pack(fill="x", pady=3)
        for i, (val, n) in enumerate(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))):
            v = tk.BooleanVar(value=val in keep[facet])
            v.trace_add("write", lambda *_: self.refresh())
            self.vars[facet][val] = v
            ttk.Checkbutton(lf, text=f"{display(val)} ({n})", variable=v
                            ).grid(row=i // 2, column=i % 2, sticky="w", padx=2)

    def clear(self):
        self.search.set("")
        self.noid.set(False)
        for facet in self.vars.values():
            for v in facet.values():
                v.set(False)

    def matches(self, g, sel, q):
        if q and q not in g.filename.lower() and q not in g.title.lower():
            return False
        if sel["lang"] and not (set(g.languages or [whdparse.DEFAULT_LANGUAGE]) & sel["lang"]):
            return False
        for facet, vals in (("platform", g.platforms), ("memory", g.memory),
                            ("media", g.media), ("other", g.other)):
            if sel[facet] and not (set(vals) & sel[facet]):
                return False
        return not (self.noid.get() and g.ids)

    def refresh(self):
        sel = {f: self._selected(f) for f in FACETS}
        q = self.search.get().strip().lower()
        if self.review.get():
            rows = [g for g in self.games if g.path in self.picked]
        else:
            rows = [g for g in self.games if self.matches(g, sel, q)]
        if self.group_latest.get() and not self.review.get():
            best = {}
            for g in rows:
                k = (g.title, tuple(g.languages), tuple(g.platforms), tuple(g.memory),
                     tuple(g.media), tuple(g.other))
                if k not in best or _vkey(g.version) > _vkey(best[k].version):
                    best[k] = g
            rows = list(best.values())
        keyf = {
            "title": lambda g: g.title.lower(), "version": lambda g: _vkey(g.version),
            "lang": lambda g: ",".join(g.languages), "platform": lambda g: ",".join(g.platforms),
            "memory": lambda g: ",".join(g.memory), "media": lambda g: ",".join(g.media),
            "other": lambda g: ",".join(g.other), "ids": lambda g: ",".join(g.ids),
            "filename": lambda g: g.filename.lower(),
        }[self.sort_key]
        rows.sort(key=keyf, reverse=self.sort_rev)
        # Group by first character of the title; rows stay in display order so Shift+click ranges match the screen.
        rev = self.sort_key == "title" and self.sort_rev
        groups = {}
        for g in rows:
            groups.setdefault(self._group(g), []).append(g)
        order = sorted(groups, key=lambda k: (k == "#", k != "0-9", k), reverse=rev)
        rows = [g for k in order for g in groups[k]]
        self.rows = rows
        work = tuple(Path(v.get()) for v in self.folders) if self.folders and self.folders[0].get() else None
        opened = {self.tree.item(n, "text") for n in self.tree.get_children() if self.tree.item(n, "open")}
        expand_all = self.review.get() or bool(q)  # keep search / review results visible
        self.tree.delete(*self.tree.get_children())
        self._anchor = None
        ticked = self._ticked() if self._ticked else set()
        nodes = {}
        for i, g in enumerate(rows):
            k = self._group(g)
            if k not in nodes:
                nodes[k] = self.tree.insert("", "end", iid=f"g:{k}", text=k, open=expand_all or k in opened)
            self.tree.insert(nodes[k], "end", iid=str(i), values=self._values(g), tags=self._tags(g, work, ticked))
        self._status_base = (f"{len(rows)} of {len(self.games)} archives  —  {self.root_dir}"
                             + ("  (reviewing selection, filters ignored)" if self.review.get() else ""))
        self._update_status()

    @staticmethod
    def _group(g):
        first = g.title[:1].upper()
        return "0-9" if first.isdigit() else first if first.isalpha() else "#"

    def _tags(self, g, work, ticked):
        return self._state(g, work, ticked) + (("picked",) if g.path in self.picked else ())

    def toggle(self, event):
        """Click a row to select it (and only it), click it again to unselect; Cmd+click (Ctrl+click on Windows and Linux)
        adds or removes that row; Shift+click selects the range from the last clicked row."""
        if self.tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return  # let the arrow expand / collapse the group
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid.startswith("g:"):
            self.tree.item(iid, open=not self.tree.item(iid, "open"))
            return "break"
        if event.state & ADD_KEY:                          # Cmd (Ctrl elsewhere): add or remove just this row
            self.picked.symmetric_difference_update({self.rows[int(iid)].path})
            self._anchor = int(iid)
        elif event.state & 0x1 and self._anchor is not None:  # Shift: add the range from the last clicked row
            a, b = sorted((self._anchor, int(iid)))
            self.picked.update(g.path for g in self.rows[a:b + 1])
        else:
            path = self.rows[int(iid)].path
            self.picked = set() if self.picked == {path} else {path}      # a click never adds to the selection
            self._anchor = int(iid)
        self.restyle()
        self.tree.focus(iid)
        return "break"

    def toggle_review(self):
        self.review.set(not self.review.get())
        self.review_btn.configure(style="on.TButton" if self.review.get() else "TButton")
        self.refresh()

    def clear_selection(self):
        self.picked.clear()
        self._anchor = None
        if self.review.get():
            self.refresh()
        else:
            self.restyle()

    @staticmethod
    def _state(g, work, ticked=()):
        """Row tags: 'ticked' if selected in the Builder tab, else the game's build_state: 'executable' (built),
        'prepared' / 'needs_prep' (a game that runs from a prepared drive has / lacks it), or no colour."""
        if g.path in ticked:
            return ("ticked",)
        if work is None:
            return ()
        work_dir, whdload_dir, exe_dir = work
        state = build_state(game_name(g.path), work_dir, whdload_dir, exe_dir)
        return (state,) if state else ()

    @staticmethod
    def _values(g):
        return (g.title, g.version, ", ".join(g.language_names), ", ".join(g.platforms),
                ", ".join(g.memory), ", ".join(g.media), ", ".join(g.other),
                " & ".join(g.ids), g.filename)

    def sort_by(self, key):
        self.sort_rev = (not self.sort_rev) if key == self.sort_key else False
        self.sort_key = key
        self.refresh()

    def send(self):
        """Hand the selected rows (all displayed rows if none selected) to the Builder tab."""
        rows = [g for g in self.rows if g.path in self.picked]
        if not rows:
            rows = self.rows
            if not rows:
                messagebox.showinfo("Send to Builder", "No archives to send.")
                return
            if not messagebox.askokcancel("Send to Builder", f"No files are selected, so all {len(rows)} displayed "
                                          "files will be sent to Builder.\n\nContinue?", icon="warning"):
                return
        self._on_send([g.path for g in rows])
        self.restyle()

    def launch(self):
        """Run the one selected game in Amiberry (the launcher shows the launch screen first)."""
        rows = [g for g in self.rows if g.path in self.picked]
        if len(rows) != 1:
            messagebox.showinfo("Launch in Amiberry", "Select exactly one game (click its row) to launch it.")
            return
        self.launcher.launch(rows[0].path, Path(self.folders[0].get()), Path(self.folders[1].get()))

    def _launch_failed(self, error):
        messagebox.showerror("Launch in Amiberry", error)

    def _update_status(self):
        self.status.config(text=f"{len(self.picked)} selected  |  {self._status_base}")

    def restyle(self):
        """Re-tag the rows in place (keeps the scroll position)."""
        work = tuple(Path(v.get()) for v in self.folders) if self.folders and self.folders[0].get() else None
        ticked = self._ticked() if self._ticked else set()
        for i, g in enumerate(self.rows):
            self.tree.item(str(i), tags=self._tags(g, work, ticked))
        self._update_status()

    def reveal(self, _event):
        iid = self.tree.identify_row(_event.y)
        if iid and iid.startswith("g:"):
            return "break"  # a group row was already toggled by the click
        if not iid:
            return
        p = self.rows[int(iid)].path
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(p)])
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", "/select,", str(p)])
        else:
            subprocess.run(["xdg-open", str(p.parent)])
