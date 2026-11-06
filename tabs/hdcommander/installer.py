"""Install WHDLoad .lha archives into an HdfVolume.

Layout inside the image:  Games/<A-Z|0-9|#>/<GameFolder>/...   (+ the archive's
top-level .info icon next to the folder, so it shows up in Workbench).
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from common import lha
from common.gamepaths import game_name, group_dir
from .drawericon import drawer_icon
from .volume import HdfVolume, HdfError, MAX_NAME, _clean

GAMES_DIR = "Games"
INSTALLED, SKIPPED, FAILED = "installed", "skipped", "failed"
NOT_WHDLOAD = "not_whdload"   # no .slave in the archive: not a game, callers may copy it as a file


class NotWhdload(HdfError):
    pass


@dataclass
class InstallResult:
    archive: Path
    status: str
    message: str = ""
    folder: str = ""          # e.g. "Games/A/AlienBreed"
    files: int = 0
    size: int = 0


def _plan(archive: Path):
    """Read the archive and work out where everything goes. Returns (folder_name, group, entries)
    with entries = [(relative_path, bytes|None)]. Raises HdfError/lha.LhaError."""
    entries = [(p, c) for p, c in lha.iter_files(archive)]
    slaves = sorted((p for p, c in entries if c is not None and p.lower().endswith(".slave")),
                    key=lambda p: (p.count("/"), p.lower()))
    if not slaves:
        raise NotWhdload("no .slave file in archive (not a WHDLoad game)")
    parts = PurePosixPath(slaves[0]).parts
    if len(parts) > 1:
        folder = parts[0]
    else:                                    # slave at the archive root: wrap in a folder
        folder = game_name(archive)[:MAX_NAME]
        entries = [(folder + "/" + p, c) for p, c in entries]
    return folder, group_dir(folder), entries


def install(volume: HdfVolume, archive, progress=None, overwrite=False) -> InstallResult:
    """Install one archive. progress(done_bytes, total_bytes, path) is called per file."""
    archive = Path(archive)
    try:
        folder, group, entries = _plan(archive)
        base = f"{GAMES_DIR}/{group}"
        dest = f"{base}/{folder}"
        if volume.exists(dest):
            if not overwrite:
                return InstallResult(archive, SKIPPED, "already installed", dest)
        # validate every name and collision before touching the image
        seen = {}
        for path, _ in entries:
            _clean(path)
            key = path.lower()
            if key in seen:
                raise HdfError("names differ only by case: %s / %s" % (seen[key], path))
            seen[key] = path
        total = sum(len(c) for _, c in entries if c is not None)
        if total > volume.free_bytes + _existing_size(volume, dest, overwrite):
            raise HdfError("not enough free space (%d bytes needed)" % total)
    except NotWhdload as exc:
        return InstallResult(archive, NOT_WHDLOAD, str(exc))
    except Exception as exc:
        return InstallResult(archive, FAILED, str(exc))

    created_dest = not volume.exists(dest)
    try:
        if not created_dest:
            volume.delete(dest, recursive=True)
            created_dest = True
        volume.makedirs(base)
        # without these icons the Games and letter drawers are invisible in Workbench
        for icon in (GAMES_DIR + ".info", base + ".info"):
            if not volume.exists(icon):
                volume.put_bytes(_system_drawer_icon(volume), icon)
        done = count = 0
        for path, content in entries:
            target = f"{base}/{path}"
            if content is None:
                volume.makedirs(target)
                continue
            volume.makedirs(str(PurePosixPath(target).parent))
            if volume.exists(target):               # e.g. icon shared by two games
                volume.delete(target)
            volume.put_bytes(content, target)
            done += len(content)
            count += 1
            if progress:
                progress(done, total, path)
        return InstallResult(archive, INSTALLED, "", dest, count, done)
    except Exception as exc:
        try:
            if volume.exists(dest):
                volume.delete(dest, recursive=True)
        except HdfError:
            pass
        return InstallResult(archive, FAILED, str(exc))


def _system_drawer_icon(volume) -> bytes:
    """The drawer icon of the image's own Workbench (so ours matches the other drawers);
    a generated one if the image has none."""
    try:
        names = {e.name.lower(): e.name for e in volume.listdir("") if not e.is_dir}
        for want in ("utilities.info", "tools.info", "storage.info", "prefs.info", "system.info"):
            if want in names:
                data = volume.read(names[want])
                if data[:2] == b"\xe3\x10" and data[48] == 2:     # WBDRAWER
                    # forget the source drawer's position so Workbench places ours itself
                    return data[:58] + b"\x80\x00\x00\x00\x80\x00\x00\x00" + data[66:]
    except HdfError:
        pass
    return drawer_icon()


def _existing_size(volume, path, overwrite):
    if not overwrite or not volume.exists(path):
        return 0
    total = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        for e in volume.listdir(cur):
            if e.is_dir:
                stack.append(cur + "/" + e.name)
            else:
                total += e.size
    return total
