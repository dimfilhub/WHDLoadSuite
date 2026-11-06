"""Amiberry command lines, the per-user Amiberry home and per-game overrides.

Standard library only and no imports from this project: the app uses it, and so does the small stub frozen
into every standalone executable (see tabs/builder/bundle.py), so both run exactly the same code.

How a game is started:
  * "autoload": `amiberry --autoload game.lha`. Amiberry builds the whole setup itself (model, memory, slave) from
    its WHDLoad game database. This is the default.
  * "drive": a prepared drive folder (the Prepare step) mounted as SYS:, started with an A1200 and a Kickstart
    3.1 ROM. The fallback for games that cannot run from a read-only .lha.
Games that need something else are listed in amiberry_overrides.json.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Keyboard joystick layouts as Amiberry's `joyport1` values: A numpad, B cursors + Right Alt/Ctrl, C WASD,
# D cursors + Left Ctrl/Alt (fire).
KEYBOARDS = {"a": "kbd1", "b": "kbd2", "c": "kbd3", "d": "kbd4"}
WINDOW_MODES = ("windowed", "fullscreen")
LOOKS = ("normal", "scanlines", "crt")      # crt = scanlines plus Amiberry's 1084 monitor shader
# (value kept in the settings, what the user reads): the drop-downs of the settings window and the launch screen
KEYBOARD_CHOICES = (("", "None"),
                    ("a", "Layout A: numeric keypad, 0 or 5 = fire"),
                    ("b", "Layout B: cursor keys, Right Ctrl or Alt = fire"),
                    ("c", "Layout C: W A S D, Left Alt = fire"),
                    ("d", "Layout D: cursor keys, Left Ctrl or Alt = fire"))
WINDOW_CHOICES = (("windowed", "Windowed"), ("fullscreen", "Fullscreen (borderless window)"))
LOOK_CHOICES = (("normal", "Normal"), ("scanlines", "Scanlines"), ("crt", "CRT monitor (scanlines + 1084 look)"))
DB_FILE = Path("WHDBoot") / "game-data" / "whdload_db.json"
OVERRIDES_FILE = Path(__file__).with_name("amiberry_overrides.json")


@dataclass(frozen=True)
class Options:
    """What the user can choose (Settings > Amiberry…). Games started from their .lha use all of it; the few that
    run from a prepared drive, and disk images, ignore quit_on_exit and splash (those belong to WHDBooter)."""
    keyboard: str = "d"          # keyboard joystick on port 1: "a".."d", or "" for none
    window: str = "windowed"     # "windowed" or "fullscreen" (a borderless window over the desktop)
    look: str = "normal"         # "normal", "scanlines" or "crt"
    quit_on_exit: bool = False   # close Amiberry when the WHDLoad game exits
    splash: bool = True          # show WHDLoad's splash screen before the game

    @classmethod
    def from_dict(cls, data):
        """Options from saved settings or a bundle's manifest: tolerant, anything unknown or invalid falls back to
        the default (and the old `fullscreen` / `scanlines` flags are still understood)."""
        data = data if isinstance(data, dict) else {}
        keyboard = str(data.get("keyboard", "d")).lower()
        if keyboard and keyboard not in KEYBOARDS:
            keyboard = "d"
        window = data.get("window", "fullscreen" if data.get("fullscreen") else "windowed")
        look = data.get("look", "scanlines" if data.get("scanlines") else "normal")
        return cls(keyboard, window if window in WINDOW_MODES else "windowed", look if look in LOOKS else "normal",
                   bool(data.get("quit_on_exit", False)), bool(data.get("splash", True)))


# --- where things live ------------------------------------------------------------------------------------

def data_dir() -> Path:
    """Per-user folder shared by the app and every standalone executable."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "WHDLoadSuite"


def home_dir() -> Path:
    """The one Amiberry settings/ROMs/WHDBoot folder shared by all games (AMIBERRY_HOME_DIR), kept apart
    from the user's own Amiberry."""
    return data_dir() / "Amiberry"


def games_dir() -> Path:
    """Writable copies of prepared game drives (saves and high scores live here)."""
    return data_dir() / "Games"


def environment(home: Path, create: bool = True) -> dict:
    """The environment Amiberry runs in. AMIBERRY_HOME_DIR moves its data folders, but its small settings file
    (window positions and the list of ROMs it found) stays in the user's own settings folder unless HOME is
    moved too. So HOME and the XDG folders point inside the app's home: the user's own Amiberry never sees,
    or is changed by, anything done here. (Windows: not handled yet.) `create=False` leaves the folders uncreated,
    for a look at Amiberry that must not leave anything behind."""
    env = {**os.environ, "AMIBERRY_HOME_DIR": str(home)}
    if os.name == "posix":
        user = Path(home) / "Settings"
        if create:
            user.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(user)
        env["XDG_CONFIG_HOME"] = str(user / ".config")
        env["XDG_DATA_HOME"] = str(user / ".local" / "share")
    return env


