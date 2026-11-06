import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from common import amiberry, amiberry_runtime as rt
from tests.amiberry.fake import make_fake, recorded, requires_posix, write_db


class FindTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make_app(self, parent):
        binary = Path(parent) / "Amiberry.app" / "Contents" / "MacOS" / "Amiberry"
        binary.parent.mkdir(parents=True)
        binary.write_text("x")
        return binary

    def test_resolves_an_app_a_folder_or_the_binary(self):
        binary = self.make_app(self.root)
        self.assertEqual(amiberry.resolve_executable(self.root / "Amiberry.app"), binary)
        self.assertEqual(amiberry.resolve_executable(self.root), binary)
        self.assertEqual(amiberry.resolve_executable(binary), binary)

    def test_nothing_found(self):
        self.assertIsNone(amiberry.resolve_executable(""))
        self.assertIsNone(amiberry.resolve_executable(None))
        self.assertIsNone(amiberry.resolve_executable(self.root / "missing"))
        self.assertIsNone(amiberry.resolve_executable(self.root))      # an empty folder

    def test_detect_looks_in_the_emulator_folder_first(self):
        binary = self.make_app(self.root / "emulator")
        with mock.patch.object(amiberry, "EMULATOR_DIR", self.root / "emulator"):
            self.assertEqual(amiberry.detect(), binary)
            self.assertEqual(amiberry.find(self.root / "nope"), binary)   # a bad setting falls back to detection

    def test_bundle_source_is_the_whole_app_on_macos(self):
        binary = self.make_app(self.root)
        source, rel = amiberry.bundle_source(binary)
        self.assertEqual(source, (self.root / "Amiberry.app").resolve())
        self.assertEqual(rel, "Amiberry.app/Contents/MacOS/Amiberry")
        plain = self.root / "Amiberry-win" / "amiberry.exe"
        plain.parent.mkdir()
        plain.write_text("x")
        self.assertEqual(amiberry.bundle_source(plain)[1], "Amiberry-win/amiberry.exe")


class RomTest(unittest.TestCase):
    def test_finds_roms_and_the_a1200_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("Kickstart v1.3.rom", "Kickstart v3.1 (A1200).ROM", "notes.txt"):
                (Path(tmp) / name).write_bytes(b"x")
            self.assertEqual([p.name for p in amiberry.rom_files(tmp)], ["Kickstart v1.3.rom", "Kickstart v3.1 (A1200).ROM"])
            self.assertEqual(amiberry.a1200_rom(tmp).name, "Kickstart v3.1 (A1200).ROM")
            self.assertEqual(amiberry.rom_files(Path(tmp) / "missing"), [])
            self.assertIsNone(amiberry.a1200_rom(None))


