# HDCommander tab (experimental)

> **Experimental.** HDCommander is still being tested and may have bugs. It writes into your `.hdf` images directly, so **work on a copy** and keep a backup of any image you care about. The rest of the app does not depend on it.

The tab itself says so too: an orange bar at the top reads *EXPERIMENTAL* and the tab is called *HDCommander (experimental)*.

HDCommander is a two-pane file manager for **Amiga hard disk images** (`.hdf` files), in the style of Norton Commander. The left pane shows files on your computer, the right pane shows the inside of an image. It needs the `amitools` package (see `requirements.txt`). Images use the OFS/FFS file system, so keep them under about 4 GB.

## What you see

- **A top bar:** *Image:* with the path of the open image, then **Open…**, **New…**, **Close**, **Make bootable…**, **Install BetterWB…**, **Install WHDLoad…**, **Test in emulator** and **Quit**.
- **Two panes:** **Host** on the left (your computer, starting in the downloads folder) and **Image** on the right (the inside of the open `.hdf`). The **active pane** has an orange title bar; it is the **source** for copying and moving.
- **A button row:** **View (F3)**, **Install Game (F4)**, **Copy (F5)**, **Move (F6)**, **MkDir (F7)**, **Delete (F8)** and **Refresh**.
- **A progress bar and status line** at the bottom.

## What you can do

1. **Open or create an image:** **Open…** an existing `.hdf`, or **New…** to create one. The last image is remembered.
2. **Move around:** double-click a folder (or press Enter) to open it, double-click `..` or press Backspace to go up.
3. **Make a pane active:** click its list or its title bar.
4. **Copy files:** select rows in the active pane and press **Copy (F5)**. They are copied to the other pane.
5. **Install games:** select `.lha` archives on the left and press **Install Game (F4)**. See [Installing games into an image](help:hd-games).
6. **Make the image start:** **Make bootable…**. See [Making an image bootable](help:hd-boot).
7. **Try it:** **Test in emulator**.

## Buttons and controls

- **Open…:** opens an `.hdf` image.
- **New…:** creates an empty image; you give its file name and its size in MB (4 to the maximum). A new image is empty: it needs Workbench and a Kickstart to start, which you supply yourself.
- **Close:** closes the image.
- **Make bootable…:** installs Amiga Workbench 3.1 into the image from your original floppy disk images. See [Making an image bootable](help:hd-boot).
- **Install BetterWB…:** adds the BetterWB add-on to an image that has Workbench 3.1. See [WHDLoad and BetterWB in an image](help:hd-whdload).
- **Install WHDLoad…:** installs the official WHDLoad distribution into the image. See [WHDLoad and BetterWB in an image](help:hd-whdload).
- **Test in emulator:** starts the image in Amiberry as an Amiga 1200 with 8 MB of Fast RAM and a Kickstart 3.1 ROM from `emulator/Kickstarts`, with the choices from **Settings > Amiberry…**. The image is closed in HDCommander while the emulator runs, so both never write to it at once, and is opened again afterwards. See [Kickstart ROMs](help:kickstarts).
- **View (F3):** shows the selected file as text, or as a hex dump if it is not text.
- **Install Game (F4):** installs the selected WHDLoad `.lha` archives, or folders of them, into the image.
- **Copy (F5) / Move (F6):** copy or move the selected rows (folders too, recursively) from the active pane to the other one. Copy keeps `.lha` archives exactly as they are.
- **MkDir (F7):** creates a folder in the active pane.
- **Delete (F8):** deletes the selected rows after a confirmation. **Host files are deleted permanently.**
- **Refresh:** reads both panes again.
- **Quit:** closes the app.

The keys F3–F8 work when a file list has the focus; the buttons do the same.

## Using an image on real hardware

An image is a raw copy of a hard disk, so it can be written to an SD or CF card for a real Amiga. See [Writing an image to an SD card](help:hd-sdcard).

## Amiga rules inside an image

Names can have up to 30 characters, are case-insensitive, and may use Latin-1 characters only. Items that cannot be copied are listed in a report instead of stopping the whole job.

## Tips

- Source and destination are always "active pane" and "the other pane". The title bar of the active pane is orange, as a reminder.
- Images work in other Amiga emulators and on real hardware as well.
- Problems? See [Troubleshooting](help:troubleshooting).
