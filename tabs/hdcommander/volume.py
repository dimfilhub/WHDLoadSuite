"""HdfVolume: a small wrapper over amitools for working inside an .hdf image.

The image is an RDB disk with one OFS/FFS partition. All Amiga paths use "/" as
separator and are relative to the volume root ("Games/A-Z/Foo"). Amiga rules
apply: names up to 30 characters, case-insensitive, Latin-1 characters only.
"""
import contextlib
import io
import os
from dataclasses import dataclass

try:
    from amitools.fs.ADFSVolume import ADFSVolume
    from amitools.fs.FSError import FSError
    from amitools.fs.FSString import FSString
    from amitools.fs.blkdev.PartBlockDevice import PartBlockDevice
    from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
    from amitools.fs.rdb.RDisk import RDisk
    from amitools.tools.rdbtool import main as _rdbtool_main
    _IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    _IMPORT_ERROR = exc

DOS3 = 0x444F5303  # FFS + international mode
MAX_NAME = 30


class HdfError(Exception):
    """Any problem reading or writing the image."""


# File systems found on Amiga hard disks that amitools can neither read nor write: tag -> name for the user.
# (DOS0 to DOS7, the standard OFS/FFS family, are the ones it can.)
_UNSUPPORTED = {b"PFS": "PFS3", b"PDS": "PFS3", b"SFS": "SFS", b"FAT": "FAT"}


class UnsupportedFileSystem(HdfError):
    """The image is fine, but it uses a file system that HDCommander cannot write, such as PFS3."""

    def __init__(self, image, fs):
        self.fs = fs
        self.short = "it uses the %s file system" % fs
        super().__init__(
            "%s uses the %s file system, which HDCommander cannot write.\n\n"
            "Only the standard Amiga file systems (OFS and FFS, for example DOS3) can be written from here. "
            "Create a new image with New\u2026 to put files on, or fill this one inside the emulator."
            % (os.path.basename(str(image)), fs))


def _unsupported(dos_type: int):
    """The name of the file system if HDCommander cannot write it, else None."""
    tag = dos_type.to_bytes(4, "big")
    if tag[:3] == b"DOS":
        return None
    return _UNSUPPORTED.get(tag[:3], "unknown (0x%08x)" % dos_type)


@dataclass
class HdfEntry:
    name: str
    is_dir: bool
    size: int = 0
    protect: int = 0
    comment: str = ""


def _fs(path):
    return FSString(path)


def _clean(path):
    path = path.replace("\\", "/").strip("/")
    for part in filter(None, path.split("/")):
        if len(part) > MAX_NAME:
            raise HdfError("name longer than %d characters: %r" % (MAX_NAME, part))
        try:
            part.encode("latin-1")
        except UnicodeEncodeError:
            raise HdfError("name has characters outside Latin-1: %r" % part)
    return path


