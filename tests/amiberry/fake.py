"""A stand-in for the Amiberry binary: a shell script that records how it was started."""
import json
import stat
import sys
import unittest
from pathlib import Path

SCRIPT = """#!/bin/sh
# records arguments and the home folder; `--download-whdboot` fakes a WHDLoad download
if [ "$1" = "--dump-paths" ]; then
  [ -n "$FAKE_INI" ] && echo "amiberry_ini_file=$FAKE_INI"
  exit 0
fi
if [ "$1" = "--download-whdboot" ]; then
  [ -n "$FAKE_FAIL" ] && { echo "no network" >&2; exit 1; }
  mkdir -p "$AMIBERRY_HOME_DIR/WHDBoot/game-data"
  echo whdload > "$AMIBERRY_HOME_DIR/WHDBoot/WHDLoad"
  [ -n "$FAKE_DB" ] && printf '%s' "$FAKE_DB" > "$AMIBERRY_HOME_DIR/WHDBoot/game-data/whdload_db.json"
  exit 0
fi
printf '%s\\n' "$@" > "$FAKE_ARGS"
printf '%s\\n' "$AMIBERRY_HOME_DIR" > "$FAKE_ARGS.home"
"""


def make_fake(folder: Path, name="amiberry") -> Path:
    exe = Path(folder) / name
    exe.write_text(SCRIPT)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return exe


def recorded(args_file: Path) -> list:
    return Path(args_file).read_text().splitlines()


def write_db(home: Path, games: list):
    path = Path(home) / "WHDBoot" / "game-data" / "whdload_db.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"games": games}))
    return path


requires_posix = unittest.skipIf(sys.platform == "win32", "uses a shell script as the emulator")
