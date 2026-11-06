import tempfile
import unittest
from pathlib import Path

from tabs.hdcommander import HdfVolume, whdinstall
from tabs.hdcommander.volume import HdfError
from tests.helpers import binary, distribution, make_lha


class WhdInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.vol = HdfVolume.create(str(self.dir / "t.hdf"), 8)
        self.addCleanup(self.vol.close)

    def archive(self, **kw):
        p = self.dir / "WHDLoad_usr_small.lha"
        p.write_bytes(distribution(**kw))
        return p

    def by_name(self, items):
        return {i.name: i for i in items}

    def test_parse_version(self):
        self.assertEqual(whdinstall.parse_version(binary("WHDLoad", "20.1")), (20, 1))
        self.assertEqual(whdinstall.parse_version(b"Nu$VER: RawDIC 6.1 [build 172]"), (6, 1))
        self.assertIsNone(whdinstall.parse_version(b"no version here"))

    def test_fresh_install_without_docs(self):
        progress = []
        items = whdinstall.install_whdload(self.vol, self.archive(), progress=lambda f, t: progress.append(f))
        self.assertTrue(all(i.status == "ok" for i in items), items)
        self.assertEqual(self.vol.read("C/WHDLoad"), binary("WHDLoad", "20.1"))
        self.assertEqual(self.vol.read("C/RawDIC"), binary("RawDIC", "6.1"))
        self.assertEqual(self.vol.read("S/WHDLoad.prefs"), b"prefs v2")
        self.assertEqual(self.vol.read("S/WHDLoad-Startup"), b"startup")
        self.assertFalse(self.vol.exists("Help"))             # docs not requested
        self.assertFalse(self.vol.exists("Install"))          # the installer script is not copied
        self.assertTrue(self.vol.isdir("Devs/Kickstarts"))    # created for the user's ROMs
        self.assertTrue(progress and progress[0] == 0)

    def test_docs_and_archive_without_root_folder(self):
        arc = self.dir / "flat.lha"
        arc.write_bytes(distribution(root=""))
        self.assertGreater(whdinstall.docs_size(arc), 0)
        items = whdinstall.install_whdload(self.vol, arc, include_docs=True)
        self.assertEqual(self.vol.read("Help/WHDLoad/History.txt"), b"history")
        self.assertEqual(self.vol.read("Help/WHDLoad/en/index.html"), b"<html>")
        self.assertIn("Docs", self.by_name(items))

    def test_upgrade_and_never_downgrade(self):
        self.vol.makedirs("C")
        self.vol.put_bytes(binary("WHDLoad", "20.0"), "C/WHDLoad")
        items = self.by_name(whdinstall.install_whdload(self.vol, self.archive()))
        self.assertEqual(items["WHDLoad"].status, "ok")
        self.assertIn("20.0 -> 20.1", items["WHDLoad"].message)
        self.assertEqual(self.vol.read("C/WHDLoad"), binary("WHDLoad", "20.1"))
        # an archive with an OLDER WHDLoad must not replace the installed 20.1
        old = self.dir / "old.lha"
        old.write_bytes(distribution(whdload_ver="19.0"))
        items = self.by_name(whdinstall.install_whdload(self.vol, old))
        self.assertEqual(items["WHDLoad"].status, "skipped")
        self.assertIn("20.1", items["WHDLoad"].message)
        self.assertEqual(self.vol.read("C/WHDLoad"), binary("WHDLoad", "20.1"))
        # same archive again: everything up to date
        items = whdinstall.install_whdload(self.vol, self.archive())
        self.assertTrue(all(i.status == "skipped" for i in items), items)

    def test_existing_prefs_are_kept(self):
        self.vol.makedirs("S")
        self.vol.put_bytes(b"my tuned prefs", "S/WHDLoad.prefs")
        items = self.by_name(whdinstall.install_whdload(self.vol, self.archive()))
        self.assertEqual(self.vol.read("S/WHDLoad.prefs"), b"my tuned prefs")        # untouched
        self.assertEqual(self.vol.read("S/WHDLoad.prefs.default"), b"prefs v2")      # new one beside it
        self.assertIn(".default", items["WHDLoad.prefs"].message)
        again = self.by_name(whdinstall.install_whdload(self.vol, self.archive()))
        self.assertEqual(again["WHDLoad.prefs"].status, "skipped")

    def test_not_a_distribution_and_no_space(self):
        junk = self.dir / "junk.lha"
        junk.write_bytes(make_lha({"Game/Game.slave": b"s"}))
        with self.assertRaises(HdfError):
            whdinstall.docs_size(junk)
        items = whdinstall.install_whdload(self.vol, junk)
        self.assertEqual([i.status for i in items], ["failed"])
        self.assertFalse(self.vol.exists("C"))                 # nothing written
        big = self.dir / "big.lha"
        big.write_bytes(make_lha({"C/WHDLoad": binary("WHDLoad", "20.1") + b"x" * (9 * 1024 * 1024)}))
        items = whdinstall.install_whdload(self.vol, big)
        self.assertEqual(items[0].status, "failed")
        self.assertIn("free space", items[0].message)

    def test_template_kickstarts_and_install(self):
        folder = self.dir / "ks"
        folder.mkdir()
        (folder / "kick34005.A500").write_bytes(b"rom" * 10)
        (folder / "kick34005.A500.RTB").write_bytes(b"rtb")
        (folder / "put-your-kickstart-files-here.txt").write_text("notes")
        (folder / ".DS_Store").write_bytes(b"x")
        (folder / "sub").mkdir()
        files = whdinstall.template_kickstarts(folder)
        self.assertEqual([p.name for p in files], ["kick34005.A500", "kick34005.A500.RTB"])
        self.assertEqual(whdinstall.template_kickstarts(self.dir / "missing"), [])
        whdinstall.install_whdload(self.vol, self.archive())
        items = whdinstall.install_kickstarts(self.vol, files)
        self.assertEqual([i.status for i in items], ["ok", "ok"])
        self.assertEqual(self.vol.read("Devs/Kickstarts/kick34005.A500"), b"rom" * 10)
        self.assertFalse(self.vol.exists("Devs/Kickstarts/put-your-kickstart-files-here.txt"))
        again = whdinstall.install_kickstarts(self.vol, files)               # already there: kept
        self.assertEqual([i.status for i in again], ["skipped", "skipped"])
        self.assertEqual(whdinstall.kickstart_report(self.vol).count("missing"), 4)   # ROM + RTB of 1.3 are in

    def test_kickstart_report_and_notice(self):
        whdinstall.install_whdload(self.vol, self.archive())
        report = whdinstall.kickstart_report(self.vol)
        self.assertIn("kick34005.A500", report)
        self.assertEqual(report.count("missing"), 5)
        self.vol.put_bytes(b"rom", "Devs/Kickstarts/KICK34005.a500")      # case-insensitive, like AmigaDOS
        self.assertIn("ROM found, .RTB missing", whdinstall.kickstart_report(self.vol))
        self.vol.put_bytes(b"rtb", "Devs/Kickstarts/kick34005.A500.RTB")
        self.assertEqual(whdinstall.kickstart_report(self.vol).count("found"), 1)   # only kick34005 is complete
        notice = whdinstall.kickstart_notice(self.vol)
        self.assertIn("Devs:Kickstarts", notice)
        self.assertIn("copyrighted", notice)


if __name__ == "__main__":
    unittest.main()
