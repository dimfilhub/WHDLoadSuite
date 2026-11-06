"""Pictures of the games from a GamebaseAmiga folder, for the launch screen.

The user points the app at the `data` folder of GamebaseAmiga (the one with `screenshots/` and
`extras/Cover Scans/`), which is only read. Or at the original Gamebase_Amiga_v2.3 source (Screenshots.rar and
Extras.rar): then extract() unpacks the screenshots and the front covers into the app's own data folder, with
`unar`, and those are used. Which picture belongs to which WHDLoad game is in gamebase_images.json
(made by tools/make_gamebase_map.py from the GamebaseAmiga database): game name -> relative file names. A game that
is not in that file is looked for by its name among the picture file names.

Names are compared ignoring case and Unicode form, so a collection extracted on one OS works on another.
Standard library only (no tkinter, no Pillow): the launch screen does the drawing.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

from . import amiberry_runtime
from .gamepaths import base_name
from .paths import PROJECT_ROOT

MAP_FILE = Path(__file__).with_name("gamebase_images.json")
MODES = ("best", "screenshot", "cover")        # which picture the launch screen shows
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
SCREENSHOTS = "screenshots"
COVERS = "extras/Cover Scans"
SOURCE_ARCHIVES = {"screenshots": "Screenshots.rar", "extras": "Extras.rar"}
FRONT_COVERS = "Extras/Cover Scans/*_Front.*"       # inside Extras.rar: the other 6 GB are not needed
NO_UNAR = ("unar not found. Install The Unarchiver's command line tools (macOS: brew install unar; Linux: "
           "sudo apt install unar; Windows: https://theunarchiver.com/command-line).")
NEEDED_BYTES = 700 * 2 ** 20                          # room wanted before extracting (about 330 MB are written)


def norm(text: str) -> str:
    """A name or relative path as compared: one Unicode form, no case."""
    return unicodedata.normalize("NFC", text).casefold()


def name_key(text: str) -> str:
    """A game name reduced to its letters and digits, accents removed: 'Dragon's Lair (AGA)' -> 'dragonslair'."""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)).casefold())


def split_camel(text: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)


def load_map() -> dict:
    """{game name: {"s": screenshot path, "c": cover path}} (paths relative to the data folder); {} if missing."""
    try:
        data = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    images = data.get("images") if isinstance(data, dict) else None
    return images if isinstance(images, dict) else {}


def _child(root: Path, *names: str) -> Path | None:
    """root/names…, matching each name without regard to case (the folders are `Screenshots` in the original
    archives, `screenshots` in GamebaseAmiga's data folder)."""
    path = Path(root)
    for name in names:
        if not path.is_dir():
            return None
        found = next((c for c in path.iterdir() if c.name.casefold() == name.casefold()), None)
        if found is None:
            return None
        path = found
    return path


def _has_pictures(folder: Path) -> bool:
    return _child(folder, *SCREENSHOTS.split("/")) is not None or _child(folder, *COVERS.split("/")) is not None


def extracted_dir() -> Path:
    """Where extract() puts the pictures: inside the app's own data folder."""
    return amiberry_runtime.data_dir() / "Gamebase"


def extracted_size() -> int:
    """Bytes the extracted pictures take; 0 if there are none."""
    folder = extracted_dir()
    if not folder.is_dir():
        return 0
    return sum(os.path.getsize(os.path.join(root, f)) for root, _, files in os.walk(folder) for f in files)


def delete_extracted() -> int:
    """Delete the pictures extract() made (only that folder, never the source) and return the bytes freed."""
    folder = extracted_dir()
    if not folder.is_dir():
        return 0
    freed = extracted_size()
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        raise ExtractError(f"Could not delete {folder}: {exc}") from exc
    forget()
    return freed


def source_archives(folder) -> dict:
    """{"screenshots": Path, "extras": Path} for the Gamebase archives found in a folder (either may be missing);
    {} if the folder holds neither."""
    if not folder or not str(folder).strip():
        return {}
    top = Path(str(folder).strip()).expanduser()
    if not top.is_dir():
        return {}
    found = {}
    for key, filename in SOURCE_ARCHIVES.items():
        path = _child(top, filename)
        if path is not None and path.is_file():
            found[key] = path
    return found


