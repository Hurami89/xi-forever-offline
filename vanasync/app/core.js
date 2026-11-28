export const ARRANGEMENTS = ["solo", "party", "alliance"];
export const SLOTS = ["solo", "party", "alliance", "nativeSolo", "nativeParty",
  "nativeAlliance", "exploration", "cutscene", "ambience", "fishing", "venture", "moghouse"];
// (2026-11-27, J's usability, Mog House and Radio handoffs) what the player listens to:
//   game      Game Sync: the game decides (battle music, fishing, the Ventures window, Mog Houses, else the game's music)
//   playlist  an album or a saved playlist, in order
//   radio     a shuffled mix of the listening albums chosen
//   fishing / venture   that tune, chosen by hand, until something else is chosen
export const LISTEN = ["game", "playlist", "radio", "fishing", "venture"];
export const FISHING_HOLD = 20;     // seconds the fishing tune stays after the last fishing state (between casts)
// Mog Houses with a door in a town, by zone (the game's zone ids). The music follows the zone-in's Mog House state, so
// a Mog House in a zone missing here still plays the "All Mog Houses" choice; this list is only for choosing per house.
export const MOG_HOUSES = [
  { zone: 230, name: "Southern San d'Oria", nation: "San d'Oria" },
  { zone: 231, name: "Northern San d'Oria", nation: "San d'Oria" },
  { zone: 232, name: "Port San d'Oria", nation: "San d'Oria" },
  { zone: 234, name: "Bastok Mines", nation: "Bastok" },
  { zone: 235, name: "Bastok Markets", nation: "Bastok" },
  { zone: 236, name: "Port Bastok", nation: "Bastok" },
  { zone: 238, name: "Windurst Waters", nation: "Windurst" },
  { zone: 239, name: "Windurst Walls", nation: "Windurst" },
  { zone: 240, name: "Port Windurst", nation: "Windurst" },
  { zone: 241, name: "Windurst Woods", nation: "Windurst" },
  { zone: 243, name: "Ru'Lude Gardens", nation: "Jeuno" },
  { zone: 244, name: "Upper Jeuno", nation: "Jeuno" },
  { zone: 245, name: "Lower Jeuno", nation: "Jeuno" },
  { zone: 246, name: "Port Jeuno", nation: "Jeuno" },
  { zone: 50, name: "Aht Urhgan Whitegate", nation: "Aht Urhgan" },
  { zone: 48, name: "Al Zahbi", nation: "Aht Urhgan" }
];
export const KEYS = { collapse: "F2", album: "F3", emergency: "F8" };
const idPattern = /^[a-f0-9]{32}$/;
const validId = value => typeof value === "string" && idPattern.test(value);
const listId = /^p[a-z0-9]{1,16}$/;
const setId = /^[GA]\d{3}$/;
const text = (value, max = 80) => typeof value === "string"
  ? value.replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, max) : "";
const zoneChoice = value => value === "native" || validId(value) ? value : "";
const number = (value, fallback, min, max) => typeof value === "number" && Number.isFinite(value)
  ? Math.max(min, Math.min(max, value)) : fallback;

