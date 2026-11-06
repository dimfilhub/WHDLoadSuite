"""Read-only access to Amiga floppy disk images: .adf, or .adz (the same, gzip-compressed).

amitools refuses a few real Commodore disks (e.g. the Workbench 3.1 disk) because one file header lists
more data blocks than the file's size needs. A real Amiga simply ignores the surplus, so reading here is
lenient about that; everything else is still checked.
"""
import gzip
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import amitools.fs.ADFSDir as _adfs_dir
from amitools.fs.ADFSFile import ADFSFile
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory

from .volume import HdfError

FLOPPY_SUFFIXES = (".adf", ".adz")
MAX_FLOPPY_BYTES = 1_000_000      # a DD floppy is 901,120 bytes; HD floppies and hard disk images are not handled


class _LenientFile(ADFSFile):
    def calc_number_of_data_blks(self):
        return max(super().calc_number_of_data_blks(), len(self.data_blk_nums))


@dataclass
class AdfEntry:
    path: str                 # "S/Startup-Sequence", in the case used on the disk
    is_dir: bool
    size: int
    _node: object = None


class AdfDisk:
    """An opened floppy image. Use as a context manager (or call close())."""

    def __init__(self, path):
        self.path = Path(path)
        self._temp = None
        self._blkdev = self._vol = None
        self._entries = None
        try:
            image = self._prepare()
            self._blkdev = BlkDevFactory().open(image, read_only=True)
            self._vol = ADFSVolume(self._blkdev)
            self._vol.open()
        except HdfError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise HdfError(f"{self.path.name}: not a readable Amiga disk image ({exc})") from None

    def _prepare(self) -> str:
        suffix = self.path.suffix.lower()
        if suffix not in FLOPPY_SUFFIXES:
            raise HdfError(f"{self.path.name}: only .adf and .adz disk images are supported")
        if suffix == ".adf":
            if self.path.stat().st_size > MAX_FLOPPY_BYTES:
                raise HdfError(f"{self.path.name}: too big for a floppy disk image")
            return str(self.path)
        with gzip.open(self.path, "rb") as fh:                 # .adz: unpack to a temporary .adf
            data = fh.read(MAX_FLOPPY_BYTES + 1)
        if len(data) > MAX_FLOPPY_BYTES:
            raise HdfError(f"{self.path.name}: too big for a floppy disk image")
        handle, name = tempfile.mkstemp(suffix=".adf")
        self._temp = name
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        return name

    @property
    def name(self) -> str:
        """The volume name, e.g. 'Workbench3.1'."""
        return self._vol.get_volume_name().get_unicode()

    def entries(self) -> list:
        """Every file and folder on the disk, in directory order, folders before their contents."""
        if self._entries is None:
            original = _adfs_dir.ADFSFile
            _adfs_dir.ADFSFile = _LenientFile          # amitools builds file nodes through this name
            try:
                found = []
                self._walk(self._vol.get_root_dir(), "", found)
                self._entries = found
            except Exception as exc:
                raise HdfError(f"{self.path.name}: cannot read the disk ({exc})") from None
            finally:
                _adfs_dir.ADFSFile = original
        return self._entries

    def _walk(self, node, prefix, out):
        for child in node.get_entries():
            name = child.name.get_unicode_name()
            is_dir = child.is_dir()
            out.append(AdfEntry(prefix + name, is_dir, 0 if is_dir else child.block.byte_size, child))
            if is_dir:
                self._walk(child, prefix + name + "/", out)

    def read(self, entry: AdfEntry) -> bytes:
        try:
            return bytes(entry._node.get_file_data())
        except Exception as exc:
            raise HdfError(f"{self.path.name}: {entry.path}: {exc}") from None

    def meta(self, entry: AdfEntry):
        """The file's attributes (protection bits, comment, date), to pass to HdfVolume.put_bytes."""
        return entry._node.get_meta_info()

    def close(self):
        for obj in (self._vol, self._blkdev):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._vol = self._blkdev = None
        if self._temp:
            try:
                os.remove(self._temp)
            except OSError:
                pass
            self._temp = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
