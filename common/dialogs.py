"""Amiga-style dialogs (Workbench blue, like the About and Download-filters windows).

They rely on the ttk theme the main window applies (common/theme.py and gui.py): blue frames, white labels,
blue buttons with a white border. choose()/message() block until the user answers, like messagebox.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .theme import WB_BLUE

DARK_BLUE = "#003377"      # inset panels (same blue as the notebook tabs and progress trough)
WRAP = 480
SUBMIT = object()        # button value meaning "accept the text field" (see ask_text)


def center(win, parent, size=None):
    """Put a window over the middle of the application window. `size` = (width, height) gives it that size; without
    it the window keeps the size its contents ask for. Call it while the window is still withdrawn and show it
    afterwards, so it never appears elsewhere first."""
    win.update_idletasks()
    w, h = size or (win.winfo_reqwidth(), win.winfo_reqheight())
    top = parent.winfo_toplevel()
    x = max(top.winfo_rootx() + max((top.winfo_width() - w) // 2, 0), 0)
    y = max(top.winfo_rooty() + max((top.winfo_height() - h) // 3, 0), 0)
    win.geometry(f"{w}x{h}+{x}+{y}" if size else f"+{x}+{y}")


_center = center


class AmigaDialog(tk.Toplevel):
    """Modal question/notice: optional heading, message, a monospace panel and a row of buttons.

    buttons: [(label, value)]; `result` is the value of the clicked button, or `cancel` if the window
    is closed or Esc is pressed. Return picks the default button.
    field: initial text of an entry box (None = no entry). A button whose value is SUBMIT returns the
    entry text; validator(text) may return a converted value or raise ValueError(message), which is shown
    in the dialog and keeps it open."""

    def __init__(self, parent, title, message, buttons, default=0, cancel=None, heading=None, mono=None,
                 footer=None, field=None, validator=None):
        super().__init__(parent)
        self.withdraw()            # hidden until built and centred, so it never shows in the corner first
        self.result = cancel
        self._cancel, self._default = cancel, buttons[default][1]
        self._validator = validator
        self.title(title)
        self.configure(background=WB_BLUE)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)

        body = ttk.Frame(self, padding=20)
        body.pack()
        if heading:
            ttk.Label(body, text=heading, font=("Helvetica", 16, "bold")).pack(pady=(0, 10))
        ttk.Label(body, text=message, wraplength=WRAP, justify="left").pack(anchor="w")
        if mono:
            tk.Label(body, text=mono, font=tkfont.nametofont("TkFixedFont"), justify="left", anchor="w",
                     background=DARK_BLUE, foreground="white", padx=10, pady=8).pack(fill="x", pady=(12, 0))
        if footer:
            ttk.Label(body, text=footer, wraplength=WRAP, justify="left").pack(anchor="w", pady=(12, 0))
        if field is not None:
            self.entry_var = tk.StringVar(master=self, value=field)
            self.error_var = tk.StringVar(master=self)
            self.entry = ttk.Entry(body, textvariable=self.entry_var, width=44)
            self.entry.pack(fill="x", pady=(12, 0))
            ttk.Label(body, textvariable=self.error_var, foreground="#ff8800", wraplength=WRAP).pack(anchor="w")
            self.entry.focus_set()
            self.entry.selection_range(0, "end")
        row = ttk.Frame(body)
        row.pack(pady=(18, 0))
        self.buttons = []
        for i, (label, value) in enumerate(buttons):
            b = ttk.Button(row, text=label, command=lambda v=value: self._done(v))
            b.pack(side="left", padx=6)
            self.buttons.append(b)
            if i == default and field is None:
                b.focus_set()
        self.bind("<Escape>", lambda _e: self.on_escape())
        self.bind("<Return>", lambda _e: self.on_return())
        self.protocol("WM_DELETE_WINDOW", lambda: self._done(self._cancel))
        _center(self, parent)
        self.deiconify()
        self.lift()                # never hide behind another window of the application
        self.update()              # on screen now: a window must be viewable before it can grab the input
        try:
            self.grab_set()
        except tk.TclError:       # window not viewable (e.g. the parent is withdrawn): stay non-grabbing
            pass

    def on_return(self):
        self._done(self._default)

    def on_escape(self):
        self._done(self._cancel)

    def _done(self, value):
        if value is SUBMIT:
            value = self.entry_var.get()
            if self._validator:
                try:
                    value = self._validator(value)
                except ValueError as exc:
                    self.error_var.set(str(exc))
                    self.entry.focus_set()
                    return
        self.result = value
        self.destroy()


def choose(parent, title, message, buttons, default=0, cancel=None, heading=None, mono=None, footer=None):
    """Show an AmigaDialog and return the value of the button the user picked."""
    dialog = AmigaDialog(parent, title, message, buttons, default, cancel, heading, mono, footer)
    if dialog.winfo_exists():                # it can be answered while it is still being shown
        parent.wait_window(dialog)
    return dialog.result


def confirm(parent, title, message, yes="Yes", no="No", heading=None, default_yes=True):
    """Yes/No question; returns True or False (Esc and closing the window mean No)."""
    return bool(choose(parent, title, message, [(yes, True), (no, False)], default=0 if default_yes else 1,
                       cancel=False, heading=heading or title))


def ask_text(parent, title, prompt, initial="", heading=None, validator=None, ok="OK"):
    """Ask for a line of text; returns it (or the validator's result), or None if cancelled."""
    def nonblank(text):
        if not text.strip():
            raise ValueError("Please enter a name.")
        return text.strip()

    dialog = AmigaDialog(parent, title, prompt, [(ok, SUBMIT), ("Cancel", None)], heading=heading or title,
                         field=initial, validator=validator or nonblank)
    if dialog.winfo_exists():                # it can be answered while it is still being shown
        parent.wait_window(dialog)
    return dialog.result


def ask_integer(parent, title, prompt, initial, minvalue, maxvalue, heading=None):
    """Ask for a whole number in a range; returns it, or None if cancelled."""
    def check(text):
        try:
            number = int(text.strip())
        except ValueError:
            raise ValueError("Please enter a whole number.") from None
        if not minvalue <= number <= maxvalue:
            raise ValueError(f"Please enter a number from {minvalue} to {maxvalue}.")
        return number

    return ask_text(parent, title, prompt, str(initial), heading, validator=check)


def message(parent, title, text, heading=None, mono=None, footer=None):
    """A notice with a single OK button."""
    choose(parent, title, text, [("OK", True)], heading=heading or title, mono=mono, footer=footer)


def show_text(parent, title, text, modal=False):
    """Scrollable read-only text window (file viewer, reports): white mono text on Workbench blue, like
    the Help window. Esc closes it.

    modal=True waits until the window is closed and holds the input grab meanwhile. Use it for a report that
    is followed by another dialog: that dialog grabs the mouse too, and a report left open beside it would
    have a Close button that does nothing."""
    win = tk.Toplevel(parent)
    win.withdraw()                 # hidden until built and centred
    win.title(title)
    win.configure(background=WB_BLUE)
    win.transient(parent.winfo_toplevel())
    frame = ttk.Frame(win, padding=8)
    frame.pack(fill="both", expand=True)
    bottom = ttk.Frame(frame)
    bottom.pack(side="bottom", fill="x", pady=(8, 0))
    ttk.Button(bottom, text="Close", command=win.destroy).pack()
    vsb = ttk.Scrollbar(frame, orient="vertical")
    hsb = ttk.Scrollbar(frame, orient="horizontal")
    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    box = tk.Text(frame, wrap="none", font=tkfont.nametofont("TkFixedFont"), padx=10, pady=8,
                  borderwidth=0, highlightthickness=0, background=DARK_BLUE, foreground="white",
                  insertbackground="white", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.configure(command=box.yview)
    hsb.configure(command=box.xview)
    box.pack(fill="both", expand=True)
    box.insert("1.0", text)
    box.configure(state="disabled")
    win.bind("<Escape>", lambda _e: win.destroy())
    box.focus_set()
    center(win, parent, (760, 480))
    win.deiconify()
    if modal:
        win.lift()
        win.update()               # on screen now: a window must be viewable before it can grab the input
        try:
            win.grab_set()
        except tk.TclError:       # window not viewable (e.g. the parent is withdrawn): stay non-grabbing
            pass
        if win.winfo_exists():
            parent.wait_window(win)
    return win
