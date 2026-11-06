"""Pictures from a GamebaseAmiga data folder: finding a game's screenshot or cover."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from common import gamebase

FAKE_UNAR = """#!/usr/bin/env python3
# a stand-in for unar: writes what the real one would for the two Gamebase archives
import sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("-o") + 1])
rest = [a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] != "-o")]
archive, patterns = rest[0], rest[1:]
if "fail" in archive:
    sys.stderr.write("broken archive\\n")
    sys.exit(1)
if archive.endswith("Screenshots.rar"):
    files = ["Screenshots/A/Alien.png", "Screenshots/Z/Zool.png"]
else:
    files = ["Extras/Cover Scans/A/Alien_Front.jpg"] + ([] if patterns else ["Extras/Cover Scans/A/Alien_Back.jpg"])
for f in files:
    (out / f).parent.mkdir(parents=True, exist_ok=True)
    (out / f).write_bytes(b"x")
"""


def make_folder(root: Path) -> Path:
    data = root / "GamebaseAmiga" / "data"
    for rel in ("screenshots/A/Alien_Breed.png", "screenshots/D/Dragons_Lair_(AGA)_1.png", "screenshots/Z/Zool.png",
                "extras/Cover Scans/A/Alien Breed_Front.jpg", "extras/Cover Scans/A/Alien Breed_Back.jpg",
                "extras/Cover Scans/Z/Zool_Front.jpg", "extras/Cover Scans/B/Bubble Bobble_Front.jpg"):
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return data


class GamebaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = make_folder(Path(self.tmp.name))
        patch = mock.patch.object(gamebase, "extracted_dir", lambda: Path(self.tmp.name) / "no-app-data" / "Gamebase")
        patch.start()                       # never the real folder in the user's application data
        self.addCleanup(patch.stop)
        self.addCleanup(gamebase.forget)
        gamebase.forget()
        self.map = {"AlienBreed": {"s": "screenshots/A/Alien_Breed.png", "c": "extras/Cover Scans/A/Alien Breed_Front.jpg"},
                    "BubbleBobble": {"c": "extras/Cover Scans/B/Bubble Bobble_Front.jpg"},
                    "Missing": {"s": "screenshots/Q/Nothing.png"}}
        self.lib = gamebase.Library(self.data)

    def test_the_folder_is_the_data_folder_or_the_project_that_holds_it(self):
        self.assertEqual(gamebase.resolve_root(self.data), self.data)
        self.assertEqual(gamebase.resolve_root(self.data.parent), self.data)
        self.assertIsNone(gamebase.resolve_root(self.tmp.name))
        self.assertIsNone(gamebase.resolve_root(""))
        self.assertIsNone(gamebase.library(self.tmp.name))

    def test_the_folder_is_described_by_what_it_holds(self):
        self.assertEqual(self.lib.describe(), "3 screenshots and 4 cover scans")

    def test_a_game_in_the_map_gets_its_screenshot_then_its_cover(self):
        found = self.lib.find("AlienBreed_v1.2", games=self.map)            # a version the map does not list
        self.assertEqual((found[0].name, found[1]), ("Alien_Breed.png", "screenshot"))
        self.assertEqual(self.lib.find("AlienBreed", "cover", self.map)[0].name, "Alien Breed_Front.jpg")
        self.assertEqual(self.lib.find("BubbleBobble_v1.0", "best", self.map)[1], "cover")     # no screenshot: the cover
        self.assertIsNone(self.lib.find("BubbleBobble_v1.0", "screenshot", self.map))

    def test_a_mapped_file_that_is_not_on_disk_is_not_a_picture(self):
        self.assertIsNone(self.lib.find("Missing", games=self.map))

    def test_names_are_compared_without_case_or_unicode_form(self):
        lib = gamebase.Library(self.data)
        found = lib.find("alienbreed", games={"ALIENBREED": {"s": "SCREENSHOTS/a/ALIEN_BREED.PNG"}})
        self.assertEqual(found[0].name, "Alien_Breed.png")

    def test_a_game_not_in_the_map_is_found_by_its_picture_file_name(self):
        self.assertEqual(self.lib.find("Zool_v1.0", games={})[0].name, "Zool.png")                  # screenshot
        self.assertEqual(self.lib.find("DragonsLair_v1.1_AGA", games={})[0].name, "Dragons_Lair_(AGA)_1.png")
        self.assertEqual(self.lib.find("Zool", "cover", {})[0].name, "Zool_Front.jpg")
        self.assertIsNone(self.lib.find("Nothing_v1.0", games={}))

    def test_find_image_uses_the_folder_the_user_chose(self):
        self.assertEqual(gamebase.find_image(str(self.data), "Zool_v1.0")[0].name, "Zool.png")
        self.assertIsNone(gamebase.find_image("", "Zool_v1.0"))

    def test_the_original_folder_layout_is_understood_too(self):
        raw = Path(self.tmp.name) / "raw"
        for rel in ("Screenshots/Z/Zool.png", "Extras/Cover Scans/Z/Zool_Front.jpg"):
            (raw / rel).parent.mkdir(parents=True, exist_ok=True)
            (raw / rel).write_bytes(b"x")
        self.assertEqual(gamebase.resolve_root(raw), raw)
        self.assertEqual(gamebase.Library(raw).find("Zool_v1.0", games={})[0].name, "Zool.png")

    def test_the_real_map_is_well_formed(self):
        games = gamebase.load_map()
        self.assertGreater(len(games), 2000)
        for entry in list(games.values())[:200]:
            self.assertTrue(set(entry) <= {"s", "c"} and entry)
            self.assertTrue(all(v.startswith(("screenshots/", "extras/Cover Scans/")) for v in entry.values()))


@unittest.skipIf(os.name == "nt", "the stand-in unar is a script")
class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "Gamebase_Amiga_v23"
        self.source.mkdir()
        for name in ("Screenshots.rar", "Extras.rar"):
            (self.source / name).write_bytes(b"rar")
        self.unar = self.root / "unar"
        self.unar.write_text(FAKE_UNAR)
        self.unar.chmod(self.unar.stat().st_mode | stat.S_IEXEC)
        self.dest = self.root / "app" / "Gamebase"
        patch = mock.patch.object(gamebase, "extracted_dir", lambda: self.root / "no-app-data" / "Gamebase")
        patch.start()                       # extract() is given self.dest; the default must not be the real folder
        self.addCleanup(patch.stop)
        self.addCleanup(gamebase.forget)

    def run_extract(self, **kw):
        return gamebase.extract(self.source, self.dest, unar=str(self.unar), lsar="", **kw)

    def test_the_source_archives_are_found_whatever_the_case(self):
        (self.source / "Extras.rar").rename(self.source / "EXTRAS.RAR")
        self.assertEqual(sorted(gamebase.source_archives(self.source)), ["extras", "screenshots"])
        self.assertEqual(gamebase.source_archives(self.root), {})
        self.assertEqual(gamebase.source_archives(""), {})

    def test_extracting_unpacks_the_screenshots_and_only_the_front_covers(self):
        told = []
        done = self.run_extract(progress=told.append)
        self.assertIn("2 screenshots and 1 cover scans", done)
        self.assertTrue((self.dest / "Screenshots" / "A" / "Alien.png").is_file())
        self.assertTrue((self.dest / "Extras" / "Cover Scans" / "A" / "Alien_Front.jpg").is_file())
        self.assertFalse((self.dest / "Extras" / "Cover Scans" / "A" / "Alien_Back.jpg").exists())    # asked for fronts only
        self.assertFalse(list(self.dest.parent.glob("*.extracting")))                                  # nothing left over

    def test_the_extracted_pictures_are_used_for_the_source_folder(self):
        self.assertIsNone(gamebase.resolve_root(self.source))                  # not extracted yet
        self.run_extract()
        with mock.patch.object(gamebase, "extracted_dir", lambda: self.dest):
            self.assertEqual(gamebase.resolve_root(self.source), self.dest)
            self.assertEqual(gamebase.find_image(str(self.source), "Zool_v1.0")[0].name, "Zool.png")

    def test_extracting_again_replaces_the_earlier_pictures(self):
        (self.dest / "Screenshots").mkdir(parents=True)
        (self.dest / "Screenshots" / "Old.png").write_bytes(b"x")
        self.run_extract()
        self.assertFalse((self.dest / "Screenshots" / "Old.png").exists())
        self.assertTrue((self.dest / "Screenshots" / "Z" / "Zool.png").is_file())

    def test_the_extracted_pictures_can_be_deleted_and_nothing_else(self):
        self.run_extract()
        with mock.patch.object(gamebase, "extracted_dir", lambda: self.dest):
            self.assertGreater(gamebase.extracted_size(), 0)
            freed = gamebase.delete_extracted()
            self.assertEqual(freed, 2 + 1)                                 # the three one-byte files
            self.assertFalse(self.dest.exists())
            self.assertTrue((self.source / "Screenshots.rar").is_file())    # the source is untouched
            self.assertEqual((gamebase.extracted_size(), gamebase.delete_extracted()), (0, 0))   # nothing left: no error

    def test_a_failing_unar_is_reported_and_leaves_nothing_behind(self):
        bad = self.root / "bad"
        bad.mkdir()
        (bad / "Screenshots.rar").write_bytes(b"x")
        fail = self.root / "unar_fail"
        fail.write_text("#!/bin/sh\necho 'broken archive' >&2\nexit 1\n")
        fail.chmod(fail.stat().st_mode | stat.S_IEXEC)
        with self.assertRaisesRegex(gamebase.ExtractError, "Screenshots.rar.*broken archive"):
            gamebase.extract(bad, self.dest, unar=str(fail), lsar="")
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.dest.parent.glob("*.extracting")))

    def test_it_explains_a_missing_unar_and_a_wrong_folder(self):
        with mock.patch.object(gamebase, "find_tool", lambda _name: None):
            with self.assertRaisesRegex(gamebase.ExtractError, "unar not found"):
                gamebase.extract(self.source, self.dest)
        with self.assertRaisesRegex(gamebase.ExtractError, "not found in that folder"):
            gamebase.extract(self.root, self.dest, unar=str(self.unar))

    def test_it_refuses_when_the_disk_is_nearly_full(self):
        with mock.patch.object(gamebase.shutil, "disk_usage", return_value=SimpleNamespace(free=1024)):
            with self.assertRaisesRegex(gamebase.ExtractError, "Not enough free space"):
                self.run_extract()


class OtherSystemsTest(unittest.TestCase):
    """What differs on Windows and Linux: where unar is looked for, and the console window."""

    def test_unar_is_looked_for_on_the_path_then_in_the_usual_places(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "unar").write_text("x")
            (folder / "unar").chmod(0o755)
            with mock.patch.object(gamebase.shutil, "which", return_value="/on/path/unar"):
                self.assertEqual(gamebase.find_tool("unar"), "/on/path/unar")
            with mock.patch.object(gamebase.shutil, "which", return_value=None), \
                    mock.patch.object(gamebase, "tool_folders", lambda: [Path(tmp, "nothing"), folder]):
                self.assertEqual(gamebase.find_tool("unar"), str(folder / "unar"))
                self.assertIsNone(gamebase.find_tool("lsar"))

    def test_on_windows_unar_exe_is_found_in_program_files_or_next_to_the_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "unar"
            folder.mkdir()
            (folder / "unar.exe").write_text("x")
            (folder / "unar.exe").chmod(0o755)                     # Windows has no execute bit; this system does
            with mock.patch.object(gamebase.sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"ProgramFiles": tmp}), \
                    mock.patch.object(gamebase.shutil, "which", return_value=None):
                self.assertIn(folder, gamebase.tool_folders())
                self.assertEqual(Path(gamebase.find_tool("unar")), folder / "unar.exe")
            with mock.patch.object(gamebase.sys, "platform", "linux"):
                self.assertNotIn(folder, gamebase.tool_folders())
                self.assertIn(gamebase.PROJECT_ROOT / "tools", gamebase.tool_folders())

    def test_no_console_window_is_asked_for_except_on_windows(self):
        with mock.patch.object(gamebase.sys, "platform", "linux"):
            self.assertEqual(gamebase._no_console(), {})
        with mock.patch.object(gamebase.sys, "platform", "win32"), \
                mock.patch.object(gamebase.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True):
            self.assertEqual(gamebase._no_console(), {"creationflags": 0x08000000})

    def test_the_folders_are_found_whatever_their_case_as_on_linux(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SCREENSHOTS" / "Z").mkdir(parents=True)
            (root / "SCREENSHOTS" / "Z" / "Zool.png").write_bytes(b"x")
            (root / "extras" / "COVER SCANS" / "Z").mkdir(parents=True)
            (root / "extras" / "COVER SCANS" / "Z" / "Zool_Front.jpg").write_bytes(b"x")
            lib = gamebase.Library(root)
            self.assertEqual((lib.screenshots, lib.covers), (1, 1))
            self.assertEqual(lib.find("Zool", games={"Zool": {"s": "screenshots/z/zool.PNG"}})[0].name, "Zool.png")


if __name__ == "__main__":
    unittest.main()
