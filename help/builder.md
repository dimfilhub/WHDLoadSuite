# Builder tab

The Builder tests games and builds standalone programs from them. It works on the archives in the downloads folder.

## What you see

- **A top row** with how many archives were found, how many are ticked, a **Select all** tick box and the buttons **Clear selection** and **Refresh list**.
- **The archive list**, titled *Archives (select the ones to launch or build)*. Games are grouped by their first letter. Each row has a box in front of it: ☐ not ticked, ☑ ticked, and for a letter ⊟ when only some of its games are ticked.
- **A progress bar**, then a **Log** line with the current status, and a colour legend: *Needs preparation*, *Prepared*, *Executable built*.
- **The log** itself: what happened to each game.
- **Four buttons** at the bottom: **Launch to test**, **Build App** (macOS) or **Build Exe** (Windows and Linux), **Clear Prepared** and **Quit**.

## What you can do

1. **Tick games.** Click a row to tick or untick it. Click a letter to tick all its games. The small arrow opens or closes a letter.
2. **Test one.** Tick exactly one game and press **Launch to test**.
3. **Build.** Tick any number of games and press **Build App** or **Build Exe**. The log shows each result and the progress bar fills as games finish.
4. **Start fresh.** Press **Clear Prepared** to delete the prepared drives.

## Buttons and controls

- **Select all:** ticks every archive (or unticks them all).
- **Clear selection:** unticks everything.
- **Refresh list:** scans the downloads folder again. Your ticks and open letters are kept.
- **Launch to test:** starts the one ticked game in Amiberry, straight from its `.lha` file. With nothing ticked, or more than one, a message asks you to tick exactly one. The first launch downloads WHDLoad. The [launch screen](help:launch-screen) comes first.
- **Build App / Build Exe:** builds a standalone program of each ticked game in the Executables folder (see [Standalone executables](help:executables)). It needs a complete Amiberry. Games that need a [prepared drive](help:prepared) are prepared as part of the build, and the log says so.
- **Clear Prepared:** deletes the prepared drives in the `Whdload` folder, after a warning (for example after changing `Template_WHDLoad`). They are made again whenever needed. Your downloads, your executables and the saved games of your standalone programs are not touched.
- **Quit:** closes the app (it asks first if a job is still running).

## What the colours mean

- **Orange:** the game needs a prepared drive and has none yet.
- **Green:** it has one.
- **Blue:** a standalone program was built.
- **No colour:** the game needs nothing; it runs straight from its `.lha`.

## Tips

- The folders used here (work, prepared games, executables) are chosen in **Settings > Builder…**. See [Folder locations](help:locations).
- The Browser can send a selection here: **Send to Builder**. See [Browser tab](help:browser).
- You can also do all this from a terminal. See [Command line](help:commandline).
