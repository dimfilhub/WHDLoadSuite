import os
import queue
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from common.help_dialog import HelpDialog
from common.settings import Settings
from common.theme import HAVE_COLOR, MISSING_COLOR
from common.utils import human

from .downloader import Downloader, local_path
from .filters import FileFilter, FilterDialog
from .ftp import ROOT_PATH, FtpSession
from .sizing import FolderSizer
from .widgets import ActionBar, CheckTree, ConnectionPanel, DestinationPanel, ProgressPanel

APP_NAME = "Downloader"
README = Path(__file__).resolve().parent / "README.md"

# Messages carrying the session generation as their first argument; stale ones are dropped.
GEN_TAGGED = {"root", "connect_error", "children", "error", "foldersize", "sizefail", "sizing_idle"}


class DownloaderTab(ttk.Frame):
    """Downloader tab: wires the widgets to the FTP session, folder sizer and downloader.

    Background workers never touch Tk; they post (kind, ...) tuples to self.msgs and _poll()
    dispatches each one to the matching _on_<kind> handler on the UI thread.
    """

    def __init__(self, master, download_var, on_destination_change=None, on_quit=None, on_download_done=None):
        """download_var: StringVar shared with the host app (the downloads folder) holding the download folder."""
        super().__init__(master)
        self.download_var = download_var
        self._on_destination_change = on_destination_change
        self._on_quit = on_quit
        self._on_download_done = on_download_done
        self.settings = Settings()
        self.msgs = queue.Queue()
        self.sizer = FolderSizer(self.msgs.put)
        self.downloader = Downloader(self.msgs.put, ROOT_PATH)
        self._presence = {}  # remote file path -> already in the download folder? (cache)
        self.filter = FileFilter()  # applied to the files inside ticked folders at download time
        self._filter_dialog = None
        self.busy = False
        self.connected = False
        self.connecting = False
        self.gen = 0  # bumped on disconnect so late results from old sessions are ignored
        self._build_ui()
        self.update_total()
        self.after(100, self._poll)

    # ---------- UI ----------
    def show_help(self):
        HelpDialog.show(self.winfo_toplevel(), "WHDLoadSuite", start="downloader")

    def _build_ui(self):
        self.connection = ConnectionPanel(self, on_toggle=self.connect_clicked)
        self.connection.pack(fill="x", padx=10, pady=(10, 4))
        self.tree = CheckTree(self, ROOT_PATH, on_change=self.update_total, on_expand=self._load_children,
                              is_present=self._is_downloaded)
        self.tree.pack(fill="both", expand=True, padx=10, pady=4)
        self.destination = DestinationPanel(self, variable=self.download_var,
                                            on_change=self._destination_changed)
        self.destination.pack(fill="x", padx=10, pady=4)
        self.actions = ActionBar(self, on_download=self.download_clicked, on_cancel=self.downloader.cancel,
                                 on_select=self.tree.select_toggle, on_quit=self.quit_app,
                                 on_filter=self.show_filters)
        self.actions.pack(fill="x", padx=10, pady=4)
        # selection summary sits at the bottom left of the server list
        info = ttk.Frame(self)
        info.pack(fill="x", padx=10, before=self.destination)
        ttk.Label(info, textvariable=self.actions.total_text).pack(side="left")
        legend = tk.Frame(info, background="white")  # white so green/red read on the blue window
        legend.pack(side="right")
        for text, color in (("Already downloaded", HAVE_COLOR), ("Not downloaded yet", MISSING_COLOR)):
            tk.Label(legend, text=f"■ {text}", foreground=color, background="white").pack(side="left", padx=4)
        self.progress = ProgressPanel(self)
        self.progress.pack(fill="x", padx=10)

    def update_state(self):
        self.connection.set_state(self.connected, self.connecting)
        self.actions.set_state(self.connected and not self.busy, self.busy)

    def set_busy(self, busy):
        self.busy = busy
        self.update_state()

    def folder_files(self):
        """(files listed so far inside the ticked folders, number of ticked folders not listed yet)."""
        files, pending = [], 0
        for node in self.tree.top_items():
            if node.is_dir:
                if node.path in self.sizer.files:
                    files.extend(self.sizer.files[node.path])
                else:
                    pending += 1
        return files, pending

    def show_filters(self):
        if self._filter_dialog is not None and self._filter_dialog.winfo_exists():
            self._filter_dialog.lift()
            return
        self._filter_dialog = FilterDialog(self, self.filter, self.folder_files, self._set_filter)

    def _set_filter(self, new_filter):
        self.filter = new_filter
        self.actions.set_filter_active(new_filter.active)
        self.update_total()

    def update_total(self):
        totals = self.sizer.summarize(self.tree.top_items())
        if not totals.count:
            text = "Selected: nothing"
        else:
            text = f"Selected: {totals.count} item(s), {human(totals.total)}"
            if totals.measuring:
                text += f" + {totals.measuring} folder(s) being measured..."
            if totals.unavailable:
                text += f" (size of {totals.unavailable} folder(s) unavailable)"
            if self.filter.active:
                files, pending = self.folder_files()
                kept = self.filter.apply(files)
                loose = sum(n.size for n in self.tree.top_items() if not n.is_dir)
                text += (f"  |  Filters keep {len(kept)} of {len(files)} file(s), {human(loose + sum(f[1] for f in kept))}"
                         + (" so far" if pending or totals.unavailable else ""))
        self.actions.set_selection(text, self.tree.has_ticks)
        if self.connected:
            self.sizer.start(self.connection.credentials(), self.gen, lambda gen: gen == self.gen)

    # ---------- Connect / browse ----------
    def _reset_session_view(self):
        self.tree.clear()
        self._presence.clear()
        self.sizer.reset()
        self.update_total()

    def disconnect(self):
        self.gen += 1
        self.downloader.cancel()
        self.connected = False
        self.connecting = False
        self._reset_session_view()
        self.progress.reset()
        self.progress.set_status("Disconnected.")
        self.update_state()

    def _present(self, path, size):
        """True if the file is already in the download folder with the expected size."""
        if path not in self._presence:
            dest = self.destination.path
            try:
                ok = bool(dest) and os.path.getsize(local_path(dest, ROOT_PATH, path)) == size
            except OSError:
                ok = False
            self._presence[path] = ok
        return self._presence[path]

    def _is_downloaded(self, node):
        return self._present(node.path, node.size)

    def _destination_changed(self, path):
        self._presence.clear()
        self.tree.recolor_all()
        if self._on_destination_change:
            self._on_destination_change(path)

    def quit_app(self):
        if self.connected or self.connecting:
            msg = "You are connected to the FTP server.\n\nQuitting will close the connection"
            if self.busy:
                msg += " and cancel the running download"
            if not messagebox.askokcancel("Quit", msg + ". Continue?", icon="warning"):
                return
            self.disconnect()
        if self._on_quit:
            self._on_quit()

    def connect_clicked(self):
        if self.connected:
            self.disconnect()
            return
        if self.connecting:
            return
        if not self.connection.has_credentials():
            messagebox.showwarning("Missing credentials", "Please enter your username and password.")
            return
        self._reset_session_view()
        self.progress.set_status("Connecting...")
        self.connecting = True
        self.update_state()
        self._list_in_background(ROOT_PATH,
                                 lambda gen, entries: ("root", gen, entries),
                                 lambda gen, e: ("connect_error", gen, str(e)))

    def _load_children(self, iid, path):
        self._list_in_background(path,
                                 lambda gen, entries: ("children", gen, iid, entries),
                                 lambda gen, e: ("error", gen, f"Could not list {path}: {e}"))

    def _list_in_background(self, path, make_ok, make_err):
        """List path on a worker thread and post the message built by make_ok / make_err."""
        creds, gen = self.connection.credentials(), self.gen

        def work():
            try:
                with FtpSession(creds) as ftp:
                    entries = ftp.list_dir(path)
            except Exception as e:
                self.msgs.put(make_err(gen, e))
            else:
                self.msgs.put(make_ok(gen, entries))

        threading.Thread(target=work, daemon=True).start()

    # ---------- Download ----------
    def download_clicked(self):
        items = self.tree.top_items()
        if not items:
            messagebox.showinfo("Nothing selected", "Tick one or more files/folders first.")
            return
        dest = self.destination.path
        if not dest:
            messagebox.showwarning("No destination", "Choose a download folder.")
            return
        os.makedirs(dest, exist_ok=True)
        self.set_busy(True)
        self.downloader.start(self.connection.credentials(), items, dest, self.filter, dict(self.sizer.files))

    # ---------- Message handling ----------
    def _poll(self):
        try:
            while True:
                kind, *args = self.msgs.get_nowait()
                if kind in GEN_TAGGED:
                    gen, *args = args
                    if gen != self.gen:
                        continue
                getattr(self, f"_on_{kind}")(*args)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _on_foldersize(self, path, size, files):
        self.sizer.on_size(path, size, files)
        self.update_total()

    def _on_sizefail(self, paths):
        self.sizer.on_failed(paths)
        self.update_total()

    def _on_sizing_idle(self):
        self.sizer.on_idle()
        self.update_total()  # restarts the measuring thread if more folders were ticked meanwhile

    def _on_root(self, entries):
        self.connecting = False
        self.connected = True
        self.tree.populate("", entries)
        self.update_state()
        self.progress.set_status(f"Connected. {len(entries)} entries in {ROOT_PATH}. "
                                 "Select items (Cmd/Ctrl/Shift-click) and download.")

    def _on_connect_error(self, text):
        self.connecting = False
        self.update_state()
        self.progress.set_status("Connection failed.")
        messagebox.showerror("Connection failed", text)

    def _on_children(self, iid, entries):
        self.tree.populate(iid, entries)

    def _on_error(self, text):
        self.progress.set_status(text)

    def _on_status(self, text):
        self.progress.set_status(text)

    def _on_progress(self, value, maximum):
        self.progress.set_overall(value, maximum)

    def _on_fprogress(self, value, maximum):
        self.progress.set_file(value, maximum)

    def _on_filedone(self, path):
        self._presence.pop(path, None)
        self.tree.recolor_path(path)

    def _on_done(self, text):
        self.progress.set_file(0)
        self.progress.set_status(text)
        self.set_busy(False)
        if self._on_download_done:
            self._on_download_done()
