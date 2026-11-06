# Writing an image to an SD card

A `.hdf` made with HDCommander is a raw copy of an Amiga hard disk: a partition table and one bootable FFS partition. That means you can write it, byte for byte, onto an SD or CF card and use the card as the hard disk of a real Amiga.

> **Experimental, and not tested on real hardware.** HDCommander is still being tested, and the steps below describe how it should work. Try it with a spare card and keep a copy of the `.hdf`. Writing to the wrong disk erases it.

## Before you write

1. **Finish the image first.** Make it bootable with **Make bootable…**, add WHDLoad with **Install WHDLoad…**, and install your games. See [Making an image bootable](help:hd-boot), [WHDLoad and BetterWB in an image](help:hd-whdload) and [Installing games into an image](help:hd-games).
2. **Check that the image fits the card.** The card must be at least as big as the image. If it is bigger, the rest is simply unused; you can partition it later on the Amiga.
3. **Keep the image under about 4 GB.** That is the size limit of the app, because Kickstart 3.1 on real hardware wants partitions under about 4 GB.
4. **Close the image** in HDCommander (**Close**) so nothing is still writing to it.

## Writing it

Use a tool that writes a disk image to a raw device:

- **macOS or Linux:** balenaEtcher, or the `dd` command.
- **Windows:** balenaEtcher or Win32DiskImager.

Choose the `.hdf` file as the image and your **card** as the target. Check the target carefully: the tool replaces everything on it.

## What your Amiga needs

- **A way to see the card as a hard disk:** an IDE-to-CF/SD adapter in an A1200, A600 or A4000, an accelerator or controller with an SD slot, or an FPGA board with a card reader. The PCMCIA slot of an A600 or A1200 does not boot an image like this.
- **Kickstart 2.0 or newer.** Kickstart 1.3 cannot boot from a hard disk.
- **Kickstart files for WHDLoad** in `Devs/Kickstarts` inside the image, for games that use a Kickstart emulation. See [Kickstart ROMs](help:kickstarts). They are copyrighted: see the [Legal notice](help:legal).

## If it does not work

- Some machines and adapters are fussy about the disk geometry stored in the partition table. This is the most likely cause if the card is not seen or does not boot.
- Try **Test in emulator** first: if the image does not start there, it will not start on the card either. See [HDCommander tab](help:hdcommander).
- Problems with the image itself: [Troubleshooting](help:troubleshooting).

## Machines that do not need a card written

On a MiSTer, a PiStorm and similar systems you normally copy the `.hdf` onto the card as an ordinary file, and the machine mounts it. No imaging tool is needed.
