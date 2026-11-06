# Browser tab

The Browser is the main place to look through your game archives and start a game.

## What you see

- **A filter row** at the top: **Search**, **Latest version only**, **Only entries without ID** and **Clear filters**.
- **A button row** below it: **Refresh**, **Clear selection**, **Review selection**, **Launch in Amiberry**, **Send to Builder** and **Quit**.
- **A filter panel on the left** with check lists for **Language**, **Platform**, **Memory**, **Media** and **Other tags**. Each value has a count.
- **The game list** in the middle. Archives are grouped by the first character of the title (`0-9`, `A`–`Z`); the groups start closed. The columns show the title, version, language, platform, memory, media, other tags, ID and file name.
- **A colour legend** and a **status line** at the bottom. The status line shows how many archives are selected and how many are listed.

The app reads the file name of each archive, such as `Game_v1.2_AGA_De_2MB_Disk2_1234.lha`, and splits it into title, version, language, platform, memory, media, other tags and ID.

## What you can do

1. **Find a game:** type in **Search**; the list narrows as you type. It matches the title and the file name.
2. **Narrow the list:** tick values in the left panel. Several values in one list match **any** of them; ticking in different lists must match **all** of them.
3. **Select a game:** click its row (see the selection rules below).
4. **Play it:** press **Launch in Amiberry**.
5. **Build it:** select games and press **Send to Builder**, then build in the [Builder tab](help:builder).

## Buttons and controls

- **Search:** type part of a title or file name. It filters as you type.
- **Latest version only:** keeps just the newest version of each game variant.
- **Only entries without ID:** shows archives whose name has no ID number.
- **Clear filters:** empties the search and unticks every filter.
- **Refresh:** scans the downloads folder again. This also happens whenever you open the tab.
- **Clear selection:** unselects every row.
- **Review selection:** lists only the selected rows, ignoring the filters. Press it again to go back. While it is on, the button is green.
- **Launch in Amiberry:** starts the one selected game. Select exactly one row first. The [launch screen](help:launch-screen) appears, then the game starts. A game that needs a [prepared drive](help:prepared) is prepared first, and the launch screen says so.
- **Send to Builder:** ticks the selected archives in the Builder tab. With nothing selected it offers to send **all listed** archives, after a warning. Only `.lha` files can be launched or built.
- **Quit:** closes the app.
- **Column headings:** click one to sort, click again to reverse the order.
- **Double-click a row:** shows the file in Finder or Explorer.

## How selecting rows works

- **Click** a row to select **only** that row. Click it again to unselect it.
- **Cmd+click** (Ctrl+click on Windows and Linux) adds or removes a single row.
- **Shift+click** selects the range from the last row you clicked.
- Selected rows are shown in **bold**.

## What the colours mean

- **Orange** (*Needs preparation*): the game needs a [prepared drive](help:prepared) and has none yet.
- **Green** (*Prepared*): it has one.
- **Blue** (*Executable built*): a [standalone program](help:executables) was built.
- **Gold** (*Selected in Builder*): ticked in the Builder tab.
- **No colour:** the game runs straight from its `.lha` and needs nothing.

## Tips

- The downloads folder is set in **Settings > Browser…**. If the list is empty, check that folder. See [Folder locations](help:locations).
- To launch a game you need Amiberry and Kickstart ROMs: [The emulator (Amiberry)](help:emulator), [Kickstart ROMs](help:kickstarts).
- Once a game has a picture, the launch screen shows it. See [Launch screen](help:launch-screen).
