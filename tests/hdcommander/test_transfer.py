import tempfile
import unittest
from pathlib import Path

from tabs.hdcommander import HdfVolume
from tabs.hdcommander import transfer
from tests.helpers import make_lha


class TransferTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.vol = HdfVolume.create(str(self.dir / "t.hdf"), 8)
        self.addCleanup(self.vol.close)

    def test_put_file_and_folder_with_lha(self):
        src = self.dir / "src" / "stuff"
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_bytes(b"aaa")
        (src / "sub" / "b.txt").write_bytes(b"bbb")
        (src / "empty").mkdir()
        (src / ".hidden").write_bytes(b"x")
        (src / "Game.lha").write_bytes(make_lha({"Game/Game.slave": b"s"}))
        items = transfer.put_host(self.vol, src, "Work")
        self.assertTrue(all(i.status == transfer.OK for i in items), transfer.report(items))
        self.assertEqual(self.vol.read("Work/stuff/a.txt"), b"aaa")
        self.assertEqual(self.vol.read("Work/stuff/sub/b.txt"), b"bbb")
        self.assertTrue(self.vol.isdir("Work/stuff/empty"))
        self.assertFalse(self.vol.exists("Work/stuff/.hidden"))
        self.assertEqual(self.vol.read("Work/stuff/Game.lha"), (src / "Game.lha").read_bytes())  # plain copy
        self.assertFalse(self.vol.exists("Games"))                                               # not installed

    def test_install_games_mode(self):
        folder = self.dir / "pack"
        folder.mkdir()
        (folder / "Game.lha").write_bytes(make_lha({"Game/Game.slave": b"s"}))
        (folder / "Docs.lha").write_bytes(make_lha({"Docs/readme": b"x"}))     # archive, but not a game
        (folder / "readme.txt").write_bytes(b"ignore me")
        items = transfer.put_host(self.vol, folder, "Elsewhere", install_games=True)
        by_name = {i.name: i for i in items}
        self.assertEqual(sorted(by_name), ["Docs.lha", "Game.lha"])           # readme.txt ignored silently
        self.assertEqual(by_name["Game.lha"].status, "ok")
        self.assertEqual(by_name["Docs.lha"].status, "skipped")
        self.assertEqual(self.vol.read("Games/G/Game/Game.slave"), b"s")
        self.assertFalse(self.vol.exists("Elsewhere"))                         # dest dir not used/created
        again = transfer.put_host(self.vol, folder / "Game.lha", "", install_games=True)
        self.assertEqual(again[0].status, "skipped")                           # already installed
        txt = transfer.put_host(self.vol, folder / "readme.txt", "", install_games=True)
        self.assertEqual(txt[0].status, "skipped")                             # directly selected non-archive

    def test_skip_existing_and_failures(self):
        f = self.dir / "a.txt"
        f.write_bytes(b"1")
        self.assertEqual(transfer.put_host(self.vol, f, "")[0].status, transfer.OK)
        self.assertEqual(transfer.put_host(self.vol, f, "")[0].status, "skipped")
        long = self.dir / ("x" * 31)
        long.write_bytes(b"1")
        self.assertEqual(transfer.put_host(self.vol, long, "")[0].status, "failed")

    def test_get_hdf_roundtrip(self):
        self.vol.makedirs("D/E")
        self.vol.put_bytes(b"one", "D/f1")
        self.vol.put_bytes(b"two", "D/E/f2")
        out = self.dir / "out"
        out.mkdir()
        items = transfer.get_hdf(self.vol, "D", out)
        self.assertTrue(all(i.status == transfer.OK for i in items))
        self.assertEqual((out / "D" / "f1").read_bytes(), b"one")
        self.assertEqual((out / "D" / "E" / "f2").read_bytes(), b"two")
        self.assertEqual(transfer.get_hdf(self.vol, "D/f1", out / "D")[0].status, "skipped")

    def test_transfer_items_move_delete_preview(self):
        from tabs.hdcommander.browse import HdfLocation, HostLocation
        host, hdf = HostLocation(self.dir), HdfLocation(self.vol)
        (self.dir / "m.txt").write_bytes(b"text")
        (self.dir / "skipme.txt").write_bytes(b"s")
        seen = []
        items = transfer.transfer_items(self.vol, host, hdf, ["m.txt"], move=True,
                                        progress=lambda f, t: seen.append(f))
        self.assertEqual([i.status for i in items], ["ok"])
        self.assertFalse((self.dir / "m.txt").exists())          # moved
        self.assertEqual(self.vol.read("m.txt"), b"text")
        self.assertTrue(seen and seen[0] == 0)
        # moving something that is skipped must NOT delete the source
        self.vol.put_bytes(b"x", "skipme.txt")
        items = transfer.transfer_items(self.vol, host, hdf, ["skipme.txt"], move=True)
        self.assertEqual(items[0].status, "skipped")
        self.assertTrue((self.dir / "skipme.txt").exists())
        # image -> host, then preview
        out = self.dir / "out"
        out.mkdir()
        items = transfer.transfer_items(self.vol, hdf, HostLocation(out), ["m.txt"], move=True)
        self.assertEqual(items[0].status, "ok")
        self.assertFalse(self.vol.exists("m.txt"))
        self.assertEqual(transfer.preview_text(self.vol, HostLocation(out), "m.txt"), "text")
        self.vol.put_bytes(b"\0\1\2abc", "bin")
        self.assertIn("00 01 02 61 62 63", transfer.preview_text(self.vol, hdf, "bin"))
        self.assertEqual(transfer.delete_items(self.vol, hdf, ["bin"]), [])
        self.assertEqual(transfer.delete_items(self.vol, hdf, ["nope"])[0].status, "failed")

    def test_delete_host(self):
        d = self.dir / "dd"
        (d / "x").mkdir(parents=True)
        transfer.delete_host(d)
        self.assertFalse(d.exists())


if __name__ == "__main__":
    unittest.main()
