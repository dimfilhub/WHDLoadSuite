"""Copy files between the host and an HdfVolume (no UI, so it can be tested without Tk)."""
import shutil
from dataclasses import dataclass
from pathlib import Path

from .installer import install, INSTALLED, SKIPPED, FAILED, NOT_WHDLOAD
from .volume import HdfError, HdfVolume

OK = "ok"
LHA_SUFFIXES = (".lha", ".lzh")


@dataclass
class Item:
    name: str
    status: str            # "ok" | "skipped" | "failed"
    message: str = ""


def join(base: str, name: str) -> str:
    return f"{base}/{name}" if base else name


def put_host(vol: HdfVolume, src, dest_dir: str, progress=None, overwrite=False, install_games=False) -> list:
    """Copy a host file or folder into dest_dir of the image, as plain files.
    With install_games only .lha archives are processed: each WHDLoad game is installed under
    Games/... (dest_dir is ignored) and anything else is skipped. progress(done_bytes, total_bytes,
    name) is called while an archive is installed."""
    src = Path(src)
    if src.is_dir():
        base = join(dest_dir, src.name)
        items, seen = [], False
        for child in sorted(src.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith("."):
                continue
            if install_games and child.is_file() and child.suffix.lower() not in LHA_SUFFIXES:
                continue                           # e.g. a readme next to the games
            seen = True
            items += put_host(vol, child, base, progress, overwrite, install_games)
        if not seen and not install_games:
            try:
                vol.makedirs(base)
            except HdfError as exc:
                items.append(Item(src.name, FAILED, str(exc)))
        return items
    try:
        if install_games:
            if src.suffix.lower() not in LHA_SUFFIXES:
                return [Item(src.name, SKIPPED, "not an .lha archive")]
            res = install(vol, src, progress, overwrite=overwrite)
            if res.status == INSTALLED:
                return [Item(src.name, OK, res.folder)]
            return [Item(src.name, SKIPPED if res.status == NOT_WHDLOAD else res.status, res.message)]
        dest = join(dest_dir, src.name)
        if vol.exists(dest):
            if not overwrite:
                return [Item(src.name, SKIPPED, "already exists")]
            vol.delete(dest, recursive=True)
        vol.makedirs(dest_dir)
        vol.put(str(src), dest)
        return [Item(src.name, OK, dest)]
    except (HdfError, OSError) as exc:
        return [Item(src.name, FAILED, str(exc))]


def get_hdf(vol: HdfVolume, ami_path: str, host_dir, overwrite=False) -> list:
    """Copy a file or folder from the image into a host folder."""
    host_dir = Path(host_dir)
    name = ami_path.rsplit("/", 1)[-1]
    target = host_dir / name
    try:
        if vol.isdir(ami_path):
            target.mkdir(exist_ok=True)
            items = []
            for e in vol.listdir(ami_path):
                items += get_hdf(vol, join(ami_path, e.name), target, overwrite)
            return items
        if target.exists() and not overwrite:
            return [Item(name, SKIPPED, "already exists")]
        target.write_bytes(vol.read(ami_path))
        return [Item(name, OK, str(target))]
    except (HdfError, OSError) as exc:
        return [Item(name, FAILED, str(exc))]


def delete_host(path) -> None:
    path = Path(path)
    shutil.rmtree(path) if path.is_dir() else path.unlink()


def summarize(items) -> str:
    counts = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1
    return ", ".join(f"{n} {k}" for k, n in counts.items()) or "nothing to do"


def report(items) -> str:
    tag = {OK: "OK  ", SKIPPED: "SKIP", FAILED: "FAIL"}
    return "\n".join(f"{tag.get(i.status, i.status)} {i.name}  {i.message}" for i in items)


def transfer_items(volume, src, dst, names, move=False, progress=None, install_games=False) -> list:
    """Copy (or move) names from location `src` to `dst`; one is a HostLocation, the other an
    HdfLocation (see browse.py). progress(fraction, text) is called as work proceeds.
    install_games=True (host -> image only) installs the selected .lha archives as WHDLoad games instead
    of copying files."""
    to_hdf = src.is_host
    items, total = [], max(len(names), 1)
    for i, name in enumerate(names):
        if progress:
            progress(i / total, name)

        def inner(done, size, label, _i=i):
            progress((_i + done / max(size, 1)) / total, label)

        if to_hdf:
            got = put_host(volume, src.file_path(name), dst.path, inner if progress else None,
                           install_games=install_games)
        else:
            got = get_hdf(volume, src.file_path(name), dst.path)
        items += got
        if move and got and all(it.status == OK for it in got):
            try:
                if to_hdf:
                    delete_host(src.file_path(name))
                else:
                    volume.delete(src.file_path(name), recursive=True)
            except (HdfError, OSError) as exc:
                items.append(Item(name, FAILED, f"copied, but not removed: {exc}"))
    return items


def delete_items(volume, loc, names) -> list:
    """Delete names from a location (host: permanently); returns the failures as Items."""
    failed = []
    for name in names:
        try:
            if loc.is_host:
                delete_host(loc.file_path(name))
            else:
                volume.delete(loc.file_path(name), recursive=True)
        except (HdfError, OSError) as exc:
            failed.append(Item(name, FAILED, str(exc)))
    return failed


def preview_text(volume, loc, name, limit=64 * 1024) -> str:
    """Text for viewing a file: its content, or a hex dump when it looks binary."""
    if loc.is_host:
        with open(loc.file_path(name), "rb") as fh:
            data = fh.read(limit)
    else:
        data = volume.read(loc.file_path(name))[:limit]
    if b"\0" not in data[:4096]:
        return data.decode("latin-1")
    lines = []
    for off in range(0, min(len(data), 4096), 16):
        chunk = data[off:off + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk).ljust(47)
        lines.append(f"{off:06x}  {hexs}  {''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)}")
    return "\n".join(lines)