@requires_posix
class SetupAndLaunchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.exe = make_fake(self.root)
        self.args = self.root / "args.txt"
        env = mock.patch.dict(os.environ, {"FAKE_ARGS": str(self.args)})
        env.start()
        self.addCleanup(env.stop)
        self.kick = self.root / "Kickstarts"
        self.kick.mkdir()
        (self.kick / "Kickstart v3.1 (A1200).rom").write_bytes(b"rom")
        (self.root / "Alien_v1.0.lha").write_bytes(b"lha")

    def launch(self, *a, **kw):
        proc = amiberry.launch_game(self.exe, *a, home=self.home, **kw)
        proc.wait(timeout=20)
        return recorded(self.args)

    def test_prepare_home_copies_roms_and_downloads_whdload_once(self):
        ok, message = amiberry.prepare_home(self.exe, self.kick, self.home)
        self.assertEqual((ok, message), (True, ""))
        self.assertTrue(rt.has_whdload(self.home))
        self.assertTrue((self.home / "ROMs" / "Kickstart v3.1 (A1200).rom").is_file())
        self.exe.write_text("#!/bin/sh\nexit 1\n")           # a second call must not download again
        self.assertEqual(amiberry.prepare_home(self.exe, self.kick, self.home), (True, ""))

    def test_a_failed_download_is_reported(self):
        with mock.patch.dict(os.environ, {"FAKE_FAIL": "1"}):
            ok, message = amiberry.prepare_home(self.exe, self.kick, self.home)
        self.assertFalse(ok)
        self.assertIn("no network", message)
        self.assertFalse(amiberry.prepare_home(self.exe, self.kick, self.home, download=False)[0])

    def test_a_download_counts_by_its_result_not_by_amiberrys_exit_code(self):
        self.exe.write_text("#!/bin/sh\nmkdir -p \"$AMIBERRY_HOME_DIR/WHDBoot\" && echo w > \"$AMIBERRY_HOME_DIR/WHDBoot/WHDLoad\"\nexit 3\n")
        self.assertEqual(amiberry.prepare_home(self.exe, self.kick, self.home), (True, ""))

    def test_a_normal_game_runs_from_its_lha(self):
        args = self.launch(self.root / "Alien_v1.0.lha", kickstarts=self.kick, overrides={})
        self.assertEqual(args[-2], "--autoload")
        self.assertEqual(Path(args[-1]).resolve(), (self.root / "Alien_v1.0.lha").resolve())

    def test_hardware_overrides_reach_the_database_before_launch(self):
        amiberry.prepare_home(self.exe, self.kick, self.home)
        db = write_db(self.home, [{"filename": "Alien_v1.0", "hardware": {}}])
        self.launch(self.root / "Alien_v1.0.lha", kickstarts=self.kick,
                    overrides={"Alien_v1.0": {"hardware": {"z3_ram": 16}}})
        self.assertIn('"z3_ram": 16', db.read_text())

    def test_a_drive_game_needs_its_prepared_drive(self):
        overrides = {"Alien_v1.0": {"mode": "drive"}}
        with self.assertRaisesRegex(RuntimeError, "prepare it first"):
            amiberry.launch_game(self.exe, self.root / "Alien_v1.0.lha", None, self.kick, home=self.home, overrides=overrides)
        drive = self.root / "drive"
        drive.mkdir()
        args = self.launch(self.root / "Alien_v1.0.lha", drive=drive, kickstarts=self.kick, overrides=overrides)
        self.assertIn(f"filesystem2=rw,DH0:SYS:{drive.resolve()},1", args)
        self.assertNotIn("--autoload", args)

    def test_a_drive_game_without_an_a1200_rom_says_so(self):
        drive = self.root / "drive"
        drive.mkdir()
        with self.assertRaisesRegex(RuntimeError, "A1200 ROM"):
            amiberry.launch_game(self.exe, self.root / "Alien_v1.0.lha", drive, None, home=self.home,
                                 overrides={"Alien_v1.0": {"mode": "drive"}})

    def test_launch_hdf_boots_the_image(self):
        hdf = self.root / "Disk.hdf"
        hdf.write_bytes(b"x")
        amiberry.launch_hdf(self.exe, hdf, self.kick, home=self.home).wait(timeout=20)
        self.assertIn(f"hardfile2=rw,DH0:{hdf.resolve()},0,0,0,512,0,,uae0", recorded(self.args))
        with self.assertRaisesRegex(RuntimeError, "A1200 ROM"):
            amiberry.launch_hdf(self.exe, hdf, None, home=self.root / "empty-home")


INI = """[Amiberry]
FullScreenMode=-1
Version=Amiberry 8.5.0 (2026.10.27)

[DetectedROMs]
ROM_005=KS ROM v1.2 (A500,A1000,A2000) rev 33.180 (256k) [315093-01] / "{roms}/Kickstart v1.2.rom"
ROM_014=KS ROM v3.1 (A500,A600,A2000) rev 40.63 (512k) / "{roms}/Kickstart v3.1 (A600).rom"
ROM_015=KS ROM v3.1 (A1200) rev 40.68 (512k) [391773-01/391774-01] / "{roms}/Kickstart v3.1 (A1200).rom"
ROM_062=:SuperIV
ROM_066=:AROS
"""
DB_HEAD = '{"schema_version": 2, "source": "x", "generated": "2026-11-04T15:49:50Z", "upstream_timestamp": "y", "game_count": 11255, "games": []}'


