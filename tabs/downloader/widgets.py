import os
import tkinter as tk
from tkinter import filedialog, ttk

from .ftp import DEFAULT_HOST, HOSTS, DEFAULT_PORT, Credentials
from common.theme import HAVE_COLOR, MISSING_COLOR, WB_BLUE
from common.utils import human

DUMMY = "__dummy__"


BUTTON_WIDTH = 21  # every button is as wide as the longest label ("Switch to Builder")


class ConnectionPanel(ttk.LabelFrame):
    """Host / port / credentials form with a connect button and a status LED."""

    def __init__(self, master, on_toggle):
        super().__init__(master, text="Connection", padding=8)
        self.host = tk.StringVar(value=DEFAULT_HOST)
        self.port = tk.StringVar(value=str(DEFAULT_PORT))
        self.user = tk.StringVar(value="ftp")
        self.pw = tk.StringVar(value="ftp")
        self.tls = tk.BooleanVar(value=False)
        ttk.Label(self, text="Host").grid(row=0, column=0, sticky="w")
        ttk.Combobox(self, textvariable=self.host, values=HOSTS, state="readonly", width=20).grid(row=0, column=1, padx=4)
        ttk.Label(self, text="Port").grid(row=0, column=2, sticky="w")
        ttk.Entry(self, textvariable=self.port, width=6).grid(row=0, column=3, padx=4)
        ttk.Checkbutton(self, text="Use FTPS (TLS)", variable=self.tls).grid(row=0, column=4, padx=8)
        ttk.Label(self, text="Username").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self, textvariable=self.user, width=22).grid(row=1, column=1, padx=4, pady=(6, 0))
        ttk.Label(self, text="Password").grid(row=1, column=2, sticky="w", pady=(6, 0))
        pw = ttk.Entry(self, textvariable=self.pw, show="*", width=22)
        pw.grid(row=1, column=3, columnspan=2, sticky="w", padx=4, pady=(6, 0))
        pw.bind("<Return>", lambda e: on_toggle())
        self.button = ttk.Button(self, width=BUTTON_WIDTH, text="Connect", command=on_toggle)
        self.button.grid(row=1, column=5, padx=8, pady=(6, 0))

        led_frame = ttk.Frame(self)
        led_frame.grid(row=0, column=5, sticky="w", padx=8)
        self.led = tk.Canvas(led_frame, width=16, height=16, highlightthickness=0, background=WB_BLUE)
        self.led_dot = self.led.create_oval(2, 2, 14, 14, fill="red", outline="")
        self.led.pack(side="left")
        self.led_label = ttk.Label(led_frame, text="Disconnected")
        self.led_label.pack(side="left", padx=(4, 0))

        ttk.Label(self, text="Enter your credentials and click Connect.\n"
                             "Note: the free FTP account uses username \"ftp\" and password \"ftp\".",
                  foreground="#cfe0f5").grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))

    def credentials(self):
        try:
            port = int(self.port.get())
        except ValueError:
            port = DEFAULT_PORT
        return Credentials(self.host.get().strip(), port, self.user.get(), self.pw.get(), self.tls.get())

    def has_credentials(self):
        return bool(self.user.get() and self.pw.get())

    def set_state(self, connected, connecting):
        self.led.itemconfig(self.led_dot, fill="green" if connected else "red")
        self.led_label.config(text="Connected" if connected else "Disconnected")
        self.button.config(text="Disconnect" if connected else "Connect",
                           state="disabled" if connecting else "normal")


