"""File filters for the Downloader: choose by language, platform, ... which files a download keeps.

The names on the server follow the same convention as the local archives, so whdparse reads them.
"""
import tkinter as tk
from functools import lru_cache
from pathlib import PurePosixPath
from tkinter import ttk

from common import whdparse
from common.dialogs import center
from common.utils import bind_wheel, human, unbind_wheel

FACETS = ("lang", "platform", "memory", "media", "other")
FACET_LABELS = {"lang": "Language", "platform": "Platform", "memory": "Memory",
                "media": "Media", "other": "Other tags (≥2)"}


@lru_cache(maxsize=None)
def parsed(remote):
    """The parsed game for a remote file path (cached: filtering re-reads the same names a lot)."""
    return whdparse.parse(PurePosixPath(remote))


def facet_values(g, facet):
    if facet == "lang":
        return g.languages or [whdparse.DEFAULT_LANGUAGE]
    return {"platform": g.platforms, "memory": g.memory, "media": g.media, "other": g.other}[facet]


class FileFilter:
    """Which files to keep. Within a facet any selected value matches; facets are combined with AND."""

    def __init__(self):
        self.search = ""
        self.noid = False
        self.latest = False
        self.sel = {f: set() for f in FACETS}

    @property
    def active(self):
        return bool(self.search or self.noid or self.latest or any(self.sel.values()))

    def matches(self, g):
        q = self.search.lower()
        if q and q not in g.filename.lower() and q not in g.title.lower():
            return False
        for facet, wanted in self.sel.items():
            if wanted and not (set(facet_values(g, facet)) & wanted):
                return False
        return not (self.noid and g.ids)

    @staticmethod
    def _family(g):
        """Same game and same variant tags: only the version differs."""
        return (g.title, tuple(g.languages), tuple(g.platforms), tuple(g.memory), tuple(g.media), tuple(g.other))

    def apply(self, files):
        """Keep the (remote_path, size, ...) tuples that match."""
        if not self.active:
            return list(files)
        kept = [f for f in files if self.matches(parsed(f[0]))]
        if self.latest:
            best = {}
            for f in kept:
                k = self._family(parsed(f[0]))
                if k not in best or whdparse.version_key(parsed(f[0]).version) > whdparse.version_key(parsed(best[k][0]).version):
                    best[k] = f
            kept = [f for f in kept if best[self._family(parsed(f[0]))] is f]
        return kept


class FilterDialog(tk.Toplevel):
    """Window to pick the filters. get_files() -> (files, pending): the (path, size) files in the
    ticked folders that are known so far, and how many folders are still being listed."""

    def __init__(self, master, current, get_files, on_apply):
        super().__init__(master)
        self.withdraw()              # hidden until built and centred
        self.title("Download filters")
        self.transient(master.winfo_toplevel())
        self._get_files, self._on_apply = get_files, on_apply
        self._sig = None
        self.vars = {}
        self.search = tk.StringVar(value=current.search)
        self.noid = tk.BooleanVar(value=current.noid)
        self.latest = tk.BooleanVar(value=current.latest)
        self._keep = {f: set(current.sel[f]) for f in FACETS}
        for v in (self.search, self.noid, self.latest):
            v.trace_add("write", lambda *_: self._preview())

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        ttk.Entry(top, textvariable=self.search, width=28).pack(side="left", padx=4)
        ttk.Checkbutton(top, text="Latest version only", variable=self.latest).pack(side="left", padx=6)
        ttk.Checkbutton(top, text="Only entries without ID", variable=self.noid).pack(side="left")

        bottom = ttk.Frame(self, padding=6)
        bottom.pack(side="bottom", fill="x")
        self.info = ttk.Label(bottom, anchor="w")
        self.info.pack(fill="x", pady=(0, 6))
        ttk.Button(bottom, text="Clear filters", command=self.clear).pack(side="left")
        ttk.Button(bottom, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Apply", command=self.apply).pack(side="right", padx=6)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        canvas = tk.Canvas(body, highlightthickness=0, background="#0055aa")
        vsb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.side = ttk.Frame(canvas, padding=4)
        win = canvas.create_window((0, 0), window=self.side, anchor="nw")
        self.side.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.bind("<Enter>", lambda _e: bind_wheel(canvas, canvas))
        canvas.bind("<Leave>", lambda _e: unbind_wheel(canvas))
        self.bind("<Destroy>", lambda e: unbind_wheel(canvas) if e.widget is self else None)
        self._rebuild_if_changed()
        center(self, master, (560, 560))
        self.deiconify()

    # ----- state -----
    def collect(self):
        f = FileFilter()
        f.search = self.search.get().strip()
        f.noid, f.latest = self.noid.get(), self.latest.get()
        f.sel = {facet: {k for k, v in self.vars.get(facet, {}).items() if v.get()} for facet in FACETS}
        for facet in FACETS:  # selections whose files are not listed (yet) stay in force
            f.sel[facet] |= self._keep[facet] - set(self.vars.get(facet, {}))
        return f

    def clear(self):
        self.search.set("")
        self.noid.set(False)
        self.latest.set(False)
        self._keep = {f: set() for f in FACETS}
        for vs in self.vars.values():
            for v in vs.values():
                v.set(False)

    def apply(self):
        self._on_apply(self.collect())
        self.destroy()

    # ----- facets -----
    def _rebuild_if_changed(self):
        """Poll: folders are listed in the background, so new files can appear while the window is open."""
        if not self.winfo_exists():
            return
        files, pending = self._get_files()
        sig = (len(files), pending)
        if sig != self._sig:
            self._sig = sig
            self._build_facets(files)
            self._preview()
        self.after(500, self._rebuild_if_changed)

    def _build_facets(self, files):
        self._keep = self.collect().sel if self.vars else self._keep
        for w in self.side.winfo_children():
            w.destroy()
        self.vars = {}
        games = [parsed(f[0]) for f in files]
        counts = {f: {} for f in FACETS}
        for g in games:
            for facet in FACETS:
                for v in facet_values(g, facet):
                    counts[facet][v] = counts[facet].get(v, 0) + 1
        counts["other"] = {k: n for k, n in counts["other"].items() if n >= 2}
        for facet in FACETS:
            if not counts[facet]:
                continue
            lf = ttk.LabelFrame(self.side, text=FACET_LABELS[facet], padding=4)
            lf.pack(fill="x", pady=3)
            self.vars[facet] = {}
            for i, (val, n) in enumerate(sorted(counts[facet].items(), key=lambda kv: (-kv[1], kv[0]))):
                v = tk.BooleanVar(value=val in self._keep[facet])
                v.trace_add("write", lambda *_: self._preview())
                self.vars[facet][val] = v
                shown = whdparse.LANGUAGES.get(val, val) if facet == "lang" else val
                ttk.Checkbutton(lf, text=f"{shown} ({n})", variable=v).grid(row=i // 2, column=i % 2, sticky="w", padx=2)

    def _preview(self):
        files, pending = self._get_files()
        kept = self.collect().apply(files)
        text = f"Keeps {len(kept)} of {len(files)} files ({human(sum(f[1] for f in kept))})"
        if pending:
            text += f" — {pending} folder(s) still being listed"
        if not files and not pending:
            text = "Tick one or more folders in the list first; their files are then offered here."
        self.info.config(text=text)
