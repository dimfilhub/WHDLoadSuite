"""Install BetterWB (an add-on for AmigaOS 3.1) into an image that already holds Workbench 3.1.

BetterWB comes as six floppy images, each with one zip. This repeats what its Install_BetterWB script does,
without needing an Amiga: unzip the six zips over the system drive, copy the readme to Locale/Help, delete the
files BetterWB makes obsolete, set the "pure" bit on the C: commands and the "script" bit on three scripts, and
optionally use the Env-Handler startup script. The disks are the author's own distribution: supply your own.
"""
import contextlib
import io
import zipfile
from math import ceil
from pathlib import Path

from .adf import FLOPPY_SUFFIXES, AdfDisk
from .browse import human
from .transfer import FAILED, OK, SKIPPED, Item
from .volume import HdfError, HdfVolume

# volume name on the disk (lower case) -> (label, zip inside it); this is the order the script unzips them in
DISKS = {"misc3.1": ("Misc3.1", "BetterWB1.zip"), "tools3.1": ("Tools3.1", "BetterWB2.zip"),
         "bonus3.1": ("Bonus3.1", "BetterWB3.zip"), "docs3.1": ("Docs3.1", "BetterWB4.zip"),
         "icons3.1": ("Icons3.1", "BetterWB5.zip"), "drivers3.1": ("Drivers3.1", "BetterWB6.zip")}
REQUIRED = ("misc3.1",)
README = ("BetterWB.readme.txt", "Locale/Help/BetterWB.readme.txt")
STARTUP, ENV_STARTUP = "S/Startup-Sequence", "S/Startup-Envhandler"
PURE, SCRIPT = 0x20, 0x40

OBSOLETE = ("S/BRUtab", "S/HDBackup.config", "Tools/calculator", "Tools/calculator.info", "Tools/BRU",
            "Tools/HDBackup.help", "Tools/HDBackup.info", "Tools/HDBackup", "Tools/Showconfig.info",
            "Tools/Showconfig", "System/NoFastMem", "System/NoFastMem.info", "Tools/Commodities/Clicktofront",
            "Tools/Commodities/Clicktofront.info", "Tools/PrepCard.info")
PURE_COMMANDS = ("AddBuffers AddDataTypes Assign Avail Break ChangeTaskPri ConClip Copy CPU Date Delete Dir "
                 "DiskChange Ed Edit Eval Execute Filenote IconX Info Install Join List Lock MagTape MakeDir "
                 "MakeLink Mount Protect Relabel RemRAD Rename RequestChoice RequestFile Search SetClock "
                 "SetDate SetFont SetKeyboard Sort Status Type Version").split()
SCRIPTS = ("System/Rebooter", "System/HardWiz", "Tools/PrepCard+")


def find_disks(folder) -> dict:
    """{volume name (lower case): path} of the BetterWB disks in a folder (or, if it holds no disk images itself,
    in its sub-folders)."""
    folder = Path(folder)
    candidates = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in FLOPPY_SUFFIXES)
    if not candidates:
        candidates = sorted(p for p in folder.glob("*/*") if p.is_file() and p.suffix.lower() in FLOPPY_SUFFIXES)
    found = {}
    for path in candidates:
        try:
            with AdfDisk(path) as disk:
                name = disk.name.lower()
        except HdfError:
            continue
        if name in DISKS and name not in found:
            found[name] = path
    return found


def missing(found: dict) -> tuple:
    """(required labels not found, optional labels not found)"""
    return (tuple(DISKS[v][0] for v in REQUIRED if v not in found),
            tuple(DISKS[v][0] for v in DISKS if v not in REQUIRED and v not in found))


def needs_workbench(volume: HdfVolume) -> bool:
    return not (volume.exists(STARTUP) and volume.isdir("C") and volume.isdir("Libs"))


def _blocks(size: int) -> int:
    data = ceil(size / 512)
    return data + 1 + ceil(data / 72)


