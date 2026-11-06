import os
import threading
from typing import NamedTuple

from .ftp import FtpSession
from common.utils import human


def relative_path(root, remote):
    """Path of a remote file below the server root, with forward slashes."""
    return remote[len(root):].lstrip("/") if remote.startswith(root) else remote.lstrip("/")


def local_path(dest, root, remote):
    """Where a remote file is stored: the server layout is mirrored below dest."""
    return os.path.join(dest, *relative_path(root, remote).split("/"))


class PlannedFile(NamedTuple):
    remote: str
    rel: str  # path relative to the download folder
    size: int


class Downloader:
    """Downloads files and folders in a background thread and reports progress through post()."""

    def __init__(self, post, root_path):
        self._post = post
        self._root = root_path
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def start(self, creds, items, dest, file_filter=None, listed=None):
        """file_filter: FileFilter applied to the files found inside ticked folders.
        listed: {folder path: [(file path, size)]} already listed by the folder sizer (saves the FTP calls)."""
        self._cancel.clear()
        threading.Thread(target=self._run, args=(creds, items, dest, file_filter, listed or {}), daemon=True).start()

    # ----- Worker -----
    def _run(self, creds, items, dest, file_filter, listed):
        try:
            with FtpSession(creds) as ftp:
                files = self._scan(ftp, items, file_filter, listed)
                total = sum(f.size for f in files)
                span = max(total, 1)
                done = skipped = 0
                self._post(("progress", 0, span))
                for idx, f in enumerate(files, 1):
                    if self._cancel.is_set():
                        break
                    local = self._local_path(dest, f.rel)
                    if local is None:
                        continue
                    os.makedirs(os.path.dirname(local), exist_ok=True)
                    if os.path.exists(local) and os.path.getsize(local) == f.size:
                        done += f.size
                        skipped += 1
                        self._post(("progress", done, span))
                        self._post(("filedone", f.remote))
                        continue
                    self._post(("status", f"[{idx}/{len(files)}] {f.rel}"))
                    self._post(("fprogress", 0, max(f.size, 1)))
                    if not self._fetch(ftp, f, local, done, span):
                        break
                    done += f.size
                    self._post(("fprogress", max(f.size, 1), max(f.size, 1)))
                    self._post(("filedone", f.remote))
            if self._cancel.is_set():
                self._post(("done", "Cancelled."))
            else:
                self._post(("done", f"Finished: {len(files)} file(s), {skipped} skipped, {human(total)} total."))
        except Exception as e:
            self._post(("done", f"Error: {e}"))

    def _scan(self, ftp, items, file_filter, listed):
        """Plan the download. The filter only applies to files found inside ticked folders;
        a file that was ticked itself is always kept."""
        files, inside = [], []
        for n, node in enumerate(items, 1):
            self._post(("status", f"Scanning {node.name} ({n}/{len(items)})..."))
            self._walk(ftp, node, inside if node.is_dir else files, listed)
        if file_filter is not None and file_filter.active:
            found = len(inside)
            inside = file_filter.apply(inside)
            self._post(("status", f"Filters keep {len(inside)} of {found} files."))
        return files + inside

    def _walk(self, ftp, node, out, listed):
        """Collect a PlannedFile for every file below node."""
        if self._cancel.is_set():
            return
        if not node.is_dir:
            out.append(PlannedFile(node.path, relative_path(self._root, node.path), node.size))
            return
        if node.path in listed:
            out.extend(PlannedFile(p, relative_path(self._root, p), s) for p, s in listed[node.path])
            return
        for child in ftp.list_dir(node.path):
            self._walk(ftp, child, out, listed)

    @staticmethod
    def _local_path(dest, rel):
        """Resolve rel under dest, or None if a malicious server name would escape it."""
        local = os.path.realpath(os.path.join(dest, rel))
        if not local.startswith(os.path.realpath(dest) + os.sep):
            return None
        return local

    def _fetch(self, ftp, f, local, base, span):
        """Download one file. Returns False if it was cancelled (the partial file is removed)."""
        got = 0
        cancelled = False

        with open(local, "wb") as fh:
            def write(data):
                nonlocal got
                if self._cancel.is_set():
                    raise InterruptedError
                fh.write(data)
                got += len(data)
                self._post(("progress", base + got, span))
                self._post(("fprogress", got, max(f.size, 1)))

            try:
                ftp.retrieve(f.remote, write)
            except InterruptedError:
                cancelled = True
        if cancelled:
            os.remove(local)
        return not cancelled
