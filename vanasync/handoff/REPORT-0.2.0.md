# VanaSync 0.2.0 · report for J

27 November 2026. Your three handoffs: **Usability, Activity Modes & Playlists**, **Mog Houses Zone Music** and
**Radio, Catalog Organization & Album Sets**. Everything below is built in the XI: Forever Offline kit
(`vanasync/` and the add-on `addons-src/vanasync/`). **Nothing has been tried in the real game yet**: every result
here is from the tests and a real browser (headless Chrome) driving the player against the real host, with the game
simulated. The live checks are at the end, for Hurami.

## 1. What the current build was (before)

- One list of controls: Soundtrack, Battle arrangement, **Enable audio** beside **Restore native**, then four folded
  sections. The **Game simulator** was open by default, also in the live window.
- Status in technical words ("Simulator · Enable audio to listen", "Vanilla reference · Simulator"). No line saying
  whether the game is connected.
- One album list ("Album Mode"), filled only by importing files. No saved playlists. **Battle interruptions** already
  existed (checkbox, off by default) and worked: reused, renamed and explained (see 3).
- Fishing and Ventures tunes were in the library but nothing played them. No zone music. Any audio format accepted.
- Track titles from file names only.

Screenshots: `before-1-first-look.png`, `before-2-after-enable.png`; after: `after-1` ... `after-6`.

## 2. Three usability improvements (from the review)

| # | Problem seen | Change | Checked by |
|---|---|---|---|
| 1 | Starting was two unclear buttons ("Enable audio" next to "Restore native"); nothing said whether the game was connected. | One **Start music** button, shown only while music may not play (and after "Game music only"). A connection line in plain words with a green/grey dot: "Connected to the game" / "Not connected to the game. Music you choose here still plays." | Browser test: the button is there before, gone after; status texts. |
| 2 | Every control on one level, the simulator open in the live window, "Vanilla reference" labels in the main flow. | **Listen to** (one choice of five) with the current choice also shown as a badge under the title, and **Return to Game Sync** whenever another choice is active. The simulator is folded ("Test without the game") and hidden while the game is connected; settings and track assignments are under **More settings**. | Browser test: folded by default; Return to Game Sync. |
| 3 | Empty and error states were silent or technical. | Messages with the next step: an empty playlist ("Add a track below, or import songs"), a missing track ("Pick another in Music library, or the game's own music plays"), music blocked by the browser (a **Start music** button in the message), nothing to play on Radio, **Undo** after deleting a playlist, "Not saved" when the browser refuses to store. | Browser test: delete + Undo; empty Radio and playlist texts; refused WAV import says why. |

Task paths now (clicks): start synced music in the game 0 (the launcher starts it) or 1 (Start music on the test
page); choose Fishing or Venture 1, back 1; make a playlist: Playlist, New playlist, type a name, then 2 per track
(pick, Add) or Import songs; it saves itself.

## 3. Your requests, one by one

**Battle Themes and Zone Music apart.** Music library lists the gameplay sets (G001 Battle Themes, G002 Fishing,
G003 Ventures), then **Zone Music** (Mog Houses), then albums, then My imports. Fishing and Ventures are never used as
solo/party/alliance themes.

**Fishing Mode and Venture Mode.**

