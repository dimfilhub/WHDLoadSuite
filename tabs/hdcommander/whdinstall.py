"""Install the WHDLoad user distribution (WHDLoad_usr*.lha) into an image.

This does what the distribution's own Installer script does, without needing the Amiga Installer:
  C/*                                   -> C:        (never replaces a newer version)
  S/WHDLoad.prefs, WHDLoad-Startup,
  S/WHDLoad-Cleanup                     -> S:        (an existing, different file is kept and the
                                                      new one is saved as <name>.default)
  Docs/                                 -> Help:WHDLoad   (optional)
It also creates Devs:Kickstarts, where games that emulate a Kickstart find their ROM images.
The ROMs themselves are copyrighted and are never part of the distribution.
"""
import re
from pathlib import Path

from common import lha
from .browse import human
from .transfer import Item, OK, SKIPPED, FAILED, put_host
from .volume import HdfError, HdfVolume

PREFS = ("WHDLoad.prefs", "WHDLoad-Startup", "WHDLoad-Cleanup")
DOCS_DEST = "Help/WHDLoad"
KICKSTART_DIR = "Devs/Kickstarts"
# (Kickstart version, image name) as listed in WHDLoad's documentation; each also needs <name>.RTB.
KICKSTARTS = (
    ("1.2", "kick33180.A500"),
    ("1.3", "kick34005.A500"),
    ("3.1 (A500/A600)", "kick40063.A600"),
    ("3.1 (A1200)", "kick40068.A1200"),
    ("3.1 (A4000)", "kick40068.A4000"),
)
_VER = re.compile(rb"\$VER:\s*\S+\s+(\d+)\.(\d+)")


def parse_version(data: bytes):
    """(version, revision) from the first '$VER: name 20.1 ...' string in an Amiga file, or None."""
    m = _VER.search(data)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _fmt(version) -> str:
    return f"{version[0]}.{version[1]}"


def _find_root(paths) -> str:
    """Folder prefix (with trailing '/', or '') in front of C/WHDLoad inside the archive."""
    found = [p for p in paths if p.lower() == "c/whdload" or p.lower().endswith("/c/whdload")]
    if not found:
        raise HdfError("not a WHDLoad distribution (no C/WHDLoad inside)")
    best = min(found, key=len)
    return best[:len(best) - len("C/WHDLoad")]


def _read_distribution(archive) -> dict:
    entries = [(p, c) for p, c in lha.iter_files(archive) if c is not None]
    root = _find_root([p for p, _ in entries])
    return {p[len(root):]: c for p, c in entries if p.startswith(root)}


def docs_size(archive) -> int:
    """Uncompressed size of the documentation in the archive; raises HdfError if it is not a
    WHDLoad distribution. Reads only the archive headers."""
    entries = [e for e in lha.read_entries(Path(archive).read_bytes()) if e.path and not e.is_dir]
    root = _find_root([e.path for e in entries])
    return sum(e.size for e in entries if e.path.startswith(root + "Docs/"))


def _install_command(volume, rel, data) -> Item:
    name = rel[2:]
    new = parse_version(data)
    if volume.exists(rel):
        if volume.isdir(rel):
            raise HdfError("a directory with this name exists")
        old_data = volume.read(rel)
        if old_data == data:
            return Item(name, SKIPPED, "already up to date")
        old = parse_version(old_data)
        if new and old and old > new:
            return Item(name, SKIPPED, f"newer version {_fmt(old)} is already installed (kept)")
        volume.delete(rel)
        volume.put_bytes(data, rel)
        return Item(name, OK, f"upgraded {_fmt(old)} -> {_fmt(new)}" if old and new else "replaced")
    volume.put_bytes(data, rel)
    return Item(name, OK, f"installed {_fmt(new)}" if new else "installed")


def _install_prefs(volume, rel, data) -> Item:
    name = rel[2:]
    if not volume.exists(rel):
        volume.put_bytes(data, rel)
        return Item(name, OK, "installed")
    if volume.read(rel) == data:
        return Item(name, SKIPPED, "unchanged")
    alt = rel + ".default"
    if volume.exists(alt):
        if volume.read(alt) == data:
            return Item(name, SKIPPED, f"yours differs; the new one is already saved as {name}.default")
        volume.delete(alt)
    volume.put_bytes(data, alt)
    return Item(name, OK, f"your file was kept; the new one is saved as {name}.default, compare them for new options")


