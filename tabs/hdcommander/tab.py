"""HDCommander tab for the Tkinter main window: host files (left) and an .hdf image (right).

This tab is EXPERIMENTAL: it is labelled so in the window, in the Help and in the README. Keep that wording in step
with EXPERIMENTAL_NOTICE below."""
import os
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, ttk

from common import amiberry, dialogs, lha
from common.dialogs import show_text
from common.settings import Settings

from common.paths import EMULATOR_DIR

from . import betterwb, transfer, whdinstall, workbench
from .browse import HdfLocation, HostLocation, human, sorted_entries
from .volume import HdfError, HdfVolume, UnsupportedFileSystem

APP_NAME = "HDCommander"
TAB_LABEL = f"{APP_NAME} (experimental)"           # what the tab is called in the window
EXPERIMENTAL_NOTICE = ("EXPERIMENTAL: HDCommander is still being tested and may have bugs. It writes into your .hdf "
                       "images directly, so work on a copy and keep a backup of any image you care about.")
SETTING_IMAGE = "hdcommander_image"
SETTING_BETTERWB = "hdcommander_betterwb_disks"        # the folder with the BetterWB floppies, remembered
SETTING_DISKS = "hdcommander_workbench_disks"      # the folder with the Workbench floppies, remembered
GERUND = {"Install": "Installing", "Copy": "Copying", "Move": "Moving", "Install WHDLoad": "Installing WHDLoad", "Install Workbench": "Installing Workbench", "Install BetterWB": "Installing BetterWB",
          "Install Kickstarts": "Copying Kickstarts"}
MAX_IMAGE_MB = 4000          # Kickstart 3.1 on real hardware wants partitions under ~4 GB


def _short(location, limit=44):
    """A long path for a dialog: keep its tail."""
    return location if len(location) <= limit else "…" + location[-(limit - 1):]


class _Panel(ttk.Frame):
    """One file list with a header showing where it points."""

    def __init__(self, master, tab, title):
        super().__init__(master)
        self.tab, self.title = tab, title
        self.loc = None
        self.entries = []
        self.header = ttk.Label(self, anchor="w", padding=(6, 2), style="Panel.TLabel")
        self.header.pack(fill="x")
        self.header.bind("<Button-1>", lambda _e: self.activate())   # click the bar to pick this pane
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("size", "info"), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("info", text="Info")
        self.tree.column("#0", width=230, stretch=True)
        self.tree.column("size", width=70, anchor="e", stretch=False)
        self.tree.column("info", width=90, stretch=False)
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for seq in ("<Return>", "<Double-1>"):
            self.tree.bind(seq, lambda _e: self.open_current())
        self.tree.bind("<BackSpace>", lambda _e: self.up())
        self.tree.bind("<FocusIn>", lambda _e: tab.set_active(self))
        self.tree.bind("<Button-1>", lambda _e: tab.set_active(self), add="+")
        for key, action in (("<F3>", tab.view), ("<F4>", tab.install_games), ("<F5>", tab.copy), ("<F6>", tab.move),
                            ("<F7>", tab.mkdir), ("<F8>", tab.delete)):
            self.tree.bind(key, lambda _e, a=action: a())

    def set_location(self, loc):
        self.loc = loc
        self.reload()

    def activate(self):
        self.tab.set_active(self)
        self.tree.focus_set()

    def set_active(self, active: bool):
        self.header.configure(style="PanelActive.TLabel" if active else "Panel.TLabel")

    def reload(self, keep=None):
        tree = self.tree
        tree.delete(*tree.get_children())
        self.entries = []
        if self.loc is None:
            self.header.configure(text=f"{self.title}: (no image open)")
            return
        loc = self.loc.location
        self.header.configure(text=f"{self.title}: " + (loc if len(loc) <= 60 else "..." + loc[-57:]))
        try:
            entries = self.loc.list_entries()
        except (HdfError, OSError) as exc:
            self.tab.error(str(exc))
            entries = []
        self.entries = sorted_entries(entries, self.loc.at_root())
        for i, e in enumerate(self.entries):
            name = f"[{e.name}]" if e.is_dir and e.name != ".." else e.name
            tree.insert("", "end", iid=str(i), text=name,
                        values=("<DIR>" if e.is_dir else human(e.size), e.info))
        if keep is not None:
            for i, e in enumerate(self.entries):
                if e.name == keep:
                    tree.selection_set(str(i))
                    tree.focus(str(i))
                    tree.see(str(i))
                    break

    def selected(self) -> list:
        return [self.entries[int(i)] for i in self.tree.selection() if int(i) < len(self.entries)]

    def names(self) -> list:
        return [e.name for e in self.selected() if e.name != ".."]

    def open_current(self):
        sel = self.selected() or ([self.entries[int(self.tree.focus())]] if self.tree.focus() else [])
        if not sel or not sel[0].is_dir or self.loc is None:
            return "break"
        if sel[0].name == "..":
            self.up()
        else:
            self.loc.change_dir(sel[0].name)
            self.reload()
        return "break"

    def up(self):
        if self.loc is not None and not self.loc.at_root():
            self.reload(keep=self.loc.go_up())
        return "break"