# --- command lines ----------------------------------------------------------------------------------------

def _check_path(path) -> str:
    """Amiberry reads `filesystem2=`/`hardfile2=` values as comma separated lists, so a comma in a path
    cannot be passed."""
    text = str(path)
    if "," in text:
        raise ValueError(f"Amiberry cannot open a path containing a comma: {text}")
    return text


def common_arguments(options: Options, whdbooter: bool = False) -> list:
    """Amiberry options for what the user chose. They are the `-o default_*` amiberry.conf settings, because
    WHDBooter replaces plain `-s ...` settings (the keyboard joystick and the display) when it sets a game up;
    the same options also work for games that do not go through it."""
    args = ["-o", "update_check=no"]                        # a standalone game must not phone home
    if options.keyboard:
        layout = KEYBOARDS[options.keyboard.lower()]
        # WHDBooter gives joystick 1 the device named by default_controller1; without it, set the port directly
        args += ["-o", f"default_controller1={layout}"] if whdbooter else ["-s", f"joyport1={layout}"]
    if options.window == "fullscreen":
        args += ["-o", "default_fullscreen_mode=2"]         # borderless window over the desktop
    if options.look in ("scanlines", "crt"):
        args += ["-o", "default_line_mode=2"]
    if options.look == "crt":
        args += ["-o", "shader=1084"]                       # Amiberry's 1084 monitor shader
    if whdbooter:                                           # these two are WHDBooter's own
        if options.quit_on_exit:
            args += ["-o", "default_whd_quit_on_exit=yes"]
        if not options.splash:
            args += ["-o", "default_whd_showsplash=no"]
    return args


def archive_command(exe, archive, options: Options = Options()) -> list:
    """Run a WHDLoad .lha directly. The path must be absolute: Amiberry resolves relative ones against its
    own HardDrives folder. `--rescan-roms` so ROMs added since the last run are seen."""
    return [str(exe), "--rescan-roms", *common_arguments(options, whdbooter=True), "--autoload",
            str(Path(archive).resolve())]


def drive_command(exe, drive, rom, options: Options = Options(), model="A1200", fast_mb=8, label="SYS",
                  extra=()) -> list:
    """Boot a prepared WHDLoad drive folder as SYS: from a Kickstart ROM file."""
    return [str(exe), "--model", model, "-G", "-r", str(Path(rom).resolve()), *common_arguments(options),
            "-s", f"fastmem_size={fast_mb}",
            "-s", f"filesystem2=rw,DH0:{label}:{_check_path(Path(drive).resolve())},1", *extra]


def hdf_command(exe, hdf, rom, options: Options = Options(), fast_mb=8) -> list:
    """Boot a hard disk image (RDB, as made by HDCommander) as an Amiga 1200."""
    return [str(exe), "--model", "A1200", "-G", "-r", str(Path(rom).resolve()), *common_arguments(options),
            "-s", f"fastmem_size={fast_mb}",
            "-s", f"hardfile2=rw,DH0:{_check_path(Path(hdf).resolve())},0,0,0,512,0,,uae0"]


# --- the shared home --------------------------------------------------------------------------------------

def has_whdload(home: Path) -> bool:
    return (Path(home) / "WHDBoot" / "WHDLoad").is_file()


def seed_home(home: Path, whdboot=None, roms=()) -> list:
    """Make the home usable: copy a WHDBoot folder (WHDLoad and its boot files) in if the home has no WHDLoad
    yet, and copy any ROM files it lacks. Existing files are never replaced. Returns the paths added."""
    home = Path(home)
    added = []
    (home / "ROMs").mkdir(parents=True, exist_ok=True)
    if whdboot is not None and Path(whdboot).is_dir() and not has_whdload(home):
        shutil.copytree(whdboot, home / "WHDBoot", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("tmp", "*.bak"))
        added.append(home / "WHDBoot")
    for rom in roms:
        target = home / "ROMs" / Path(rom).name
        if not target.exists():
            shutil.copy2(rom, target)
            added.append(target)
    return added


# --- per-game overrides -----------------------------------------------------------------------------------

def load_overrides(path=OVERRIDES_FILE) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and not k.startswith("_")}


def mode_for(stem: str, overrides: dict | None = None) -> str:
    """"autoload" (default) or "drive" for a game, by archive name without .lha."""
    overrides = load_overrides() if overrides is None else overrides
    return overrides.get(stem, {}).get("mode", "autoload")


