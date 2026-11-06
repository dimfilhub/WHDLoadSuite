#!/usr/bin/env python3
"""WHDLoadSuite main window: one window with four tabs. Each tab lives in its own folder under tabs/; this
file only builds the window, the menu and the styles, and connects the tabs to each other."""
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from common.about_dialog import AboutDialog
from common.help_dialog import HelpDialog
from common.paths import PROJECT_ROOT
from common.theme import apply_app_theme
from tabs.builder.tab import APP_NAME as BUILDER_NAME, BuilderTab
from tabs.browser.tab import APP_NAME as BROWSER_NAME, BrowserTab
from tabs.downloader.tab import APP_NAME as DOWNLOADER_NAME, DownloaderTab
from tabs.settings.settings import KIND, AppSettings
from tabs.settings.window import SettingsWindow
from tabs.hdcommander.tab import APP_NAME as HDCOMMANDER_NAME, TAB_LABEL as HDCOMMANDER_LABEL, HdCommanderTab

APP_NAME = "WHDLoadSuite"
VERSION = "1.0.0"
HERE = PROJECT_ROOT
ABOUT_TEXT = ("WHDLoadSuite runs WHDLoad .lha game archives in Amiberry and turns them into standalone "
              "executables. The window has four tabs:\n\n"
              "Browser: search and filter the archives in the downloads folder by language, platform, "
              "memory, media and more.\n\n"
              "Builder: test-launch and build standalone executables of the games found in the downloads folder.\n\n"
              "Downloader: browse the Retroplay WHDLoad Packs on the grandis.nu FTP server and download "
              "them into the downloads folder.\n\n"
              "HDCommander (experimental): copy files and install WHDLoad games into an Amiga hard disk image "
              "(.hdf), with a dual-pane file manager. It is still being tested: work on copies of your images.\n\n"
              "Settings menu: the folders used by the tabs, in separate windows for the Browser, the Builder and "
              "Amiberry.\n\n"
              "WHDLoadSuite includes no games or Kickstart ROMs. You are responsible for having the right to use "
              "and share them; the author is not responsible for any distribution of copyrighted material by "
              "users, or for illegally obtained material used with the app. See Help > Legal notice.\n\n"
              "@Dimfil 2026\n\n"
              "The WHDLoad packs are created by Retroplay (EAB forum) and everyone who builds WHDLoad packs. "
              "All credit goes to Retroplay and to all the people creating WHDLoad packs.")


def show_about(parent):
    AboutDialog(parent, APP_NAME, VERSION, ABOUT_TEXT)


HELP_PAGES = {BROWSER_NAME: "browser", BUILDER_NAME: "builder", DOWNLOADER_NAME: "downloader",
              HDCOMMANDER_LABEL: "hdcommander"}      # the Help page of each tab, shown by F1


def show_help(parent, tab_name: str | None = None):
    """Open the Help window, at the page of the tab you are on if `tab_name` is given."""
    HelpDialog.show(parent, APP_NAME, start=HELP_PAGES.get(tab_name or ""))


def main():
    root = tk.Tk()
    root.title(f"{APP_NAME} v{VERSION} – WHDLoad {KIND} Creator  ©  DimFil 2026")
    root.minsize(640, 580)
    apply_app_theme(root)

    # One window with four tabs. The downloader's download folder is the shared downloads folder (one variable).
    def on_downloads_changed():
        app.refresh()
        browser.reload()
        hdcommander.downloads_changed()

    def send_to_builder(paths):
        skipped = app.select_paths(paths)
        if skipped:
            messagebox.showinfo("Send to Builder", f"{skipped} file(s) skipped: only .lha archives can be launched or built.")

    def on_tab_changed(_e):
        if tabs.select() == str(app):
            app.refresh()
        elif tabs.select() == str(browser):
            browser.reload()
        elif tabs.select() == str(hdcommander):
            hdcommander.refresh()

    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True)
    settings = AppSettings(root)
    app = BuilderTab(tabs, settings)
    tabs.add(app, text=BUILDER_NAME)
    downloader = DownloaderTab(tabs, app.downloads, on_destination_change=app.downloader_folder_changed,
                               on_quit=app.quit_app, on_download_done=lambda: on_downloads_changed())
    tabs.add(downloader, text=DOWNLOADER_NAME)
    browser = BrowserTab(tabs, app.downloads, (app.work_dir, app.whdload_dir, app.exe_dir), on_quit=downloader.quit_app, on_send=send_to_builder,
                         ticked=app.ticked_paths, settings=settings)
    hdcommander = HdCommanderTab(tabs, app.downloads, on_quit=downloader.quit_app,
                                 kickstart_source=lambda: Path(app.work_dir.get()) / "Template_WHDLoad" / "Devs" / "Kickstarts",
                                 emulator=lambda: (settings.amiberry_exe(), settings.kickstarts_dir(), settings.amiberry_options()))
    settings.on_downloads_changed = on_downloads_changed
    settings.on_folders_changed = app.refresh_prepared
    # Builder is built first (the others use its folder variables); then put the tabs in display order
    tabs.insert(0, browser, text=BROWSER_NAME)   # Builder and Downloader follow it in the order they were added
    tabs.add(hdcommander, text=HDCOMMANDER_LABEL)
    tabs.select(browser)  # the app starts on the Browser tab
    root.update_idletasks()
    root.minsize(max(640, browser.min_width()), 580)   # narrower and the Browser's buttons would be squeezed away

    tabs.bind("<<NotebookTabChanged>>", on_tab_changed)

    menubar = tk.Menu(root, tearoff=False)
    settings_menu = tk.Menu(menubar, tearoff=False)
    for section, label in (("browser", "Browser…"), ("builder", "Builder…"), ("amiberry", "Amiberry…")):
        settings_menu.add_command(label=label, command=lambda s=section: SettingsWindow.show(root, settings, s))
    menubar.add_cascade(label="Settings", menu=settings_menu)
    help_menu = tk.Menu(menubar, name="help", tearoff=False)
    help_menu.add_command(label=f"{APP_NAME} Help", accelerator="F1",
                          command=lambda: show_help(root, tabs.tab(tabs.select(), "text")))
    help_menu.add_command(label=f"About {APP_NAME}…", command=lambda: show_about(root))
    menubar.add_cascade(label="Help", menu=help_menu)
    root.config(menu=menubar)
    root.bind("<F1>", lambda _e: show_help(root, tabs.tab(tabs.select(), "text")))
    root.protocol("WM_DELETE_WINDOW", downloader.quit_app)  # confirms if an FTP session is open
    root.mainloop()


if __name__ == "__main__":
    main()
