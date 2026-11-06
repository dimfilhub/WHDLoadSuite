#!/usr/bin/env python3
"""Make common/gamebase_images.json: which GamebaseAmiga picture belongs to which WHDLoad game.

    python tools/make_gamebase_map.py --gamebase ~/VSCodeProjects/GamebaseAmiga --downloads work/downloads

--gamebase is the GamebaseAmiga project (it holds gb_amiga_23.sqlite3 and the populated data/ folder); --downloads is a
folder with the WHDLoad .lha archives (for example the Retroplay collection). The game names of the two collections
differ, so a game is matched in steps: its name (case, punctuation, "The", roman numerals and subtitles ignored),
the names of Gamebase's own WHDLoad entries, then a close spelling (never when the numbers in the names differ). A demo
or preview without a picture of its own takes its parent game's. Run it again when new archives are added; the result is
only a list of names and relative file names, the pictures themselves are never copied.
"""
import argparse
import difflib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import gamebase                                     # noqa: E402
from common.gamepaths import base_name                          # noqa: E402

ROMAN = {"xiii": "13", "xii": "12", "xi": "11", "viii": "8", "vii": "7", "vi": "6", "iv": "4", "ix": "9", "iii": "3",
         "ii": "2", "x": "10", "v": "5"}
WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
         "nine": "9", "ten": "10"}
SKIP = {"the", "a", "an", "and", "of"}
RELEASE = re.compile(r"[_ ](cd32|cdtv|aga|ecs|ntsc|pal|1mb|2mb|512k|1meg|ratsoft|dizzy|german|english|french|italian|"
                     r"spanish|demo|preview|ldk|crack\w*)$", re.I)
# close spellings that are really another game
NOT_THE_SAME = {"Raiders", "WhereInTheUSAIsCarmenSandiego"}


def key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold().replace("&", " and ")
    words = [w for w in re.findall(r"[a-z0-9]+", text) if w not in SKIP]
    return "".join(ROMAN.get(w, WORDS.get(w, w)) for w in words)


def archive_keys(name: str) -> set:
    shorter = RELEASE.sub("", name)
    keys = {key(gamebase.split_camel(n)) for n in (name, shorter)} | {key(name), key(shorter)}
    return {k for k in keys if len(k) >= 3}


def game_keys(name: str) -> set:
    keys = {key(name)}
    m = re.match(r"^(.*?),\s*(the|a|an)$", name.strip(), re.I)
    if m:
        keys.add(key(m.group(1)))
    for sep in (":", " - ", " – ", "("):
        if sep in name:
            keys.add(key(name.split(sep)[0]))
    return {k for k in keys if len(k) >= 3}


def build(project: Path, downloads: Path):
    lib = gamebase.Library(project / "data")
    db = sqlite3.connect(project / "gb_amiga_23.sqlite3")
    shots, covers, keys = {}, {}, {}

    def add(k, ga):
        keys.setdefault(k, set()).add(ga)

    for ga, name, shot in db.execute("select GA_Id, Name, ScrnshotFilename from Games"):
        shot = (shot or "").replace("\\", "/")
        path = lib.path("screenshots/" + shot) if shot else None
        if path:
            shots[ga] = path.relative_to(lib.root).as_posix()
        for k in game_keys(name):
            add(k, ga)
        if shot:
            for k in game_keys(Path(shot).stem.replace("_", " ")):
                add(k, ga)
    for ga, path in db.execute("select GA_Id, Path from Extras where Name like 'Cover%Front'"):
        found = lib.path("extras/" + path.replace("\\", "/"))
        if found:
            covers.setdefault(ga, found.relative_to(lib.root).as_posix())
    for ga, path in db.execute("select GA_Id, Path from Extras where Name = 'WHDLoad' and Type = 1"):
        for k in archive_keys(base_name(Path(path.replace("\\", "/")).stem)):
            add(k, ga)

    def pictures(hit):
        ids = sorted(hit)
        s = next((shots[g] for g in ids if g in shots), None)
        c = next((covers[g] for g in ids if g in covers), None)
        return {k: v for k, v in (("s", s), ("c", c)) if v}

    def lookup(name):
        ks = archive_keys(name)
        hit = set().union(*[keys[k] for k in ks if k in keys]) if any(k in keys for k in ks) else set()
        if not hit and name not in NOT_THE_SAME:
            for k in sorted(ks, key=len, reverse=True):
                for close in difflib.get_close_matches(k, list(keys), n=3, cutoff=0.88):
                    if abs(len(close) - len(k)) <= max(2, len(k) // 8) and \
                            re.findall(r"\d+", close) == re.findall(r"\d+", k):
                        hit |= keys[close]
                if hit:
                    break
        return hit

    names = sorted({base_name(p.stem) for p in downloads.rglob("*.lha")}, key=str.casefold)
    images, matched = {}, 0
    for name in names:
        hit = lookup(name)
        matched += bool(hit)
        found = pictures(hit) if hit else {}
        if not found:                                        # a demo or preview: its parent game's picture
            m = re.search(r"(Demo|Preview)", name)
            if m and m.start() >= 4:
                parent = lookup(name[:m.start()])
                found = pictures(parent) if parent else {}
        if found:
            images[name] = found
    return names, matched, images


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gamebase", required=True, type=Path, help="the GamebaseAmiga project folder")
    parser.add_argument("--downloads", required=True, type=Path, help="folder with the WHDLoad .lha archives")
    parser.add_argument("--out", type=Path, default=gamebase.MAP_FILE)
    args = parser.parse_args()
    for needed in (args.gamebase / "gb_amiga_23.sqlite3", args.gamebase / "data" / "screenshots"):
        if not needed.exists():
            sys.exit(f"{needed} not found")
    names, matched, images = build(args.gamebase.expanduser(), args.downloads.expanduser())
    shots = sum(1 for v in images.values() if "s" in v)
    args.out.write_text(json.dumps({"images": images}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                        encoding="utf-8")
    print(f"{len(names)} games, {matched} found in Gamebase, {len(images)} with a picture ({shots} with a screenshot)")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
