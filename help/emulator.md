# The emulator (Amiberry)

[Amiberry](https://github.com/BlitterStudio/amiberry) is the Amiga emulator that actually runs your games. WHDLoadSuite does not include it: you download it once and tell the app where it is.

## Where Amiberry must be

The app looks for Amiberry in this order and uses the first one it finds:

1. The folder or app you chose in **Settings > Amiberry… > Amiberry folder**.
2. The `emulator` folder next to the app.
3. **macOS:** `/Applications/Amiberry.app`, then `~/Applications/Amiberry.app`.
4. A program called `amiberry` on your `PATH`.

What to put there:

- **macOS:** the whole `Amiberry.app`, for example `emulator/Amiberry.app`.
- **Windows and Linux:** the Amiberry folder, with its program, data and libraries, for example `emulator/amiberry/`.

In **Settings > Amiberry…** you can choose the app itself, the folder that contains it, or the program file. Leave the box empty to use the list above.

## What you see when it is found

There is no message when everything is fine. Open **Settings > Amiberry…** and look at **Kickstart ROMs**: if it lists your ROMs, Amiberry was found. If it says *Amiberry not found*, the app could not find it; launching a game shows the same message.

## What the app does with it

- Games start straight from their `.lha` file: Amiberry chooses the model and memory from its own WHDLoad game database. A few games need something different and are run from a [prepared drive](help:prepared) instead.
- Your choices (keyboard joystick, window, screen look) are passed to Amiberry on its command line, so they do not change any file of your own Amiberry.
- Amiberry's update check is switched off, so a standalone program never connects to the internet when it starts.
- Several games can run at the same time. Games started from their `.lha` share one boot folder, so if you use Amiberry's reset on one game after starting another, the first game restarts as the newer one. Close it and launch it again.

## The app's own copy of Amiberry's settings

The app does **not** use the settings of your own Amiberry. It keeps a private copy in the `Amiberry` folder of your user data folder (see [Folder locations](help:locations)). It holds:

- Amiberry's settings,
- copies of your Kickstart ROMs (made automatically from `emulator/Kickstarts`),
- WHDLoad and the WHDLoad boot files, downloaded the first time you launch a game from whdload.de and Aminet (a few seconds).

So your own Amiberry is never read or changed, and the app's games never depend on how you set yours up.

In **Settings > Amiberry…** this is the **Amiberry data** row:

- **Open** shows the folder in Finder or Explorer.
- **Reset…** deletes it after a confirmation. The next launch copies your ROMs and downloads WHDLoad again. Your files in `emulator/Kickstarts`, your games and the saved games of your standalone programs are never touched. Reset is refused while a game started from this app is still open.

The **WHDLoad games** row shows the date of the game database Amiberry uses; **Update now** fetches the newest WHDLoad and database.

## Standalone programs need a complete Amiberry

When you build a standalone program, Amiberry is copied into it, so it must be a complete, self-contained copy:

- **macOS:** the whole `Amiberry.app`.
- **Windows and Linux:** the folder holding the program together with its data and libraries.

A bare program found on your `PATH`, for example a Homebrew install, can be used to play games but cannot be bundled. A standalone program only runs on the system it was built on. See [Standalone executables](help:executables).

## Tips

- If a game does not start, check the **Kickstart ROMs** panel in **Settings > Amiberry…** first. See [Kickstart ROMs](help:kickstarts).
- To use a newer Amiberry, replace the app in `emulator/` and press **Reset…** only if something misbehaves.
- More help with problems: [Troubleshooting](help:troubleshooting).
