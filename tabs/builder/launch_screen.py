"""The launch screen shown before a game starts from the Browser or the Builder.

It shows the game's picture (a screenshot or cover from the GamebaseAmiga folder chosen in Settings > Amiberry…) and
lets the user pick the keyboard joystick, the window and the screen look for this launch. `ask` returns the Options to
start the game with, or None when the user cancels. The window itself is common/launch_window.py, which the standalone
executables use too.
"""
from common.amiberry_runtime import Options
from common.launch_window import HINT, MAX_PICTURE, LaunchWindow, fit_size

try:
    from PIL import Image, ImageTk
except ImportError:                  # Pillow is only needed to show pictures
    Image = ImageTk = None


def load_picture(master, path, max_width: int, max_height: int):
    """A Tk image (for the window `master`) of the picture inside the box, or None if it cannot be read (or Pillow is
    missing)."""
    if Image is None or path is None:
        return None
    try:
        with Image.open(path) as source:
            picture = source.convert("RGB")
        width, height, sharp = fit_size(*picture.size, max_width, max_height)
        picture = picture.resize((width, height), Image.NEAREST if sharp else Image.LANCZOS)
        return ImageTk.PhotoImage(picture, master=master)
    except (OSError, ValueError):
        return None


class LaunchScreen(LaunchWindow):
    def __init__(self, parent, name, options: Options, picture=None, kind="", preparing=False, settings=None):
        """picture: the file to show (None = none); kind: "screenshot" or "cover" (a caption); preparing: the game
        needs a prepared drive, which is made after Launch; settings: the AppSettings, for "remember" and "show"."""
        self.settings = settings
        box = (min(MAX_PICTURE[0], int(parent.winfo_screenwidth() * 0.45)),
               min(MAX_PICTURE[1], int(parent.winfo_screenheight() * 0.45)))
        super().__init__(parent, name, options, load_picture(parent, picture, *box), kind, preparing,
                         show_again=None if settings is None else settings.launch_screen.get(), hint=HINT)

    def finished(self, result):
        if self.settings is None:
            return
        if result is not None and self.remember.get():
            for field in ("keyboard", "window", "look"):
                getattr(self.settings, field).set(getattr(result, field))
        self.settings.launch_screen.set(self.show_again.get())      # "don't show again" counts even if cancelled


def ask(parent, name, options: Options, picture=None, kind="", preparing=False, settings=None):
    """Show the launch screen and wait; returns the Options to launch with, or None if cancelled."""
    screen = LaunchScreen(parent, name, options, picture, kind, preparing, settings)
    if screen.winfo_exists():              # it can be answered while it is still being shown
        parent.wait_window(screen)
    return screen.result
