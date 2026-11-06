# Installing games into an image

> **Experimental.** This is part of [HDCommander](help:hdcommander), which is still being tested. It changes your `.hdf` image directly: work on a copy and keep a backup.

**Install Game (F4)** puts WHDLoad games into the open hard disk image, ready to start from Workbench with WHDLoad.

## What you see

On the **Host** pane (left) you select `.lha` WHDLoad archives, or folders that contain them. The **Image** pane (right) shows the image.

## What you can do

1. Open or create an image (see [HDCommander tab](help:hdcommander)).
2. On the left, select the archives, or folders of archives. Several at once is fine.
3. Press **Install Game (F4)**.
4. Wait for the progress bar; a report lists what was installed and what was skipped.

## What it does

- Each game goes under `Games/<A-Z|0-9|#>/<Game>/` in the image.
- A game that is already there is **skipped**.
- Archives without a WHDLoad slave file are reported as skipped.
- Other files in a selected folder are ignored.

## What you need in the image for the games to start

- **Workbench 3.1** and a way to boot: see [Making an image bootable](help:hd-boot).
- **WHDLoad** itself: see [WHDLoad and BetterWB in an image](help:hd-whdload).
- **Kickstart files** for games that use a Kickstart emulation, in `Devs/Kickstarts`: see [Kickstart ROMs](help:kickstarts).

## Tips

- To copy any other file exactly as it is (an `.lha` too), use **Copy (F5)** instead.
- **Test in emulator** starts the image in Amiberry so you can check that a game runs.
