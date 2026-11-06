import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from common import amiberry_runtime as rt
from tests.amiberry.fake import make_fake, recorded, requires_posix, write_db


class CommandTest(unittest.TestCase):
    def test_archive_command_uses_an_absolute_path_and_the_defaults(self):
        cmd = rt.archive_command("/x/amiberry", "game.lha")
        self.assertEqual(cmd[:2], ["/x/amiberry", "--rescan-roms"])
        self.assertEqual(cmd[-2], "--autoload")
        self.assertTrue(Path(cmd[-1]).is_absolute() and cmd[-1].endswith("game.lha"))
        self.assertIn("update_check=no", cmd)
        self.assertIn("default_controller1=kbd4", cmd)     # keyboard layout D for joystick 1 by default
        self.assertFalse([c for c in cmd if c.startswith("joyport")])   # WHDBooter would replace it

    def test_the_keyboard_layout_and_none(self):
        cmd = rt.archive_command("a", "g.lha", rt.Options(keyboard="b"))
        self.assertIn("default_controller1=kbd2", cmd)
        self.assertIn("joyport1=kbd3", rt.hdf_command("a", "/d/x.hdf", "/r/k.rom", rt.Options(keyboard="c")))
        none = rt.archive_command("a", "g.lha", rt.Options(keyboard=""))
        self.assertFalse([c for c in none if c.startswith(("joyport1", "default_controller1"))])

    def test_each_choice_becomes_its_amiberry_option(self):
        def opts(**kw):
            return rt.common_arguments(rt.Options(**kw), whdbooter=True)
        self.assertNotIn("default_fullscreen_mode=2", opts())                       # the defaults add nothing
        self.assertNotIn("default_line_mode=2", opts())
        self.assertNotIn("shader=1084", opts())
        self.assertFalse([a for a in opts() if "whd" in a])
        self.assertIn("default_fullscreen_mode=2", opts(window="fullscreen"))
        self.assertIn("default_line_mode=2", opts(look="scanlines"))
        self.assertNotIn("shader=1084", opts(look="scanlines"))
        crt = opts(look="crt")
        self.assertIn("default_line_mode=2", crt)
        self.assertIn("shader=1084", crt)                                           # scanlines plus the 1084 shader
        self.assertIn("default_whd_quit_on_exit=yes", opts(quit_on_exit=True))
        self.assertIn("default_whd_showsplash=no", opts(splash=False))

    def test_the_same_display_options_apply_to_drives_and_disk_images_but_not_the_whdbooter_ones(self):
        o = rt.Options(window="fullscreen", look="crt", quit_on_exit=True, splash=False)
        for cmd in (rt.drive_command("a", "/g/Game", "/r/k.rom", o), rt.hdf_command("a", "/d/x.hdf", "/r/k.rom", o)):
            self.assertIn("default_fullscreen_mode=2", cmd)
            self.assertIn("default_line_mode=2", cmd)
            self.assertIn("shader=1084", cmd)
            self.assertIn("joyport1=kbd4", cmd)
            self.assertFalse([c for c in cmd if "whd" in c])                        # WHDBooter is not involved

    def test_options_from_saved_values_are_tolerant(self):
        self.assertEqual(rt.Options.from_dict(None), rt.Options())
        self.assertEqual(rt.Options.from_dict({"keyboard": "B", "window": "fullscreen", "look": "crt",
                                               "quit_on_exit": True, "splash": False}),
                         rt.Options("b", "fullscreen", "crt", True, False))
        self.assertEqual(rt.Options.from_dict({"keyboard": ""}).keyboard, "")      # "none" is a real choice
        bad = rt.Options.from_dict({"keyboard": "z", "window": "huge", "look": "sepia", "unknown": 1})
        self.assertEqual(bad, rt.Options())                                         # everything invalid: the defaults

    def test_the_old_fullscreen_and_scanlines_flags_are_still_understood(self):
        old = rt.Options.from_dict({"keyboard": "d", "fullscreen": True, "scanlines": True})
        self.assertEqual((old.window, old.look), ("fullscreen", "scanlines"))

    def test_drive_command_mounts_the_drive_as_sys(self):
        cmd = rt.drive_command("a", "/g/Game", "/r/kick.rom")
        self.assertEqual(cmd[1:5], ["--model", "A1200", "-G", "-r"])
        self.assertIn("filesystem2=rw,DH0:SYS:%s,1" % Path("/g/Game").resolve(), cmd)
        self.assertIn("fastmem_size=8", cmd)
        self.assertIn("joyport1=kbd4", cmd)                # no WHDBooter here: the port is set directly

    def test_hdf_command_detects_the_rdb(self):
        cmd = rt.hdf_command("a", "/d/Disk.hdf", "/r/kick.rom")
        self.assertIn("hardfile2=rw,DH0:%s,0,0,0,512,0,,uae0" % Path("/d/Disk.hdf").resolve(), cmd)

    def test_a_comma_in_a_path_is_refused(self):
        with self.assertRaises(ValueError):
            rt.drive_command("a", "/g/Foo,Bar", "/r/k.rom")
        with self.assertRaises(ValueError):
            rt.hdf_command("a", "/d/a,b.hdf", "/r/k.rom")