class CheckTree(ttk.Frame):
    """Lazy-loading remote folder tree where every row has a tri-state checkbox."""

    def __init__(self, master, root_path, on_change, on_expand, is_present=None):
        super().__init__(master)
        self._is_present = is_present  # file node -> bool, colours files green/red when given
        self._iids = {}                # remote path -> iid
        self.root_path = root_path
        self._on_change = on_change   # called after the ticked set changed
        self._on_expand = on_expand   # called with (iid, remote_path) when a folder needs loading
        self.nodes = {}               # iid -> RemoteNode
        self.checked = set()          # iids of ticked items
        self.partial = set()          # folders with only some of their items ticked

        self.tree = ttk.Treeview(self, columns=("size",), selectmode="browse")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.column("#0", width=560)
        self.tree.column("size", width=100, anchor="e")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("have", foreground=HAVE_COLOR)
        self.tree.tag_configure("missing", foreground=MISSING_COLOR)
        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<space>", self._on_space)

    @property
    def has_ticks(self):
        return bool(self.checked or self.partial)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        self._iids.clear()
        self.checked.clear()
        self.partial.clear()

    def populate(self, parent, entries):
        """Replace the children of parent ('' for the root) with entries."""
        if parent:
            self.tree.delete(*self.tree.get_children(parent))
        inherit = parent in self.checked
        for node in sorted(entries, key=lambda e: (not e.is_dir, e.name.lower())):
            iid = self.tree.insert(parent, "end", values=("" if node.is_dir else human(node.size),))
            self.nodes[iid] = node
            self._iids[node.path] = iid
            self._retag(iid)
            if inherit:
                self.checked.add(iid)
            self._label(iid)
            if node.is_dir:
                self.tree.insert(iid, "end", iid=f"{iid}{DUMMY}", text="loading...")

    def _retag(self, iid):
        """Colour a file row green if it is in the download folder, red if not. Folders stay plain."""
        node = self.nodes.get(iid)
        if node is None or node.is_dir or self._is_present is None:
            return
        self.tree.item(iid, tags=("have" if self._is_present(node) else "missing",))

    def recolor_all(self):
        """Re-check every loaded file against the download folder."""
        for iid in self.nodes:
            self._retag(iid)

    def recolor_path(self, path):
        iid = self._iids.get(path)
        if iid:
            self._retag(iid)

    def top_items(self):
        """Ticked nodes that have no ticked ancestor (a ticked folder already covers its contents)."""
        items = []
        for iid in self.checked:
            if iid not in self.nodes:
                continue
            p = self.tree.parent(iid)
            while p and p not in self.checked:
                p = self.tree.parent(p)
            if not p:
                items.append(self.nodes[iid])
        return items

    def select_toggle(self):
        """Clear everything if anything is ticked, otherwise tick everything."""
        self.set_all(not self.has_ticks)

    def set_all(self, state):
        for iid in self.tree.get_children(""):
            self._set_checked(iid, state)
        self._on_change()

    def toggle(self, iid):
        if iid not in self.nodes:
            return
        self._set_checked(iid, iid not in self.checked)
        self._refresh_ancestors(iid)
        self._on_change()

    # ----- Internals -----
    def _label(self, iid):
        node = self.nodes[iid]
        box = "☑" if iid in self.checked else "⊟" if iid in self.partial else "☐"
        self.tree.item(iid, text=f"{box} {'📁 ' if node.is_dir else ''}{node.name}")

    def _set_checked(self, iid, state):
        self.partial.discard(iid)
        if state:
            self.checked.add(iid)
        else:
            self.checked.discard(iid)
        self._label(iid)
        for child in self.tree.get_children(iid):
            if child in self.nodes:
                self._set_checked(child, state)

    def _refresh_ancestors(self, iid):
        """A folder is ticked while every loaded child is ticked, and shows a dash if only some are."""
        parent = self.tree.parent(iid)
        while parent:
            kids = [k for k in self.tree.get_children(parent) if k in self.nodes]
            if kids and all(k in self.checked for k in kids):
                self.checked.add(parent)
                self.partial.discard(parent)
            else:
                self.checked.discard(parent)
                if any(k in self.checked or k in self.partial for k in kids):
                    self.partial.add(parent)
                else:
                    self.partial.discard(parent)
            self._label(parent)
            parent = self.tree.parent(parent)

    def _on_open(self, _event):
        iid = self.tree.focus()
        kids = self.tree.get_children(iid)
        if iid not in self.nodes or not (len(kids) == 1 and kids[0].endswith(DUMMY)):
            return
        self._on_expand(iid, self.nodes[iid].path)

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "tree":
            return
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return  # let the expand/collapse arrow work normally
        iid = self.tree.identify_row(event.y)
        if iid:
            self.toggle(iid)  # default handling still runs, so the row is also highlighted

    def _on_space(self, _event):
        iid = self.tree.focus()
        if iid:
            self.toggle(iid)
            return "break"


