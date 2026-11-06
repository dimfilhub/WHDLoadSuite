# Command line

Everything the Builder does can also be done from a terminal with `builder.py`, for example in a script. The choices you made in **Settings > Amiberry…** (joystick, window, screen look, launch screen, pictures) are used.

## Commands

```
python builder.py [games ...] [--work-dir DIR] [--force]
python builder.py GAME --launch [--amiberry-dir DIR]
python builder.py GAME [GAME ...] --bundle
```

- **Prepare drives by hand:** the first form prepares the drives of the games that match the names. Normally this is automatic. `--force` rebuilds a drive that already exists.
- **Launch a game:** `--launch` starts one game in Amiberry. Give the whole name if more than one archive matches.
- **Build executables:** `--bundle` builds a standalone program for every game you name (names are required). It gives them a launch screen, with the picture, when that is switched on in the settings.

## Options

- **`games ...`:** names to match against the archives in `<work>/downloads`, including sub-folders. With none, every archive is used (not for `--bundle`).
- **`--work-dir DIR`:** the work folder (default `work/` next to the app).
- **`--amiberry-dir DIR`:** the folder with Amiberry, for `--launch` and `--bundle`. Default: `emulator/`, then the usual install places.
- **`python builder.py --help`:** lists everything.

## Tips

- The app itself starts with `python gui.py`, or with the start script for your system: `start_macos.command`, `start_windows.bat` or `start_linux.sh`. The script creates a `.venv`, installs the requirements and opens the window.
- Kickstart ROMs and game archives are copyrighted; you must supply your own.
