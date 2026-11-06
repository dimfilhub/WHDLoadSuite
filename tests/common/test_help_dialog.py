"""The Help window and the pages in help/."""
import gc
import re
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from common import help_dialog
from common.help_dialog import HelpDialog, load_contents, parse, read_page
from common.paths import PROJECT_ROOT

from tests.helpers import reset_root, shared_root

ROOT = shared_root()


def tearDownModule():
    reset_root()

HELP = PROJECT_ROOT / "help"

# The button and row names each page must explain; each is also checked against the code, so a renamed button
# makes this test fail until the page is updated.
LABELS = {
    "browser": (PROJECT_ROOT / "tabs/browser/tab.py",
                ["Search:", "Latest version only", "Only entries without ID", "Clear filters", "Refresh", "Clear selection",
                 "Review selection", "Launch in Amiberry", "Send to Builder", "Quit"]),
    "builder": (PROJECT_ROOT / "tabs/builder/tab.py",
                ["Select all", "Launch to test", "Clear Prepared", "Quit", "Clear selection", "Refresh list"]),
    "downloader": (PROJECT_ROOT / "tabs/downloader/widgets.py",
                   ["Connect", "Browse...", "Select all", "Download selected", "Cancel", "Filters…", "Quit",
                    "Use FTPS (TLS)"]),
    "filters": (PROJECT_ROOT / "tabs/downloader/filters.py",
                ["Search:", "Latest version only", "Only entries without ID", "Clear filters", "Apply", "Close"]),
    "hdcommander": (PROJECT_ROOT / "tabs/hdcommander/tab.py",
                    ["Open…", "New…", "Close", "Make bootable…", "Install BetterWB…", "Install WHDLoad…",
                     "Test in emulator", "Quit", "View (F3)", "Install Game (F4)", "Copy (F5)", "Move (F6)",
                     "MkDir (F7)", "Delete (F8)", "Refresh"]),
    "launch-screen": (PROJECT_ROOT / "common/launch_window.py",
                      ["Launch", "Cancel", "Use these choices from now on", "Show this screen when I launch a game"]),
}


class ParseTest(unittest.TestCase):
    def test_headings_paragraphs_and_lists(self):
        blocks = parse("# Title\n\nFirst line\nsecond line.\n\n## Part\n\n- one\n  continued\n  - nested\n1. numbered\n")
        self.assertEqual(blocks, [("h1", 0, "Title"), ("p", 0, "First line second line."), ("h2", 0, "Part"),
                                  ("li", 0, "one continued"), ("li", 1, "nested"), ("ol", 0, "1. numbered")])

    def test_notes_and_code_blocks(self):
        blocks = parse("> Tip one\n> goes on\n\n```\ncode  line\n  indented\n```\nafter\n")
        self.assertEqual(blocks, [("note", 0, "Tip one goes on"), ("code", 0, "code  line"), ("code", 0, "  indented"),
                                  ("p", 0, "after")])

    def test_a_list_ends_at_a_blank_line_and_a_new_paragraph_starts(self):
        self.assertEqual(parse("- a\n\ntext\n"), [("li", 0, "a"), ("p", 0, "text")])


