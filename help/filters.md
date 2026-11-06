# Download filters

The filters decide which files are fetched from the folders you ticked in the [Downloader](help:downloader). You open them with **Filters…**.

## What you see

A window with:

- **Search**, **Latest version only** and **Only entries without ID** at the top.
- **Check lists** for **Language**, **Platform**, **Memory**, **Media** and **Other tags**, each value with a count of the files that have it.
- **A summary** of how many files, and how many bytes, the filters keep.
- **Three buttons**: **Clear filters**, **Apply** and **Close**.

## What you can do

- Type in **Search** to keep only titles and file names that match.
- Tick **Latest version only** to keep just the newest version of each game variant.
- Tick **Only entries without ID** to keep archives whose name has no ID number.
- Tick values in a list. Several values in one list match **any** of them; different lists must **all** match.
- The summary updates as you change things, so you can see the effect before you apply it.

## Buttons

- **Apply:** saves the filters. The Downloader's button then reads **Filters (on)…**.
- **Clear filters:** unticks everything and empties the search.
- **Close:** closes the window without applying changes you did not apply.

## What is filtered

- The filters apply only to the files found **inside ticked folders**. A file you tick yourself is always downloaded.
- Only matching files are transferred. The folder contents are listed once and reused, so filtering adds no extra FTP calls.

## Tips

- The names of the files follow one convention, such as `Game_v1.2_AGA_De_2MB_Disk2_1234.lha`. The filters read it into title, version, language, platform, memory, media, other tags and ID. The [Browser](help:browser) filters the same way.