@unittest.skipIf(os.name != "posix", "settings folders are moved through HOME and XDG_*")
class EnvironmentTest(unittest.TestCase):
    def test_amiberry_keeps_its_settings_file_inside_the_apps_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "WHDLoadSuite" / "Amiberry"
            env = rt.environment(home)
        self.assertEqual(env["AMIBERRY_HOME_DIR"], str(home))
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            self.assertTrue(Path(env[key]).is_relative_to(home), key)
        self.assertNotEqual(env["HOME"], os.environ.get("HOME"))       # the user's own settings are not used
        self.assertEqual(env["PATH"], os.environ["PATH"])              # the rest of the environment is kept


class SeedHomeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        (self.src / "tmp").mkdir(parents=True)
        (self.src / "WHDLoad").write_text("w")
        (self.src / "db.bak").write_text("b")
        (self.src / "tmp" / "junk").write_text("j")

    def test_copies_whdboot_without_scratch_files_and_roms_once(self):
        home = self.root / "home"
        rom = self.root / "kick.rom"
        rom.write_bytes(b"one")
        added = rt.seed_home(home, self.src, [rom])
        self.assertTrue(rt.has_whdload(home))
        self.assertFalse((home / "WHDBoot" / "tmp").exists())
        self.assertFalse((home / "WHDBoot" / "db.bak").exists())
        self.assertEqual((home / "ROMs" / "kick.rom").read_bytes(), b"one")
        self.assertEqual(len(added), 2)
        rom.write_bytes(b"two")                              # an existing ROM is never replaced
        (home / "WHDBoot" / "WHDLoad").write_text("mine")    # nor is an installed WHDLoad
        self.assertEqual(rt.seed_home(home, self.src, [rom]), [])
        self.assertEqual((home / "ROMs" / "kick.rom").read_bytes(), b"one")
        self.assertEqual((home / "WHDBoot" / "WHDLoad").read_text(), "mine")


class OverridesTest(unittest.TestCase):
    def test_shipped_file_lists_the_known_exceptions(self):
        o = rt.load_overrides()
        self.assertEqual(rt.mode_for("RocketAttack_v1.0", o), "drive")
        self.assertEqual(rt.mode_for("UpScope_v1.01_Arcadia", o), "drive")
        self.assertEqual(rt.mode_for("Rockford_v1.0", o), "autoload")
        self.assertEqual(rt.hardware_for("SuperSillySkidmarks_v2.2_CD", o), {"z3_ram": 16, "cpu_24bitaddressing": False})
        self.assertNotIn("_comment", o)

    def test_missing_or_broken_file_means_no_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "x.json"
            bad.write_text("{not json")
            self.assertEqual(rt.load_overrides(bad), {})
            self.assertEqual(rt.load_overrides(Path(tmp) / "missing.json"), {})

    def test_apply_hardware_patches_only_the_matching_game_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = write_db(home, [{"filename": "Skid", "hardware": {"port1": "joy"}},
                                   {"filename": "Other", "hardware": {}}])
            self.assertTrue(rt.apply_hardware(home, "Skid", {"z3_ram": 16}))
            games = {g["filename"]: g["hardware"] for g in json.loads(path.read_text())["games"]}
            self.assertEqual(games["Skid"], {"port1": "joy", "z3_ram": 16})
            self.assertEqual(games["Other"], {})
            self.assertFalse(rt.apply_hardware(home, "Skid", {"z3_ram": 16}))   # nothing left to change
            self.assertFalse(rt.apply_hardware(home, "Skid", {}))
            self.assertFalse(rt.apply_hardware(home, "Unknown", {"z3_ram": 16}))

    def test_apply_hardware_without_a_database_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(rt.apply_hardware(Path(tmp), "Skid", {"z3_ram": 16}))


