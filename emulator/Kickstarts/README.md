# Kickstarts

Put your Kickstart ROM files in this folder, with the extension `.rom`. They are copyrighted and are not included in the repository.

## What the app does with them

The first time a game is launched, the app copies every `.rom` file from this folder into its own Amiberry folder (the
**Amiberry data** row in **Settings > Amiberry…** shows where). Your files here are never changed. A ROM is copied only
if the app's folder does not have one of that name yet, so **a file you replace or fix here is not copied again**: use
**Reset…** next to **Amiberry data** (it is set up again on the next launch), or save the file under a new name.
Deleting a file here does not delete the app's copy either.

## Checking them: Settings > Amiberry… > Kickstart ROMs

The **Kickstart ROMs** panel shows what Amiberry made of your files. It fills in after Amiberry has run once; until then it
says to launch a game and press **Refresh**.

| Line | Meaning |
|------|---------|
| `✔ Kickstart v1.3 (A500,A1000,A2000) rev 34.5   <file>` | Amiberry recognised the ROM and can use it |
| `✘ <file>   not a known Kickstart dump: Amiberry ignores it` | the file is not an original, unmodified dump; Amiberry ignores it without any message |
| `✘ … (the file is missing)` | Amiberry remembers the ROM, but the file is gone |
| `No Kickstart 3.1 for the A500/A600 …` | games that prefer an A500/A600 ROM run as an A1200 instead; most still work |

Amiberry recognises a ROM by its content, never by its name, so renaming a file cannot make it work. A file shown with ✘ is
usually a bad, over-sized or modified dump, or an encrypted one (for example from Amiga Forever, which needs its `rom.key`
to decrypt first). Replace it with an original dump, then **Reset…** as described above, launch a game and press **Refresh**.

## Which ROMs are used for what

| ROM | Used for |
|-----|----------|
| Kickstart 3.1 (A1200), for example `Kickstart v3.1 rev 40.68 (1993)(Commodore)(A1200).rom` | prepared drives and **Test image** in HDCommander (a file name containing `A1200` is picked) |
| Kickstart 1.3 (A500) and 3.1 (A500/A600) | many older games, chosen by Amiberry from its game database |
| Kickstart 1.2 (A500) | games that ask for it (for example UpScope) |

A game that needs a ROM you do not have says so on the Amiga screen (for example a missing `kick33180.A500`).

The ROMs WHDLoad itself needs for prepared drives are separate: see `work/Template_WHDLoad/Devs/Kickstarts/`.

The rest of `emulator/` (Amiberry, ...) is git-ignored; see the main README.