def install_betterwb(volume: HdfVolume, disks: dict, env_handler=False, progress=None) -> list:
    """Install BetterWB from the disks in {volume name: path} (see find_disks). env_handler: use the Env-Handler
    startup script (saves RAM, but warns whenever preferences are saved). Returns one Item per disk plus one per
    problem. progress(fraction, text) is called as work proceeds."""
    lost = missing(disks)[0]
    if lost:
        return [Item("BetterWB", FAILED, "missing disk(s): " + ", ".join(lost))]
    if needs_workbench(volume):
        return [Item("BetterWB", FAILED, "the image has no Workbench 3.1 yet: use Make bootable first")]
    names = [v for v in DISKS if v in disks]
    items = [Item(DISKS[v][0], SKIPPED, "disk not found") for v in DISKS if v not in disks]
    try:
        with contextlib.ExitStack() as stack:
            archives = {}
            for v in names:
                disk = stack.enter_context(AdfDisk(disks[v]))
                entry = next((e for e in disk.entries() if e.path.lower() == DISKS[v][1].lower()), None)
                if entry is None:
                    return [Item(DISKS[v][0], FAILED, f"{DISKS[v][1]} is not on this disk")] + items
                archives[v] = zipfile.ZipFile(io.BytesIO(disk.read(entry)))
            readme = stack.enter_context(AdfDisk(disks["misc3.1"]))
            readme_entry = next((e for e in readme.entries() if e.path.lower() == README[0].lower()), None)
            readme_data = readme.read(readme_entry) if readme_entry else None

            files = [(v, i) for v in names for i in archives[v].infolist() if not i.is_dir()]
            needed = sum(_blocks(i.file_size) for _, i in files) * 512
            if needed > volume.free_bytes:
                return [Item("BetterWB", FAILED, f"not enough free space ({human(needed)} needed, "
                                                 f"{human(volume.free_bytes)} free); use a bigger image")]
            if volume.exists(STARTUP) and not volume.exists(STARTUP + ".old"):
                volume.put_bytes(volume.read(STARTUP), STARTUP + ".old", volume.meta(STARTUP))
            if readme_data is not None:
                volume.makedirs("Locale/Help")
                if volume.exists(README[1]):
                    volume.delete(README[1])
                volume.put_bytes(readme_data, README[1])

            counts = {v: 0 for v in names}
            for n, (v, info) in enumerate(files):
                dest = info.filename.strip("/")
                if progress:
                    progress(n / len(files), dest)
                try:
                    if "/" in dest:
                        volume.makedirs(dest.rsplit("/", 1)[0])
                    if volume.exists(dest):
                        volume.delete(dest, recursive=True)
                    volume.put_bytes(archives[v].read(info), dest)
                    counts[v] += 1
                except HdfError as exc:
                    items.append(Item(f"{DISKS[v][0]}: {dest}", FAILED, str(exc)))
            items = [Item(DISKS[v][0], OK, f"{counts[v]} files") for v in names] + items
    except (HdfError, zipfile.BadZipFile) as exc:
        return [Item("BetterWB", FAILED, str(exc))] + items

    items.append(_clean_up(volume, env_handler))
    return items


def _clean_up(volume: HdfVolume, env_handler: bool) -> Item:
    """The script's closing steps: obsolete files, protection bits, the startup script."""
    problems = []
    for path in OBSOLETE:
        try:
            if volume.exists(path):
                volume.delete(path, recursive=True)
        except HdfError as exc:
            problems.append(str(exc))
    for paths, bits in (([f"C/{c}" for c in PURE_COMMANDS], PURE), (SCRIPTS, SCRIPT)):
        for path in paths:
            try:
                if volume.exists(path):
                    volume.add_protect(path, bits)
            except HdfError as exc:
                problems.append(str(exc))
    if env_handler and volume.exists(ENV_STARTUP):
        try:
            data = volume.read(ENV_STARTUP)
            volume.delete(STARTUP)
            volume.put_bytes(data, STARTUP, volume.meta(ENV_STARTUP))
        except HdfError as exc:
            problems.append(str(exc))
    if problems:
        return Item("Clean-up", FAILED, "; ".join(problems[:3]))
    return Item("Clean-up", OK, "obsolete files removed, protection bits set"
                                + (", Env-Handler startup" if env_handler else ""))