| Mode | Track | Automatic | Where the game tells it | Manual |
|---|---|---|---|---|
| Fishing | Just One More Cast | yes, with add-on 0.2.0 | the character's status is one of the game's fishing states (38-43, 50, 56-62: casting, a bite, caught, broken, stopped). It stays 20 s after the last one, so casting again does not restart it. A fight, a cutscene or a new zone ends it. | Listen to > Fishing |
| Venture | Beyond the Next Hill | yes, with add-on 0.2.0 | the **Ventures window is open** (the venture add-on's own `venture.open` mark for this character and this game). Ventures themselves run for hours in the background while you play on, so a venture being out does **not** count; only the window. | Listen to > Venture |

With an older add-on or no game the player says **Manual only**. Order in Game Sync: cutscene, then battle, then
fishing, then the Ventures window, then a Mog House, then the game's own music. Chosen by hand, Fishing and Venture
stay through fights and zoning until you choose something else.

**Playlists and private imports.** New, name, add tracks, import songs (MP3), reorder, remove, delete (only the list;
Undo for a few seconds; playback of a deleted list stops and the next list is chosen, paused). Saved in the player
window's own browser profile on this PC (the launcher opens it with its own profile, so it survives restarts). Imported
songs are **copied** into `%LOCALAPPDATA%\VanaSync\tracks`, so nothing breaks when the original file moves; no Relink
is needed. Clearing that folder removes them. Nothing is uploaded. Album Mode is now **Playlist** in Listen to; catalog
albums play there in their own order. An old single album list becomes the playlist "My album".

**Switch to battle music during combat.** One checkbox in Playlist (and one for Radio). Off (new profiles): the list
plays through fights. On: a fight plays the battle theme; after the post-combat delay the same track resumes at the
same second. Switching it on mid-fight starts battle music; off mid-fight resumes the list. A pause by the player is
respected (nothing restarts by itself). An existing choice from 0.1.x is kept.

**Help in place.** "?" beside Listen to, Game Sync, each activity, Mog Houses, Playlist, the battle switches, Import,
Radio, Game music only and the Now Playing file. Opens on hover, keyboard focus and tap; Escape or a second tap closes
it. Your suggested texts are used, adjusted to what the build does.

**Mog Houses.** Told apart from the town by the zone-in packet (0x00A): its login state is "my room" (1, or 5 after
logging back in) inside a Mog House and "game" (2) outside. That covers every town's Mog House, upstairs and visiting,
because they all come the same way; the Feretory uses the same state and is excluded. Choices: **All Mog Houses**
(default: your theme), and one per house. A house not in the list still plays the All Mog Houses choice.

| Location (zone id) | Group | Detection | Tested in game |
|---|---|---|---|
| Southern San d'Oria (230), Northern San d'Oria (231), Port San d'Oria (232) | San d'Oria | zone-in state | NOT TESTED |
| Bastok Mines (234), Bastok Markets (235), Port Bastok (236) | Bastok | zone-in state | NOT TESTED |
| Windurst Waters (238), Windurst Walls (239), Port Windurst (240), Windurst Woods (241) | Windurst | zone-in state | NOT TESTED |
| Ru'Lude Gardens (243), Upper Jeuno (244), Lower Jeuno (245), Port Jeuno (246) | Jeuno | zone-in state | NOT TESTED |
| Aht Urhgan Whitegate (50), Al Zahbi (48) | Aht Urhgan | zone-in state | NOT TESTED |
| Upstairs (2F), a friend's Mog House | any | same state | NOT TESTED |
| The town around a Mog House | any | state "game": no Mog House music | simulated only |

Limit: if the add-on is loaded by hand while already inside a Mog House it only knows after the next zone-in.

## 4. Catalog and Radio

**Inventory** (every track the kit carries; id = first 32 hex digits of the file's sha256):

| Set | No. | Title (approved) | Artist | Role | File's own tags | Note |
|---|---|---|---|---|---|---|
| G001 Battle Themes | 01 | Against the Odds (Solo Battle Theme) | jnull | battle-solo | "Against the Odds (solo battle theme)", jnull | file name has a copy number " (1)": kept, not shown |
| G001 | 02 | Beyond the Veil (Party Battle Theme) | jnull | battle-party | "Beyond the Veil (Fighting Theme)", jnull | tag title differs |
| G001 | 03 | The March of Many (Alliance Battle Theme) | jnull | battle-alliance | "The March of Many (Alliance Theme)", jnull | tag title differs |
| G001 | 04 | Choose to Fight (Special Battle Theme XIFO Exclusive) | jnull | battle-special | **"We Are Who We Choose (The One Sin Battle Theme)"**, jnull | tag title is another song's name: please check |
| G002 Fishing | 01 | Just One More Cast | jnull | fishing | same | |
| G003 Ventures | 01 | Beyond the Next Hill | jnull | venture | same | |
| G004 Mog Houses | 01 | A Place to Call Home (Mog House Theme) | jnull | zone-moghouse | "A Place to Call Home", jnull | |
| A001 Resonance of Vana'diel | | (no files in the kit) | JØ × NOX | listening | | the 11 numbered songs are needed |

Unresolved, for you and Hurami to decide: (1) artist credit: every file says **jnull**; the catalog shows that for now
(nothing invented). If the credit should read "JØ" or "JØ × NOX", say which and it is one line per track in
`catalog.json`. (2) Choose to Fight's own tag names "We Are Who We Choose". (3) *We Are Who We Choose* (the launcher's
main theme) and the Resonance album files are not in VanaSync yet; with the 11 files (folders 1-11) A001 fills in that
order and Radio has a shared album to play.

**How it is stored.** `catalog.json` beside the player lists each set (G### gameplay, A### album), its tracks in order,
their approved title and artist, and the role. Ids, files and paths are unchanged. A new set is a few lines there plus
its files in `battle-pack.json`; the player lists it without any code change. Display numbers are separate from ids.

**Radio.** Listen to > Radio: tick albums (shared albums, and "My listening music": your own imports that you marked as
listening music in Music library > My imports). Play, Pause, Next. One shuffled pool across all ticked albums; no
song twice before all have played; the first of a new round is never the last of the round before; Radio skips a song
that will not play and stops with a message if none will. Gameplay tracks (battle, fishing, ventures, Mog Houses) and
imports nobody marked never enter Radio, also when they are in a playlist. Radio keeps its own place and pause and
starts paused after a restart. Battle switch off by default; Game Sync events never replace Radio.

**Three suggestions for Radio** (not built):
1. *Problem:* a 30-song album drowns a 5-song one in the pool. *Change:* a weight per ticked album (equal per album,
   or per song). *Benefit:* a mix that sounds like the albums chosen. *Effort:* small (pool building only).
2. *Problem:* the only way to never hear a song on Radio is to untick its whole album. *Change:* "Not on Radio" on a
   song (kept in its album and playlists). *Benefit:* a personal station. *Effort:* small (one list in the settings).
3. *Problem:* Radio shows only the song now; a song you liked is gone after Next. *Change:* "Up next" line and a Back
   button that replays the previous song. *Benefit:* control without leaving shuffle. *Effort:* small to medium.

## 5. Credits, window title, Now Playing

- **MP3 only** for new imports: the file picker asks for MP3 and the host checks the content (a renamed WAV or text file
  is refused: "this is not really an MP3 (renamed?)"). Older imports in other formats keep playing.
- **Tags** read on import: Title, Artist, Album, Track number (ID3v2.2, 2.3, 2.4 and ID3v1). The player shows them in a
  check card (title proposed from the file name when the tag is empty, "Artist not provided" when there is none, with
  a note asking for the artist) with **Keep** or **Remove from VanaSync**. Corrections are stored beside the song and
  win over the tags; the catalog's approved credits win for shared tracks. Nothing is guessed from accounts or names.
  Submitter text: in the README ("Sending music for the shared catalog").
- **Window title**: "VanaSync — Title — Artist" from what really plays (battle overrides and the resumed track too);
  no artist part when unknown; "Paused — ..." for a paused playlist or Radio; "VanaSync" when nothing plays. The live
  window is an Edge app window, which shows the page title as its window title (to be seen on Windows).
- **Now Playing file**: More settings > Now Playing file. `%LOCALAPPDATA%\VanaSync\NowPlaying.txt`, UTF-8, written
  through a temporary file and swapped in, on each real change; "(Paused) Title — Artist" when paused; empty when
  stopped or switched off. OBS: Text source, "Read from file", that file. No path or other private text goes in it.

## 6. Test results

| Check | Result | How |
|---|---|---|
| Library: Battle Themes, activities, Zone Music, albums apart | PASS | browser test, screenshots |
| Fishing / Venture by hand, through a fight, Return to Game Sync | PASS | browser test (simulated) |
| Automatic fishing: starts, no restart between casts, 20 s hold, fight first | PASS (simulated) / NOT TESTED in game | browser + core tests; add-on test (statuses) |
| Automatic Ventures window | PASS (simulated) / NOT TESTED in game | add-on test (the mark file), browser test |
| Mog House on, off in town, per-house choice, game's own music | PASS (simulated) / NOT TESTED in game | add-on test (zone-in packet), browser test |
| Playlists: new, name, add, import, order, delete + Undo, reload | PASS | browser test |
| Battle switch off / on / toggled mid-fight / resume position / cutscene | PASS (simulated) | browser + core tests |
| Radio: only listening music, pool across albums, no repeats, skips failures | PASS (simulated) | core tests (200 rounds), browser test |
| MP3 only, tags read, missing artist, duplicates are one song | PASS | host tests, browser test |
| Window title and Now Playing (playing, paused, stopped, Unicode) | PASS (browser tab) / NOT TESTED in the Edge app window | browser + host tests |
| Help by mouse, keyboard and tap | PASS (focus, Escape, click); touch NOT TESTED on a touch screen | browser test |
| Webpage version (Music Box on the site/app) | NOT BUILT | the Music Box pack is still to do; this is the local player |

Suites: player logic (Node) 23, host (Python) 22, add-on and launcher 23, browser test 8 sections. All pass.

## 7. Live checks (Hurami, in the game)

1. OPTIONS > Addons: `vanasync` on. PLAY. The window says "Connected to the game"; Fishing, Ventures window and Mog
   Houses say **Automatic**. `/vanasync debug` on.
2. Walk into your Mog House: the chat says "zone-in: Mog House yes" and *A Place to Call Home* plays; the game's music
   fades. Walk out: the town's own music comes back. Try upstairs and another nation's Mog House.
3. Fish: *Just One More Cast* starts at the first cast and does not restart on the next. Stop fishing: it stays about
   20 s, then the game's music.
4. Squads menu > Ventures (window open): *Beyond the Next Hill*. Close it: back.
5. Playlist with the battle switch off: fight, the playlist plays on and the game's battle theme stays silent. Switch
   on: fight, battle theme; after the fight the playlist goes on where it stopped.
6. Radio: tick an album, Play; fight and zone: Radio stays.
7. The window's title bar shows "VanaSync — title — jnull".

## 8. Files

`vanasync/app/` (index.html, app.js, core.js, style.css), `vanasync/server.py`, `vanasync/tags.py` (new),
`vanasync/catalog.json` (new), `vanasync/battle-pack.json`, `vanasync/battle-pack/A Place to Call Home (Mog House
Theme).mp3` (new), tests in `vanasync/tests/`, `addons-src/vanasync/vanasync.lua` (0.2.0),
`dev/launcher-tests/test_vanasync.py`. Rollback: the earlier files are kept beside them as `.before-vanasync020`.
