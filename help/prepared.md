# Prepared drives

Almost every game runs straight from its `.lha` archive: Amiberry sets up the model and the memory itself. A **prepared drive** is a folder that looks like an Amiga hard disk with the game already installed on it, started with WHDLoad. Only a few games need one: for example a game that writes into its own folder (and so cannot run from a read-only archive), or a game that hangs without a prepared drive.

## Which games need one

The list is in `common/amiberry_overrides.json`. The same file can also give a game extra hardware, for example 16 MB of Zorro III RAM for Super Silly Skidmarks.

## What happens automatically

You never prepare a drive by hand. The first time you **Launch** or **Build** such a game, the app:

1. copies `work/Template_WHDLoad` to `work/Whdload/<letter>/<Game>/`,
2. unpacks the game on top of it, and
3. rewrites `S/Startup-Sequence` so that it starts the game's slave file with WHDLoad.

It tells you before it does this (on the [launch screen](help:launch-screen), or in a question if the launch screen is switched off), and you can cancel.

## What you see

- In the Browser and the Builder, a game that needs a drive is **orange** until it has one, then **green**.
- A prepared drive runs with Kickstart 3.1 for the A1200, from `emulator/Kickstarts`. See [Kickstart ROMs](help:kickstarts).

## What you can do

- **Clear Prepared** (Builder tab) deletes all prepared drives, for example after you changed `Template_WHDLoad`. They are made again when needed.
- The prepared folder can be moved: **Settings > Builder… > Prepared (Whdload) folder**.

## The template

`work/Template_WHDLoad` must contain `C/WHDLoad`, `S/Startup-Sequence` and `Devs/Kickstarts`. Put the WHDLoad Kickstart files in `Devs/Kickstarts` as described in [Kickstart ROMs](help:kickstarts).

## Tips

- A standalone program for a drive game contains its prepared drive. The program makes a writable copy for its saves in the `Games` folder of your user data. See [Standalone executables](help:executables).
