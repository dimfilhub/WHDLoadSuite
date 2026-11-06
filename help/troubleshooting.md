# Troubleshooting

## A game does not start

- **"Amiberry not found."** Put Amiberry in the `emulator` folder, or choose it in **Settings > Amiberry… > Amiberry folder**. See [The emulator (Amiberry)](help:emulator).
- **The emulator opens and complains about a ROM.** A Kickstart is missing. Check **Settings > Amiberry… > Kickstart ROMs**. See [Kickstart ROMs](help:kickstarts).
- **"Could not download WHDLoad."** The first launch downloads WHDLoad from whdload.de and Aminet; it needs the internet. Try **Update now** in **Settings > Amiberry…** later.
- **"Select exactly one game."** **Launch in Amiberry** needs one selected row; **Launch to test** needs exactly one ticked game.
- **"X runs from a prepared drive: prepare it first."** It is normally prepared automatically. If it is not, check that `work/Template_WHDLoad` is complete. See [Prepared drives](help:prepared).
- **A game restarts when I start another.** Games started from their `.lha` share one boot folder. See [The emulator (Amiberry)](help:emulator).

## The ROM panel shows a ✘

- **"the file is missing"**: the file was removed; add it again.
- **"not a known Kickstart dump"**: the file is not an original ROM; Amiberry ignores it. See [Kickstart ROMs](help:kickstarts).

## The launch screen has no picture

- Check **Settings > Amiberry… > GamebaseAmiga folder**. The note under it should say how many screenshots and covers were found.
- A game that is not in Gamebase, or whose name differs, has no picture. See [Launch screen](help:launch-screen).
- **"unar not found"** when extracting: install The Unarchiver's command line tools. See [Launch screen](help:launch-screen).

## Building a standalone program fails

- **"PyInstaller is not installed."** Run `pip install -r requirements.txt` in the app's `.venv`.
- **"Amiberry not found."** See above. A bare program from your `PATH` cannot be bundled; you need a complete copy. See [Standalone executables](help:executables).
- A program only runs on the kind of computer it was built on.

## The Browser or the Builder is empty

The downloads folder is empty or wrong. Check **Settings > Browser…**, or download games with the [Downloader](help:downloader). See [Folder locations](help:locations).

## HDCommander (experimental)

HDCommander is still being tested, so it can have bugs. Work on a **copy** of your `.hdf` images and keep a backup; if something goes wrong, open the backup instead.


- **"Workbench needed"** when installing BetterWB: use **Make bootable…** first. See [Making an image bootable](help:hd-boot).
- **"Disks not found":** the folder must contain the disks as `.adf` or `.adz` files; they are recognised by their disk names, not their file names.
- Images over about 4 GB are not supported.

## Starting over

- **Reset the app's Amiberry data:** **Settings > Amiberry… > Amiberry data > Reset…**.
- **Delete prepared drives:** **Clear Prepared** in the Builder.
- **Delete saved games:** **Settings > Amiberry… > Saved games > Delete…**.
- **Forget all settings:** delete `.whdloadsuite.json` in the app's folder.

## Legal questions

See the [Legal notice](help:legal): what you may and may not share, and what is your responsibility.

## Windows and Linux

The app was developed and tested on macOS. The Windows and Linux paths are written but have not been tested, so please report anything that does not work.