def resolve_root(folder) -> Path | None:
    """Where the pictures are for the folder the user chose: the data folder itself, the GamebaseAmiga folder that
    holds it, or, for the original Gamebase source, the folder its pictures were extracted to. None if there are none."""
    if not folder or not str(folder).strip():
        return None
    folder = Path(str(folder).strip()).expanduser()
    for candidate in (folder, folder / "data"):
        if candidate.is_dir() and _has_pictures(candidate):
            return candidate
    if source_archives(folder) and _has_pictures(extracted_dir()):
        return extracted_dir()
    return None


class Library:
    """The pictures found in one data folder. Built once (a walk over the two folders), then looked up by name."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.files = {}              # normalised relative path -> real path
        self._names = None           # name_key -> {"s": path, "c": path}, built the first time it is needed
        for sub in (SCREENSHOTS, COVERS):
            top = _child(self.root, *sub.split("/"))
            if top is None:
                continue
            for path in top.rglob("*"):
                if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file():
                    self.files[norm(path.relative_to(self.root).as_posix())] = path
        self.screenshots = sum(1 for k in self.files if k.startswith(norm(SCREENSHOTS) + "/"))
        self.covers = len(self.files) - self.screenshots

    def path(self, relative: str) -> Path | None:
        return self.files.get(norm(relative)) if relative else None

    def by_name(self) -> dict:
        """Pictures by game name, for games the map does not know: screenshots by file name, covers by the name in
        front of `_Front`."""
        if self._names is None:
            names = {}
            for path in self.files.values():
                rel = path.relative_to(self.root).as_posix()
                if norm(rel).startswith(norm(SCREENSHOTS) + "/"):
                    stem = re.sub(r"_\d+$", "", path.stem)
                    names.setdefault(name_key(stem.replace("_", " ")), {}).setdefault("s", path)
                elif path.stem.endswith("_Front"):
                    names.setdefault(name_key(path.stem[:-6]), {}).setdefault("c", path)
            self._names = names
        return self._names

    def describe(self) -> str:
        return f"{self.screenshots:,} screenshots and {self.covers:,} cover scans"

    def find(self, archive_stem: str, mode: str = "best", games: dict | None = None):
        """(file, "screenshot" or "cover") for a game, or None. `archive_stem` is the archive name without .lha;
        `mode` is one of MODES. A version the map does not list uses its game's entry (the name without `_v1.0`)."""
        games = load_map() if games is None else games
        base = base_name(archive_stem)
        entry = games.get(archive_stem) or games.get(base)
        if not entry:
            lowered = {norm(k): v for k, v in games.items()} if games else {}
            entry = lowered.get(norm(archive_stem)) or lowered.get(norm(base))
        found = {}
        if entry:
            for kind in ("s", "c"):
                path = self.path(entry.get(kind, ""))
                if path:
                    found[kind] = path
        if not found:                                           # not in the map: go by the picture file names
            found = self.by_name().get(name_key(split_camel(base))) or self.by_name().get(name_key(base)) or {}
        order = {"screenshot": ("s",), "cover": ("c",)}.get(mode, ("s", "c"))
        for kind in order:
            if kind in found:
                return found[kind], "screenshot" if kind == "s" else "cover"
        return None


_libraries: dict = {}


def library(folder) -> Library | None:
    """The Library for the folder the user chose (kept between calls), or None if it holds no pictures."""
    root = resolve_root(folder)
    if root is None:
        return None
    key = str(root)
    if key not in _libraries:
        _libraries.clear()                        # only the current folder is worth keeping
        _libraries[key] = Library(root)
    return _libraries[key]


def forget():
    """Drop the kept Library, so the next lookup walks the folder again (after the user changed it)."""
    _libraries.clear()


def find_image(folder, archive_stem: str, mode: str = "best"):
    """(file, kind) of the game's picture in the chosen folder, or None."""
    lib = library(folder)
    return lib.find(archive_stem, mode) if lib else None


# --- extracting the pictures from the original Gamebase source ----------------------------------------------

class ExtractError(RuntimeError):
    pass