export function settings(raw = {}) {
  raw = raw && typeof raw === "object" ? raw : {};
  const album = Array.isArray(raw.album) ? raw.album.filter(validId).slice(0, 200) : [];
  // Saved playlists. A player from before 2026-11-27 had one list (album): it becomes the playlist "My album".
  const seen = new Set();
  let playlists = Array.isArray(raw.playlists) ? raw.playlists.filter(p => p && listId.test(p.id) && !seen.has(p.id)
    && seen.add(p.id)).slice(0, 50).map(p => ({ id: p.id, name: text(p.name) || "Playlist",
    tracks: Array.isArray(p.tracks) ? p.tracks.filter(validId).slice(0, 200) : [] })) : null;
  if (!playlists) playlists = album.length ? [{ id: "palbum", name: "My album", tracks: [...album] }] : [];
  const active = typeof raw.active === "string" && (setId.test(raw.active.slice(4)) && raw.active.startsWith("set:")
    || raw.active.startsWith("pl:") && playlists.some(p => "pl:" + p.id === raw.active)) ? raw.active
    : playlists.length ? "pl:" + playlists[0].id : "";
  const listen = LISTEN.includes(raw.listen) ? raw.listen : raw.albumOn === true ? "playlist" : "game";
  const zones = {};
  for (const [key, value] of Object.entries(raw.zones && typeof raw.zones === "object" ? raw.zones : {}))
    if (/^mog(?::\d{1,4})?$/.test(key) && zoneChoice(value)) zones[key] = value;
  const cursor = Math.floor(number(raw.cursor, 0, 0, 199));   // (the queue's length is checked where it is known)
  const usedKeys = new Set();
  const keys = {};
  const slots = {};
  for (const slot of SLOTS) slots[slot] = validId(raw.slots?.[slot]) ? raw.slots[slot] : "";
  for (const action of Object.keys(KEYS)) {
    const value = raw.keys?.[action] ?? KEYS[action];
    if (/^(?:F[2-9]|[A-Z])$/.test(value) && !usedKeys.has(value)) {
      keys[action] = value;
      usedKeys.add(value);
    } else {
      keys[action] = "";
    }
  }
  return {
    mode: ["Vanilla", "Resonance", "Off"].includes(raw.mode) ? raw.mode : "Vanilla",
    override: ARRANGEMENTS.includes(raw.override) ? raw.override : "auto",
    grace: number(raw.grace, 5, 0, 30), fade: number(raw.fade, 0.8, 0, 4),
    sync: raw.sync === true, slots, album, cursor,
    position: number(raw.position, 0, 0, 86400), listen, playlists, active, zones,
    radio: [...new Set(Array.isArray(raw.radio) ? raw.radio.filter(v => setId.test(v) || v === "mine") : [])],
    radioInterrupt: raw.radioInterrupt === true, nowPlaying: raw.nowPlaying === true,
    paused: raw.paused === true, repeat: raw.repeat === true,
    interrupt: raw.interrupt === true, locked: raw.locked === true,
    collapsed: raw.collapsed === true, transparency: number(raw.transparency, 1, 0.45, 1),
    scale: number(raw.scale, 1, 0.75, 1.4),
    x: number(raw.x, 0, -10000, 10000), y: number(raw.y, 0, -10000, 10000),
    volume: Object.fromEntries(["battle", "exploration", "album", "ambience"]
      .map(key => [key, number(raw.volume?.[key], key === "ambience" ? 0.4 : 0.8, 0, 1)])),
    keys
  };
}

export function arrangement(prefs, game) {
  if (prefs.override !== "auto") return prefs.override;
  if (game.alliance || game.members > 6) return "alliance";
  return game.members > 1 ? "party" : "solo";
}

export class CombatState {
  game = { engaged: false, members: 1, alliance: false, zone: 1, cutscene: false,
    fishing: false, venture: false, mog: false };
  endedAt = null;
  fishedAt = null;     // when the character was last seen fishing (casts have short gaps between them)

  update(snapshot, now) {
    if (this.game.engaged && !snapshot.engaged) this.endedAt = now;
    if (snapshot.engaged) this.endedAt = null;
    // a fight, a cutscene or another zone ends the fishing hold (casting again starts it again)
    if (snapshot.engaged || snapshot.cutscene || (snapshot.zone ?? this.game.zone) !== this.game.zone) this.fishedAt = null;
    if (snapshot.fishing) this.fishedAt = now;
    this.game = { fishing: false, venture: false, mog: false, ...snapshot };
  }

  // The activity the game shows now: "fishing" (also for FISHING_HOLD seconds after the last fishing state),
  // "venture" (the Ventures window is open), or "". A new zone, combat or a cutscene ends the fishing hold.
  activity(now) {
    if (this.game.fishing || (this.fishedAt !== null && now - this.fishedAt < FISHING_HOLD * 1000)) return "fishing";
    return this.game.venture ? "venture" : "";
  }

  forgetFishing() {
    this.fishedAt = null;
  }

  phase(now, grace) {
    if (this.game.engaged) return "combat";
    if (this.endedAt !== null && now - this.endedAt < grace * 1000) return "grace";
    return "exploration";
  }
}

// The music for the Mog House the character is in: that house's own choice, else "All Mog Houses", else the bundled
// Mog House theme. "native" is the game's own music. null outside a Mog House.
export function zoneMusic(prefs, game) {
  if (!game.mog) return null;
  const choice = prefs.zones["mog:" + game.zone] || prefs.zones.mog || prefs.slots.moghouse;
  return { key: "zone/mog", id: choice === "native" ? "" : choice || "", native: choice === "native" || !choice };
}

