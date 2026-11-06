# Launch screen

The launch screen is the window that appears just before a game starts, when you press **Launch in Amiberry** in the [Browser](help:browser) or **Launch to test** in the [Builder](help:builder). Standalone programs can have one too.

## What you see

- **The game's name** at the top.
- **Its picture**: a screenshot, or the front cover when there is no screenshot, enlarged by a whole number so the pixels stay sharp. A caption says which one it is. Without a picture you see *No picture for this game*.
- **Three choices**: **Keyboard joystick**, **Window** and **Screen look**.
- **Two tick boxes**: **Use these choices from now on** and **Show this screen when I launch a game**, with a hint on how to bring the screen back.
- **A note in orange** when the game needs a [prepared drive](help:prepared): it is prepared when you press Launch.
- **Two buttons**: **Launch** and **Cancel**.

## What you can do

- Change the three choices for **this launch only**: they start from your choices in **Settings > Amiberry…**.
- Tick **Use these choices from now on** to keep them as your new defaults.
- Untick **Show this screen when I launch a game** to skip the screen in future.
- Press **Launch** (or Return) to start the game, or **Cancel** (or Esc) to start nothing.

## The three choices

- **Keyboard joystick**: which keys act as the joystick on port 1.
  - Layout A: numeric keypad, 0 or 5 = fire.
  - Layout B: cursor keys, Right Ctrl or Alt = fire.
  - Layout C: W A S D, Left Alt = fire.
  - Layout D: cursor keys, Left Ctrl or Alt = fire (the default).
  - None: no keyboard joystick.
- **Window**: **Windowed**, or **Fullscreen (borderless window)** over the desktop.
- **Screen look**: **Normal**, **Scanlines**, or **CRT monitor (scanlines + 1084 look)**, which also uses Amiberry's 1084 monitor look.

## Switching it off and on

- Unticking **Show this screen when I launch a game** switches the screen off from now on.
- To switch it back on: **Settings > Amiberry… > Show a launch screen before a game starts**. It is the same switch.
- A standalone program remembers its own switch. To bring its screen back, delete `Launch/<Game>.json` in your user data folder. See [Folder locations](help:locations).

## Where the pictures come from

The pictures belong to the **GamebaseAmiga** collection, which you obtain yourself. You tell the app where it is in **Settings > Amiberry… > GamebaseAmiga folder**:

- **The `data` folder of GamebaseAmiga** (the one with `screenshots` and `extras`), or the GamebaseAmiga folder that holds it. It is only read; nothing is copied.
- **Or the original `Gamebase_Amiga_v2.3` source folder** (the one with `Screenshots.rar` and `Extras.rar`): press **Extract pictures…**. The screenshots and the front covers (about 330 MB, a few seconds) are unpacked into your user data folder and used from there. The rest of the 6 GB `Extras.rar` is skipped. **Delete extracted…** removes them again. Pressing **Extract pictures…** again replaces the earlier ones.

Extracting needs `unar` and `lsar` from The Unarchiver's command line tools:

- **macOS:** `brew install unar`.
- **Linux:** `sudo apt install unar`.
- **Windows:** download them from theunarchiver.com/command-line and unzip them into a `tools` folder next to the app, or add them to the `PATH`.

**Picture** chooses which one is shown: the screenshot, the front cover, or the screenshot with the cover as a fallback.

## How a game finds its picture

The app matches a game to Gamebase by name, using `common/gamebase_images.json`. About 3,300 of the 3,990 Retroplay archives have a picture. A game that is not in that file is looked for by name among the picture files. To make the file again for other archives:

```
python tools/make_gamebase_map.py --gamebase <GamebaseAmiga project> --downloads <archives folder>
```

## In a standalone program

If the switch is on while you build, the picture is saved inside the program as a small PNG, so the program needs no Gamebase folder afterwards. See [Standalone executables](help:executables).

## Tips

- No picture? Check the **GamebaseAmiga folder** setting; the note under it says how many screenshots and covers were found.
- Settings are described in [Amiberry settings](help:settings-amiberry).