@requires_posix
class RomStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        (self.home / "ROMs").mkdir(parents=True)
        self.ini = self.root / "amiberry.ini"
        self.exe = make_fake(self.root)
        env = mock.patch.dict(os.environ, {"FAKE_INI": str(self.ini)})
        env.start()
        self.addCleanup(env.stop)

    def write_ini(self, text=INI):
        self.ini.write_text(text.format(roms=self.home / "ROMs"))

    def test_the_ini_is_found_through_dump_paths(self):
        self.assertEqual(amiberry.settings_ini(self.exe, self.home), self.ini)
        with mock.patch.dict(os.environ, {"FAKE_INI": ""}):
            self.assertIsNone(amiberry.settings_ini(self.exe, self.home))
        self.assertIsNone(amiberry.settings_ini(self.root / "missing", self.home))

    def test_detected_roms_are_read_and_builtin_replacements_left_out(self):
        self.write_ini()
        found = amiberry.detected_roms(self.ini)
        self.assertEqual([name for _, name in [(d, p.name) for d, p in found]],
                         ["Kickstart v1.2.rom", "Kickstart v3.1 (A600).rom", "Kickstart v3.1 (A1200).rom"])
        self.assertTrue(found[0][0].startswith("KS ROM v1.2"))
        self.assertEqual(amiberry.detected_roms(self.root / "none.ini"), [])
        self.ini.write_text("[Amiberry]\nA=1\n")
        self.assertEqual(amiberry.detected_roms(self.ini), [])

    def test_the_report_lists_known_roms_and_the_files_amiberry_ignored(self):
        self.write_ini()
        for name in ("Kickstart v1.2.rom", "Kickstart v3.1 (A600).rom", "Kickstart v3.1 (A1200).rom", "Bad dump.rom"):
            (self.home / "ROMs" / name).write_bytes(b"x")
        report = amiberry.rom_report(self.exe, self.home)
        self.assertTrue(report.scanned)
        self.assertEqual([k[1] for k in report.known], ["Kickstart v1.2.rom", "Kickstart v3.1 (A600).rom", "Kickstart v3.1 (A1200).rom"])
        self.assertEqual(report.unknown, ["Bad dump.rom"])
        self.assertTrue(report.has_a600)
        self.assertTrue(all(exists for _, _, exists in report.known))               # the three listed files are on disk

    def test_a_listed_rom_whose_file_is_gone_is_marked(self):
        self.write_ini()
        (self.home / "ROMs" / "Kickstart v1.2.rom").write_bytes(b"x")
        known = amiberry.rom_report(self.exe, self.home).known
        self.assertEqual([exists for _, _, exists in known], [True, False, False])

    def test_no_a600_when_only_the_a1200_rom_is_known(self):
        self.write_ini("[DetectedROMs]\nROM_015=KS ROM v3.1 (A1200) rev 40.68 (512k) / \"{roms}/Kickstart v3.1 (A1200).rom\"\n")
        (self.home / "ROMs" / "Kickstart v3.1 (A1200).rom").write_bytes(b"x")
        self.assertFalse(amiberry.rom_report(self.exe, self.home).has_a600)

    def test_before_amiberry_has_ever_run_nothing_is_claimed(self):
        (self.home / "ROMs" / "some.rom").write_bytes(b"x")
        report = amiberry.rom_report(self.exe, self.home)                      # no ini yet
        self.assertEqual((report.scanned, report.known, report.unknown), (False, [], []))

    def test_database_info_reads_the_header_only(self):
        self.assertIsNone(amiberry.database_info(self.home))
        db = self.home / "WHDBoot" / "game-data" / "whdload_db.json"
        db.parent.mkdir(parents=True)
        db.write_text(DB_HEAD)
        self.assertEqual(amiberry.database_info(self.home), {"games": 11255, "generated": "2026-11-04"})
        db.write_text("not json at all")
        self.assertIsNone(amiberry.database_info(self.home))


@requires_posix
class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.exe = make_fake(self.root)

    def test_an_update_succeeds_when_whdload_and_the_database_are_there_afterwards(self):
        with mock.patch.dict(os.environ, {"FAKE_DB": DB_HEAD}):
            ok, output = amiberry.update_whdboot(self.exe, self.home)
        self.assertTrue(ok)
        self.assertEqual(amiberry.database_info(self.home)["games"], 11255)

    def test_a_failed_download_is_reported_with_amiberrys_own_words(self):
        with mock.patch.dict(os.environ, {"FAKE_FAIL": "1"}):
            ok, output = amiberry.update_whdboot(self.exe, self.home)
        self.assertFalse(ok)
        self.assertIn("no network", output)

    def test_no_database_after_the_download_counts_as_a_failure(self):
        ok, _ = amiberry.update_whdboot(self.exe, self.home)                    # the fake wrote WHDLoad but no database
        self.assertFalse(ok)


class ResetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "WHDLoadSuite"
        self.home = self.data / "Amiberry"
        (self.home / "WHDBoot").mkdir(parents=True)
        (self.home / "WHDBoot" / "WHDLoad").write_bytes(b"x" * 1000)
        (self.home / "ROMs").mkdir()
        (self.home / "ROMs" / "k.rom").write_bytes(b"y" * 500)
        (self.data / "Games" / "Alien").mkdir(parents=True)
        (self.data / "Games" / "Alien" / "save.dat").write_text("score")

    def test_folder_size(self):
        self.assertEqual(amiberry.folder_size(self.home), 1500)
        self.assertEqual(amiberry.folder_size(self.data / "missing"), 0)

    def test_reset_deletes_the_home_but_keeps_saved_games(self):
        self.assertEqual(amiberry.reset_home(self.home), 1500)
        self.assertFalse(self.home.exists())
        self.assertEqual((self.data / "Games" / "Alien" / "save.dat").read_text(), "score")
        self.assertEqual(amiberry.reset_home(self.home), 0)             # nothing left: not an error

    def test_delete_games_removes_the_executables_copies_but_keeps_the_amiberry_home(self):
        games = self.data / "Games"
        self.assertEqual(amiberry.delete_games(games), 5)
        self.assertFalse(games.exists())
        self.assertTrue((self.home / "WHDBoot" / "WHDLoad").is_file())
        self.assertEqual(amiberry.delete_games(games), 0)                  # nothing left: not an error

    def test_delete_games_only_deletes_the_apps_games_folder(self):
        for wrong in (self.data, self.home, Path(self.tmp.name), self.data / "Games" / "Alien"):
            with self.assertRaises(ValueError):
                amiberry.delete_games(wrong)
        self.assertTrue((self.data / "Games" / "Alien" / "save.dat").is_file())

    @requires_posix
    def test_delete_games_is_refused_while_a_game_is_running(self):
        exe = Path(self.tmp.name) / "slow"
        exe.write_text("#!/bin/sh\nsleep 30\n")
        exe.chmod(0o755)
        proc = amiberry._start([str(exe)], self.home)
        try:
            with self.assertRaisesRegex(RuntimeError, "running game"):
                amiberry.delete_games(self.data / "Games")
            self.assertTrue((self.data / "Games" / "Alien" / "save.dat").is_file())
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_reset_only_deletes_a_folder_that_is_the_apps_amiberry_home(self):
        for wrong in (self.data, self.data / "Games", Path(self.tmp.name), self.data / "Games" / "Alien"):
            with self.assertRaises(ValueError):
                amiberry.reset_home(wrong)
        self.assertTrue((self.home / "WHDBoot" / "WHDLoad").is_file())
        self.assertTrue((self.data / "Games" / "Alien" / "save.dat").is_file())

    @requires_posix
    def test_reset_is_refused_while_a_game_is_running(self):
        exe = Path(self.tmp.name) / "slow"
        exe.write_text("#!/bin/sh\nsleep 30\n")
        exe.chmod(0o755)
        proc = amiberry._start([str(exe)], self.home)
        try:
            self.assertTrue(amiberry.running())
            with self.assertRaisesRegex(RuntimeError, "running game"):
                amiberry.reset_home(self.home)
            self.assertTrue(self.home.exists())
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        self.assertFalse(amiberry.running())
        amiberry.reset_home(self.home)                                    # fine once it has closed
        self.assertFalse(self.home.exists())

    def test_open_folder_creates_it_and_asks_the_system_to_show_it(self):
        target = Path(self.tmp.name) / "new" / "folder"
        with mock.patch.object(amiberry.subprocess, "Popen") as popen:
            amiberry.open_folder(target)
        self.assertTrue(target.is_dir())
        self.assertEqual(popen.call_args[0][0][-1], str(target))


if __name__ == "__main__":
    unittest.main()
