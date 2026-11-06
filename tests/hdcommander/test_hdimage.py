import os
import tempfile
import unittest
from pathlib import Path

from tabs.hdcommander import HdfVolume, HdfError, UnsupportedFileSystem
from tests.helpers import make_rdb_image


class HdfVolumeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "t.hdf")

    def test_create_write_reopen_read(self):
        data = bytes(range(256)) * 400
        with HdfVolume.create(self.path, 8, name="DH0") as v:
            self.assertEqual(v.volume_name, "DH0")
            v.makedirs("Games/A-Z/Foo")
            v.put_bytes(data, "Games/A-Z/Foo/test.bin")
        with HdfVolume(self.path) as v:
            self.assertEqual(v.read("Games/A-Z/Foo/test.bin"), data)
            self.assertEqual([e.name for e in v.listdir()], ["Games"])
            entry = v.listdir("Games/A-Z/Foo")[0]
            self.assertEqual((entry.name, entry.is_dir, entry.size), ("test.bin", False, len(data)))
            self.assertTrue(v.isdir("games/a-z"))      # case-insensitive
            self.assertFalse(v.exists("Games/nope"))

    def test_put_host_file_and_delete(self):
        src = os.path.join(self.tmp.name, "src.txt")
        with open(src, "wb") as fh:
            fh.write(b"hello")
        with HdfVolume.create(self.path, 4) as v:
            free = v.free_bytes
            v.put(src, "src.txt")
            self.assertEqual(v.read("src.txt"), b"hello")
            v.delete("src.txt")
            self.assertFalse(v.exists("src.txt"))
            self.assertEqual(v.free_bytes, free)
            v.makedirs("a/b")
            v.put_bytes(b"x", "a/b/f")
            with self.assertRaises(HdfError):
                v.delete("a")
            v.delete("a", recursive=True)
            self.assertFalse(v.exists("a"))

    def test_errors(self):
        with HdfVolume.create(self.path, 4) as v:
            with self.assertRaises(HdfError):
                v.put_bytes(b"x", "missing/dir/f")
            v.put_bytes(b"x", "f")
            with self.assertRaises(HdfError):
                v.put_bytes(b"y", "f")                  # exists
            with self.assertRaises(HdfError):
                v.mkdir("x" * 31)                       # name too long
            with self.assertRaises(HdfError):
                v.mkdir("caf€")                    # not Latin-1
            with self.assertRaises(HdfError):
                v.put_bytes(b"x" * (8 * 1024 * 1024), "big")   # no space
            with self.assertRaises(HdfError):
                v.read("nothing")
        with self.assertRaises(HdfError):
            HdfVolume.create(self.path, 4)              # image exists

    def test_free_space_matches_amitools(self):
        with HdfVolume.create(self.path, 8) as v:
            self.assertEqual(v._free_blocks(), v._vol.get_free_blocks())
            v.makedirs("a/b")
            v.put_bytes(b"x" * 123457, "a/b/f")
            self.assertEqual(v._free_blocks(), v._vol.get_free_blocks())

    def test_pfs3_image_is_refused_with_a_clear_message(self):
        make_rdb_image(self.path, "PFS3")
        with self.assertRaises(UnsupportedFileSystem) as caught:
            HdfVolume(self.path)
        error = caught.exception
        self.assertEqual(error.fs, "PFS3")
        self.assertIsInstance(error, HdfError)                     # callers that catch HdfError still work
        for text in ("t.hdf", "PFS3 file system", "cannot write", "OFS and FFS", "New", "emulator"):
            self.assertIn(text, str(error))
        self.assertNotIn("Boot Block", str(error))                # not the cryptic block-level message
        self.assertEqual(error.short, "it uses the PFS3 file system")

    def test_other_unsupported_file_systems_are_named(self):
        for dostype, name in (("SFS2", "SFS"), ("FAT0", "FAT"), ("PDS3", "PFS3")):
            path = Path(self.path).with_name(dostype + ".hdf")
            make_rdb_image(path, dostype)
            with self.assertRaises(UnsupportedFileSystem, msg=dostype) as caught:
                HdfVolume(path)
            self.assertEqual(caught.exception.fs, name)

    def test_a_bare_pfs3_image_without_partition_table_is_recognised(self):
        Path(self.path).write_bytes(b"PFS\x03" + b"\0" * (1 << 20))
        with self.assertRaises(UnsupportedFileSystem) as caught:
            HdfVolume(self.path)
        self.assertEqual(caught.exception.fs, "PFS3")

    def test_standard_file_systems_still_open(self):
        for dostype in ("DOS0", "DOS1", "DOS3"):
            path = Path(self.path).with_name(dostype + ".hdf")
            make_rdb_image(path, dostype, name="DH0")
            HdfVolume(path, "DH0", _format=True).close()           # format it, then open it again
            with HdfVolume(path) as vol:
                self.assertEqual(vol.listdir(""), [], dostype)       # not refused as unsupported

    def test_junk_and_wrong_partition_names_keep_their_own_errors(self):
        Path(self.path).write_bytes(b"this is not a disk image" * 100)
        with self.assertRaises(HdfError) as caught:
            HdfVolume(self.path)
        self.assertNotIsInstance(caught.exception, UnsupportedFileSystem)
        other = Path(self.path).with_name("other.hdf")
        with HdfVolume.create(str(other), 4, name="DH1"):
            pass
        with self.assertRaises(HdfError) as caught:
            HdfVolume(other)                                       # looks for DH0
        self.assertIn("DH1", str(caught.exception))                # and says what the image does have

    def test_read_only(self):
        HdfVolume.create(self.path, 4).close()
        with HdfVolume(self.path, read_only=True) as v:
            with self.assertRaises(HdfError):
                v.mkdir("x")


if __name__ == "__main__":
    unittest.main()
