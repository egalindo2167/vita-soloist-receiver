# Favorites — version 1.3.1

Favorites are this app's local shortcuts to Spotify songs, albums, playlists or
episodes. They are separate from Spotify's Liked Songs/library. Up to 32 shortcuts
are supported. This release documents the existing workflow; it does not add new
favorite-editing controls to the Vita.

## Add a song or playlist from Windows

1. In Spotify, open the song/album/playlist/episode menu and choose **Share → Copy
   link**. A normal `https://open.spotify.com/...` link or Spotify URI works.
2. Open the extracted release's **pc** folder in File Explorer. Right-click an
   empty area and choose **Open in Terminal** (PowerShell is fine).
3. Run this command, replacing the quoted placeholder with the copied link and
   the name with the label you want on the Vita:

```powershell
py -3.14 favorites.py add "PASTE_SPOTIFY_LINK_HERE" --name "Artist - Song"
```

4. Keep the quotation marks, especially for names with spaces and links containing
   `?` or `&`. Press Enter. The script should say that favorites.json was saved.
5. On the Vita, tap **Favorites** in the left sidebar, or press **Triangle** twice
   from Now playing. In Queue, D-pad Left/Right switches to Favorites.
   Use Up/Down and X, or tap a row, to play it. **L/R skips songs** while browsing.
   A running host
   reloads the file about every two seconds; you do not need to restart it.

## List or remove a shortcut

Run these from the same **pc** folder:

```powershell
py -3.14 favorites.py list
py -3.14 favorites.py remove 1
```

The removal number is the position printed by `list`, starting at 1. Check the
list again after a removal because later numbers move up. Removing a shortcut
does not remove the music from Spotify or change its library state.

## Where the list is saved

On Windows it is saved centrally at:

`%LOCALAPPDATA%\VitaAudioReceiver\favorites.json`

Setup and Upgrade Host preserve that file. The empty/template `pc/favorites.json`
inside a new download is not your live list once the host is installed. Editing
the central JSON manually is possible, but the script checks the link, limit and
file format and writes it atomically. No Spotify credentials are needed for
editing these local shortcuts.

## Could adding favorites be easier?

Yes. A future **Save current song** button on the Vita could send the URI/title
already supplied by Soloist through the existing paired control connection. The
PC would save it and return the updated list. The same could work for a highlighted
Up Next item, with a small confirmation/rename/remove interface. It would need
no extra Spotify login for this app-local list.

A PC/phone editor is another possibility. It would require its own carefully
restricted/authenticated interface if reachable beyond the PC. A feature that
actually likes tracks in Spotify's account library would be a separate integration.
None of these new adding/editing features is included in this release.