class PagesTest(unittest.TestCase):
    """The real pages in help/."""

    def setUp(self):
        self.pages = load_contents(HELP)
        self.ids = {p.id for p in self.pages}

    def test_the_tree_has_every_page_once_and_each_file_exists(self):
        self.assertGreaterEqual(len(self.pages), 20)
        self.assertEqual(len(self.ids), len(self.pages))                      # no id twice
        for page in self.pages:
            self.assertTrue((HELP / page.file).is_file(), page.file)
        listed = {p.file for p in self.pages}
        self.assertEqual({f.name for f in HELP.glob("*.md")} - listed, set())  # no page left out of the tree

    def test_every_page_starts_with_its_title_and_every_link_leads_somewhere(self):
        for page in self.pages:
            text = read_page(page, HELP)
            self.assertTrue(text.startswith("# "), page.file)
            self.assertTrue(text.splitlines()[0][2:].startswith(page.title), page.file)     # "Welcome" -> "Welcome to …"
            for target in re.findall(r"\]\(help:([^)]+)\)", text):
                self.assertIn(target, self.ids, f"{page.file} links to a page that does not exist: {target}")

    def test_the_tab_pages_say_what_you_see_what_you_can_do_and_what_the_buttons_do(self):
        for page_id in ("browser", "builder", "downloader", "hdcommander", "launch-screen", "filters"):
            text = read_page(next(p for p in self.pages if p.id == page_id), HELP)
            for heading in ("## What you see", "## What you can do"):
                self.assertIn(heading, text, f"{page_id} lacks '{heading}'")
        for page_id in ("browser", "builder", "downloader", "hdcommander"):
            text = read_page(next(p for p in self.pages if p.id == page_id), HELP)
            self.assertIn("## Buttons and controls", text, page_id)

    def test_the_buttons_named_in_the_help_exist_and_are_explained(self):
        for page_id, (source, labels) in LABELS.items():
            code = source.read_text(encoding="utf-8")
            text = read_page(next(p for p in self.pages if p.id == page_id), HELP)
            for label in labels:
                self.assertIn(f'"{label}"', code, f"'{label}' is no longer in {source.name}: update the Help")
                self.assertIn(label.rstrip(":"), text, f"the {page_id} page does not mention '{label}'")

    def test_hdcommander_is_called_experimental_wherever_it_is_described(self):
        text = {p.id: read_page(p, HELP) for p in self.pages}
        titles = {p.id: p.title for p in self.pages}
        self.assertIn("experimental", titles["hdcommander"])
        for page_id in ("hdcommander", "hd-games", "hd-boot", "hd-whdload", "hd-sdcard", "welcome", "troubleshooting"):
            self.assertIn("xperimental", text[page_id], f"the {page_id} page does not say HDCommander is experimental")
        self.assertIn("work on a copy", text["hdcommander"].lower())

    def test_the_legal_notice_is_clear_and_is_pointed_to_from_where_it_matters(self):
        text = {p.id: read_page(p, HELP) for p in self.pages}
        legal = " ".join(text["legal"].split())
        for needed in ("not responsible", "no responsibility", "illegally obtained", "redistribution of copyrighted material",
                       "solely your responsibility", "Standalone executables", "Kickstart ROMs are copyrighted",
                       "not legal advice", "at your own risk"):
            self.assertIn(needed, legal, needed)
        for page_id in ("welcome", "executables", "kickstarts", "downloader", "about", "troubleshooting"):
            self.assertIn("(help:legal)", text[page_id], f"the {page_id} page does not point to the legal notice")
        readme = " ".join((PROJECT_ROOT / "README.md").read_text(encoding="utf-8").split())
        for needed in ("not responsible for any distribution of copyrighted games or ROMs", "illegally obtained",
                       "solely the user's responsibility", "Legal notice and responsibility"):
            self.assertIn(needed, readme, needed)

    def test_the_sd_card_page_gives_the_steps_and_the_warnings(self):
        text = " ".join(read_page(next(p for p in self.pages if p.id == "hd-sdcard"), HELP).split())
        for needed in ("balenaEtcher", "Win32DiskImager", "dd", "at least as big as the image", "4 GB",
                       "Kickstart 2.0 or newer", "erases it", "not tested on real hardware", "PCMCIA", "geometry",
                       "MiSTer", "PiStorm", "(help:legal)", "(help:hd-boot)"):
            self.assertIn(needed, text, needed)
        self.assertIn("(help:hd-sdcard)", read_page(next(p for p in self.pages if p.id == "hdcommander"), HELP))

    def test_the_folders_emulator_and_kickstart_pages_cover_the_essentials(self):
        text = {p.id: read_page(p, HELP) for p in self.pages}
        for needed in ("emulator/Kickstarts", "downloads", "Whdload", "Executables", "Template_WHDLoad", "Application Support",
                       "%APPDATA%", ".local/share", "Games", "Gamebase", ".whdloadsuite.json"):
            self.assertIn(needed, text["locations"], needed)
        for needed in ("emulator", "/Applications/Amiberry.app", "PATH", "Reset", "Amiberry data"):
            self.assertIn(needed, text["emulator"], needed)
        for needed in (".rom", "A1200", "kick34005.A500", "Devs/Kickstarts", "Kickstart ROMs"):
            self.assertIn(needed, text["kickstarts"], needed)


