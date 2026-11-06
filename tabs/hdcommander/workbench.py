"""Make an image bootable by installing Amiga Workbench 3.1 from the original floppy disks.

This repeats what the official Install3.1 disk's Installer script does (its script is on that disk), without
needing the Amiga Installer program:

    Workbench3.1  -> the root of the image          Extras3.1  -> merged into the root
    Locale        -> Locale/                        Fonts      -> Fonts/
    Storage3.1    -> Storage/, Devs/Printers, Devs/Keymaps
    Install3.1    -> the disk icon, the hard disk tools (Tools/, S/), 68040.library and its
                     Update/Startup-HardDrive as S/Startup-Sequence
    and the PAL (or NTSC) monitor driver moves from Storage/Monitors to Devs/Monitors.

Not done: placing the icons on the Workbench window (the Installer's IconPos step is cosmetic), upgrading older
Workbench installs, and the A2090/A2232 special cases. The disks are copyrighted: you must supply your own.
"""
import contextlib
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path

from .adf import FLOPPY_SUFFIXES, AdfDisk
from .browse import human
from .transfer import FAILED, OK, SKIPPED, Item
from .volume import HdfError, HdfVolume

# volume name on the disk (lower case) -> what the disk is for
VOLUMES = {"workbench3.1": "workbench", "install3.1": "install", "extras3.1": "extras",
           "locale": "locale", "fonts": "fonts", "storage3.1": "storage"}
LABELS = {"workbench": "Workbench3.1", "install": "Install3.1", "extras": "Extras3.1",
          "locale": "Locale", "fonts": "Fonts", "storage": "Storage3.1"}
REQUIRED = ("workbench", "install")                 # the system itself, and the hard disk startup script
OPTIONAL = ("extras", "locale", "fonts", "storage")
STARTUP = "S/Startup-Sequence"

# the folders the Installer creates before copying (it also puts an icon on Storage)
FOLDERS = ("Prefs", "Prefs/Env-Archive", "Prefs/Env-Archive/Sys", "Fonts", "Expansion", "WBStartup",
           "Locale", "Locale/Catalogs", "Locale/Languages", "Locale/Countries", "Locale/Help",
           "Classes", "Classes/Gadgets", "Classes/DataTypes", "Classes/Images",
           "Devs", "Devs/Monitors", "Devs/DataTypes", "Devs/DOSDrivers", "Devs/Printers", "Devs/Keymaps",
           "Storage", "Storage/DOSDrivers", "Storage/Printers", "Storage/Monitors", "Storage/Keymaps",
           "Storage/DataTypes", "S", "Tools", "Libs", "L")


@dataclass
class DiskSet:
    """The Workbench disks found in a folder."""
    found: dict = field(default_factory=dict)       # role -> path
    others: list = field(default_factory=list)      # "file (volume name)" of readable disks that are not Workbench 3.1

    @property
    def missing_required(self) -> list:
        return [LABELS[r] for r in REQUIRED if r not in self.found]

    @property
    def missing_optional(self) -> list:
        return [LABELS[r] for r in OPTIONAL if r not in self.found]

    @property
    def usable(self) -> bool:
        return not self.missing_required


def find_disks(folder) -> DiskSet:
    """Look through a folder (and, if it holds no disk images itself, its sub-folders) for the Workbench 3.1
    disks, recognised by their volume names."""
    folder = Path(folder)
    candidates = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in FLOPPY_SUFFIXES)
    if not candidates:
        candidates = sorted(p for p in folder.glob("*/*") if p.is_file() and p.suffix.lower() in FLOPPY_SUFFIXES)
    disks = DiskSet()
    for path in candidates:
        try:
            with AdfDisk(path) as disk:
                name = disk.name
        except HdfError:
            continue
        role = VOLUMES.get(name.lower())
        if role is None:
            disks.others.append(f"{path.name} ({name})")
        elif role not in disks.found:
            disks.found[role] = path
    return disks


def _top(path: str) -> str:
    return path.split("/", 1)[0].lower()


def _destination(role: str, path: str, has_fast_file_system: bool):
    """Where a file or folder of this disk goes in the image, or None if it is not copied (see module doc)."""
    low = path.lower()
    top = _top(path)
    if role == "workbench":
        return None if top == "locale" else path
    if role == "locale":
        return f"Locale/{path}" if top in ("catalogs", "countries", "help", "languages") else None
    if role == "extras":
        return None if top == "fonts" else path
    if role == "fonts":
        return f"Fonts/{path}"
    if role == "storage":
        if "/" not in path:
            return f"Storage/{path}" if low.endswith(".info") else None      # the drawer icons
        if top in ("monitors", "dosdrivers"):
            return f"Storage/{path}"
        if top in ("printers", "keymaps"):
            return f"Devs/{path}"                                              # all of them, the active ones
        return None
    if role == "install":
        parts = path.split("/")
        if low == "update/disk.info":
            return "Disk.info"
        if low == "update/startup-harddrive":
            return STARTUP
        if low == "libs/68040.library":
            return path
        if low == "l/fastfilesystem":
            return path if has_fast_file_system else None
        if len(parts) == 2 and parts[0].lower() == "hdtools" and parts[1].lower().startswith(("hd", "bru")):
            return f"Tools/{parts[1]}"
        if len(parts) == 3 and parts[0].lower() == "hdtools" and parts[1].lower() == "s":
            return f"S/{parts[2]}"
    return None


