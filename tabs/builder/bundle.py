"""Build a standalone executable of one game with Amiberry (PyInstaller).

The executable holds Amiberry, the game, the WHDBoot files (WHDLoad) and the Kickstart ROMs. It runs
common/amiberry_runtime.py, the same code the app uses to start games, and keeps its data in the per-user
WHDLoadSuite folder: one shared Amiberry home plus a writable copy of each prepared drive.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import amiberry
from common import amiberry_runtime as rt
from common.gamepaths import drive_path, executable_path, find_icon, game_name, group_dir
from common.launch_window import MAX_PICTURE, fit_size
from common.paths import PROJECT_ROOT

STUB = '''\
import sys
from pathlib import Path

import amiberry_runtime

sys.exit(amiberry_runtime.run_bundle(Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))))
'''


def make_launch_image(picture: Path, dest: Path) -> bool:
    """Save a game's picture as the small PNG the executable's launch screen shows (Tk reads PNG itself, so the
    executable needs no Pillow). False if it cannot be made, for example without Pillow: the screen then has no picture."""
    try:
        from PIL import Image
        with Image.open(picture) as source:
            image = source.convert("RGB")
        width, height, sharp = fit_size(*image.size, *MAX_PICTURE)
        image.resize((width, height), Image.NEAREST if sharp else Image.LANCZOS).save(dest, "PNG")
        return True
    except (ImportError, OSError, ValueError):
        return False


def stage(archive: Path, staging: Path, exe, home: Path, kickstarts=None, drive: Path | None = None,
          options: rt.Options = rt.Options(), overrides: dict | None = None, launch: dict | None = None) -> dict:
    """Lay out what goes into the executable and return its manifest. `drive` is the game's prepared drive
    folder, needed only for games that run from one (see amiberry_overrides.json). `launch` = {"picture": file or
    None, "kind": "screenshot"/"cover"} gives the executable a launch screen."""
    stem = game_name(archive)
    overrides = rt.load_overrides() if overrides is None else overrides
    mode = rt.mode_for(stem, overrides)
    source, exe_rel = amiberry.bundle_source(exe)
    manifest = {"name": stem, "stem": stem, "mode": mode, "exe": exe_rel,
                "options": rt.options_dict(options), "hardware": rt.hardware_for(stem, overrides)}
    staging.mkdir(parents=True, exist_ok=True)
    if launch is not None:
        picture = launch.get("picture")
        made = bool(picture) and make_launch_image(Path(picture), staging / "launch.png")
        manifest["launch"] = {"image": "launch.png" if made else None, "kind": launch.get("kind", "") if made else ""}
    if mode == "drive":
        if drive is None or not Path(drive).is_dir():
            raise RuntimeError(f"{stem} runs from a prepared drive: prepare it first")
        rom = amiberry.a1200_rom(kickstarts) or amiberry.a1200_rom(home / "ROMs")
        if rom is None:
            raise RuntimeError("no Kickstart 3.1 A1200 ROM found")
        shutil.copytree(drive, staging / "game", symlinks=True)
        shutil.copy2(rom, staging / "kick.rom")
    else:
        if not rt.has_whdload(home):
            raise RuntimeError("WHDLoad is not installed in the Amiberry folder yet")
        manifest["archive"] = archive.name      # the original file name: Amiberry may use it to recognise the game
        shutil.copy2(archive, staging / archive.name)
        shutil.copytree(home / "WHDBoot", staging / "WHDBoot", ignore=shutil.ignore_patterns("tmp", "*.bak"))
        roms = amiberry.rom_files(kickstarts) or amiberry.rom_files(home / "ROMs")
        (staging / "ROMs").mkdir()
        for rom in roms:
            shutil.copy2(rom, staging / "ROMs" / rom.name)
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def create_executable(archive: Path, work_dir: Path, out_dir: Path | None = None, whdload_dir: Path | None = None,
                      exe=None, kickstarts=None, options: rt.Options = rt.Options(), home: Path | None = None,
                      overrides: dict | None = None, launch_screen: bool = False, picture=None) -> Path:
    """Freeze Amiberry and one game into a native executable. Games that run straight from their .lha need
    nothing prepared; the few that need a prepared drive use <work>/Whdload (see amiberry_overrides.json).
    `launch_screen` gives it a launch screen (with `picture` = (file, "screenshot"/"cover") if there is one); that
    adds Tk to the executable, about 3 MB."""
    archive = Path(archive)
    name = game_name(archive)
    exe = exe or amiberry.find()
    if exe is None:
        raise RuntimeError("Amiberry not found (put it in the emulator folder or choose it in Settings)")
    home = Path(home or rt.home_dir())
    ok, message = amiberry.prepare_home(exe, kickstarts, home)
    if not ok:
        raise RuntimeError(message)
    source, exe_rel = amiberry.bundle_source(exe)
    out = (out_dir or work_dir / "Executables").resolve() / group_dir(name)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        staging = tmp / "stage"
        launch = None
        if launch_screen:
            launch = {"picture": picture[0], "kind": picture[1]} if picture else {"picture": None}
        stage(archive, staging, exe, home, kickstarts, drive_path(name, work_dir, whdload_dir), options, overrides, launch)
        (tmp / "launcher.py").write_text(STUB, encoding="utf-8")
        cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--name", name,
               "--distpath", str(out), "--workpath", str(tmp / "build"), "--specpath", str(tmp),
               "--paths", str(PROJECT_ROOT / "common"), "--exclude-module", "PIL",
               "--add-data", f"{source}{os.pathsep}emulator/{source.name}"]
        if not launch_screen:
            cmd += ["--exclude-module", "tkinter"]          # Tk is only needed for the launch screen
        for item in sorted(staging.iterdir()):
            cmd += ["--add-data", f"{item}{os.pathsep}{item.name if item.is_dir() else '.'}"]
        if sys.platform in ("win32", "darwin"):
            cmd.append("--noconsole")   # no console/Terminal window next to the emulator (macOS: builds a .app)
        icon = find_icon(name, work_dir)
        if icon is not None:
            cmd += ["--icon", str(icon)]
        cmd.append(str(tmp / "launcher.py"))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            if "No module named PyInstaller" in proc.stderr:
                raise RuntimeError("PyInstaller is not installed (pip install pyinstaller)")
            raise RuntimeError("PyInstaller failed: " + (proc.stderr.strip().splitlines() or ["?"])[-1])
    if sys.platform == "darwin":
        (out / name).unlink(missing_ok=True)   # PyInstaller also leaves a plain binary that opens Terminal
    return executable_path(name, work_dir, out.parent)