// ctx (2026-11-27): queue: the ids of the album or playlist being played (default: prefs.album, the old single list);
// radio: Radio's state now ({ id, index, position, paused }); no id: nothing to play.
export function select(prefs, state, now, emergency = false, ctx = {}) {
  const listen = prefs.listen || (prefs.albumOn ? "playlist" : "game");
  const queue = ctx.queue ?? prefs.album;
  const phase = state.phase(now, prefs.grace);
  const battle = phase !== "exploration";
  const kind = arrangement(prefs, state.game);
  const nativeBattle = "native" + kind[0].toUpperCase() + kind.slice(1);
  const native = battle ? nativeBattle : "exploration";
  const stack = [];
  const add = (key, id, channel, ownership, match = null, loop = true, position = 0) => {
    stack.push({ key, id, channel, ownership, match, loop, position });
  };
  if (state.game.cutscene) {
    add("cutscene", prefs.slots.cutscene, "exploration", "native");
  } else if (emergency) {
    add(native, prefs.slots[native], battle ? "battle" : "exploration", "native");
  } else if (listen === "fishing" || listen === "venture") {
    // chosen by hand: stays through fights and zoning until something else is chosen
    add("activity/" + listen, prefs.slots[listen], "activity", "custom");
    add(native, prefs.slots[native], battle ? "battle" : "exploration", "native");
  } else if (listen === "playlist" && !(battle && prefs.interrupt && !prefs.paused)) {
    if (!prefs.paused && queue.length) {
      add("album/" + prefs.cursor, queue[prefs.cursor], "album", "custom",
        null, false, prefs.position);
      add(native, prefs.slots[native], battle ? "battle" : "exploration", "native");
    } else if (!prefs.paused) {
      add("album/empty", "", "album", "custom", null, false);
      add(native, prefs.slots[native], battle ? "battle" : "exploration", "native");
    }
  } else if (listen === "radio" && !(battle && prefs.radioInterrupt && !ctx.radio?.paused)) {
    // Radio keeps its own place and pause (ctx.radio: { id, index, position, paused })
    if (!ctx.radio?.paused && ctx.radio?.id) {
      add("radio/" + ctx.radio.index, ctx.radio.id, "radio", "custom", null, false, ctx.radio.position ?? 0);
      add(native, prefs.slots[native], battle ? "battle" : "exploration", "native");
    } else if (!ctx.radio?.paused) {
      add("radio/empty", "", "radio", "custom", null, false);
      add(native, prefs.slots[native], battle ? "battle" : "exploration", "native");
    }
  } else if (battle || listen !== "game") {
    // a fight (Game Sync, or a playlist / Radio set to switch to battle music)
    if (prefs.mode !== "Off") {
      const match = battle && prefs.sync ? "battle-shared-timeline" : null;
      if (battle && prefs.mode === "Resonance") add(kind, prefs.slots[kind], "battle", "custom", match);
      add(native, prefs.slots[native], battle ? "battle" : "exploration", "native", match);
    }
  } else {
    // Game Sync out of a fight: fishing, the Ventures window, a Mog House, else the game's own music
    const activity = state.activity(now);
    const zone = zoneMusic(prefs, state.game);
    if (activity) add("activity/" + activity, prefs.slots[activity], "activity", "custom");
    else if (zone && !zone.native) add(zone.key, zone.id, "zone", "custom");
    if (prefs.mode !== "Off" || activity || (zone && !zone.native))
      add(native, prefs.slots[native], "exploration", "native");
  }
  const ambience = !emergency && !state.game.cutscene && prefs.slots.ambience
    ? { key: "ambience", id: prefs.slots.ambience, channel: "ambience", loop: true, position: 0 }
    : null;
  return { phase, kind, stack, ambience, listen };
}

export function nextAlbum(prefs, step, automatic = false, queue = prefs.album) {
  if (!queue.length) return;
  const next = Math.min(prefs.cursor, queue.length - 1) + step;
  if (automatic && next >= queue.length && !prefs.repeat) {
    prefs.paused = true;
    prefs.cursor = 0;
  } else {
    prefs.cursor = (next + queue.length) % queue.length;
  }
  prefs.position = 0;
}

