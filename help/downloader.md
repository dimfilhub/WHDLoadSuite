# Downloader tab

The Downloader browses the **Retroplay WHDLoad Packs** on the grandis.nu FTP server and downloads the ones you tick into your downloads folder. The packs are made by Retroplay and many other people (see [About and credits](help:about)).

> **Third-party server.** The server and its contents belong to others; the author of WHDLoadSuite does not run or control them. You are responsible for checking that you may download and use what you fetch. See the [Legal notice](help:legal).

## What you see

- **Connection** at the top: **Host**, **Port**, **Use FTPS (TLS)**, **Username**, **Password**, a **Connect** button and a status light that reads *Connected* or *Disconnected*.
- **A folder tree** with a tick box for every folder and file, and a **Size** column. It is empty until you connect.
- **Download to**: the destination folder, with a **Browse...** button.
- **A bar of buttons**: **Select all**, **Download selected**, **Cancel**, **Filters…** and **Quit**, with the total size of what is ticked.
- **Two progress bars**: the current file and the overall download.

## What you can do

1. Press **Connect**. The login `ftp` / `ftp` and a host are already filled in.
2. Open folders with the arrow to see what is inside. Folders are loaded as you open them.
3. Click a row, or press Space, to tick it. Ticking a folder ticks everything inside it.
4. Optionally press **Filters…** to download only some of the files (see [Download filters](help:filters)).
5. Check **Download to** (it is your downloads folder), then press **Download selected**.
6. Watch the progress bars. Press **Cancel** to stop; the partly downloaded file is removed.

## Buttons and controls

- **Host / Port / Use FTPS (TLS):** the server. The defaults work. FTPS encrypts the connection.
- **Username / Password:** the free account is `ftp` / `ftp`.
- **Connect / Disconnect:** opens or closes the session.
- **Browse...:** chooses the destination folder. This **is** the shared downloads folder: changing it changes it for the Browser, the Builder and HDCommander too.
- **Select all / Clear:** ticks everything, or clears every tick.
- **Download selected:** copies the ticked files to the destination, in the same folder layout as the server. Files that already exist with the same size are skipped, so an interrupted download can simply be started again.
- **Cancel:** stops the download.
- **Filters… / Filters (on)…:** opens the [filters window](help:filters); the button reads *Filters (on)…* while a filter is active.
- **Quit:** closes the app (it asks first if you are connected).

## What the colours mean

- **Green:** the file is already in your downloads folder with the expected size.
- **Red:** it is missing or incomplete.

The total size of the ticked files is shown next to the buttons. Folder sizes are measured in the background, so they appear a little later.

## Tips

- After a download, the Browser and the Builder list the new archives automatically.
- Downloads mirror the server layout: a file at `<server root>/Games/A/file.lha` is saved as `<destination>/Games/A/file.lha`.