@unittest.skipIf(ROOT is None, "no display")
class HelpDialogTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(gc.collect)
        HelpDialog._open = None
        self.addCleanup(lambda: setattr(HelpDialog, "_open", None))

    def open(self, start=None, **kw):
        window = HelpDialog(ROOT, "WHDLoadSuite", start, **kw)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        return window

    def text_of(self, window):
        return window.text.get("1.0", "end")

    def test_it_opens_on_the_first_page_with_the_whole_tree(self):
        window = self.open()
        self.assertEqual(window.title(), "WHDLoadSuite Help")
        self.assertEqual(window.current(), "welcome")
        self.assertIn("Welcome to WHDLoadSuite", self.text_of(window))
        shown = set()

        def walk(item):
            shown.add(item)
            for child in window.tree.get_children(item):
                walk(child)
        walk("")
        self.assertEqual(shown - {""}, {p.id for p in window.pages})

    def test_it_can_open_on_a_given_page_and_shows_where_it_is_in_the_tree(self):
        window = self.open("kickstarts")
        self.assertEqual(window.current(), "kickstarts")
        self.assertIn("Kickstart ROMs", self.text_of(window))
        self.assertEqual(window.tree.selection(), ("kickstarts",))
        self.assertEqual(window.crumbs.get(), "Folders, emulator and Kickstarts  ›  Kickstart ROMs")
        self.assertEqual(self.open("nonsense").current(), "welcome")             # an unknown page: the first one

    def test_choosing_a_page_in_the_tree_shows_it(self):
        window = self.open()
        window.tree.selection_set("builder")
        window.update()
        self.assertEqual(window.current(), "builder")
        self.assertIn("Builder tab", self.text_of(window))

    def test_a_link_goes_to_that_page_and_back_and_forward_walk_through_the_visits(self):
        window = self.open("welcome")
        window._follow("help:emulator")
        window._follow("help:kickstarts")
        self.assertEqual(window.current(), "kickstarts")
        window.back()
        self.assertEqual(window.current(), "emulator")
        window.back()
        self.assertEqual(window.current(), "welcome")
        self.assertEqual(str(window.back_button.cget("state")), "disabled")      # nothing before the first page
        window.forward()
        window.forward()
        self.assertEqual(window.current(), "kickstarts")
        self.assertEqual(str(window.forward_button.cget("state")), "disabled")
        window.back()
        window._follow("help:browser")                                           # a new visit drops the "forward" ones
        self.assertEqual(str(window.forward_button.cget("state")), "disabled")

    def test_a_link_to_a_missing_page_is_ignored_and_web_links_open_the_browser(self):
        window = self.open("welcome")
        window._follow("help:nowhere")
        self.assertEqual(window.current(), "welcome")
        with mock.patch.object(help_dialog.webbrowser, "open") as opened:
            window._follow("https://example.com/x")
        opened.assert_called_once_with("https://example.com/x")

    def test_clicking_a_link_in_the_text_follows_it(self):
        window = self.open("welcome")
        window.update()
        names = [n for n in window.text.tag_names() if n.startswith("link:help:downloader")]
        self.assertTrue(names)
        index = window.text.tag_ranges(names[0])[0]
        window.text.see(index)
        window.lift()
        window.text.focus_force()                                          # Windows ignores synthetic events otherwise
        window.update()
        x, y, _w, _h = window.text.bbox(index)
        window.text.event_generate("<Enter>", x=x + 3, y=y + 3)
        window.text.event_generate("<Motion>", x=x + 3, y=y + 3)           # the pointer must be over the link first
        window.update()
        window.text.event_generate("<Button-1>", x=x + 3, y=y + 3)
        window.update()
        if window.current() != "downloader":
            # some window systems (Windows runners) drop synthetic pointer events: run the link's own binding instead
            script = window.text.tk.call(str(window.text), "tag", "bind", names[0], "<Button-1>")
            window.text.tk.eval(re.sub(r"%[#a-zA-Z]", "0", script))     # the event fields do not matter to the link
            window.update()
        self.assertEqual(window.current(), "downloader")

    def test_italics_and_numbers_are_shown_properly(self):
        window = self.open("builder")
        text = self.text_of(window)
        self.assertNotIn("*Archives", text)                              # *italic* marks are gone
        self.assertIn("Archives (select the ones to launch or build)", text)
        self.assertRegex(text, r"1\. Tick games\.")                       # numbered items keep their numbers
        self.assertTrue(window.text.tag_ranges("i"))

    def test_bold_text_can_hold_code_without_showing_the_marks(self):
        window = self.open("kickstarts")
        text = self.text_of(window)
        self.assertNotIn("**", text)
        self.assertNotIn("`", text)
        self.assertIn("emulator/Kickstarts", text)

    def test_every_page_of_the_help_can_be_shown(self):
        window = self.open()
        for page in window.pages:
            window.goto(page.id)
            text = self.text_of(window)
            self.assertGreater(len(text), 200, page.id)
            for mark in ("*", "`"):
                self.assertNotIn(mark, text, f"{page.id} shows a raw {mark}")      # no unconverted marks
            self.assertNotIn("](help:", text, page.id)

    def test_show_reuses_the_open_window_and_moves_it_to_the_page(self):
        first = HelpDialog.show(ROOT, "WHDLoadSuite", "browser")
        self.addCleanup(first.destroy)
        second = HelpDialog.show(ROOT, "WHDLoadSuite", "builder")
        self.assertIs(first, second)
        self.assertEqual(second.current(), "builder")

    def test_without_pages_it_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = self.open(folder=tmp)
            self.assertIn("No help pages were found", self.text_of(window))
            self.assertEqual(str(window.back_button.cget("state")), "disabled")


if __name__ == "__main__":
    unittest.main()