def _blocks(size: int) -> int:
    data = ceil(size / 512)
    return data + 1 + ceil(data / 72)             # data blocks, file header, file list (extension) blocks


def install_workbench(volume: HdfVolume, disks: dict, include=OPTIONAL, region="PAL",
                      replace_startup=False, progress=None) -> list:
    """Install Workbench 3.1 into the image from the disks in {role: path} (see find_disks).

    include: which optional disks to install. region: "PAL" or "NTSC", the monitor driver that becomes active.
    If the image already has a startup script it is only replaced when replace_startup is True (the old one
    is kept as S/Startup-Sequence.old). progress(fraction, text) is called as work proceeds.
    Returns one Item per disk, plus one for every file that could not be copied."""
    missing = [LABELS[r] for r in REQUIRED if r not in disks]
    if missing:
        return [Item("Workbench", FAILED, "missing disk(s): " + ", ".join(missing))]
    if region not in ("PAL", "NTSC"):
        raise ValueError("region must be PAL or NTSC")
    if volume.exists(STARTUP) and not replace_startup:
        return [Item(STARTUP, FAILED, "the image already has a startup script; replacing it needs your OK")]

    roles = ["workbench", "locale", "extras", "fonts", "storage", "install"]          # the Installer's order
    roles = [r for r in roles if r in REQUIRED or (r in include and r in disks)]
    items = [Item(LABELS[r], SKIPPED, "disk not found" if r not in disks else "not selected")
             for r in OPTIONAL if r not in roles]
    try:
        with contextlib.ExitStack() as stack:
            opened = {r: stack.enter_context(AdfDisk(disks[r])) for r in roles}
            entries = {r: opened[r].entries() for r in roles}
            has_ffs = any(e.path.lower() == "l/fastfilesystem" for e in entries["workbench"])
            ops = [(r, e, _destination(r, e.path, has_ffs)) for r in roles for e in entries[r]]
            ops = [(r, e, dest) for r, e, dest in ops if dest]

            needed = sum(_blocks(e.size) if not e.is_dir else 1 for _, e, _ in ops) * 512
            if needed > volume.free_bytes:
                return [Item("Workbench", FAILED,
                             f"not enough free space ({human(needed)} needed, {human(volume.free_bytes)} free); "
                             "use a bigger image")]

            for folder in FOLDERS:
                volume.makedirs(folder)
            if volume.exists(STARTUP) and not volume.exists(STARTUP + ".old"):    # replace_startup is True
                volume.put_bytes(volume.read(STARTUP), STARTUP + ".old", volume.meta(STARTUP))
            counts = {r: 0 for r in roles}
            for i, (role, entry, dest) in enumerate(ops):
                if progress:
                    progress(i / len(ops), dest)
                try:
                    if entry.is_dir:
                        volume.makedirs(dest)
                        continue
                    if "/" in dest:
                        volume.makedirs(dest.rsplit("/", 1)[0])
                    if volume.exists(dest):
                        volume.delete(dest, recursive=True)                         # later disks win, like the Installer
                    volume.put_bytes(opened[role].read(entry), dest, opened[role].meta(entry))
                    counts[role] += 1
                except HdfError as exc:
                    items.append(Item(f"{LABELS[role]}: {entry.path}", FAILED, str(exc)))
            items = [Item(LABELS[r], OK, f"{counts[r]} files") for r in roles] + items
    except HdfError as exc:
        return [Item("Workbench", FAILED, str(exc))] + items

    if "storage" in roles:
        items.append(_activate_monitor(volume, region))
    return items


def _activate_monitor(volume: HdfVolume, region: str) -> Item:
    """The Installer moves the PAL (or NTSC) driver from Storage/Monitors to Devs/Monitors so it is loaded at boot."""
    try:
        moved = 0
        for suffix in ("", ".info"):
            source, target = f"Storage/Monitors/{region}{suffix}", f"Devs/Monitors/{region}{suffix}"
            if volume.exists(source):
                if volume.exists(target):                      # installing again: the new driver replaces the old
                    volume.delete(target)
                volume.put_bytes(volume.read(source), target, volume.meta(source))
                volume.delete(source)
                moved += 1
        return Item(f"{region} monitor", OK if moved else SKIPPED, "active in Devs/Monitors" if moved else "not on the Storage disk")
    except HdfError as exc:
        return Item(f"{region} monitor", FAILED, str(exc))
