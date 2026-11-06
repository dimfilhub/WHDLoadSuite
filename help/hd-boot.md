# Making an image bootable

> **Experimental.** This is part of [HDCommander](help:hdcommander), which is still being tested. It changes your `.hdf` image directly: work on a copy and keep a backup.

A new `.hdf` image is empty. **Make bootable…** installs **Amiga Workbench 3.1** into it from your original floppy disks, so the image can start on its own. Workbench is copyrighted: you must supply the disks, as `.adf` (or `.adz`) disk image files.

## What you see

A folder chooser (it starts in the folder you used last, or `emulator/Floppies`), then a list of the disks found and a question with three buttons: **Install (PAL)**, **Install (NTSC)** and **Cancel**.

## What you can do

1. Open an image (or create one with **New…**).
2. Press **Make bootable…** and choose the folder that holds your disk files.
3. Choose **Install (PAL)** for Europe or **Install (NTSC)** for America and Japan. The progress bar shows the steps.
4. Press **Test in emulator** to check that it starts.

## Which disks are needed

The disks are recognised by their **disk names**, not their file names:

- **Required:** `Workbench3.1` and `Install3.1`.
- **Optional:** `Extras3.1`, `Locale`, `Fonts` and `Storage3.1`.

## What it does

It repeats the steps of the official Install3.1 Installer script without needing an Amiga: Workbench to the root of the image, Extras merged in, Locale, Fonts and Storage into their drawers, and the hard-disk `Startup-Sequence`. It also activates the PAL or NTSC monitor driver you chose. An existing startup script is kept as `S/Startup-Sequence.old`.

## Tips

- When the image is ready, you can write it to an SD card: [Writing an image to an SD card](help:hd-sdcard).
- After this, add WHDLoad: [WHDLoad and BetterWB in an image](help:hd-whdload), then your games: [Installing games into an image](help:hd-games).
- **Test in emulator** needs a Kickstart 3.1 A1200 ROM in `emulator/Kickstarts`. See [Kickstart ROMs](help:kickstarts).
