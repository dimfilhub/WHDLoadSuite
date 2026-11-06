import threading
from dataclasses import dataclass

from .ftp import FtpSession


@dataclass
class Totals:
    count: int = 0        # top-level ticked items
    total: int = 0        # bytes known so far
    measuring: int = 0    # folders still being measured
    unavailable: int = 0  # folders that could not be measured


class FolderSizer:
    """Measures the total size of ticked folders in a background thread.

    Results are reported through post() as tagged tuples; the owner feeds them back through
    on_size(), on_failed() and on_idle() on the UI thread.
    """

    def __init__(self, post):
        self._post = post
        self.reset()

    def reset(self):
        self.sizes = {}        # remote folder path -> total bytes of everything below it
        self.files = {}        # remote folder path -> [(file path, size)] of everything below it
        self.jobs = []         # folder paths waiting to be measured
        self.wanted = set()    # folders that are currently ticked
        self.running = False   # a measuring thread is running
        self.failed = set()    # folders that could not be measured

    # ----- UI-thread callbacks -----
    def on_size(self, path, size, files=()):
        self.sizes[path] = size
        self.files[path] = list(files)

    def on_failed(self, paths):
        self.failed.update(paths)

    def on_idle(self):
        self.running = False

    # ----- Queries -----
    def summarize(self, nodes):
        """Total up the given top-level nodes and queue any folders that still need measuring."""
        totals = Totals()
        wanted = set()
        for node in nodes:
            totals.count += 1
            if not node.is_dir:
                totals.total += node.size
            elif node.path in self.sizes:
                totals.total += self.sizes[node.path]
            elif node.path in self.failed:
                totals.unavailable += 1
            else:
                totals.measuring += 1
                wanted.add(node.path)
                if node.path not in self.jobs:
                    self.jobs.append(node.path)
        self.wanted = wanted
        return totals

    # ----- Background work -----
    def start(self, creds, gen, is_current):
        """Start the measuring thread unless one is already running or nothing is queued."""
        if self.running or not self.jobs:
            return
        self.running = True
        threading.Thread(target=self._work, args=(creds, gen, is_current), daemon=True).start()

    def _sum_dir(self, ftp, path, gen, is_current, files):
        """Total size below path; every file found is appended to files so the listing is done once."""
        total = 0
        for node in ftp.list_dir(path):
            if not is_current(gen):
                raise InterruptedError
            if node.is_dir:
                total += self._sum_dir(ftp, node.path, gen, is_current, files)
            else:
                total += node.size
                files.append((node.path, node.size))
        return total

    def _work(self, creds, gen, is_current):
        path = None
        try:
            with FtpSession(creds) as ftp:
                while is_current(gen) and self.jobs:
                    path = self.jobs.pop(0)
                    if path not in self.wanted:
                        continue  # unticked while waiting
                    files = []
                    size = self._sum_dir(ftp, path, gen, is_current, files)
                    self._post(("foldersize", gen, path, size, files))
        except InterruptedError:
            pass
        except Exception as e:
            self._post(("error", gen, f"Could not measure folder size: {e}"))
            self._post(("sizefail", gen, [p for p in [path, *self.jobs] if p]))
            self.jobs.clear()
        finally:
            self._post(("sizing_idle", gen))
