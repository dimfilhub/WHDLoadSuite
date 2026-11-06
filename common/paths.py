"""Where things live in the project: the folder that holds gui.py and builder.py."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORK_DIR = PROJECT_ROOT / "work"
EMULATOR_DIR = PROJECT_ROOT / "emulator"          # Amiberry (and the user's Kickstarts/ ROMs)
SETTINGS_FILE = PROJECT_ROOT / ".whdloadsuite.json"  # the Builder tab's folders, next to the app