class DestinationPanel(ttk.Frame):
    """Download folder entry with a Browse button."""

    def __init__(self, master, initial=None, on_change=None, variable=None):
        super().__init__(master)
        self._on_change = on_change  # called with the new path after Browse picked one
        ttk.Label(self, text="Download to").pack(side="left")
        self.var = variable or tk.StringVar(value=initial or os.path.join(os.path.expanduser("~"), "Downloads"))
        entry = ttk.Entry(self, textvariable=self.var)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        for event in ("<Return>", "<FocusOut>"):
            entry.bind(event, lambda _e: self._changed())
        ttk.Button(self, width=BUTTON_WIDTH, text="Browse...", command=self._browse).pack(side="left")

    @property
    def path(self):
        return self.var.get().strip()

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.var.get() or None)
        if d:
            self.var.set(d)
            self._changed()

    def _changed(self):
        if self._on_change:
            self._on_change(self.path)


class ActionBar(ttk.Frame):
    """Download / Cancel / Select all / Quit buttons plus the selection summary."""

    def __init__(self, master, on_download, on_cancel, on_select, on_quit, on_filter=None):
        super().__init__(master)
        self.total_text = tk.StringVar()
        self.select_btn = ttk.Button(self, width=BUTTON_WIDTH, text="Select all", command=on_select)
        self.select_btn.pack(side="left")
        self.download_btn = ttk.Button(self, width=BUTTON_WIDTH, text="Download selected", command=on_download, state="disabled")
        self.download_btn.pack(side="left", padx=6)
        self.cancel_btn = ttk.Button(self, width=BUTTON_WIDTH, text="Cancel", command=on_cancel, state="disabled")
        self.cancel_btn.pack(side="left")
        self.filter_btn = ttk.Button(self, width=BUTTON_WIDTH, text="Filters…", command=on_filter)
        self.filter_btn.pack(side="left", padx=6)
        ttk.Button(self, width=BUTTON_WIDTH, text="Quit", style="quit.TButton", command=on_quit).pack(side="right")

    def set_state(self, can_download, busy):
        self.download_btn.config(state="normal" if can_download else "disabled")
        self.cancel_btn.config(state="normal" if busy else "disabled")

    def set_filter_active(self, active):
        self.filter_btn.config(text="Filters (on)…" if active else "Filters…")

    def set_selection(self, text, any_ticked):
        self.total_text.set(text)
        self.select_btn.config(text="Clear" if any_ticked else "Select all")


class ProgressPanel(ttk.Frame):
    """Per-file and overall progress bars with a status line underneath."""

    def __init__(self, master):
        super().__init__(master)
        self._file = ttk.Progressbar(self, mode="determinate")
        self._file.pack(fill="x", pady=(4, 0))
        self._overall = ttk.Progressbar(self, mode="determinate")
        self._overall.pack(fill="x", pady=(4, 0))
        self._status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._status, anchor="w").pack(fill="x", pady=(2, 10))

    def set_status(self, text):
        self._status.set(text)

    def set_overall(self, value, maximum=None):
        self._set(self._overall, value, maximum)

    def set_file(self, value, maximum=None):
        self._set(self._file, value, maximum)

    def reset(self):
        self.set_overall(0)
        self.set_file(0)

    @staticmethod
    def _set(bar, value, maximum):
        if maximum is None:
            bar.config(value=value)
        else:
            bar.config(maximum=maximum, value=value)