// (2026-11-26, J's Choose to Fight update) the title shown for a file: its name without the extension and without the
// copy numbers a download adds at the very end ("Against the Odds (Solo Battle Theme) (1).mp3", "Track (2) (1).mp3").
// Only whole " (n)" groups at the end go, n from 1 to 99; words in brackets ("(Battle Theme)", "(Remix)", "(Live)") and
// numbers anywhere else stay. Display only: ids, files and assignments are untouched, and two files may show one title.
export function trackTitle(filename) {
  const dot = filename.lastIndexOf(".");
  const name = dot > 0 ? filename.slice(0, dot) : filename;
  const clean = name.replace(/(?:\s+\([1-9]\d?\))+\s*$/, "");
  return clean.trim() ? clean : name;
}

// (2026-11-27) The ordered tracks of what Playlist Mode plays: a saved playlist ("pl:<id>") or a catalog album
// ("set:A001", in its own order). Unknown: [].
export function queueOf(prefs, library) {
  if (prefs.active.startsWith("pl:")) return prefs.playlists.find(p => "pl:" + p.id === prefs.active)?.tracks ?? [];
  const set = prefs.active.slice(4);
  return Object.entries(library?.tracks ?? {}).filter(([, t]) => t.set === set)
    .sort((a, b) => a[1].no - b[1].no).map(([id]) => id);
}

export function newPlaylistId(prefs, random = Math.random) {
  for (;;) {
    const id = "p" + Math.floor(random() * 2 ** 40).toString(36);
    if (!prefs.playlists.some(p => p.id === id)) return id;
  }
}

// Radio may only play listening music: tracks of an artist or community album (catalog group "album") and imports the
// player marked as listening music ("mine"). Gameplay tracks (battle, fishing, ventures, zones) and imports nobody
// classified never qualify, whatever playlist they are in.
export function radioEligible(track) {
  return !!track && track.role === "listening" && track.group !== "gameplay";
}

export function radioPool(prefs, library) {
  const chosen = new Set(prefs.radio);
  const out = [];
  for (const [id, track] of Object.entries(library?.tracks ?? {})) {
    if (!radioEligible(track)) continue;
    if (track.origin === "import" ? chosen.has("mine") : chosen.has(track.set)) out.push(id);
  }
  return out.sort();
}

// A shuffled round of the pool. No track twice in a round; the first of a new round is not the last of the one before.
export function shuffleRound(pool, last = null, random = Math.random) {
  const order = [...new Set(pool)];
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  if (order.length > 1 && order[0] === last) [order[0], order[1]] = [order[1], order[0]];
  return order;
}

export class Radio {
  round = [];
  index = 0;

  // The pool changed (albums chosen, catalog changed): keep the round if it still fits, otherwise start a new one.
  sync(pool, random = Math.random) {
    const allowed = new Set(pool);
    const current = this.current();
    this.round = this.round.filter(id => allowed.has(id));
    for (const id of pool) if (!this.round.includes(id)) this.round.splice(this.index + 1 + Math.floor(random()
      * (this.round.length - this.index)), 0, id);
    if (!this.round.length) this.index = 0;
    else if (current && this.round.includes(current)) this.index = this.round.indexOf(current);
    else this.index = Math.min(this.index, this.round.length - 1);
  }

  current() {
    return this.round[this.index] ?? null;
  }

  next(pool, random = Math.random) {
    if (!pool.length) return null;
    if (this.index + 1 < this.round.length) this.index++;
    else {
      this.round = shuffleRound(pool, this.current(), random);
      this.index = 0;
    }
    return this.current();
  }

  start(pool, random = Math.random) {
    this.round = shuffleRound(pool, null, random);
    this.index = 0;
    return this.current();
  }
}

// What a track is called: the catalog's approved credit, then the player's own correction or the file's tags, then
// the file name (without its copy numbers). The artist is only ever what someone wrote down: "" when nobody did.
export function credit(id, library, catalog) {
  const track = library?.tracks?.[id];
  const file = catalog?.[id] ?? track?.file ?? "";
  return { title: track?.title || (file ? trackTitle(file) : ""), artist: track?.artist || "" };
}

// The window title and the Now Playing text: "VanaSync — Title — Artist", the artist left out when unknown.
export function windowTitle(playing, paused = false) {
  if (!playing?.title) return "VanaSync";
  return (paused ? "Paused — " : "") + "VanaSync — " + playing.title + (playing.artist ? " — " + playing.artist : "");
}

export function nowPlayingText(playing, paused = false) {
  if (!playing?.title) return "";
  return (paused ? "(Paused) " : "") + playing.title + (playing.artist ? " — " + playing.artist : "");
}
