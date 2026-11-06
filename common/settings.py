import json
import os
import sys
from pathlib import Path


def settings_path():
    """Per-user settings file in the platform's usual config location."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "WHDLoadDownloader" / "settings.json"


class Settings:
    """Small JSON-backed key/value store. Missing or unreadable files just mean defaults."""

    def __init__(self, path=None):
        self.path = Path(path) if path else settings_path()
        self._data = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._data = data
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        if self._data.get(key) == value:
            return
        self._data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError:
            pass  # settings are a convenience; never break the app over them
