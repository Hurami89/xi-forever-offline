# Known issues

- Combat, groups, zones, cutscenes and Vanilla references are simulated. Native hooks, BGM ownership, SFX preservation and installer behavior need game-side verification.
- The album masters are a separate delivery. In 0.1.0, add the files from folders 1 through 11 in numeric order. Folder import automation is pending.
- The battle mixes have different durations and lack verified timing landmarks. Shared-position matching defaults off. Sample-accurate looping is beyond the current browser playback implementation.
- Browser audio requires activation each session. Background scheduling and codec support vary.
- Settings persist per browser profile and loopback port. Use one active tab. An abrupt close may lose the last second of an album checkpoint.
- A corrupt album entry yields to a playable reference where assigned. Use Next to skip it. Retry audio reopens repaired files with unchanged names.
- Rename a track inside its ID directory and keep one supported file there. Catalog file removal is manual.
- Dragging moves the player inside the page. Shortcut handling is tab-local.

## 0.2.0 (2026-11-27)

- Fishing, the Ventures window and Mog Houses are detected by add-on 0.2.0 but have not been seen in the real game yet
  (fishing status numbers, the zone-in packet's Mog House byte at 0x80, the venture add-on's mark file).
- An add-on loaded by hand while already inside a Mog House knows it only after the next zone-in.
- Ventures music follows the Ventures window, not a venture being out (those run for hours in the background).
- The window title is the page title; the Edge app window should show it as its title bar (to be seen on Windows).
- Playlists live in the player window's own browser profile on this PC; they do not move to another PC by themselves.
- The tag reader skips unsynchronised, compressed or encrypted ID3 frames (rare); the file name is the fallback.
- The Resonance of Vana'diel album (A001) has no files in the kit yet, so Radio has no shared album until it does.