def tool_folders() -> list:
    """Where `unar` and `lsar` are looked for besides the PATH: the usual install places (a started app may not
    see them on its PATH) and a `tools` or `unar` folder next to the app, which is where Windows users can unzip
    The Unarchiver's command line tools."""
    if sys.platform == "win32":
        places = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        folders = [Path(p) / "unar" for p in places] + [Path(p) / "The Unarchiver" for p in places]
    else:
        folders = [Path(p) for p in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/opt/local/bin", "/snap/bin")]
    return folders + [PROJECT_ROOT / "tools", PROJECT_ROOT / "unar"]


def find_tool(name: str) -> str | None:
    """`unar` or `lsar` (`unar.exe` on Windows): on the PATH, else in one of tool_folders()."""
    found = shutil.which(name)
    if found:
        return found
    suffixes = ("", ".exe") if sys.platform == "win32" else ("",)
    for folder in tool_folders():
        for suffix in suffixes:
            path = folder / (name + suffix)
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
    return None


def _no_console() -> dict:
    """Windows: do not flash a console window for the helper program."""
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def _count_files(folder: Path) -> int:
    return sum(len(files) for _, _, files in os.walk(folder))


def _expected(lsar, archive: Path, pattern: re.Pattern | None) -> int | None:
    """How many files will be extracted (for the progress), or None if it cannot be told."""
    if not lsar:
        return None
    try:
        out = subprocess.run([lsar, str(archive)], capture_output=True, text=True, timeout=60, errors="replace",
                             **_no_console()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    names = out.splitlines()[1:]
    return sum(1 for n in names if pattern is None or pattern.match(n)) or None


def extract(source_folder, dest=None, progress=None, unar=None, lsar=None) -> str:
    """Unpack the screenshots and the front covers of the Gamebase source (Screenshots.rar and Extras.rar in
    `source_folder`) into `dest` (default: the app's own data folder). Only what the launch screen uses is
    written, about 330 MB; the rest of Extras.rar (6 GB) is skipped. `progress(text)` is told how it goes.
    Returns a one-line summary. Raises ExtractError."""
    sources = source_archives(source_folder)
    if not sources:
        raise ExtractError("Screenshots.rar and Extras.rar were not found in that folder.")
    unar = unar or find_tool("unar")
    if not unar:
        raise ExtractError(NO_UNAR)
    lsar = lsar or find_tool("lsar")
    dest = Path(dest) if dest else extracted_dir()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(dest.parent).free < NEEDED_BYTES:
        raise ExtractError(f"Not enough free space for the pictures in {dest.parent} (about 700 MB are needed).")
    jobs = []
    if "screenshots" in sources:
        jobs.append(("screenshots", sources["screenshots"], [], None))
    if "extras" in sources:
        jobs.append(("front covers", sources["extras"], [FRONT_COVERS],
                     re.compile(r"^Extras/Cover Scans/.*_Front\.", re.I)))
    tmp = dest.parent / (dest.name + ".extracting")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    try:
        for label, archive, patterns, pattern in jobs:
            total = _expected(lsar, archive, pattern)
            part = tmp / label.replace(" ", "_")
            part.mkdir()
            with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as errors:    # a file: a full pipe would stall unar
                proc = subprocess.Popen([unar, "-q", "-f", "-D", "-o", str(part), str(archive), *patterns],
                                        stdout=subprocess.DEVNULL, stderr=errors, text=True, **_no_console())
                while proc.poll() is None:
                    if progress:
                        done = _count_files(part)
                        progress(f"Extracting {label}… {done:,}" + (f" of {total:,}" if total else "") + " files")
                    time.sleep(0.4)
                errors.seek(0)
                detail = errors.read().strip().splitlines()
            if proc.returncode != 0:
                raise ExtractError(f"unar could not unpack {archive.name}" + (f": {detail[-1]}" if detail else "."))
        dest.mkdir(parents=True, exist_ok=True)
        for part in tmp.iterdir():                      # replace what an earlier extraction left, folder by folder
            for item in part.iterdir():
                target = dest / item.name
                if target.is_dir():
                    shutil.rmtree(target)
                os.replace(item, target)
    except OSError as exc:
        raise ExtractError(str(exc)) from exc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    forget()
    lib = Library(dest)
    return f"Extracted {lib.describe()} to {dest}."
