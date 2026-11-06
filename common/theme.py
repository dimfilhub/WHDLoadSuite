from tkinter import ttk

WB_BLUE = "#0055aa"  # Amiga Workbench 1.x blue, same as the Amiga Workbench look
LINK_COLOR = "#9fd0ff"
TEXT_COLOR = "white"
HAVE_COLOR = "#008000"     # file already in the download folder
MISSING_COLOR = "#cc0000"  # file not downloaded yet


def apply_theme(root):
    """Same look as the GamebaseST tree: clam theme, white rows, blue headings and selection."""
    bg = WB_BLUE
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=bg)
    for name in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label", "TCheckbutton"):
        style.configure(name, background=bg, foreground="white")
    style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", "white")])
    style.configure("TProgressbar", background="#ff8800", troughcolor="#003377")
    style.configure("TButton", background=bg, foreground="white", bordercolor="white",
                    lightcolor=bg, darkcolor=bg, focuscolor=bg)
    style.map("TButton", background=[("active", "#3377cc"), ("disabled", bg)],
              foreground=[("disabled", "#7fa6d4")])
    style.configure("quit.TButton", background="#c62828", lightcolor="#c62828", darkcolor="#c62828",
                    focuscolor="#c62828")
    style.map("quit.TButton", background=[("active", "#e53935"), ("disabled", "#c62828")])
    style.configure("TEntry", fieldbackground="white", foreground="blue")
    style.configure("Treeview", background="white", fieldbackground="white", foreground="black",
                    rowheight=22)
    style.map("Treeview", background=[("selected", "#0078d7")],
              foreground=[("selected", "white")])
    style.configure("Treeview.Heading", foreground="blue")


def apply_app_theme(root):
    """The whole application's look: the Downloader's base styles plus the Workbench-blue frames, buttons,
    notebook tabs and tree colours used by every tab."""
    # Same tree look as GamebaseST: clam has fixed light colours (the macOS theme follows dark mode).
    apply_theme(root)  # Downloader's base styles; the Builder styles below build on them
    style = ttk.Style(root)
    root.configure(background=WB_BLUE)
    for name in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label", "TCheckbutton"):
        style.configure(name, background=WB_BLUE, foreground="white")
    style.map("TCheckbutton", background=[("active", WB_BLUE)], foreground=[("active", "white")])
    style.configure("TProgressbar", background="#ff8800", troughcolor="#003377")
    style.configure("TButton", background=WB_BLUE, foreground="white", bordercolor="white",
                    lightcolor=WB_BLUE, darkcolor=WB_BLUE, focuscolor=WB_BLUE)
    style.map("TButton", background=[("active", "#3377cc"), ("disabled", WB_BLUE)],
              foreground=[("disabled", "#7fa6d4")])
    style.configure("clear.TButton", background="#c62828", lightcolor="#c62828", darkcolor="#c62828",
                    focuscolor="#c62828")
    style.map("clear.TButton", background=[("active", "#e53935"), ("disabled", "#c62828")])
    style.configure("on.TButton", background="#2e7d32", lightcolor="#2e7d32", darkcolor="#2e7d32",
                    focuscolor="#2e7d32")  # toggle buttons that are switched on
    style.map("on.TButton", background=[("active", "#43a047"), ("disabled", "#2e7d32")])
    style.configure("Treeview", background="white", fieldbackground="white", foreground="black")
    style.map("Treeview", background=[("selected", "#0078d7")], foreground=[("selected", "white")])
    style.configure("Treeview.Heading", foreground="blue")
    # Ticked archives (the tree's "selection") show in bold on white instead of the usual blue highlight.
    style.configure("Archives.Treeview")
    style.map("Archives.Treeview", background=[("selected", "white")], foreground=[("selected", "black")])
    style.configure("TNotebook", background=WB_BLUE, bordercolor="white")
    style.configure("TNotebook.Tab", background="#003377", foreground="white", padding=(14, 4))
    style.map("TNotebook.Tab", background=[("selected", "#3377cc")], foreground=[("selected", "white")])
