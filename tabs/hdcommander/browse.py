"""UI-independent file listing/navigation for the two locations (host folder, HDF image).

Used by the HDCommander tab."""
from dataclasses import dataclass
from pathlib import Path

from common import whdparse

from . import transfer
from .volume import HdfVolume


@dataclass
class Entry:
    name: str
    is_dir: bool
    size: int = 0
    info: str = ""


def human(n: float) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def sorted_entries(entries, at_root: bool):
    """Folders first, then by name; '..' on top unless at the root."""
    entries = sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))
    if not at_root:
        entries.insert(0, Entry("..", True))
    return entries


class HostLocation:
    is_host = True
    label = "Host"

    def __init__(self, path):
        self.path = Path(path).resolve()

    @property
    def location(self) -> str:
        return str(self.path)

    def at_root(self) -> bool:
        return self.path.parent == self.path

    def list_entries(self) -> list:
        out = []
        for p in self.path.iterdir():
            if p.name.startswith("."):
                continue
            try:
                is_dir = p.is_dir()
                size = 0 if is_dir else p.stat().st_size
            except OSError:
                continue
            info = ""
            if not is_dir and p.suffix.lower() in transfer.LHA_SUFFIXES:
                try:
                    g = whdparse.parse(p)
                    info = " ".join(x for x in (g.version, ",".join(g.languages)) if x)
                except Exception:
                    pass
            out.append(Entry(p.name, is_dir, size, info))
        return out

    def change_dir(self, name):
        self.path = self.path / name

    def go_up(self) -> str:
        old = self.path.name
        self.path = self.path.parent
        return old

    def file_path(self, name) -> Path:
        return self.path / name


class HdfLocation:
    is_host = False
    label = "Image"

    def __init__(self, volume: HdfVolume):
        self.volume = volume
        self.path = ""

    @property
    def location(self) -> str:
        return f"{self.volume.volume_name}:{self.path}"

    def at_root(self) -> bool:
        return not self.path

    def list_entries(self) -> list:
        return [Entry(e.name, e.is_dir, e.size, e.comment) for e in self.volume.listdir(self.path)]

    def change_dir(self, name):
        self.path = transfer.join(self.path, name)

    def go_up(self) -> str:
        head, _, tail = self.path.rpartition("/")
        self.path = head
        return tail

    def file_path(self, name) -> str:
        return transfer.join(self.path, name)