class HdCommanderTab(ttk.Frame):
    """Dual-pane copy tool. `downloads_var` is the Builder downloads folder shared with the other tabs."""

    def __init__(self, master, downloads_var, on_quit=None, settings=None, kickstart_source=None, emulator=None):
        super().__init__(master)
        self.downloads = downloads_var
        self.settings = settings or Settings()
        self.volume = None
        self.busy = False
        self._workers = []                # background threads still running (tests join them)
        self.events = queue.Queue()
        self._home = None                 # host folder the panel was last pointed at by the downloads setting
        self.image_var = tk.StringVar()
        self.status = tk.StringVar()
        self._on_quit = on_quit
        self._kickstart_source = kickstart_source   # callable -> folder with the user's Kickstart files
        self._emulator = emulator   # callable -> (Amiberry binary or None, Kickstarts folder, Options), from Settings > Amiberry…
        self._emu_proc = None
        self._build()
        self.after(100, self._poll)
        self.downloads_changed()
        saved = self.settings.get(SETTING_IMAGE)
        if saved and Path(saved).is_file():
            self.open_image(saved, quiet=True)
        else:
            self.status.set("Open an existing .hdf image or create a new one.")
        self.bind("<Destroy>", self._on_destroy)

    # ----- layout -----

    def _build(self):
        style = ttk.Style(self)
        style.configure("Panel.TLabel", background="#003377", foreground="white")
        style.configure("PanelActive.TLabel", background="#ff8800", foreground="black")

        self._notice_font = tkfont.nametofont("TkDefaultFont").copy()      # kept: Tk drops a font nobody refers to
        self._notice_font.configure(weight="bold")
        notice = tk.Label(self, text=EXPERIMENTAL_NOTICE, background="#ff8800", foreground="black", anchor="w",
                          justify="left", padx=10, pady=4, font=self._notice_font)
        notice.pack(fill="x")
        notice.bind("<Configure>", lambda e: notice.configure(wraplength=max(200, e.width - 24)))
        self.notice = notice

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Image:").pack(side="left")
        ttk.Entry(top, textvariable=self.image_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(top, text="Open…", command=self.open_dialog).pack(side="left", padx=2)
        ttk.Button(top, text="New…", command=self.new_dialog).pack(side="left", padx=2)
        ttk.Button(top, text="Close", command=self.close_image).pack(side="left", padx=2)
        ttk.Button(top, text="Make bootable…", command=self.make_bootable).pack(side="left", padx=(10, 2))
        ttk.Button(top, text="Install BetterWB…", command=self.install_betterwb).pack(side="left", padx=2)
        ttk.Button(top, text="Install WHDLoad…", command=self.install_whdload).pack(side="left", padx=2)
        self.test_button = ttk.Button(top, text="Test in emulator", command=self.test_image)
        self.test_button.pack(side="left", padx=(10, 2))
        if self._on_quit:
            ttk.Button(top, text="Quit", style="quit.TButton", command=self._on_quit).pack(side="left", padx=(10, 0))

        bottom = ttk.Frame(self, padding=(6, 2))
        bottom.pack(side="bottom", fill="x")
        self.progress = ttk.Progressbar(bottom, maximum=100)
        self.progress.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status, anchor="w").pack(fill="x")

        bar = ttk.Frame(self, padding=(6, 2))
        bar.pack(side="bottom", fill="x")
        bar.columnconfigure(0, weight=1, uniform="side")      # two equal side columns keep the buttons centered
        bar.columnconfigure(2, weight=1, uniform="side")
        buttons = ttk.Frame(bar)
        buttons.grid(row=0, column=1)
        self.button_row = buttons
        self.buttons = []
        for text, command in (("View (F3)", self.view), ("Install Game (F4)", self.install_games), ("Copy (F5)", self.copy),
                              ("Move (F6)", self.move),
                              ("MkDir (F7)", self.mkdir), ("Delete (F8)", self.delete), ("Refresh", self.refresh)):
            b = ttk.Button(buttons, text=text, command=command)
            b.pack(side="left", padx=2)
            self.buttons.append(b)
        ttk.Label(bar, text="Orange pane = source").grid(row=0, column=2, sticky="e")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, pady=4)
        self.host = _Panel(body, self, "Host")
        self.hdf = _Panel(body, self, "Image")
        body.add(self.host, weight=1)
        body.add(self.hdf, weight=1)
        self.active = self.host
        self.set_active(self.host)

    def set_active(self, panel):
        self.active = panel
        for p in (self.host, self.hdf):
            p.set_active(p is panel)

    @property
    def other(self):
        return self.hdf if self.active is self.host else self.host

    # ----- image handling -----

    def open_dialog(self):
        path = filedialog.askopenfilename(parent=self, title="Open Amiga hard disk image",
                                          filetypes=[("Hard disk images", "*.hdf"), ("All files", "*")])
        if path:
            self.open_image(path)

    def new_dialog(self):
        path = filedialog.asksaveasfilename(parent=self, title="Create Amiga hard disk image",
                                            defaultextension=".hdf", filetypes=[("Hard disk images", "*.hdf")])
        if not path:
            return
        size = dialogs.ask_integer(self, "New image", f"Size of the new image in MB (4 to {MAX_IMAGE_MB}):",
                                   256, 4, MAX_IMAGE_MB, heading="New image")
        if not size:
            return
        try:
            if os.path.exists(path):          # the save dialog already asked about overwriting
                os.remove(path)
            self._set_volume(HdfVolume.create(path, size), path)
            self.status.set(f"Created {path} ({size} MB). The image is empty: it needs Workbench/Kickstart to boot.")
        except (HdfError, OSError) as exc:
            self.error(str(exc))

    def open_image(self, path, quiet=False):
        try:
            self._set_volume(HdfVolume(str(path)), str(path))
        except UnsupportedFileSystem as exc:
            if quiet:
                self.status.set(f"Could not reopen the last image: {exc.short}, and only OFS/FFS images can be written.")
            else:
                dialogs.message(self, APP_NAME, str(exc), heading=f"{exc.fs} images are not supported")
        except HdfError as exc:
            if quiet:
                self.status.set(f"Could not reopen the last image: {exc}")
            else:
                self.error(str(exc))

    def _set_volume(self, volume, path):
        self._close_volume()
        self.volume = volume
        self.image_var.set(path)
        self.settings.set(SETTING_IMAGE, path)
        self.hdf.set_location(HdfLocation(volume))
        self._update_status()

    def _close_volume(self):
        if self.volume is not None:
            try:
                self.volume.close()
            except Exception:
                pass
            self.volume = None

    def close_image(self):
        if self.busy:
            return
        self._close_volume()
        self.image_var.set("")
        self.settings.set(SETTING_IMAGE, "")
        self.hdf.set_location(None)
        self.status.set("Image closed.")

    def _on_destroy(self, event):
        if event.widget is self:
            self._close_volume()

    def _update_status(self):
        if self.volume is not None:
            v = self.volume
            self.status.set(f"{v.volume_name}: free {human(v.free_bytes)} of {human(v.total_bytes)}")

    # ----- host folder -----

    def downloads_changed(self):
        """Follow the Builder downloads folder, unless the user has navigated elsewhere."""
        new = Path(self.downloads.get()) if self.downloads.get() else Path.home()
        if not new.is_dir():
            new = Path.home()
        if self.host.loc is None or self.host.loc.path == self._home:
            self.host.set_location(HostLocation(new))
        else:
            self.host.reload()
        self._home = HostLocation(new).path

    def refresh(self):
        self.host.reload()
        self.hdf.reload()
        self._update_status()

    # ----- actions -----

    def error(self, text):
        dialogs.message(self, APP_NAME, text, heading="Error")

    def _need_image(self) -> bool:
        if self.volume is None:
            dialogs.message(self, APP_NAME, "Open or create an image first.", heading="No image")
            return False
        return not self.busy

    def view(self):
        panel = self.active
        sel = [e for e in panel.selected() if not e.is_dir]
        if not sel or (not panel.loc.is_host and not self._need_image()):
            return
        try:
            text = transfer.preview_text(self.volume, panel.loc, sel[0].name)
        except (HdfError, OSError) as exc:
            self.error(str(exc))
            return
        show_text(self, sel[0].name, text)

    def install_games(self):
        """Install the selected host .lha archives as WHDLoad games."""
        if self.active is not self.host:
            if self.volume is not None:
                dialogs.message(self, "Install Game",
                                "Install Game works from the host pane: select .lha archives there.")
            return
        self._transfer("Install", install_games=True)

    def copy(self):
        self._transfer("Copy")

    def move(self):
        self._transfer("Move")

    def _transfer(self, verb, install_games=False):
        if not self._need_image():
            return
        src, dst = self.active, self.other
        names = src.names()
        if not names:
            return
        what = names[0] if len(names) == 1 else f"{len(names)} items"
        if install_games:
            msg = (f"Install {what} as WHDLoad games\nunder Games/ on the image?\n\n"
                   "Only .lha archives with a WHDLoad slave are installed; everything else is skipped.")
        else:
            msg = (f"{verb} {what}\nfrom {src.loc.label.lower()} ({_short(src.loc.location)})\n"
                   f"to {dst.loc.label.lower()} ({_short(dst.loc.location)})?")
        if not dialogs.confirm(self, verb, msg, yes=verb, no="Cancel", heading=verb):
            return
        self._run(verb, lambda progress: transfer.transfer_items(
            self.volume, src.loc, dst.loc, names, verb == "Move", progress, install_games))

    def mkdir(self):
        panel = self.active
        if panel.loc is None or not (panel.loc.is_host or self._need_image()):
            return
        name = dialogs.ask_text(self, "MkDir", "Name of the new directory:", heading="New directory")
        if not name:
            return
        try:
            if panel.loc.is_host:
                (panel.loc.path / name).mkdir()
            else:
                self.volume.mkdir(panel.loc.file_path(name))
        except (HdfError, OSError) as exc:
            self.error(str(exc))
            return
        panel.reload(keep=name)
        self._update_status()

    def delete(self):
        panel = self.active
        if panel.loc is None or self.busy or (not panel.loc.is_host and not self._need_image()):
            return
        names = panel.names()
        if not names:
            return
        what = names[0] if len(names) == 1 else f"{len(names)} items"
        where = "from the host (permanently)" if panel.loc.is_host else "from the image"
        if not dialogs.confirm(self, "Delete", f"Delete {what} {where}?", yes="Delete", no="Cancel",
                               heading="Delete", default_yes=False):
            return
        failed = transfer.delete_items(self.volume, panel.loc, names)
        self.refresh()
        if failed:
            show_text(self, "Delete errors", transfer.report(failed), modal=True)

    def make_bootable(self):
        """Install Amiga Workbench 3.1 from the original floppy disks, so that the image boots."""
        if not self._need_image():
            return
        remembered = self.settings.get(SETTING_DISKS)
        start = next((p for p in (remembered, EMULATOR_DIR / "Floppies", Path.home()) if p and Path(p).is_dir()))
        folder = filedialog.askdirectory(parent=self, initialdir=str(start), mustexist=True,
                                         title="Select the folder with your Workbench 3.1 disks (.adf)")
        if not folder:
            return
        disks = workbench.find_disks(folder)
        if not disks.usable:
            others = ("\n\nOther disks in that folder: " + ", ".join(disks.others[:6])) if disks.others else ""
            dialogs.message(self, "Make bootable",
                            "The folder needs the Workbench 3.1 disks as .adf (or .adz) files, recognised by their "
                            "disk names. Still missing: " + ", ".join(disks.missing_required) + "." + others,
                            heading="Disks not found", mono="Needed: Workbench3.1 and Install3.1\n"
                            "Optional: Extras3.1, Locale, Fonts, Storage3.1")
            return
        self.settings.set(SETTING_DISKS, folder)
        listing = "\n".join(f"{workbench.LABELS[r]:<14}{disks.found[r].name}"
                            for r in (*workbench.REQUIRED, *workbench.OPTIONAL) if r in disks.found)
        text = "Install Amiga Workbench 3.1 into this image so that it boots?"
        replace = self.volume.exists(workbench.STARTUP)
        if replace:
            text += ("\n\nThe image already has a startup script (S/Startup-Sequence). It is replaced and the old "
                     "one kept as S/Startup-Sequence.old.")
        footer = ("Not found, so not installed: " + ", ".join(disks.missing_optional) + "." if disks.missing_optional
                  else "Which monitor driver is active: PAL (Europe) or NTSC.")
        region = dialogs.choose(self, "Make bootable", text,
                                [("Install (PAL)", "PAL"), ("Install (NTSC)", "NTSC"), ("Cancel", None)],
                                heading="Make bootable", mono=listing, footer=footer)
        if region is None:
            return
        self._run("Install Workbench",
                  lambda progress: workbench.install_workbench(self.volume, disks.found, region=region,
                                                               replace_startup=replace, progress=progress),
                  after=self._workbench_installed)

    def test_image(self):
        """Boot the image in the emulator selected on the Builder tab (Amiga 1200, 8 MB RAM). The image is
        closed here while the emulator runs, so both never write to it at once, and reopened afterwards."""
        if self.busy or self._emu_proc is not None or not self._need_image():
            return
        path = self.image_var.get()
        exe, kickstarts, options = self._emulator() if self._emulator else (None, None, amiberry.Options())
        if exe is None:
            self.error("Amiberry not found. Put it in the emulator folder or choose it in Settings > Amiberry….")
            return
        self._close_volume()          # flushes everything to the file
        self.hdf.set_location(None)
        try:
            self._emu_proc = amiberry.launch_hdf(exe, Path(path), kickstarts, options)
        except Exception as exc:
            self.open_image(path, quiet=True)
            self.error(str(exc))
            return
        self.test_button.state(["disabled"])
        for b in self.buttons:
            b.state(["disabled"])
        self.status.set("Emulator running (Amiga 1200, 8 MB). The image reopens when it quits.")
        self._watch_emulator(path)

    def _watch_emulator(self, path):
        if self._emu_proc is not None and self._emu_proc.poll() is None:
            self.after(500, lambda: self._watch_emulator(path))
            return
        self._emu_proc = None
        self.test_button.state(["!disabled"])
        for b in self.buttons:
            b.state(["!disabled"])
        self.open_image(path, quiet=True)

    def _workbench_installed(self):
        dialogs.message(
            self, "Workbench installed",
            "The image now contains Workbench 3.1 and boots from its own startup script. To start it, give "
            "the emulator this image as its hard drive together with a Kickstart 3.1 ROM (A500/A600 or A1200).",
            heading="Workbench installed",
            footer="Next: Install WHDLoad… adds WHDLoad to C: so that games can run.")

    def install_betterwb(self):
        """Add BetterWB (better icons, datatypes, tools) to an image that has Workbench 3.1, from its six floppies."""
        if not self._need_image():
            return
        if betterwb.needs_workbench(self.volume):
            dialogs.message(self, "Install BetterWB", "BetterWB is an add-on for Workbench 3.1, and this image "
                            "has no Workbench yet.", heading="Workbench needed",
                            footer="Use Make bootable… first, then come back.")
            return
        remembered = self.settings.get(SETTING_BETTERWB)
        start = next((p for p in (remembered, Path.home() / "Downloads", Path.home()) if p and Path(p).is_dir()))
        folder = filedialog.askdirectory(parent=self, initialdir=str(start), mustexist=True,
                                         title="Select the folder with the BetterWB disks (.adf)")
        if not folder:
            return
        disks = betterwb.find_disks(folder)
        lost, optional = betterwb.missing(disks)
        if lost:
            dialogs.message(self, "Install BetterWB",
                            "The folder needs the BetterWB disks as .adf (or .adz) files, recognised by their disk "
                            "names. Still missing: " + ", ".join(lost) + ".", heading="Disks not found",
                            mono="Needed: Misc3.1\nOptional: Tools3.1, Bonus3.1, Docs3.1, Icons3.1, Drivers3.1")
            return
        self.settings.set(SETTING_BETTERWB, folder)
        listing = "\n".join(f"{betterwb.DISKS[v][0]:<12}{disks[v].name}" for v in betterwb.DISKS if v in disks)
        footer = ("Not found, so not installed: " + ", ".join(optional) + "." if optional else
                  "Env-Handler saves RAM but warns each time you save preferences; most people do not need it.")
        env = dialogs.choose(self, "Install BetterWB",
                             "Install BetterWB into this image?\n\nIt replaces S/Startup-Sequence (the old one is "
                             "kept as S/Startup-Sequence.old) and needs about 10 MB.",
                             [("Install", False), ("Install with Env-Handler", True), ("Cancel", None)],
                             heading="Install BetterWB", mono=listing, footer=footer)
        if env is None:
            return
        self._run("Install BetterWB",
                  lambda progress: betterwb.install_betterwb(self.volume, disks, env_handler=env, progress=progress),
                  after=self._betterwb_installed)

    def _betterwb_installed(self):
        dialogs.message(self, "BetterWB installed", "BetterWB is in the image. Reboot the emulator to use it.",
                        heading="BetterWB installed")

    def install_whdload(self):
        """Install the WHDLoad distribution (WHDLoad_usr*.lha) into C:, S: (and optionally Help:)."""
        if not self._need_image():
            return
        downloads = Path.home() / "Downloads"
        path = filedialog.askopenfilename(
            parent=self, title="Select the WHDLoad distribution (WHDLoad_usr….lha)",
            initialdir=str(downloads if downloads.is_dir() else Path.home()),
            filetypes=[("LHA archives", "*.lha *.lzh"), ("All files", "*")])
        if not path:
            return
        try:
            docs = whdinstall.docs_size(path)
        except (HdfError, OSError, lha.LhaError) as exc:      # unreadable or not a WHDLoad archive
            dialogs.message(self, "Install WHDLoad", f"{Path(path).name}\n\n{exc}", heading="Cannot install")
            return
        choice = dialogs.choose(
            self, "Install WHDLoad",
            f"Install WHDLoad from\n{Path(path).name}\ninto C: and S: of the image?\n\n"
            f"The documentation (about {human(docs)}) can be installed into Help/WHDLoad as well.",
            [("With documentation", "docs"), ("Without documentation", "nodocs"), ("Cancel", None)],
            heading="Install WHDLoad")
        if choice is None:
            return
        self._run("Install WHDLoad",
                  lambda progress: whdinstall.install_whdload(self.volume, path, choice == "docs", progress),
                  after=self._offer_kickstarts)

    def _offer_kickstarts(self):
        """After installing WHDLoad: let the user decide whether to copy the Kickstart files kept in the
        template's Devs/Kickstarts folder into the image, then explain what WHDLoad needs there."""
        folder = self._kickstart_source() if self._kickstart_source else None
        files = whdinstall.template_kickstarts(folder) if folder else []
        if files:
            short = "…/" + "/".join(Path(folder).parts[-3:])
            names = "\n".join(p.name for p in files[:14]) + ("\n…" if len(files) > 14 else "")
            if dialogs.choose(
                    self, "Kickstart files",
                    f"The template folder ({short}) contains {len(files)} Kickstart file(s).\n\n"
                    "Copy them into Devs:Kickstarts on the image? Files already there are kept. "
                    "Choose Skip to add Kickstarts yourself later.",
                    [("Copy them", True), ("Skip", False)], cancel=False, heading="Kickstart files", mono=names):
                self._run("Install Kickstarts",
                          lambda progress: whdinstall.install_kickstarts(self.volume, files, progress),
                          after=self._kickstart_notice)
                return
        self._kickstart_notice()

    def _kickstart_notice(self):
        intro, report, outro = whdinstall.kickstart_notice_parts(self.volume)
        dialogs.message(self, "WHDLoad installed", intro, heading="WHDLoad installed", mono=report, footer=outro)

    # ----- background work -----

    def _run(self, verb, job, after=None):
        self.busy = True
        for b in self.buttons:
            b.state(["disabled"])
        self.progress.configure(value=0)
        self.status.set(GERUND[verb] + "…")

        def work():
            try:
                items = job(lambda fraction, text: self.events.put(("progress", fraction, text)))
            except Exception as exc:        # never lose the UI to a worker error
                items = [transfer.Item("(error)", transfer.FAILED, str(exc))]
            self.events.put(("done", verb, items, after))

        self._worker = threading.Thread(target=work, daemon=True)
        self._workers = [t for t in self._workers if t.is_alive()] + [self._worker]
        self._worker.start()

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.progress.configure(value=event[1] * 100)
                    self.status.set(event[2])
                else:
                    self._finished(event[1], event[2], event[3])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finished(self, verb, items, after=None):
        self.busy = False
        for b in self.buttons:
            b.state(["!disabled"])
        self.progress.configure(value=100)        # done: the bar stays full while the results are shown
        self.refresh()
        summary = transfer.summarize(items)
        if all(i.status == transfer.OK for i in items):
            self.status.set(f"{verb}: {summary}. " + self.status.get())
        else:
            show_text(self, f"{verb}: {summary}", transfer.report(items), modal=True)   # before any next dialog
            self.progress.configure(value=0)      # the results window was closed: the bar empties
        if after and not any(i.status == transfer.FAILED for i in items):
            after()
