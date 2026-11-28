# Changelog

## 0.2.0 · Listen to, Mog Houses, Radio (2026-11-27)

J's three handoffs of 27 November: Usability, Activity Modes & Playlists; Mog Houses Zone Music; Radio, Catalog
Organization & Album Sets. Full report: `handoff/REPORT-0.2.0.md`.

- **Simpler player.** One **Start music** button (only while music is not allowed to play), a plain connection line
  ("Connected to the game" / "Not connected ... music you choose here still plays") and one **Listen to** choice:
  Game Sync, Playlist, Radio, Fishing, Venture. **Return to Game Sync** whenever something else was chosen. The
  simulator is folded away (hidden while the game is connected); settings and track assignments are under More
  settings. Empty and error states say what to do (empty playlist, missing track, music blocked by the browser,
  nothing to play on Radio, playlist deleted with **Undo**, settings that could not be saved).
- **Help in place**: "?" buttons explain each choice on hover, keyboard focus and tap; Escape closes them.
- **Fishing and Venture.** Game Sync plays *Just One More Cast* while the character is fishing (it stays 20 s between
  casts; a fight, cutscene or new zone ends that) and *Beyond the Next Hill* while the Ventures window is open. Both can
  also be chosen by hand; they then stay through fights and zoning. Needs add-on 0.2.0 for the automatic part; the
  player shows "Automatic" or "Manual only".
- **Mog House music.** *A Place to Call Home (Mog House Theme)* (bundled, slot `moghouse`) plays inside every Mog House,
  told by the zone-in packet's Mog House state (add-on 0.2.0). Music library > Zone Music: a choice for All Mog Houses
  and one per house (16 houses in 5 groups), each a track, the game's own music, or "same as All Mog Houses"; one
  button clears every house's own choice.
- **Playlists.** Playlist Mode plays an album of the catalog (in its order) or a saved playlist: New, name, add tracks
  from the library, import songs, reorder, remove, delete with Undo. Saved in the player's browser profile on this PC.
  The old single album list is kept as the playlist "My album". **Switch to battle music during combat** (off for new
  profiles; an existing choice is kept): on, a fight plays battle music and the playlist resumes on the same track and
  second afterwards.
- **Radio.** A shuffled mix of the listening albums ticked (catalog albums, and the player's own imports marked as
  listening music). Never a battle, fishing, venture or zone track, and never an import nobody classified. No track
  twice in a round, no repeat across a round's edge. Its own pause and place; battle switch off by default.
- **Catalog sets** (`catalog.json`): numbered gameplay sets (G001 Battle Themes, G002 Fishing, G003 Ventures, G004 Mog
  Houses) and albums (A001 Resonance of Vana'diel, no files yet). `GET /api/library` gives every track's set, number,
  role and credit. New sets need no player change.
- **MP3 only for new imports**, checked by content (a renamed WAV is refused with a reason). The file's ID3 tags
  (Title, Artist, Album, Track; ID3v2.2-2.4 and ID3v1) are read and shown for checking; the player may correct them or
  remove the song again. Missing artist: shown as not provided, never made up. Importing the same song twice gives one
  catalog entry (the id comes from the file's content). Older imports in other formats keep working.
- **Window title** follows what really plays: "VanaSync — Title — Artist" (no artist part when unknown),
  "Paused — ..." when a playlist or Radio is paused, "VanaSync" when nothing plays.
- **Now Playing file** for streaming (More settings): "Title — Artist" in `%LOCALAPPDATA%\VanaSync\NowPlaying.txt`,
  written in one step on every change, "(Paused) ..." when paused, empty when stopped or switched off.
- Add-on 0.2.0: snapshots carry `fishing`, `venture` (the venture add-on's `venture.open` mark for this character and
  this game) and `mog` (zone-in packet 0x00A, login state 1 or 5; the Feretory excluded), and the add-on's version.
- Tests: Node 23, host 22, add-on and launcher 23, browser test 8 sections (Chrome; `VANASYNC_EDGE` can name it).

## 0.1.2 (2026-11-26)

- New bundled track from J: "Choose to Fight (Special Battle Theme XIFO Exclusive)". It is an extra (battle-pack.json
  "extras"): seeded into the library, assigned to no slot, so Solo / Party / Alliance stay as they were.
- Titles no longer show the copy numbers a download adds at the end of a file name (" (1)", " (2) (1)"). Display only:
  files, ids and assignments are untouched. Words in brackets and numbers elsewhere in a name stay.
- Two more extras from J, his in-game versions of the app's tunes: "Just One More Cast" (fishing) and "Beyond the Next
  Hill" (Ventures). In the library only: nothing starts them by itself yet (the add-on does not report fishing).
- Add-on 0.1.2: the game's own battle theme no longer plays underneath (Zaltyz525, JØ). The game starts a new track at
  its own volume when a fight begins or ends, after the add-on's one request to fade; the request is now repeated
  once a second while VanaSync plays (four times a second for two seconds around a combat change), and full volume is
  asked for a few more times after the music is handed back. Not yet confirmed in the real game.
- `/vanasync open` (or `/vsync open`) in game brings the player window back after it was closed (Hexblood). The
  add-on's next three snapshots carry `"open": true`; the host keeps the request (`GameBridge.take_open()`, one window
  per ten seconds) and the launcher, which owns the window, opens it again within its five-second check. An app window
  that is still there is closed first, so two players never play at once. Not yet tried on Windows.

## 0.1.1 · Live in XI: Forever Offline (2026-11-25)

- Live game bridge: the XI: Forever Offline add-on `vanasync` sends combat, group size, alliance, zone and cutscene
  state over loopback UDP 8766 (`--game-port`, 0 turns it off). `GET /api/game` gives the player the latest state;
  the simulator inputs are locked while the game is live.
- Ownership handshake: the player posts `POST /api/owner` while it really plays one of its own tracks; each UDP reply
  tells the add-on, which fades the game's music out with the client's music-volume command (0x060) only then. Silence
  for 2 s (window closed, crash) gives the music back to the game.
- Live mode (`/?live=1`) plays only VanaSync's own tracks: the game itself plays the "native" music. A fresh profile
  starts in Resonance, and audio is enabled at start because the launcher opens the window with autoplay allowed.
- Tests: `tests/test_bridge.py`.

## 0.1.0 · Battle Resonance

- Added the midnight-blue and antique-gold local player and persistent layout controls.
- Added battle selection and overrides, five-second grace, soundtrack modes, crossfade, optional shared position and fallback.
- Added stable filename-driven catalog with rename tracking.
- Added a separate album queue with transport, checkpoints and optional battle interruption. Simulator cutscenes have priority.
- Included the three supplied battle mixes with SHA-256 verification and first-run assignments.
- Added the Windows launcher, test suite and native integration handoff.
