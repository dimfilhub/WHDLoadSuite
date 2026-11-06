"""How a game is named and where its generated files live. Shared by the Builder tab (which creates
them), the Browser tab (which shows what exists) and HDCommander (which sorts games into A-Z folders)."""
import functools
import re
import sys
from pathlib import Path

from common import amiberry_runtime
from common.paths import PROJECT_ROOT


def game_name(archive: Path) -> str:
    """'Game_v1.5_2489.lha' -> 'Game_v1.5_2489': the full stem, so every version/variant gets its own drive."""
    return archive.stem


def base_name(name: str) -> str:
    """'Game_v1.5_2489' -> 'Game'."""
    return re.sub(r"_v\d.*$", "", name) or name


GROUPS = {*"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0-9", "#"}


def group_dir(name: str) -> str:
    """Sub-folder for a game: its first letter ('A'-'Z'), '0-9' for digits, '#' for anything else."""
    c = name[:1].upper()
    return c if "A" <= c <= "Z" else "0-9" if c.isdigit() else "#"


def drive_path(name: str, work_dir: Path, whdload_dir: Path | None = None) -> Path:
    """Where the prepared drive of a game lives (whdload_dir defaults to <work>/Whdload)."""
    return (whdload_dir or work_dir / "Whdload") / group_dir(name) / name


def executable_path(name: str, work_dir: Path, out_dir: Path | None = None) -> Path:
    """Where tabs.builder.bundle.create_executable puts the bundle for a game."""
    out_dir = (out_dir or work_dir / "Executables").resolve() / group_dir(name)
    if sys.platform == "darwin":
        return out_dir / f"{name}.app"
    return out_dir / (name + (".exe" if sys.platform == "win32" else ""))


APP_ICON = PROJECT_ROOT / "images" / "icon.png"


def find_icon(name: str, work_dir: Path) -> Path | None:
    """Icon for the executable: Icons/<game>.<ext> if there is one, else the app icon images/icon.png (the same on every
    platform; PyInstaller turns the PNG into .icns/.ico with Pillow), else Icons/default.<ext>.
    <ext> is .icns on macOS, .ico on Windows, or .png."""
    native = {"darwin": ".icns", "win32": ".ico"}.get(sys.platform)

    def lookup(stems):
        for stem in stems:
            for ext in (native, ".png"):
                if ext and (work_dir / "Icons" / f"{stem}{ext}").is_file():
                    return work_dir / "Icons" / f"{stem}{ext}"
        return None

    return lookup((name, base_name(name))) or (APP_ICON if APP_ICON.is_file() else None) or lookup(("default",))


NEEDS_PREP_COLOUR, PREPARED_COLOUR, EXECUTABLE_COLOUR = "#e65c00", "#008000", "#0000ff"   # orange, green, blue


@functools.lru_cache(maxsize=1)
def _overrides() -> dict:
    return amiberry_runtime.load_overrides()


def build_state(name: str, work_dir: Path, whdload_dir: Path | None = None, exe_dir: Path | None = None) -> str:
    """How far a game is, for the colours in the Builder and Browser lists:
      'executable'  a standalone executable was built (blue)
      'prepared'    the game needs a prepared drive (amiberry_overrides.json) and has it (green)
      'needs_prep'  the game needs a prepared drive and has none yet (orange)
      ''            the game runs straight from its .lha and needs nothing: no colour."""
    if executable_path(name, work_dir, exe_dir).exists():
        return "executable"
    if amiberry_runtime.mode_for(name, _overrides()) != "drive":
        return ""
    return "prepared" if drive_path(name, work_dir, whdload_dir).is_dir() else "needs_prep"