class LaunchChoicesTest(unittest.TestCase):
    """What a standalone executable remembers about its launch screen, and how the screen is used."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.object(rt, "data_dir", lambda: self.root / "data")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.base = rt.Options(keyboard="d", quit_on_exit=True)
        self.manifest = {"stem": "Alien_v1.0", "launch": {"image": "launch.png", "kind": "screenshot"}}

    def shown(self, result):
        """Run choose_launch_options with a launch window that answers `result` = (Options|None, show, keep)."""
        from common import launch_window
        with mock.patch.object(launch_window, "run_for_bundle", return_value=result) as ask:
            return rt.choose_launch_options(self.root, self.manifest, self.base), ask

    def test_the_choices_are_remembered_per_game(self):
        rt.save_launch_prefs("Alien_v1.0", rt.Options(keyboard="a", window="fullscreen", look="crt"), True)
        self.assertEqual(rt.load_launch_prefs("Alien_v1.0")["options"],
                         {"keyboard": "a", "window": "fullscreen", "look": "crt"})
        rt.save_launch_prefs("Alien_v1.0", None, False)                      # only the switch changes
        prefs = rt.load_launch_prefs("Alien_v1.0")
        self.assertEqual((prefs["show"], prefs["options"]["keyboard"]), (False, "a"))
        self.assertEqual(rt.load_launch_prefs("Other"), {})

    def test_an_executable_without_a_launch_screen_just_starts(self):
        self.assertEqual(rt.choose_launch_options(self.root, {"stem": "Alien_v1.0"}, self.base), self.base)

    def test_the_screen_is_shown_and_its_choice_used(self):
        chosen = rt.Options(keyboard="b", window="fullscreen", look="scanlines")
        options, ask = self.shown((chosen, True, False))
        self.assertEqual(options, chosen)
        self.assertEqual(ask.call_args.args[0:2], ("Alien_v1.0", self.base))
        self.assertTrue(ask.call_args.args[2].endswith("launch.png"))
        self.assertEqual(rt.load_launch_prefs("Alien_v1.0"), {"show": True})   # not kept: only the switch is saved

    def test_keeping_the_choices_and_switching_the_screen_off(self):
        chosen = rt.Options(keyboard="c", window="windowed", look="crt")
        self.shown((chosen, False, True))
        prefs = rt.load_launch_prefs("Alien_v1.0")
        self.assertEqual((prefs["show"], prefs["options"]), (False, {"keyboard": "c", "window": "windowed", "look": "crt"}))
        options, ask = self.shown((None, True, False))                       # the screen is off now: not even asked
        ask.assert_not_called()
        self.assertEqual((options.keyboard, options.look, options.quit_on_exit), ("c", "crt", True))   # the kept ones win

    def test_cancelling_the_screen_cancels_the_start(self):
        options, _ = self.shown((None, True, False))
        self.assertIsNone(options)

    def test_without_tk_or_a_display_the_game_starts_as_built(self):
        from common import launch_window
        with mock.patch.object(launch_window, "run_for_bundle", side_effect=RuntimeError("no display")):
            self.assertEqual(rt.choose_launch_options(self.root, self.manifest, self.base), self.base)


@requires_posix
class RunBundleTest(unittest.TestCase):
    """What a standalone executable does when started, with a fake emulator."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        patcher = mock.patch.object(rt, "data_dir", lambda: self.data)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.args = self.root / "args.txt"
        env = mock.patch.dict(os.environ, {"FAKE_ARGS": str(self.args)})
        env.start()
        self.addCleanup(env.stop)
        self.bundle = self.root / "bundle"
        (self.bundle / "emulator" / "Fake").mkdir(parents=True)
        make_fake(self.bundle / "emulator" / "Fake", "amiberry")

    def manifest(self, **extra):
        data = {"name": "Alien_v1.0", "stem": "Alien_v1.0", "mode": "autoload", "exe": "Fake/amiberry",
                "options": {"keyboard": "d"}, "hardware": {}, "archive": "Alien_v1.0.lha", **extra}
        (self.bundle / "manifest.json").write_text(json.dumps(data))

    def test_autoload_runs_the_bundled_archive_in_the_shared_home(self):
        self.manifest(hardware={"z3_ram": 16})
        (self.bundle / "Alien_v1.0.lha").write_bytes(b"lha")
        write_db(self.bundle, [{"filename": "Alien_v1.0", "hardware": {}}])   # the seed carries the game database
        (self.bundle / "WHDBoot" / "WHDLoad").write_text("w")
        (self.bundle / "ROMs").mkdir()
        (self.bundle / "ROMs" / "k.rom").write_bytes(b"rom")
        self.assertEqual(rt.run_bundle(self.bundle), 0)
        args = recorded(self.args)
        self.assertEqual(args[-2], "--autoload")
        self.assertEqual(Path(args[-1]).resolve(), (self.bundle / "Alien_v1.0.lha").resolve())
        self.assertEqual(Path(recorded(Path(str(self.args) + ".home"))[0]), self.data / "Amiberry")
        self.assertTrue((self.data / "Amiberry" / "ROMs" / "k.rom").is_file())
        db = json.loads((self.data / "Amiberry" / rt.DB_FILE).read_text())
        self.assertEqual(db["games"][0]["hardware"], {"z3_ram": 16})

    def test_the_launch_screen_picks_the_options_and_cancelling_starts_nothing(self):
        self.manifest(launch={"image": None, "kind": ""})
        (self.bundle / "Alien_v1.0.lha").write_bytes(b"lha")
        (self.bundle / "WHDBoot").mkdir()
        (self.bundle / "WHDBoot" / "WHDLoad").write_text("w")
        with mock.patch("common.launch_window.run_for_bundle",
                        return_value=(rt.Options(keyboard="a", window="fullscreen"), True, False)):
            self.assertEqual(rt.run_bundle(self.bundle), 0)
        args = recorded(self.args)
        self.assertIn("default_controller1=kbd1", args)
        self.assertIn("default_fullscreen_mode=2", args)
        self.args.unlink()
        with mock.patch("common.launch_window.run_for_bundle", return_value=(None, True, False)):
            self.assertEqual(rt.run_bundle(self.bundle), 0)
        self.assertFalse(self.args.exists())                       # the emulator was not started

    def test_a_manifest_with_the_old_option_names_still_runs(self):
        self.manifest(options={"keyboard": "d", "fullscreen": True, "scanlines": False})
        (self.bundle / "Alien_v1.0.lha").write_bytes(b"lha")
        (self.bundle / "WHDBoot").mkdir()
        (self.bundle / "WHDBoot" / "WHDLoad").write_text("w")
        self.assertEqual(rt.run_bundle(self.bundle), 0)
        self.assertIn("default_fullscreen_mode=2", recorded(self.args))

    def test_drive_mode_keeps_a_writable_copy_that_survives_the_next_run(self):
        self.manifest(mode="drive")
        (self.bundle / "game" / "S").mkdir(parents=True)
        (self.bundle / "game" / "S" / "Startup-Sequence").write_text("orig")
        (self.bundle / "kick.rom").write_bytes(b"rom")
        self.assertEqual(rt.run_bundle(self.bundle), 0)
        game = self.data / "Games" / "Alien_v1.0"
        self.assertEqual((game / "S" / "Startup-Sequence").read_text(), "orig")
        self.assertIn(f"filesystem2=rw,DH0:SYS:{game.resolve()},1", recorded(self.args))
        (game / "save.dat").write_text("score")                    # a save made while playing
        self.assertEqual(rt.run_bundle(self.bundle), 0)
        self.assertEqual((game / "save.dat").read_text(), "score")  # not overwritten by a fresh copy


if __name__ == "__main__":
    unittest.main()
