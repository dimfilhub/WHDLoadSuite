"""The Help window: a contents tree on the left and the selected page on the right.

The pages are Markdown files in the help/ folder, listed in help/contents.json (the tree). A page uses a small
part of Markdown: `#`, `##`, `###` headings, `-` and `1.` lists (indent two spaces for a sub-list), `>` notes,
``` code blocks, **bold**, `code`, and links: `[text](help:page-id)` goes to another page, `[text](https://…)` opens
the web. Consecutive lines of one paragraph are joined, so a page can be wrapped in the editor.
"""
import json
import re
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk

from .dialogs import DARK_BLUE, center
from .paths import PROJECT_ROOT
from .theme import LINK_COLOR, TEXT_COLOR, WB_BLUE

HELP_DIR = PROJECT_ROOT / "help"
CODE_COLOUR = "#ffe08a"
NOTE_COLOUR = "#ff8800"
MISSING = "This page could not be found: {file}"


@dataclass
class Page:
    id: str
    title: str
    file: str
    parent: str = ""
    children: list = field(default_factory=list)       # ids of the pages under this one


def load_contents(folder=HELP_DIR) -> list:
    """The pages of help/contents.json in tree order (a parent before its children), or [] if it cannot be read."""
    try:
        data = json.loads((Path(folder) / "contents.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    pages = []

    def walk(items, parent):
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or "id" not in item or "title" not in item:
                continue
            page = Page(str(item["id"]), str(item["title"]), str(item.get("file", "")), parent)
            pages.append(page)
            if parent:
                next(p for p in pages if p.id == parent).children.append(page.id)
            walk(item.get("pages", []), page.id)

    walk(data.get("pages", []), "")
    return pages


def read_page(page: Page, folder=HELP_DIR) -> str:
    try:
        return (Path(folder) / page.file).read_text(encoding="utf-8")
    except OSError:
        return f"# {page.title}\n\n" + MISSING.format(file=page.file)


INLINE = re.compile(r"(\*\*[^*]+\*\*|(?<![\w*])\*[^*\s][^*]*\*(?![\w*])|`[^`]+`|\[[^\]]+\]\([^)]+\)|https?://[^\s)]+)")
LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def parse(markdown: str) -> list:
    """The blocks of a page: [(kind, level, text)] with kind one of h1 h2 h3 p li ol note code."""
    blocks, para, kind = [], [], None
    level_of = [0]

    def flush():
        nonlocal para, kind
        if para:
            blocks.append((kind, level_of[0], " ".join(para)))
        para, kind = [], None

    in_code = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            blocks.append(("code", 0, raw))
            continue
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        heading = re.match(r"^(#{1,3}) (.*)$", line)
        if heading:
            flush()
            blocks.append((f"h{len(heading.group(1))}", 0, heading.group(2).strip()))
            continue
        item = LIST_ITEM.match(line)
        if item:
            flush()
            kind, level_of[0] = ("ol" if item.group(2)[0].isdigit() else "li"), min(len(item.group(1)) // 2, 3)
            para = [item.group(3)] if kind == "li" else [f"{item.group(2)} {item.group(3)}"]    # keep the number
            continue
        if stripped.startswith(">"):
            text = stripped[1:].strip()
            if kind != "note":
                flush()
                kind, level_of[0] = "note", 0
            para.append(text)
            continue
        if kind in ("li", "ol") and raw.startswith("  "):       # the next line of a list item
            para.append(stripped)
            continue
        if kind not in (None, "p"):
            flush()
        kind, level_of[0] = "p", 0
        para.append(stripped)
    flush()
    return blocks


class HelpDialog(tk.Toplevel):
    _open = None            # the one open Help window

    @classmethod
    def show(cls, parent, name, start=None, folder=HELP_DIR):
        """Open the Help window (or bring the open one to the front), at the page `start` if given."""
        window = cls._open
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            if start:
                window.goto(start)
            return window
        cls._open = window = cls(parent, name, start, folder)
        return window

    def __init__(self, parent, name, start=None, folder=HELP_DIR):
        super().__init__(parent)
        self.withdraw()                      # hidden until built and centred
        self.folder = Path(folder)
        self.pages = load_contents(self.folder)
        self.by_id = {p.id: p for p in self.pages}
        self.history, self.position = [], -1
        self.title(f"{name} Help")
        self.configure(background=WB_BLUE)
        self.transient(parent.winfo_toplevel())
        self.minsize(760, 460)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=8)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=0)
        panes.add(right, weight=1)

        ttk.Label(left, text="Contents", font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(0, 4))
        holder = ttk.Frame(left)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(holder, show="tree", selectmode="browse")
        self.tree.column("#0", width=250)
        scroll = ttk.Scrollbar(holder, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for page in self.pages:
            self.tree.insert(page.parent, "end", iid=page.id, text=page.title, open=True)
        self.tree.bind("<<TreeviewSelect>>", self._selected)

        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(0, 4))
        self.back_button = ttk.Button(bar, text="◀ Back", width=8, command=self.back)
        self.back_button.pack(side="left")
        self.forward_button = ttk.Button(bar, text="Forward ▶", width=10, command=self.forward)
        self.forward_button.pack(side="left", padx=4)
        self.crumbs = tk.StringVar(self)
        ttk.Label(bar, textvariable=self.crumbs, foreground=NOTE_COLOUR).pack(side="left", padx=10)
        body = ttk.Frame(right)
        body.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(body)
        vsb.pack(side="right", fill="y")
        self.text = tk.Text(body, wrap="word", padx=16, pady=10, yscrollcommand=vsb.set, borderwidth=0,
                            highlightthickness=0, background=WB_BLUE, foreground=TEXT_COLOR, cursor="arrow",
                            insertbackground=WB_BLUE, width=80, height=30)
        self.text.pack(side="left", fill="both", expand=True)
        vsb.config(command=self.text.yview)
        self._tags()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Alt-Left>", lambda _e: self.back())
        self.bind("<Alt-Right>", lambda _e: self.forward())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        center(self, parent, (1100, 720))
        self.deiconify()
        if self.pages:
            self.after(10, lambda: panes.sashpos(0, 280))
            self.goto(start if start in self.by_id else self.pages[0].id)
        else:
            self._write([("p", 0, "No help pages were found in " + str(self.folder))])
            self._buttons()

    def _tags(self):
        base = tkfont.nametofont("TkDefaultFont").actual()["size"]
        size = abs(base) + 2
        family = "Helvetica"
        t = self.text
        t.configure(font=(family, size))
        t.tag_configure("h1", font=(family, size + 8, "bold"), spacing1=4, spacing3=10)
        t.tag_configure("h2", font=(family, size + 3, "bold"), spacing1=16, spacing3=5)
        t.tag_configure("h3", font=(family, size + 1, "bold"), spacing1=10, spacing3=3, foreground="#cfe3ff")
        t.tag_configure("p", spacing1=2, spacing3=6)
        for level in range(4):
            indent = 12 + level * 22
            t.tag_configure(f"li{level}", lmargin1=indent, lmargin2=indent + 16, spacing3=3)
        t.tag_configure("note", background=DARK_BLUE, lmargin1=14, lmargin2=14, rmargin=14, spacing1=6, spacing3=10)
        t.tag_configure("code", font=("Courier", size - 1), foreground=CODE_COLOUR)
        t.tag_configure("codeblock", font=("Courier", size - 1), foreground=CODE_COLOUR, background=DARK_BLUE,
                        lmargin1=14, lmargin2=14, rmargin=14)
        t.tag_configure("b", font=(family, size, "bold"))
        t.tag_configure("i", font=(family, size, "italic"))
        t.tag_configure("link", foreground=LINK_COLOR, underline=True)
        t.tag_raise("sel")

    # --- showing a page ----------------------------------------------------------------------------------

    def _write(self, blocks):
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        for kind, level, text in blocks:
            if kind == "code":
                t.insert("end", text + "\n", "codeblock")
            elif kind in ("li", "ol"):
                mark = "•  " if kind == "li" else ""
                self._inline(mark + text, (f"li{level}",), t)
                t.insert("end", "\n")
            else:
                self._inline(text, (kind,), t)
                t.insert("end", "\n")
        t.configure(state="disabled")
        t.yview_moveto(0)

    def _inline(self, text, base, t):
        for chunk in INLINE.split(text):
            if not chunk:
                continue
            if chunk.startswith("**") and chunk.endswith("**") and len(chunk) > 4:
                self._inline(chunk[2:-2], base + ("b",), t)          # bold may hold `code`
            elif chunk.startswith("*") and chunk.endswith("*") and len(chunk) > 2:
                self._inline(chunk[1:-1], base + ("i",), t)
            elif chunk.startswith("`") and chunk.endswith("`") and len(chunk) > 2:
                t.insert("end", chunk[1:-1], base + ("code",))
            elif chunk.startswith("["):
                label, _, target = chunk[1:-1].partition("](")
                self._link(label, target, base, t)
            elif chunk.startswith("http"):
                self._link(chunk, chunk, base, t)
            else:
                t.insert("end", chunk, base)

    def _link(self, label, target, base, t):
        tag = f"link:{target}:{len(t.tag_names())}"
        t.tag_configure(tag)
        t.tag_bind(tag, "<Button-1>", lambda _e=None, to=target: self._follow(to))     # _e: Tk may send no event
        t.tag_bind(tag, "<Enter>", lambda _e=None: t.configure(cursor="hand2"))
        t.tag_bind(tag, "<Leave>", lambda _e=None: t.configure(cursor="arrow"))
        t.insert("end", label, base + ("link", tag))

    def _follow(self, target):
        if target.startswith("help:"):
            self.goto(target[5:])
        else:
            webbrowser.open(target)

    def _selected(self, _event=None):
        chosen = self.tree.selection()
        if chosen and (self.position < 0 or self.history[self.position] != chosen[0]):
            self.goto(chosen[0])

    def goto(self, page_id, remember=True):
        """Show a page: select it in the tree and write it. A link to a page that does not exist is ignored."""
        page = self.by_id.get(page_id)
        if page is None:
            return
        if remember:
            del self.history[self.position + 1:]
            if not self.history or self.history[-1] != page_id:
                self.history.append(page_id)
            self.position = len(self.history) - 1
        self.tree.selection_set(page_id)
        self.tree.see(page_id)
        path, node = [], page
        while node:
            path.append(node.title)
            node = self.by_id.get(node.parent)
        self.crumbs.set("  ›  ".join(reversed(path)) if len(path) > 1 else "")
        self._write(parse(read_page(page, self.folder)))
        self._buttons()

    def back(self):
        if self.position > 0:
            self.position -= 1
            self.goto(self.history[self.position], remember=False)

    def forward(self):
        if self.position < len(self.history) - 1:
            self.position += 1
            self.goto(self.history[self.position], remember=False)

    def _buttons(self):
        self.back_button.configure(state="normal" if self.position > 0 else "disabled")
        self.forward_button.configure(state="normal" if self.position < len(self.history) - 1 else "disabled")

    def current(self) -> str:
        return self.history[self.position] if 0 <= self.position < len(self.history) else ""
