"""Launch WHDLoad .lha archives in Amiberry, build standalone executables, and prepare drives.

Launch and Build start from the .lha itself (see common/amiberry.py and tabs/builder/bundle.py). The few games that
cannot (common/amiberry_overrides.json) run from a prepared drive, which Launch and Build make automatically
(ensure_prepared); `python builder.py GAME` makes one by hand. Preparing a game, for every archive in
<work>/downloads (including nested folders):
  1. extract it into <work>/Whdload/<A-Z|0-9>/<Game>/ on top of a copy of <work>/Template_WHDLoad
  2. rewrite <Game>/S/Startup-Sequence so it launches that game's slave
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

from common import amiberry, amiberry_runtime as rt, gamebase, lha
from common.gamepaths import GROUPS, base_name, drive_path, game_name
from common.paths import DEFAULT_WORK_DIR, EMULATOR_DIR
from tabs.settings.settings import load_launch_screen, load_options

from . import bundle


def find_slave(game_dir: Path):
    slaves = sorted((p for p in game_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".slave"), key=lambda p: (len(p.parts), str(p).lower()))
    return slaves[0] if slaves else None


def rewrite_startup(template: str, folder: str, slave: str) -> str:
    """Point the template's `cd` and `WHDLoad` lines at this game, keeping other options."""
    out = []
    for line in template.splitlines():
        if re.match(r"\s*cd\s+", line, re.I):
            line = f"cd SYS:{folder}"
        elif re.match(r"\s*whdload\s+", line, re.I):
            line = re.sub(r"(?i)(whdload\s+)\S+", lambda m: m.group(1) + slave, line, count=1)
        out.append(line)
    return "\n".join(out) + "\n"


def build_game(archive: Path, work_dir: Path, force: bool, whdload_dir: Path | None = None) -> str:
    name = game_name(archive)
    drive = drive_path(name, work_dir, whdload_dir)
    if drive.exists() and not force:
        return f"skipped (exists, use --force): {drive}"

    template_dir = work_dir / "Template_WHDLoad"
    startup_tpl = (template_dir / "S" / "Startup-Sequence").read_text(encoding="latin-1")

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / name
        shutil.copytree(template_dir, staging)
        lha.extract(archive, staging)

        slave = find_slave(staging)
        if slave is None:
            raise RuntimeError("no .slave file found in archive")
        folder = slave.parent.relative_to(staging).as_posix()
        if not folder or folder in ("C", "S", "Devs"):
            raise RuntimeError(f"unexpected slave location: {slave.relative_to(staging)}")

        (staging / "S" / "Startup-Sequence").write_text(
            rewrite_startup(startup_tpl, folder, slave.name), encoding="latin-1", newline="\n")

        if drive.exists():
            shutil.rmtree(drive)
        drive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), drive)
    return f"ok: {drive} (SYS:{folder}, {slave.name})"


def needs_preparing(archive: Path, work_dir: Path, whdload_dir: Path | None = None, overrides: dict | None = None) -> bool:
    """True if the game runs from a prepared drive (see amiberry_overrides.json) and has none yet."""
    name = game_name(archive)
    return rt.mode_for(name, overrides) == "drive" and not drive_path(name, work_dir, whdload_dir).is_dir()


def ensure_prepared(archive: Path, work_dir: Path, whdload_dir: Path | None = None,
                    overrides: dict | None = None) -> str | None:
    """Make the game's prepared drive if it needs one and has none yet. Returns what Prepare reported, or None
    when nothing was needed. Raises RuntimeError with a readable reason if it cannot be made."""
    if not needs_preparing(archive, work_dir, whdload_dir, overrides):
        return None
    if not (work_dir / "Template_WHDLoad").is_dir():
        raise RuntimeError(f"{game_name(archive)} runs from a prepared drive, but {work_dir} has no Template_WHDLoad")
    return build_game(archive, work_dir, False, whdload_dir)


def clear_work_dir(work_dir: Path, whdload_dir: Path | None = None) -> list[Path]:
    """Delete the prepared game folders (A-Z, 0-9 and # groups inside the Whdload folder, which is removed
    too if that leaves it empty); returns what was removed."""
    if not (work_dir / "Template_WHDLoad").is_dir():
        raise RuntimeError(f"{work_dir} does not look like a work folder (no Template_WHDLoad)")
    removed = []
    whd = whdload_dir or work_dir / "Whdload"
    if whd.is_symlink():
        whd.unlink()
        removed.append(whd)
    elif whd.is_dir():
        for child in whd.iterdir():
            if child.is_dir() and not child.is_symlink() and child.name in GROUPS:
                shutil.rmtree(child)
                removed.append(child)
        if not any(whd.iterdir()):
            whd.rmdir()
    return removed


