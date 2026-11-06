"""Find, set up and start Amiberry. The app side of the emulator: the command lines, the shared Amiberry home
and the per-game overrides live in amiberry_runtime.py (also used by standalone executables)."""
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import amiberry_runtime as rt
from .amiberry_runtime import Options
from .paths import EMULATOR_DIR

MAC_BINARY = Path("Contents") / "MacOS" / "Amiberry"
EXE_NAMES = ("Amiberry.app", "amiberry.exe", "Amiberry.exe", "amiberry", "Amiberry")


# --- finding Amiberry -------------------------------------------------------------------------------------

def resolve_executable(path):
    """The real Amiberry binary for what the user picked (an .app bundle, a folder or the binary), or None."""
    if not path or not str(path).strip():
        return None
    p = Path(path).expanduser()
    if p.is_dir() and p.suffix.lower() == ".app":
        p = p / MAC_BINARY
    elif p.is_dir():
        for name in EXE_NAMES:
            found = resolve_executable(p / name)
            if found:
                return found
        return None
    return p if p.is_file() else None


def detect():
    """Amiberry in the usual places: the project's emulator/ folder, /Applications, ~/Applications, PATH."""
    for candidate in (EMULATOR_DIR, Path("/Applications/Amiberry.app"), Path.home() / "Applications" / "Amiberry.app"):
        found = resolve_executable(candidate)
        if found:
            return found
    on_path = shutil.which("amiberry")
    return Path(on_path) if on_path else None


def find(chosen=None):
    """The folder/app the user chose in Settings if it holds Amiberry, else the usual places."""
    return resolve_executable(chosen) or detect()


def bundle_source(exe):
    """(folder to copy into an executable, path of the binary inside it, relative to that folder's parent).
    macOS: the whole Amiberry.app. Elsewhere the folder holding the binary, which must be a complete install."""
    exe = Path(exe).resolve()
    for parent in exe.parents:
        if parent.suffix.lower() == ".app":
            return parent, f"{parent.name}/{exe.relative_to(parent).as_posix()}"
    return exe.parent, f"{exe.parent.name}/{exe.name}"


# --- ROMs -------------------------------------------------------------------------------------------------

def rom_files(folder) -> list:
    """The Kickstart ROM files in a folder."""
    folder = Path(folder) if folder else None
    if folder is None or not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".rom")


def a1200_rom(folder):
    """A Kickstart 3.1 A1200 ROM in the folder, for prepared drives and hard disk images, or None."""
    roms = [p for p in rom_files(folder) if "a1200" in p.name.lower()]
    return roms[0] if roms else None


# --- setting up the shared home ---------------------------------------------------------------------------

def download_whdboot(exe, home=None):
    """`amiberry --download-whdboot` into the shared home: fetches WHDLoad (whdload.de) and the boot files and
    Kickstart RTB files (Aminet). Returns (ok, output)."""
    try:
        r = subprocess.run([str(exe), "--download-whdboot"], capture_output=True, text=True, timeout=300,
                           env=rt.environment(home or rt.home_dir()))
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def prepare_home(exe, kickstarts=None, home=None, download=True):
    """Make the shared Amiberry home ready: copy the user's Kickstart ROMs in and, if WHDLoad is missing,
    download it. Returns (ok, message); ok is False only if WHDLoad could not be obtained."""
    home = Path(home or rt.home_dir())
    rt.seed_home(home, roms=rom_files(kickstarts))
    if rt.has_whdload(home):
        return True, ""
    if not download:
        return False, "WHDLoad is not installed in the Amiberry folder yet."
    _exit_ok, output = download_whdboot(exe, home)
    ok = rt.has_whdload(home)       # Amiberry's exit code is not reliable (it can be non-zero after a good download)
    return ok, "" if ok else f"Could not download WHDLoad: {output or 'no output'}"


# --- what Amiberry knows: ROMs and the game database ------------------------------------------------------

@dataclass
class RomReport:
    scanned: bool = False                          # Amiberry has run and listed its ROMs at least once
    known: list = field(default_factory=list)      # (what Amiberry calls it, file name, file still exists)
    unknown: list = field(default_factory=list)    # file names in its ROMs folder that it did not recognise
    has_a600: bool = False                         # a Kickstart for the A500 / A600 / A2000 3.1 is among the known


