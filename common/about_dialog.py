import tkinter as tk
import webbrowser
from tkinter import ttk

from .dialogs import center
from .theme import LINK_COLOR, WB_BLUE

SOURCES_URL = "https://eab.abime.net/showthread.php?t=61028"
ABOUT_TEXT = ("Downloader: a browser and downloader for the Retroplay WHDLoad Packs "
              "on the grandis.nu FTP server.\n\n"
              "@Dimfil 2026\n\n"
              "The WHDLoad packs are created by Retroplay (EAB forum) and everyone who builds WHDLoad packs. "
              "All credit goes to Retroplay and to all the people creating WHDLoad packs.")


class AboutDialog(tk.Toplevel):
    def __init__(self, parent, name, version, text=None):
        super().__init__(parent)
        self.withdraw()              # hidden until built and centred
        self.title(f"About {name}")
        self.configure(background=WB_BLUE)
        self.transient(parent)
        self.resizable(False, False)

        body = ttk.Frame(self, padding=20)
        body.pack()
        ttk.Label(body, text=name, font=("Helvetica", 16, "bold")).pack()
        ttk.Label(body, text=f"Version {version}").pack(pady=(0, 10))
        ttk.Label(body, text=text or ABOUT_TEXT, wraplength=420, justify="center").pack()
        link = ttk.Label(body, text=SOURCES_URL, foreground=LINK_COLOR, cursor="hand2")
        link.pack(pady=(4, 12))
        link.bind("<Button-1>", lambda _e: webbrowser.open(SOURCES_URL))
        ttk.Button(body, text="Close", command=self.destroy).pack()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.destroy())
        center(self, parent)
        self.deiconify()
        self.update()                # on screen now: a window must be viewable before it can grab the input
        try:
            self.grab_set()
        except tk.TclError:          # not viewable (a withdrawn parent): carry on without grabbing
            pass