class HdfVolume:
    def __init__(self, path, partition="DH0", read_only=False, _format=False):
        if _IMPORT_ERROR:
            raise HdfError("amitools is not installed (pip install amitools): %s" % _IMPORT_ERROR)
        self.path = path
        self.partition = partition
        self.read_only = read_only
        self._raw = self._rdisk = self._bd = self._vol = None
        self.open(_format)

    # ----- creating / opening -----

    @classmethod
    def create(cls, path, size_mb, name="DH0", bootable=True):
        """Create a new RDB image with one formatted FFS partition and open it."""
        if os.path.exists(path):
            raise HdfError("already exists: %s" % path)
        args = [path, "create", "size=%dMi" % size_mb, "+", "init", "+", "add",
                "size=100%", "name=" + name, "dostype=DOS3",
                "bootable=" + ("true" if bootable else "false")]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = _rdbtool_main(args=args)
        except SystemExit as exc:
            rc = exc.code
        if rc not in (0, None) or not os.path.exists(path):
            if os.path.exists(path):
                os.remove(path)
            raise HdfError("rdbtool failed to create %s (code %s)" % (path, rc))
        # format the new partition
        return cls(path, name, _format=True)

    def _check_not_a_bare_unsupported_image(self):
        """An image without a partition table that starts with a known foreign file system (e.g. a bare PFS3
        hardfile) gets the clear message instead of a block-level error."""
        try:
            with open(self.path, "rb") as fh:
                head = fh.read(4)
        except OSError:
            return                                  # the normal open below reports it
        if len(head) == 4 and head[:3] in _UNSUPPORTED:
            raise UnsupportedFileSystem(self.path, _UNSUPPORTED[head[:3]])

    def open(self, _format=False):
        try:
            self._check_not_a_bare_unsupported_image()
            self._raw = RawBlockDevice(self.path, self.read_only)
            self._raw.open()
            self._rdisk = RDisk(self._raw)
            self._rdisk.open()
            part = self._rdisk.find_partition_by_string(self.partition)
            if part is None:
                names = ", ".join(p.get_drive_name().get_unicode() for p in self._rdisk.parts) or "none"
                raise HdfError("partition %r not found in %s (the image has: %s)" % (self.partition, self.path, names))
            unsupported = _unsupported(part.part_blk.dos_env.dos_type)
            if unsupported:
                raise UnsupportedFileSystem(self.path, unsupported)
            self._bd = PartBlockDevice(self._raw, part.part_blk)
            self._bd.open()
            self._vol = ADFSVolume(self._bd)
            if _format:
                self._vol.create(_fs(self.partition), dos_type=DOS3)
            self._vol.open()
        except HdfError:
            self._teardown()
            raise
        except Exception as exc:
            self._teardown()
            raise HdfError("cannot open %s: %s" % (self.path, exc))

    def _teardown(self):
        for obj in (self._bd, self._rdisk, self._raw):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._raw = self._rdisk = self._bd = self._vol = None

    def close(self):
        if self._vol is None:
            return
        try:
            self._vol.close()
            if not self.read_only:
                self._bd.flush()
        finally:
            self._teardown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ----- info -----

    @property
    def volume_name(self):
        return str(self._vol.get_volume_name().get_unicode())

    def _free_blocks(self):
        """Free block count. amitools counts bit by bit (very slow on big images),
        so popcount the bitmap bytes instead."""
        bm = self._vol.bitmap
        bits = bm.bitmap_bits
        data = bytes(bm.bitmap_data)
        full, rest = divmod(bits, 32)
        count = int.from_bytes(data[:full * 4], "big").bit_count()
        if rest:
            last = int.from_bytes(data[full * 4:full * 4 + 4], "big")
            count += (last & ((1 << rest) - 1)).bit_count()
        return count

    @property
    def free_bytes(self):
        return self._free_blocks() * self._bd.block_bytes

    @property
    def total_bytes(self):
        return self._vol.get_total_blocks() * self._bd.block_bytes

    # ----- queries -----

    def _node(self, path, **kw):
        path = _clean(path)
        try:
            return self._vol.get_path_name(_fs(path), **kw) if path else self._vol.get_root_dir()
        except FSError as exc:
            raise HdfError("%s: %s" % (path, exc))

    def exists(self, path):
        try:
            return self._find(path) is not None
        except HdfError:
            return False

    def _find(self, path):
        path = _clean(path)
        if not path:
            return self._vol.get_root_dir()
        try:
            return self._vol.get_path_name(_fs(path))
        except FSError:
            return None

    def isdir(self, path):
        node = self._find(path)
        return node is not None and node.is_dir()

    def listdir(self, path=""):
        node = self._node(path, allow_file=False)
        out = []
        for child in node.get_entries():
            blk = child.block
            out.append(HdfEntry(
                name=child.name.get_unicode_name(),
                is_dir=child.is_dir(),
                size=0 if child.is_dir() else blk.byte_size,
                protect=getattr(blk, "protect", 0) or 0,
                comment=getattr(blk, "comment", "") or "",
            ))
        out.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return out

    def meta(self, path):
        """The attributes (protection bits, comment, date) of a file, to pass to put_bytes."""
        node = self._find(path)
        if node is None:
            raise HdfError("%s: not found" % _clean(path))
        return node.get_meta_info()

    def add_protect(self, path, bits):
        """Set protection bits (e.g. 0x20 pure, 0x40 script) on top of the file's current ones."""
        self._writable()
        node = self._find(path)
        if node is None:
            raise HdfError("%s: not found" % _clean(path))
        try:
            node.change_protect((node.get_meta_info().protect or 0) | bits)
        except FSError as exc:
            raise HdfError("%s: %s" % (_clean(path), exc))

    def read(self, path):
        path = _clean(path)
        try:
            return bytes(self._vol.read_file(_fs(path)))
        except FSError as exc:
            raise HdfError("%s: %s" % (path, exc))

    # ----- changes -----

    def _writable(self):
        if self.read_only:
            raise HdfError("image opened read-only")

    def mkdir(self, path):
        self._writable()
        path = _clean(path)
        try:
            self._vol.create_dir(_fs(path))
        except FSError as exc:
            raise HdfError("%s: %s" % (path, exc))

    def makedirs(self, path):
        """Create a directory and any missing parents; fine if it exists."""
        parts = [p for p in _clean(path).split("/") if p]
        cur = ""
        for part in parts:
            cur = cur + "/" + part if cur else part
            node = self._find(cur)
            if node is None:
                self.mkdir(cur)
            elif not node.is_dir():
                raise HdfError("%s exists and is a file" % cur)

    def put_bytes(self, data, path, meta=None):
        """Write a file. meta: the attributes (protection bits, comment, date) of a file read from an Amiga
        volume (HdfVolume.meta or AdfDisk.meta); without it the file gets the defaults and today's date."""
        self._writable()
        path = _clean(path)
        if not self.isdir(os.path.dirname(path)):
            raise HdfError("parent directory missing: %s" % os.path.dirname(path))
        if self.exists(path):
            raise HdfError("already exists: %s" % path)
        if len(data) > self.free_bytes:
            raise HdfError("not enough free space for %s" % path)
        try:
            if meta is None:
                self._vol.write_file(bytes(data), _fs(path))
            else:
                parent, name = self._vol.get_create_path_name(_fs(path))
                if parent is None or name is None:
                    raise HdfError("invalid path: %s" % path)
                parent.create_file(name, bytes(data), meta).flush()
        except FSError as exc:
            raise HdfError("%s: %s" % (path, exc))

    def put(self, host_file, path):
        with open(host_file, "rb") as fh:
            self.put_bytes(fh.read(), path)

    def delete(self, path, recursive=False):
        self._writable()
        path = _clean(path)
        if not path:
            raise HdfError("cannot delete the volume root")
        try:
            self._vol.delete(_fs(path), all=recursive)
        except FSError as exc:
            raise HdfError("%s: %s" % (path, exc))
