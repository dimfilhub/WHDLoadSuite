# Kickstart ROMs

The **Kickstart** is the Amiga's built-in system software. Every Amiga game needs one to run in an emulator, and each Amiga model used a different version. Kickstart ROMs are copyrighted and are **not included**: you must supply your own, from your own Amiga or a legal source. You are responsible for having the right to use them, and **you may not pass them on** to others (this includes inside a standalone program you share). See the [Legal notice](help:legal).

## Which ones do you need?

- **Kickstart 3.1 for the A1200** (rev 40.68): needed for almost everything, and the one used for prepared drives and hard disk images.
- **Kickstart 1.3** (rev 34.5): for the many older games that need the original A500.
- A game that needs another version, for example **1.2** or **2.04**, says so on screen when you start it. Add that ROM and try again.

Most users get by with 1.3 and 3.1 A1200.

## Where to put them

Put the ROM files in **`emulator/Kickstarts`**, next to the app. Rules for the files:

- The name must end in **`.rom`** (any other file in that folder is ignored).
- For the file used by prepared drives and hard disk images, the name must contain **`A1200`**, for example `Kickstart v3.1 rev 40.68 (1993)(Commodore)(A1200).rom`.
- Use original, unmodified dumps. Amiberry recognises a ROM by its **content**, not its name; a modified or wrongly dumped file is silently ignored.

## What the app does with them

Whenever you launch or build a game, the app copies any ROM in `emulator/Kickstarts` that its own Amiberry folder does not have yet into the app's private copy of Amiberry's settings (see [The emulator (Amiberry)](help:emulator)). Existing files are never replaced. When you build a [standalone program](help:executables), the ROMs are copied into it, so it runs without your `emulator` folder.

## Checking that Amiberry accepts them

Open **Settings > Amiberry…** and look at the **Kickstart ROMs** panel:

- **✔ Kickstart v1.3 …** the ROM was recognised and the file is there.
- **✘ … the file is missing** Amiberry knew the ROM, but the file is gone.
- **✘ … not a known Kickstart dump: Amiberry ignores it** the file is not an original dump; replace it.
- A note says when you have no **Kickstart 3.1 for the A500/A600**. Games that prefer one then run as an A1200 instead, and most still work.

The panel is filled in after the first launch, when Amiberry has scanned the ROMs. Press **Refresh** to read it again.

## Kickstart files for WHDLoad itself

Prepared drives and hard disk images run WHDLoad directly, and some games use a *Kickstart emulation*. For those, WHDLoad looks in **`Devs/Kickstarts`** on the drive and identifies the ROMs by **file name**:

```
File name          Kickstart                 Size
kick33180.A500     1.2  (rev 33.180)         256 KB
kick34005.A500     1.3  (rev 34.5)           256 KB
kick37175.A500     2.04 (rev 37.175)         512 KB
kick37350.A600     2.05 (rev 37.350)         512 KB
kick40063.A600     3.1  (rev 40.63)          512 KB
kick39106.A1200    3.0  (rev 39.106)         512 KB
kick40068.A1200    3.1  (rev 40.68)          512 KB
kick40068.A4000    3.1  (rev 40.68, A4000)   512 KB
```

- For prepared drives, put these files in `work/Template_WHDLoad/Devs/Kickstarts`; they are copied into each prepared game.
- For hard disk images, **Install WHDLoad…** in [HDCommander](help:hd-whdload) creates `Devs/Kickstarts` in the image and offers to copy the files from the template folder.
- Use the exact upper and lower case shown. Which file a game needs is decided by the game. If WHDLoad reports a missing Kickstart, add the file it names.
- ROMs from Cloanto's Amiga Forever are encrypted (they need a `rom.key`): decrypt them first or use unencrypted dumps.

> **Games started from their `.lha`** do not use `Devs/Kickstarts`: Amiberry handles Kickstart for them itself, with the ROMs in `emulator/Kickstarts`. The files above only matter for prepared drives and hard disk images.

## Tips

- **A game says it needs Kickstart x.y:** add that ROM to `emulator/Kickstarts` and launch the game again.
- **The panel shows ✘ for a file you just added:** the dump is not original, or the file is damaged.
- More help: [Troubleshooting](help:troubleshooting).
