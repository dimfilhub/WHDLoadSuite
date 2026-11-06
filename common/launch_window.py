"""The launch window: the game's picture and the keyboard joystick, window and screen look to start it with.

Shared by the app (tabs/builder/launch_screen.py) and by every standalone executable (amiberry_runtime.py), so it
uses only the standard library and the files next to it, and the pictures it shows are Tk images: the app makes
one with Pillow, an executable reads the small PNG that was put inside it when it was built.
"""
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import replace
from tkinter import ttk

try:                                     # in the app
    from .amiberry_runtime import KEYBOARD_CHOICES, LOOK_CHOICES, WINDOW_CHOICES, Options
    from .theme import WB_BLUE, apply_theme
except ImportError:                      # in a standalone executable, where common/ is on the path
    from amiberry_runtime import KEYBOARD_CHOICES, LOOK_CHOICES, WINDOW_CHOICES, Options
    from theme import WB_BLUE, apply_theme

PANEL = "#003377"
NOTE_COLOUR = "#ff8800"
HINT = "If you switch it off, you can turn it back on in Settings > Amiberry…"
BUNDLE_HINT = "If you switch it off, delete the file {file} in the WHDLoadSuite data folder to get it back."
MAX_PICTURE = (640, 512)             # a 320x256 Amiga screenshot is shown at twice its size


def fit_size(width: int, height: int, max_width: int, max_height: int):
    """(new width, new height, sharp) for showing a picture inside a box. Pictures that can be doubled or more are
    scaled by a whole number with sharp pixels (what an Amiga screenshot looks best with); anything else is smoothed."""
    scale = min(max_width / width, max_height / height)
    if scale >= 2:
        whole = int(scale)
        return width * whole, height * whole, True
    return max(1, round(width * scale)), max(1, round(height * scale)), False


def load_png(master, path, max_width: int, max_height: int):
    """A Tk image of a PNG (or GIF) file, made smaller by a whole number if it does not fit the box; None if it
    cannot be read. Tk reads these formats itself, so this needs no Pillow."""
    if not path:
        return None
    try:
        image = tk.PhotoImage(master=master, file=str(path))
    except tk.TclError:
        return None
    factor = max(-(-image.width() // max_width), -(-image.height() // max_height), 1)
    return image.subsample(factor) if factor > 1 else image


class LaunchWindow(tk.Toplevel):
    def __init__(self, parent, name, options: Options, image=None, kind="", preparing=False, show_again=None,
                 hint=HINT):
        """image: a Tk image to show (None = a note instead); kind: "screenshot" or "cover" (a caption); preparing:
        the game needs a prepared drive, which is made after Launch; show_again: the state of the "show this screen"
        switch, or None for a window without the two tick boxes; hint: where to turn the screen back on."""
        super().__init__(parent)
        self.withdraw()              # hidden until built and centred, so it never shows in the corner first
        self.result = None
        self.options = options
        self.title("Launch")
        self.configure(background=WB_BLUE)
        if parent.winfo_toplevel().winfo_viewable():
            self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        body = ttk.Frame(self, padding=16)
        body.pack()
        ttk.Label(body, text=name, font=("Helvetica", 16, "bold")).pack(pady=(0, 10))

        self.image = image                                   # kept: Tk drops a picture nobody refers to
        if image is not None:
            tk.Label(body, image=image, borderwidth=2, relief="solid", background=PANEL).pack()
            ttk.Label(body, text=kind.capitalize()).pack(pady=(4, 0))
        else:
            tk.Label(body, text="No picture for this game", width=40, height=6, background=PANEL,
                     foreground="white", font=tkfont.nametofont("TkDefaultFont")).pack()

        form = ttk.Frame(body)
        form.pack(pady=(14, 0))
        self.vars = {}
        for row, (label, choices, field, current) in enumerate((
                ("Keyboard joystick:", KEYBOARD_CHOICES, "keyboard", options.keyboard),
                ("Window:", WINDOW_CHOICES, "window", options.window),
                ("Screen look:", LOOK_CHOICES, "look", options.look))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            names = [text for _, text in choices]
            combo = ttk.Combobox(form, values=names, state="readonly", width=44)
            combo.set(dict(choices).get(current, names[0]))
            combo.grid(row=row, column=1, padx=(8, 0), pady=3)
            self.vars[field] = (combo, {text: value for value, text in choices})

        self.remember = tk.BooleanVar(self, value=False)
        self.show_again = tk.BooleanVar(self, value=True if show_again is None else show_again)
        if show_again is not None:
            ttk.Checkbutton(body, text="Use these choices from now on", variable=self.remember).pack(anchor="w", pady=(8, 0))
            ttk.Checkbutton(body, text="Show this screen when I launch a game", variable=self.show_again).pack(anchor="w")
            ttk.Label(body, text=hint, wraplength=520, justify="left", foreground=NOTE_COLOUR).pack(anchor="w", padx=(24, 0))
        if preparing:
            ttk.Label(body, text="This game needs a prepared drive. It is prepared when you press Launch (this takes a "
                                 "moment).", wraplength=520, justify="left", foreground=NOTE_COLOUR).pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(body)
        row.pack(pady=(16, 0))
        launch = ttk.Button(row, text="Launch", command=self.launch)
        launch.pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=self.cancel).pack(side="left", padx=6)
        launch.focus_set()
        self.bind("<Return>", lambda _e: self.launch())
        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self._centre(parent)
        self.deiconify()
        self.lift()
        self.focus_force()
        self.update()                # shown now: a window must be on screen before it can grab the keyboard and mouse
        try:
            self.grab_set()
        except tk.TclError:           # not viewable (a withdrawn parent): carry on without grabbing
            pass

    def _centre(self, parent):
        """Over the application window, or in the middle of the screen when there is none to go over."""
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        top = parent.winfo_toplevel()
        if top.winfo_viewable():
            x = top.winfo_rootx() + max((top.winfo_width() - width) // 2, 0)
            y = top.winfo_rooty() + max((top.winfo_height() - height) // 4, 0)
        else:
            x = max((self.winfo_screenwidth() - width) // 2, 0)
            y = max((self.winfo_screenheight() - height) // 3, 0)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def chosen(self) -> Options:
        """The options as they stand in the three drop-downs."""
        values = {field: mapping[combo.get()] for field, (combo, mapping) in self.vars.items()}
        return replace(self.options, **values)

    def launch(self):
        self.result = self.chosen()
        self.finished(self.result)
        self.destroy()

    def cancel(self):
        self.result = None
        self.finished(None)
        self.destroy()

    def finished(self, result):
        """Called when the window closes (result is the Options, or None if cancelled); a subclass keeps the choices."""


def run_for_bundle(name, options: Options, picture, kind=""):
    """The launch window of a standalone executable: its own hidden Tk root, the picture from a PNG file inside the
    executable. Returns (Options or None if cancelled, show this screen again, keep these choices)."""
    root = tk.Tk()
    root.withdraw()
    try:
        apply_theme(root)
        image = load_png(root, picture, *MAX_PICTURE)
        window = LaunchWindow(root, name, options, image, kind, show_again=True,
                              hint=BUNDLE_HINT.format(file=f"Launch/{name}.json"))
        if window.winfo_exists():         # it can be answered while it is still being shown
            root.wait_window(window)
        return window.result, window.show_again.get(), window.remember.get()
    finally:
        root.destroy()