def settings_ini(exe, home=None):
    """Amiberry's small settings file (window positions and the list of ROMs it found), from `--dump-paths`.
    It lives inside the app's Amiberry folder (see amiberry_runtime.environment). None if it cannot be found."""
    try:
        out = subprocess.run([str(exe), "--dump-paths"], capture_output=True, text=True, timeout=20,
                             env=rt.environment(Path(home or rt.home_dir()), create=False)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "amiberry_ini_file" and value.strip():
            return Path(value.strip())
    return None


def detected_roms(ini) -> list:
    """The ROM files Amiberry recognised, from the [DetectedROMs] list of its settings file: (description, path).
    Entries without a file (its built-in ROM replacements, written as ':NAME') are left out."""
    try:
        text = Path(ini).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return []
    found, inside = [], False
    for line in text.splitlines():
        if line.startswith("["):
            inside = line.strip() == "[DetectedROMs]"
        elif inside:
            m = re.match(r'ROM_\d+=(.*?) / "(.*)"\s*$', line)
            if m:
                found.append((m.group(1), Path(m.group(2))))
    return found


def rom_report(exe, home=None) -> RomReport:
    """Which of the user's Kickstart ROMs Amiberry recognises (the rest it silently ignores)."""
    home = Path(home or rt.home_dir())
    if not home.is_dir():
        return RomReport()           # nothing has been set up yet: nothing to ask Amiberry about
    ini = settings_ini(exe, home)
    entries = detected_roms(ini) if ini else []
    report = RomReport(scanned=bool(ini and Path(ini).is_file() and entries))
    for description, path in entries:
        report.known.append((description, path.name, path.is_file()))
    known_names = {name for _, name, _ in report.known}
    report.unknown = [p.name for p in rom_files(home / "ROMs") if p.name not in known_names] if report.scanned else []
    report.has_a600 = any("A600" in d for d, _, ok in report.known if ok)
    return report


def database_info(home=None):
    """The WHDLoad game database in the app's Amiberry folder: {"games": int, "generated": "YYYY-MM-DD"} or None."""
    db = Path(home or rt.home_dir()) / rt.DB_FILE
    try:
        with open(db, "rb") as fh:
            head = fh.read(2048).decode("utf-8", errors="replace")
    except OSError:
        return None
    games = re.search(r'"game_count":\s*(\d+)', head)
    generated = re.search(r'"generated":\s*"(\d{4}-\d{2}-\d{2})', head)
    if not games:
        return None
    return {"games": int(games.group(1)), "generated": generated.group(1) if generated else ""}


def update_whdboot(exe, home=None):
    """Refresh WHDLoad and the game database (`--download-whdboot`, a few seconds). Returns (ok, output); ok means
    WHDLoad and a readable database are there afterwards, whatever Amiberry's exit code says."""
    home = Path(home or rt.home_dir())
    _exit_ok, output = download_whdboot(exe, home)
    ok = rt.has_whdload(home) and database_info(home) is not None
    return ok, output


# --- starting things --------------------------------------------------------------------------------------

_started: list = []     # emulators this app started and that may still be running


def _start(cmd, home):
    proc = subprocess.Popen(cmd, env=rt.environment(home), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    _started.append(proc)
    return proc


def running() -> bool:
    """True while an emulator started by this app is still open."""
    _started[:] = [p for p in _started if p.poll() is None]
    return bool(_started)


def launch_game(exe, archive, drive=None, kickstarts=None, options=Options(), home=None, overrides=None):
    """Start a game without waiting for it. Runs the .lha directly unless the game is listed as needing its
    prepared `drive` folder. Raises RuntimeError with a readable reason if it cannot start."""
    home = Path(home or rt.home_dir())
    archive = Path(archive)
    stem = archive.stem
    overrides = rt.load_overrides() if overrides is None else overrides
    ok, message = prepare_home(exe, kickstarts, home)
    if not ok:
        raise RuntimeError(message)
    if rt.mode_for(stem, overrides) == "drive":
        if drive is None or not Path(drive).is_dir():
            raise RuntimeError(f"{stem} runs from a prepared drive: prepare it first.")
        rom = a1200_rom(kickstarts) or a1200_rom(home / "ROMs")
        if rom is None:
            raise RuntimeError("No Kickstart 3.1 A1200 ROM found: put it in the emulator/Kickstarts folder.")
        return _start(rt.drive_command(exe, drive, rom, options), home)
    rt.apply_hardware(home, stem, rt.hardware_for(stem, overrides))
    return _start(rt.archive_command(exe, archive, options), home)


def launch_hdf(exe, hdf, kickstarts=None, options=Options(), home=None):
    """Boot a hard disk image as an Amiga 1200 with 8 MB of Fast RAM, without waiting for it."""
    home = Path(home or rt.home_dir())
    rom = a1200_rom(kickstarts) or a1200_rom(home / "ROMs")
    if rom is None:
        raise RuntimeError("No Kickstart 3.1 A1200 ROM found: put it in the emulator/Kickstarts folder.")
    rt.seed_home(home, roms=rom_files(kickstarts))
    return _start(rt.hdf_command(exe, hdf, rom, options), home)


# --- the user's Amiberry data -----------------------------------------------------------------------------

def folder_size(path) -> int:
    """Total size in bytes of the files under a folder (0 if it does not exist)."""
    total = 0
    for p in Path(path).rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def reset_home(home=None) -> int:
    """Delete the shared Amiberry folder (settings, copied ROMs, WHDLoad). It is recreated by the next launch.
    The saved games in the Games folder next to it are not touched. Returns the bytes freed.
    Only ever deletes a folder called Amiberry inside a folder called WHDLoadSuite."""
    home = Path(home or rt.home_dir())
    if home.name != "Amiberry" or home.parent.name != "WHDLoadSuite":
        raise ValueError(f"refusing to delete {home}")
    if running():
        raise RuntimeError("Close the running game first.")
    if home.is_symlink():
        home.unlink()
        return 0
    if not home.exists():
        return 0
    freed = folder_size(home)
    shutil.rmtree(home)
    return freed


def delete_games(games=None) -> int:
    """Delete the writable copies of the standalone executables' games (their saves and high scores). Each is made
    again, from the executable, the next time it runs. Returns the bytes freed. Only ever deletes a folder called
    Games inside a folder called WHDLoadSuite."""
    games = Path(games or rt.games_dir())
    if games.name != "Games" or games.parent.name != "WHDLoadSuite":
        raise ValueError(f"refusing to delete {games}")
    if running():
        raise RuntimeError("Close the running game first.")
    if games.is_symlink():
        games.unlink()
        return 0
    if not games.exists():
        return 0
    freed = folder_size(games)
    shutil.rmtree(games)
    return freed


def open_folder(path):
    """Show a folder in Finder / Explorer / the file manager, creating it first if needed."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    opener = ["open"] if sys.platform == "darwin" else ["explorer"] if sys.platform.startswith("win") else ["xdg-open"]
    subprocess.Popen([*opener, str(path)])