def select_archives(work_dir: Path, names=()) -> list[Path]:
    """The .lha archives in <work>/downloads whose game name (or name without its version) matches one of
    `names`; all of them if no names are given."""
    archives = sorted((work_dir / "downloads").rglob("*.lha"), key=lambda p: p.name.lower())
    if names:
        wanted = {n.lower() for n in names}
        archives = [a for a in archives if {game_name(a).lower(), base_name(game_name(a)).lower()} & wanted]
    return archives


def launch_game(name: str, work_dir: Path, amiberry_dir: Path | None = None) -> int:
    """Command line --launch: start one game in Amiberry (straight from its .lha unless it needs its prepared
    drive). Prints the reason and returns 1 if it cannot start."""
    matches = select_archives(work_dir, [name])
    if len(matches) != 1:
        print(f"{name}: " + ("no such archive" if not matches else "several archives match, give the full name: "
              + ", ".join(game_name(a) for a in matches)), file=sys.stderr)
        return 1
    archive = matches[0]
    exe = amiberry.find(amiberry_dir)
    if exe is None:
        print("Amiberry not found (put it in the emulator folder or use --amiberry-dir)", file=sys.stderr)
        return 1
    try:
        ensure_prepared(archive, work_dir)
        amiberry.launch_game(exe, archive, drive_path(game_name(archive), work_dir), EMULATOR_DIR / "Kickstarts",
                             options=load_options())
    except (RuntimeError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


def bundle_games(names, work_dir: Path, amiberry_dir: Path | None = None, create=bundle.create_executable) -> int:
    """Command line --bundle: build a standalone executable for every archive matching `names`."""
    archives = select_archives(work_dir, names)
    if not archives:
        print(f"no archives match {', '.join(names)} in {work_dir / 'downloads'}", file=sys.stderr)
        return 1
    exe = amiberry.find(amiberry_dir)
    if exe is None:
        print("Amiberry not found (put it in the emulator folder or use --amiberry-dir)", file=sys.stderr)
        return 1
    failed = 0
    screen, folder, mode = load_launch_screen()          # the saved choices of Settings > Amiberry…
    for archive in archives:
        try:
            ensure_prepared(archive, work_dir)
            picture = gamebase.find_image(folder, game_name(archive), mode) if screen else None
            out = create(archive, work_dir, exe=exe, kickstarts=EMULATOR_DIR / "Kickstarts", options=load_options(),
                         launch_screen=screen, picture=picture)
            print(f"{game_name(archive)}: ok: {out}")
        except Exception as exc:
            failed += 1
            print(f"{game_name(archive)}: FAILED: {exc}")
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games", nargs="*", help="only process archives whose game name matches (default: all)")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR, help=f"work folder (default: {DEFAULT_WORK_DIR})")
    ap.add_argument("--launch", action="store_true", help="launch the (single) named game in Amiberry instead of preparing")
    ap.add_argument("--bundle", action="store_true", help="create a standalone executable for each named game (names are required)")
    ap.add_argument("--amiberry-dir", type=Path, help="folder containing Amiberry for --launch and --bundle (default: emulator/, then the usual install spots)")
    ap.add_argument("--force", action="store_true", help="rebuild games that already exist")
    args = ap.parse_args(argv)

    work_dir = args.work_dir.resolve()
    if args.launch:
        if len(args.games) != 1:
            print("--launch needs exactly one game name", file=sys.stderr)
            return 1
        return launch_game(args.games[0], work_dir, args.amiberry_dir)
    if args.bundle:
        if not args.games:
            print("--bundle needs the name of at least one game", file=sys.stderr)
            return 1
        return bundle_games(args.games, work_dir, args.amiberry_dir)
    archives = select_archives(work_dir, args.games)
    if not archives:
        print(f"no .lha archives to process in {work_dir / 'downloads'}", file=sys.stderr)
        return 1

    failed = 0
    for archive in archives:
        try:
            result = build_game(archive, work_dir, args.force)
        except Exception as exc:
            failed += 1
            result = f"FAILED: {exc}"
        print(f"{archive.name}: {result}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