def install_whdload(volume: HdfVolume, archive, include_docs=False, progress=None) -> list:
    """Install the distribution; returns one Item per file in C/ and S/ plus one for the docs.
    progress(fraction, text) is called as work proceeds."""
    archive = Path(archive)
    try:
        files = _read_distribution(archive)
    except (HdfError, lha.LhaError, OSError) as exc:
        return [Item(archive.name, FAILED, str(exc))]
    plan = [("C", r) for r in sorted(files) if r.startswith("C/") and r.count("/") == 1]
    plan += [("S", f"S/{n}") for n in PREFS if f"S/{n}" in files]
    if include_docs:
        plan += [("Docs", r) for r in sorted(files) if r.startswith("Docs/")]
    needed = sum(len(files[r]) for _, r in plan)
    try:
        if needed > volume.free_bytes:
            return [Item(archive.name, FAILED, f"not enough free space ({human(needed)} needed)")]
        for folder in ("C", "S", KICKSTART_DIR):
            volume.makedirs(folder)
    except HdfError as exc:
        return [Item(archive.name, FAILED, str(exc))]

    items, docs = [], 0
    for i, (kind, rel) in enumerate(plan):
        if progress:
            progress(i / len(plan), rel)
        try:
            if kind == "C":
                items.append(_install_command(volume, rel, files[rel]))
            elif kind == "S":
                items.append(_install_prefs(volume, rel, files[rel]))
            else:
                dest = f"{DOCS_DEST}/{rel[len('Docs/'):]}"
                volume.makedirs(dest.rsplit("/", 1)[0])
                if volume.exists(dest):
                    volume.delete(dest)
                volume.put_bytes(files[rel], dest)
                docs += 1
        except (HdfError, OSError) as exc:
            items.append(Item(rel, FAILED, str(exc)))
    if docs:
        items.append(Item("Docs", OK, f"{docs} files in {DOCS_DEST}"))
    return items


def template_kickstarts(folder) -> list:
    """Kickstart files (ROM images and .RTB files) the user keeps in a folder such as the template's
    Devs/Kickstarts; notes (*.txt) and hidden files are ignored."""
    try:
        files = [p for p in Path(folder).iterdir()
                 if p.is_file() and not p.name.startswith(".") and p.suffix.lower() != ".txt"]
    except OSError:
        return []
    return sorted(files, key=lambda p: p.name.lower())


def install_kickstarts(volume: HdfVolume, files, progress=None) -> list:
    """Copy Kickstart files into Devs:Kickstarts; files already there are kept (reported as skipped)."""
    items = []
    for i, path in enumerate(files):
        if progress:
            progress(i / max(len(files), 1), Path(path).name)
        items += put_host(volume, path, KICKSTART_DIR)
    return items


def kickstart_report(volume: HdfVolume) -> str:
    """Which of the Kickstart images WHDLoad looks for are in Devs:Kickstarts, as readable text."""
    try:
        have = {e.name.lower() for e in volume.listdir(KICKSTART_DIR) if not e.is_dir}
    except HdfError:
        have = set()
    lines = []
    for version, name in KICKSTARTS:
        rom, rtb = name.lower() in have, (name + ".RTB").lower() in have
        state = ("found" if rom and rtb else "ROM found, .RTB missing" if rom else
                 ".RTB found, ROM missing" if rtb else "missing")
        lines.append(f"  Kickstart {version:<16} {name:<16} {state}")
    return "\n".join(lines)


def kickstart_notice_parts(volume: HdfVolume):
    """(intro, report, outro): what WHDLoad may need in Devs:Kickstarts. The report holds aligned columns."""
    intro = ("Some games use a Kickstart emulation. For those, WHDLoad needs original Kickstart ROM images in "
             "Devs:Kickstarts on the image (the folder has been created for you), each together with its "
             "matching .RTB relocation file, under exactly these names:")
    outro = ("The ROMs are copyrighted and not part of WHDLoad, so you must supply your own: copy them into "
             "Devs/Kickstarts with this file manager (host pane, then Copy). Games that don't use a Kickstart "
             "emulation run without them.")
    return intro, kickstart_report(volume), outro


def kickstart_notice(volume: HdfVolume) -> str:
    """The notice as one text (used where a single string is wanted)."""
    intro, report, outro = kickstart_notice_parts(volume)
    return f"WHDLoad is installed.\n\n{intro}\n\n{report}\n\n{outro}"
