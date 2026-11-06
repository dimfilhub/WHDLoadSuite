# Downloader

A small Tkinter GUI for browsing and downloading the `/Retroplay WHDLoad Packs` folder
on the grandis.nu FTP server.

## Features

- Browse the remote folder tree lazily, with tri-state checkboxes for files and folders
- Live total size of the selection (folders are measured in the background)
- Files already in your download folder show in green, missing ones in red (when browsing a folder)
- Optional download filters (language, platform, memory, media, tags, latest version) so only matching files are fetched
- Per-file and overall progress bars
- Skips files that already exist locally with the same size
- Cancel at any time; partial files are removed
- Optional FTPS (TLS)

## Requirements

Python 3.9+ with Tkinter. There are no third-party dependencies.

Tkinter is included with the python.org installers for Windows and macOS. On Debian/Ubuntu it is a separate package: `sudo apt install python3-tk`.

## Usage

macOS and Linux:

```
python3 whdload_downloader.py
```

Windows:

```
py whdload_downloader.py
```

1. The free account uses username `ftp` and password `ftp` (pre-filled). Click **Connect**.
2. Open folders with the arrow to browse them. Click a row or press Space to tick it; ticking a folder ticks everything inside it.
3. The total size of the selection is shown next to the buttons. Folder sizes are measured in the background.
4. Optional: click **Filters…** to download only some of the files inside the ticked folders (see below).
5. Choose the destination folder with **Browse...** and click **Download selected**.
6. Watch the top bar for the current file and the bar below it for the overall progress. Click **Cancel** to stop; the partly downloaded file is removed.

**Filters…** opens a window like the Browser tab's filter panel, built from the files in the ticked folders: **Search**, **Latest version only**, **Only entries without ID**, and check lists for **Language**, **Platform**, **Memory**, **Media** and **Other tags**, each with a count. Several values in one list match any of them; different lists must all match. The window shows how many files and how many bytes the filters keep, and **Apply** saves them (the button reads **Filters (on)…** while active). The filters apply only to files found inside ticked folders; a file you tick yourself is always downloaded. Folder contents are listed once and reused for the preview and the download, so filtering adds no extra FTP calls, and only matching files are transferred.

Downloads mirror the server layout: a file at `<server root>/Games/A/file.lha` is saved as `<destination>/Games/A/file.lha`. Green files are already there with the expected size; red ones are missing or incomplete.

Files that already exist in the destination with the same size are skipped, so an interrupted download can simply be started again.

## Project layout

| Path | Purpose |
|---|---|
| `tabs/downloader/tab.py` | The tab: wiring between widgets and workers |
| `tabs/downloader/widgets.py` | Connection form, checkbox tree, action bar, progress bars |
| `tabs/downloader/ftp.py` | `FtpSession`, `Credentials`, `RemoteNode` |
| `tabs/downloader/downloader.py` | Background downloader |
| `tabs/downloader/sizing.py` | Background folder-size measurement (also keeps each folder's file list) |
| `tabs/downloader/filters.py` | Download filters and the Filters window |
| `common/whdparse.py`, `common/theme.py`, `common/utils.py` | Archive-name parsing, styling and helpers shared with the other tabs |

The tab is part of the main window: start the application with `python gui.py`.

## Credits

All credit goes to **Retroplay** on the English Amiga Board (EAB) and to all the people creating
WHDLoad packs. This tool only browses and downloads their work. EAB forum thread:
<https://eab.abime.net/showthread.php?t=61028>

## License

MIT, see [LICENSE](LICENSE).
