# Amiberry settings

**Settings > Amiberry…** is where the emulator is set up and where you choose how games start. The window has two columns.

## Left column: Amiberry and its data

### Amiberry folder

- **What you see:** a box for a path, a **Browse…** button and a note.
- **What you can do:** choose the Amiberry app or the folder that contains it. Leave it **empty** to use the `emulator` folder, then the usual install places. See [The emulator (Amiberry)](help:emulator).

### Amiberry data

- **What you see:** the folder where the app keeps its own copy of Amiberry's settings, ROMs and WHDLoad, and how much space it uses.
- **Open:** shows the folder in Finder or Explorer.
- **Reset…:** deletes the folder after a confirmation. The next launch sets it up again, copying your ROMs and downloading WHDLoad again. Your `emulator/Kickstarts` files, your games and the saved games of your standalone programs are not touched. Refused while a game started from this app is open.

### Saved games

- **What you see:** the `Games` folder, how many games it holds and its size. These are the writable copies your standalone programs make of their games, with their saves and high scores.
- **Open:** shows the folder.
- **Delete…:** deletes all of them after a warning. They cannot be brought back; each program makes a new copy the next time it runs. Close any standalone program that is running first. **Clear Prepared** and **Reset…** never touch this folder.

### Kickstart ROMs

- **What you see:** a panel listing which ROMs Amiberry recognised (✔) and which files it ignores (✘). It is filled in after your first launch.
- **Refresh:** reads it again. See [Kickstart ROMs](help:kickstarts).

### WHDLoad games

- **What you see:** how many games the database Amiberry uses knows, and its date.
- **Update now:** fetches the newest WHDLoad and database from whdload.de and Aminet. It takes a few seconds. Refused while a game is running.

## Right column: how a game starts

### Launch choices

- **Keyboard joystick:** which keys act as the joystick on port 1. Layouts A, B, C, D or **None**. See [Launch screen](help:launch-screen) for the layouts.
- **Window:** **Windowed**, or **Fullscreen (borderless window)**.
- **Screen look:** **Normal**, **Scanlines** or **CRT monitor (scanlines + 1084 look)**.
- **Close Amiberry when the game exits:** closes the emulator when the WHDLoad game ends.
- **Show the WHDLoad splash screen:** keeps WHDLoad's short information screen before a game.

These apply to every game you launch from now on and are built into the executables you build from now on. The last two only apply to games that start from their `.lha`.

### Launch screen

- **Show a launch screen before a game starts:** switches the [launch screen](help:launch-screen) on or off. It is also switched off from the launch screen itself, and this is where to turn it back on.
- **Picture:** **Screenshot, else front cover** (the default), **Screenshot only** or **Front cover only**.
- **GamebaseAmiga folder:** where the pictures come from. **Browse…** chooses the `data` folder of GamebaseAmiga, or the original `Gamebase_Amiga_v2.3` source folder. A note says what was found.
- **Extract pictures…:** shown when the folder is the original source. Unpacks the screenshots and front covers (about 330 MB) into your user data folder, with a progress note. Needs `unar`.
- **Delete extracted…:** shown when extracted pictures exist. Deletes them after asking; your source folder is never touched.

## Tips

- If a game will not start, the **Kickstart ROMs** panel is the first place to look. See [Troubleshooting](help:troubleshooting).
