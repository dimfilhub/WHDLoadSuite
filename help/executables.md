# Standalone executables

A **standalone executable** is one program that contains Amiberry, WHDLoad, one game and your Kickstart ROMs. You double-click it and the game starts; nothing else needs to be installed. On macOS it is a `.app`, on Windows an `.exe`, on Linux a program file.

> **Sharing is your responsibility.** A standalone program contains a copy of the game and your Kickstart ROMs. Giving it to others, or uploading or selling it, is redistribution of copyrighted material, and that is solely your responsibility. See the [Legal notice](help:legal).

## How to build one

1. Put Amiberry in `emulator/` (a complete copy, see [The emulator (Amiberry)](help:emulator)) and your ROMs in `emulator/Kickstarts`.
2. In the [Builder tab](help:builder), tick the games.
3. Press **Build App** (macOS) or **Build Exe** (Windows, Linux).
4. Find the results in the Executables folder, in `A`–`Z`, `0-9` or `#` sub-folders: `Executables/A/Alien_v1.0.app`.

You need PyInstaller for this (`pip install -r requirements.txt`).

## What is inside, and how big

- The game's `.lha`, Amiberry, WHDLoad and your Kickstart ROMs: about 60 MB.
- The [launch screen](help:launch-screen) adds about 3 MB (it needs Tk).
- The icon is `images/icon.png`, or `work/Icons/<Game>.icns`/`.ico`/`.png` for one game.

## What happens when you start one

1. If the launch screen is included, it opens first. See below.
2. The first time, the program copies your ROMs and WHDLoad into the app's data folder, then starts Amiberry.
3. Saves are kept in your user data folder (`Games/<Game>`), not inside the program. See [Folder locations](help:locations).

## The launch screen in an executable

If **Show a launch screen before a game starts** was on when you built it (**Settings > Amiberry…**), the program opens the [launch screen](help:launch-screen) with the game's picture. It starts from the choices it was built with. **Use these choices from now on** and **Show this screen when I launch a game** are remembered for that one program. To bring a switched-off screen back, delete `Launch/<Game>.json` in your user data folder.

## Limits

- An executable only runs on the **kind of computer it was built on**: build on macOS for macOS, on Windows for Windows, on Linux for Linux.
- Amiberry must be a complete, self-contained copy; a bare program from your `PATH` cannot be bundled.
- Games that need a [prepared drive](help:prepared) are prepared automatically when you build them.

## Tips

- Several executables can run at the same time.
- Rebuild an executable to include the launch screen or a new picture.
- To delete saves: **Settings > Amiberry… > Saved games > Delete…**. See [Amiberry settings](help:settings-amiberry).
