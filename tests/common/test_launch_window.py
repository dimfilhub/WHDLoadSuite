"""The launch window shared by the app and the standalone executables."""
import gc
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from common import amiberry_runtime as rt
from common import launch_window

from tests.helpers import reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()


def make_png(path, size):
    from PIL import Image
    Image.new("RGB", size, (30, 120, 200)).save(path)
    return path


class FitSizeTest(unittest.TestCase):
    def test_small_pictures_are_enlarged_by_whole_numbers_and_big_ones_shrunk(self):
        self.assertEqual(launch_window.fit_size(320, 256, 640, 512), (640, 512, True))
        self.assertEqual(launch_window.fit_size(1000, 500, 640, 512), (640, 320, False))


@unittest.skipIf(ROOT is None, "no display")
class LaunchWindowTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_a_png_is_read_by_tk_itself_and_made_smaller_only_when_too_big(self):
        small = launch_window.load_png(ROOT, make_png(self.dir / "a.png", (640, 512)), 640, 512)
        self.assertEqual((small.width(), small.height()), (640, 512))
        big = launch_window.load_png(ROOT, make_png(self.dir / "b.png", (1280, 1024)), 640, 512)
        self.assertEqual((big.width(), big.height()), (640, 512))              # halved by a whole factor
        self.assertIsNone(launch_window.load_png(ROOT, self.dir / "gone.png", 640, 512))
        self.assertIsNone(launch_window.load_png(ROOT, None, 640, 512))
        (self.dir / "bad.png").write_bytes(b"not a picture")
        self.assertIsNone(launch_window.load_png(ROOT, self.dir / "bad.png", 640, 512))

    def window(self, **kw):
        w = launch_window.LaunchWindow(ROOT, "Alien_v1.0", rt.Options(), **kw)
        self.addCleanup(lambda: w.winfo_exists() and w.destroy())
        return w

    def texts(self, widget):
        out = [str(widget.cget("text"))] if widget.winfo_class() in ("TLabel", "Label", "TCheckbutton") else []
        for child in widget.winfo_children():
            out += self.texts(child)
        return out

    def test_without_the_switch_there_are_no_tick_boxes(self):
        texts = self.texts(self.window())
        self.assertFalse([t for t in texts if "from now on" in t or "Show this screen" in t])

    def test_with_the_switch_the_ticks_and_the_hint_show(self):
        texts = self.texts(self.window(show_again=True, hint="get it back here"))
        self.assertTrue([t for t in texts if "Use these choices from now on" in t])
        self.assertTrue([t for t in texts if t == "get it back here"])

    def test_launch_and_cancel_call_the_closing_hook(self):
        told = []

        class Hooked(launch_window.LaunchWindow):
            def finished(self, result):
                told.append(result)

        w = Hooked(ROOT, "Alien_v1.0", rt.Options(keyboard="a"))
        w.launch()
        w2 = Hooked(ROOT, "Alien_v1.0", rt.Options())
        w2.cancel()
        self.assertEqual(told, [rt.Options(keyboard="a"), None])

    def test_an_executable_runs_its_own_window_and_returns_the_choices(self):
        class Auto(launch_window.LaunchWindow):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.show_again.set(False)
                self.remember.set(True)
                combo, mapping = self.vars["keyboard"]
                combo.set(next(t for t, v in mapping.items() if v == "c"))
                self.after(50, self.launch)

        picture = make_png(self.dir / "p.png", (320, 256))
        with mock.patch.object(launch_window, "LaunchWindow", Auto):
            result = launch_window.run_for_bundle("Alien_v1.0", rt.Options(), str(picture), "screenshot")
        options, show, keep = result
        self.assertEqual((options.keyboard, show, keep), ("c", False, True))

    def test_an_executable_window_cancelled_returns_none(self):
        class Auto(launch_window.LaunchWindow):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.after(50, self.cancel)

        with mock.patch.object(launch_window, "LaunchWindow", Auto):
            self.assertEqual(launch_window.run_for_bundle("Alien_v1.0", rt.Options(), None)[0], None)


if __name__ == "__main__":
    unittest.main()
