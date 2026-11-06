"""Builders shared by the tests: small .lha archives and a fake WHDLoad distribution."""
import struct
import tkinter as tk

from common import lha


def make_lha(files):
    """Build a level-0 archive with stored (-lh0-) entries. files: {path: bytes}."""
    out = b""
    for path, data in files.items():
        name = path.encode("latin-1")
        body = (b"-lh0-" + struct.pack("<II", len(data), len(data)) + b"\0\0\0\0"
                + b"\x20\x00" + bytes([len(name)]) + name + struct.pack("<H", lha._crc16(data)))
        out += bytes([len(body), sum(body) & 0xFF]) + body + data
    return out + b"\0"


def binary(name, ver):
    """Fake Amiga executable with a $VER string."""
    return b"\x00\x00\x03\xf3" + b"\x00" * 8 + f"$VER: {name} {ver} (01.01.2026)".encode() + b"\x00" * 4


def distribution(whdload_ver="20.1", prefs=b"prefs v2", root="WHDLoad/"):
    files = {
        root + "C/WHDLoad": binary("WHDLoad", whdload_ver),
        root + "C/RawDIC": binary("RawDIC", "6.1"),
        root + "S/WHDLoad.prefs": prefs,
        root + "S/WHDLoad-Startup": b"startup",
        root + "S/WHDLoad-Cleanup": b"cleanup",
        root + "Docs/History.txt": b"history",
        root + "Docs/en/index.html": b"<html>",
        root + "Install": b"; installer script",
    }
    return make_lha(files)


def make_adf(path, volume, files):
    """Create a small floppy disk image. files: {"Dir/File": bytes} or {"Dir/File": (bytes, protection_bits)};
    folders are created as needed."""
    from amitools.fs.ADFSVolume import ADFSVolume
    from amitools.fs.DosType import DOS1
    from amitools.fs.FSString import FSString
    from amitools.fs.MetaInfo import MetaInfo
    from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory

    blkdev = BlkDevFactory().create(str(path))
    vol = ADFSVolume(blkdev)
    vol.create(FSString(volume), dos_type=DOS1)
    vol.open()
    made = set()
    for name, content in sorted(files.items()):
        protect = None
        if isinstance(content, tuple):
            content, protect = content
        folder = ""
        for part in name.split("/")[:-1]:
            folder = f"{folder}/{part}" if folder else part
            if folder not in made:
                vol.create_dir(FSString(folder))
                made.add(folder)
        if protect is None:
            vol.write_file(content, FSString(name))
        else:
            parent, leaf = vol.get_create_path_name(FSString(name))
            parent.create_file(leaf, content, MetaInfo(protect=protect)).flush()
    vol.close()
    blkdev.close()


def workbench_disks(folder):
    """A set of tiny stand-ins for the six Workbench 3.1 disks, written into `folder`."""
    from pathlib import Path
    folder = Path(folder)
    disks = {
        "Workbench.adf": ("Workbench3.1", {
            "C/SetPatch": b"setpatch", "C/Copy": (b"copy", 0x10), "S/Startup-Sequence": b"; floppy startup\n",
            "Devs/Printers/EpsonQ": b"", "Devs.info": b"icon", "Disk.info": b"workbench disk icon",
            "Prefs.info": b"workbench prefs icon", "L/aux-handler": b"old handler"}),
        "Install.adf": ("Install3.1", {
            "Update/Startup-HardDrive": (b"; hard drive startup\n", 0x40), "Update/Disk.info": b"hard disk icon",
            "HDTools/HDToolBox": b"hdtoolbox", "HDTools/BRU": b"bru", "HDTools/drive definitions": b"not copied",
            "HDTools/S/BRUtab": b"brutab", "Libs/68040.library": b"68040", "C/SetPatch": b"install setpatch"}),
        "Extras.adf": ("Extras3.1", {
            "Tools/Calculator": b"calc", "Prefs.info": b"extras prefs icon", "Disk.info": b"extras disk icon",
            "L/aux-handler": b"new handler"}),
        "Locale.adf": ("Locale", {
            "Catalogs/deutsch/Sys/workbench.catalog": b"cat", "Countries/germany.country": b"de",
            "Languages/deutsch.language": b"lang", "Help/readme": b"help", "Disk.info": b"locale disk icon"}),
        "Fonts.adf": ("Fonts", {"topaz.font": b"topaz", "topaz/8": b"8", "Disk.info": b"fonts disk icon"}),
        "Storage.adf": ("Storage3.1", {
            "Monitors/PAL": b"pal driver", "Monitors/PAL.info": b"pal icon", "Monitors/NTSC": b"ntsc driver",
            "DOSDrivers/RAD": b"rad", "Printers/EpsonQ": b"epson driver", "Keymaps/usa1": b"usa1",
            "DataTypes.info": b"dt icon", "Disk.info": b"storage disk icon"}),
    }
    for file, (volume, files) in disks.items():
        make_adf(folder / file, volume, files)
    return folder


def make_rdb_image(path, dostype="DOS3", size_mb=4, name="DH0"):
    """Create a hard disk image with a partition table and one partition of the given file system type
    ("DOS3", "PFS3", "SFS2", ...). The partition is not formatted: only its type is set."""
    import contextlib
    import io
    from amitools.tools.rdbtool import main as rdbtool

    with contextlib.redirect_stdout(io.StringIO()):
        rdbtool(args=[str(path), "create", f"size={size_mb}Mi", "+", "init", "+", "add", "size=100%",
                      f"name={name}", f"dostype={dostype}", "bootable=true"])


_root = []


def shared_root():
    """The one hidden Tk root every GUI test module uses (None when there is no display). Several Tk interpreters in
    one process hang `update()` on macOS runners, so they must not each create their own."""
    if not _root:
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            root = None
        _root.append(root)
    return _root[0]


def reset_root():
    """Leave the shared root as a new one: destroy what a test module left on it and cancel its pending timers, so
    they cannot fire inside the next module's tests."""
    root = shared_root()
    if root is None:
        return
    for child in root.winfo_children():
        child.destroy()
    for timer in root.tk.splitlist(root.tk.call("after", "info")):
        root.after_cancel(timer)
