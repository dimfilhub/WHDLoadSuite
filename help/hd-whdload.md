# WHDLoad and BetterWB in an image

> **Experimental.** This is part of [HDCommander](help:hdcommander), which is still being tested. It changes your `.hdf` image directly: work on a copy and keep a backup.

Two buttons add useful software to an image that already has Workbench 3.1: **Install WHDLoad…** and **Install BetterWB…**.

## Install WHDLoad…

Installs the official WHDLoad distribution (`WHDLoad_usr….lha`, from the WHDLoad web site or Aminet) into the image.

**What you see:** a file chooser for `WHDLoad_usr….lha` (it starts in your Downloads folder), then a question with three buttons: **With documentation**, **Without documentation** and **Cancel**.

**What it does:**

- The programs in `C/` go to `C:` (a newer version that is already there is kept).
- The three files in `S/` go to `S:` (a different existing file is kept, and the new one is saved as `<name>.default`).
- With **With documentation**, the documentation (a few MB) also goes to `Help/WHDLoad`.
- It creates `Devs/Kickstarts` and tells you which Kickstart ROM images (and matching `.RTB` files) games with Kickstart emulation need there. See [Kickstart ROMs](help:kickstarts).
- If your work folder's `Template_WHDLoad/Devs/Kickstarts` already holds Kickstart files, you are asked whether to copy them into the image (files that are already there are kept). Otherwise, copy your own into `Devs/Kickstarts` with the file manager.

## Install BetterWB…

BetterWB is an add-on for AmigaOS 3.1 with better icons, tools and datatypes. You supply its six floppy disk images.

**What you can do:**

1. Make sure the image has Workbench 3.1 (see [Making an image bootable](help:hd-boot)); otherwise the button tells you to do that first.
2. Press **Install BetterWB…** and choose the folder with the BetterWB disks as `.adf` (or `.adz`) files.
3. Confirm. You can choose **Install** or **Install with Env-Handler**; most people do not need Env-Handler.

**Disks:** `Misc3.1` is required; `Tools3.1`, `Bonus3.1`, `Docs3.1`, `Icons3.1` and `Drivers3.1` are optional (missing ones are simply not installed).

**What it does:** it repeats the steps of BetterWB's own install script: unzips the six zips over the system drive, deletes the files BetterWB makes obsolete, and sets the needed file flags. It replaces `S/Startup-Sequence`; the old one is kept as `S/Startup-Sequence.old`. It needs about 10 MB.

## Tips

- Install games afterwards: [Installing games into an image](help:hd-games).
- Running an installer again is safe: existing files are kept as described above.
