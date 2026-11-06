"""Parser for WHDLoad archive names.

Pattern:  GameName_vVersion[_Tag]...[_ID[&ID...]].lha
  e.g.    AnstossWorldCupEdition_v1.0_AGA_De.lha
          DragonsBreath_v1.6_De_0821.lha
          XTremeRacing&DataDisks_v1.1_AGA_0164&1807.lha
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

LANGUAGES = {
    "De": "German", "Fr": "French", "It": "Italian", "Es": "Spanish",
    "Pl": "Polish", "Dk": "Danish", "Se": "Swedish", "Cz": "Czech",
    "Gr": "Greek", "Fi": "Finnish", "Nl": "Dutch",
}
DEFAULT_LANGUAGE = "English/Unspecified"

PLATFORMS = {"AGA", "CD32", "CDTV", "CD", "NTSC", "NONAGA", "A1000", "A600Pack",
             "A1200Version", "DOS"}
MEMORY_RE = re.compile(r"^\d+(KB|Kb|k|MB|Mb)(Chip)?$")
MEMORY = {"Fast", "Chip", "LowMem", "Slow", "HighDensity"}
MEDIA_RE = re.compile(r"^\dDisk$")
MEDIA = {"Image", "Files"}
VERSION_RE = re.compile(r"^[vV]\d")
ID_RE = re.compile(r"^\d{4}(&\d{4})*$")
LANG_COMBO_RE = re.compile(r"^(?:[A-Z][a-z])+$")


@dataclass
class Game:
    path: Path
    filename: str
    name: str                  # raw CamelCase name
    title: str                 # spaced for display
    version: str = ""
    ids: list = field(default_factory=list)
    languages: list = field(default_factory=list)   # codes; empty => unspecified
    platforms: list = field(default_factory=list)
    memory: list = field(default_factory=list)
    media: list = field(default_factory=list)
    other: list = field(default_factory=list)       # publishers, NoIntro, ...
    folder: str = ""
    ext: str = ""

    @property
    def language_names(self):
        return [LANGUAGES[c] for c in self.languages] or [DEFAULT_LANGUAGE]


def pretty_title(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return s.replace("&", " & ")


def _languages_from(tok: str):
    if tok in LANGUAGES:
        return [tok]
    if LANG_COMBO_RE.match(tok) and len(tok) > 2:
        parts = [tok[i:i + 2] for i in range(0, len(tok), 2)]
        if all(p in LANGUAGES for p in parts):
            return parts
    return None


def version_key(v: str):
    """Sortable key for a version string such as v1.12."""
    return [int(p) if p.isdigit() else 0 for p in re.split(r"[^0-9]+", v.lstrip("vV"))]


def parse(path: Path) -> Game:
    stem = path.stem
    toks = stem.split("_")
    vi = next((i for i, t in enumerate(toks) if i > 0 and VERSION_RE.match(t)), None)
    if vi is None:
        name, version, rest = stem, "", []
    else:
        name, version, rest = "_".join(toks[:vi]), toks[vi], toks[vi + 1:]
    g = Game(path=path, filename=path.name, name=name, title=pretty_title(name),
             version=version, folder=path.parent.name, ext=path.suffix.lstrip(".").lower())
    for t in rest:
        langs = _languages_from(t)
        if ID_RE.match(t):
            g.ids.extend(t.split("&"))
        elif langs:
            g.languages.extend(l for l in langs if l not in g.languages)
        elif t in PLATFORMS:
            g.platforms.append(t)
        elif t in MEMORY or MEMORY_RE.match(t):
            g.memory.append(t)
        elif t in MEDIA or MEDIA_RE.match(t):
            g.media.append(t)
        else:
            g.other.append(t)
    return g


def scan(root: Path):
    games = [parse(p) for p in root.rglob("*")
             if p.is_file() and p.suffix.lower() in (".lha", ".lzx", ".lzh", ".zip")]
    games.sort(key=lambda g: (g.title.lower(), g.version))
    return games