def hardware_for(stem: str, overrides: dict | None = None) -> dict:
    overrides = load_overrides() if overrides is None else overrides
    return dict(overrides.get(stem, {}).get("hardware", {}))


def apply_hardware(home: Path, stem: str, hardware: dict) -> bool:
    """Set hardware fields (for example z3_ram) on a game's entry in the home's WHDLoad database, which is
    where Amiberry's WHDBooter takes memory and CPU from; command-line `-s` options are replaced by it.
    Idempotent, so it runs before every launch. Returns True if the database file was changed."""
    db_path = Path(home) / DB_FILE
    if not hardware or not db_path.is_file():
        return False
    try:
        db = json.loads(db_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    changed = False
    for game in db.get("games", []):
        if game.get("filename") == stem:
            current = game.setdefault("hardware", {})
            for key, value in hardware.items():
                if current.get(key) != value:
                    current[key] = value
                    changed = True
    if changed:
        tmp = db_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(db), encoding="utf-8")
        tmp.replace(db_path)
    return changed


# --- running a standalone bundle --------------------------------------------------------------------------

def run(cmd, home: Path) -> int:
    """Run Amiberry and wait for it. If this process is asked to stop, Amiberry is stopped too, so it is
    never left running in the background."""
    proc = subprocess.Popen(cmd, env=environment(home))
    for sig in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", signal.SIGTERM)):
        signal.signal(sig, lambda s, _frame: proc.send_signal(s))
    return proc.wait()


def launch_prefs_file(stem: str) -> Path:
    """What one standalone executable remembers between runs: its launch choices and whether to show the screen."""
    return data_dir() / "Launch" / f"{stem}.json"


def load_launch_prefs(stem: str) -> dict:
    try:
        data = json.loads(launch_prefs_file(stem).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_launch_prefs(stem: str, options: Options | None, show: bool):
    """Keep the show-the-screen switch, and the launch choices too when `options` is given."""
    prefs = load_launch_prefs(stem)
    prefs["show"] = bool(show)
    if options is not None:
        prefs["options"] = {"keyboard": options.keyboard, "window": options.window, "look": options.look}
    try:
        path = launch_prefs_file(stem)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs), encoding="utf-8")
    except OSError:
        pass                                    # a convenience: never stop a game from starting over it


def choose_launch_options(bundle: Path, manifest: dict, options: Options):
    """The options to start an executable with: the ones built in, changed by what the user kept for this game and,
    unless switched off, by the launch screen. None if the user cancelled there. Without a launch screen in the
    executable, or without a display or Tk, the game just starts."""
    launch = manifest.get("launch")
    if not isinstance(launch, dict):
        return options
    stem = manifest["stem"]
    prefs = load_launch_prefs(stem)
    kept = prefs.get("options") if isinstance(prefs.get("options"), dict) else {}
    options = Options.from_dict({**asdict(options), **{k: kept[k] for k in ("keyboard", "window", "look") if k in kept}})
    if not prefs.get("show", True):
        return options
    try:
        try:
            from . import launch_window         # in the app and its tests
        except ImportError:
            import launch_window                # in the executable, where common/ is on the path
        image = launch.get("image")
        chosen, show, keep = launch_window.run_for_bundle(
            stem, options, str(bundle / image) if image else None, launch.get("kind", ""))
    except Exception:                           # no Tk, or no display: start the game as it is
        return options
    save_launch_prefs(stem, chosen if (chosen is not None and keep) else None, show)
    return chosen


def run_bundle(bundle: Path) -> int:
    """Entry point of a standalone executable: `bundle` is the folder holding manifest.json, the emulator,
    the game and the seed data (PyInstaller's unpack folder). Uses the same home and drive folders as the app."""
    bundle = Path(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    options = Options.from_dict(manifest.get("options"))
    options = choose_launch_options(bundle, manifest, options)
    if options is None:                             # cancelled on the launch screen
        return 0
    exe = bundle / "emulator" / manifest["exe"]
    if os.name == "posix":
        exe.chmod(exe.stat().st_mode | 0o111)
    home = home_dir()
    seed_home(home, bundle / "WHDBoot", sorted((bundle / "ROMs").glob("*.rom")))
    if manifest["mode"] == "drive":
        game = games_dir() / manifest["name"]
        if not game.is_dir():                       # first run: a writable copy, so saves persist
            game.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(bundle / "game", game, symlinks=True)
        cmd = drive_command(exe, game, bundle / "kick.rom", options)
    else:
        apply_hardware(home, manifest["stem"], manifest.get("hardware", {}))
        cmd = archive_command(exe, bundle / manifest["archive"], options)
    return run(cmd, home)


def options_dict(options: Options) -> dict:
    return asdict(options)
