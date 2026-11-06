# Folder locations

WHDLoadSuite uses folders in three places: the **project folder** (where the app is), the **work folder** (your games and results), and your **user data folder** (the app's private data). Every folder you can change is changed in the [Settings windows](help:settings).

## The project folder

This is the folder that holds `gui.py`. Inside it:

- **`emulator/`**: Amiberry and your Kickstart ROMs. See [The emulator (Amiberry)](help:emulator) and [Kickstart ROMs](help:kickstarts).
  - `emulator/Amiberry.app` on macOS, or an `amiberry` folder on Windows and Linux: the emulator itself.
  - `emulator/Kickstarts/`: your Kickstart ROM files.
- **`work/`**: the default work folder (see below).
- **`images/icon.png`**: the picture used as the icon of every standalone program you build.
- **`help/`**: the pages of this Help.
- **`.whdloadsuite.json`**: the app's saved settings (the folders you chose, the Amiberry choices, the launch screen choices). Delete it to go back to the defaults.
- **`common/amiberry_overrides.json`**: the few games that need special treatment, for example games that must run from a [prepared drive](help:prepared).

## The work folder

The default is `work/` next to the app. Change it in **Settings > Builder…**. Inside it:

- **`downloads/`**: the **downloads folder**, where your `.lha` archives live. The Browser lists it, the Builder builds from it, the Downloader saves into it and HDCommander starts in it. Change it in **Settings > Browser…**. It may contain sub-folders; the app looks inside them too.
- **`Template_WHDLoad/`**: a base Amiga drive copied for every prepared game. It needs `C/WHDLoad`, `S/Startup-Sequence` and `Devs/Kickstarts`. The repository includes only `S/Startup-Sequence`: copy the `WHDLoad` executable into `C/` yourself. Only the few games that run from a prepared drive use it.
  - `Template_WHDLoad/Devs/Kickstarts/` holds the Kickstart files for WHDLoad's own use, named like `kick34005.A500`. See [Kickstart ROMs](help:kickstarts).
- **`Whdload/`**: the **prepared drives**, in sub-folders `A`–`Z`, `0-9` and `#`, one folder per game. Made automatically when needed; **Clear Prepared** deletes them. Change the folder in **Settings > Builder…**.
- **`Executables/`**: the standalone programs you build, in the same `A`–`Z`, `0-9`, `#` sub-folders. Change the folder in **Settings > Builder…**.
- **`Icons/`**: optional icons for individual games, named after the archive, like `Alien.icns`. Games without one use `images/icon.png`.

Other folders you may see in `work/` (`Cache`, `Data`, `Hard Drives` and so on) are placeholders and are not used.

> Output is named after the archive without `.lha`, so every version of a game keeps its own results.

## Your user data folder

The app keeps its private data here, apart from any Amiberry of your own:

- **macOS:** `~/Library/Application Support/WHDLoadSuite`
- **Windows:** `%APPDATA%\WHDLoadSuite`
- **Linux:** `~/.local/share/WHDLoadSuite`

It contains:

- **`Amiberry/`**: the app's own Amiberry settings, copies of your Kickstart ROMs and the downloaded WHDLoad. On macOS and Linux this folder even holds Amiberry's small settings file, so your own Amiberry is never read or changed. **Settings > Amiberry… > Amiberry data > Reset…** deletes it; the next launch sets it up again.
- **`Games/`**: the **saved games** of your standalone programs: each program makes its own writable copy of a prepared game here the first time it runs. **Settings > Amiberry… > Saved games > Delete…** removes them. **Reset** and **Clear Prepared** never touch it.
- **`Gamebase/`**: pictures extracted for the [launch screen](help:launch-screen), if you used **Extract pictures…**. **Delete extracted…** removes them.
- **`Launch/`**: what each standalone program remembers about its own launch screen.

## Folders you point to

- **The Amiberry folder** (**Settings > Amiberry…**): leave it empty to use `emulator/`, or choose another place. See [The emulator (Amiberry)](help:emulator).
- **The GamebaseAmiga folder** (**Settings > Amiberry…**): where the launch screen's pictures come from. It is only read. See [Launch screen](help:launch-screen).
- **The Downloader and HDCommander** remember their own small things (the FTP login, the last image) in a separate per-user settings file.

## Which folders can I change?

- **Settings > Browser…**: the downloads folder.
- **Settings > Builder…**: the work folder, the prepared-games folder and the executables folder. The last two follow the work folder while they are still at their defaults.
- **Settings > Amiberry…**: the Amiberry folder and the GamebaseAmiga folder.
