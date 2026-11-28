import { SLOTS, KEYS, LISTEN, MOG_HOUSES, settings, CombatState, select, nextAlbum, trackTitle, queueOf,
  newPlaylistId, radioPool, radioEligible, Radio, credit, windowTitle, nowPlayingText, FISHING_HOLD } from "/core.js";
import { Mixer } from "/audio.js";

const VERSION = "0.2.0";
const $ = id => document.getElementById(id);
const storageKey = "vanasync.settings.v1";
const game = new CombatState();
const slotLabels = {
  solo: "Battle · Solo", party: "Battle · Party", alliance: "Battle · Alliance",
  nativeSolo: "Simulator stand-in · Solo", nativeParty: "Simulator stand-in · Party",
  nativeAlliance: "Simulator stand-in · Alliance", exploration: "Simulator stand-in · Exploration",
  cutscene: "Simulator stand-in · Cutscene", ambience: "Ambience",
  fishing: "Fishing", venture: "Ventures", moghouse: "Mog Houses (all)"
};
const volumeIds = { battle: "battle", exploration: "exploration-volume",
  album: "album", ambience: "ambience" };
const phaseNames = { combat: "Combat", grace: "Post-combat", exploration: "Exploration" };
const listenNames = { game: "Game Sync", playlist: "Playlist", radio: "Radio", fishing: "Fishing", venture: "Venture" };
// (2026-11-27) short explanations: on hover, keyboard focus and tap (the "?" buttons)
const HELP = {
  listen: "Game Sync lets the game choose the music. Playlist, Radio, Fishing and Venture play what you choose until you pick Return to Game Sync.",
  game: "Changes music to match supported activities in your game: battles, fishing, the Ventures window and Mog Houses.",
  fishing: "Play Just One More Cast while fishing. Choose Fishing above if automatic detection is unavailable.",
  venture: "Play Beyond the Next Hill while the Ventures window is open. Automatic switching requires a supported game connection.",
  mog: "Play the Mog House theme inside every Mog House. Choose a different track, or the game's own music, for each house in Music library > Zone Music.",
  playlist: "Play an album or a playlist you saved on this PC.",
  interrupt: "On: battle music plays during combat, then your playlist resumes where it stopped. Off: your playlist keeps playing through battles. Requires a live game connection.",
  radioInterrupt: "Off (the usual): Radio keeps playing through battles. On: battle music plays during combat, then Radio resumes where it stopped.",
  radio: "Shuffle music from the artist albums you choose. Battle, fishing, venture and zone soundtracks stay in Game Sync.",
  import: "Add music from your PC for your own listening. MP3 only. It is copied into VanaSync on this PC and does not go to the shared catalog.",
  saved: "Keeps this playlist on this PC. It will not appear on other devices by itself.",
  restore: "Stops VanaSync's own music at once and gives the music back to the game. Start music returns to your choice.",
  nowPlaying: "Writes \"Title — Artist\" to a text file whenever the music changes, for OBS or other streaming software (Text source > Read from file).",
  mine: "Songs you imported and marked as listening music. They stay on this PC."
};

let prefs;
let catalog = {};
let library = { sets: [], tracks: {} };
let enabled = false;
let emergency = false;
let pending = false;
let selected = null;
let lastPlayed = null;       // the last track that really played (for "Paused — ..." titles)
let graceTimer;
let polling = false;
let drag;
let disposed = false;
const journal = [];
const failed = new Set();
let previousPlan = "";
const liveLaunch = new URLSearchParams(location.search).has("live");
let live = false;
let livePolling = false;
let lastLive = "";
let lastOwn = null;
let nowPlayingFile = "";
let lastNowPlaying = null;
let undo = null;             // a deleted playlist, for a few seconds
const radio = new Radio();
const radioState = { position: 0, paused: true };   // Radio starts paused after a restart: press Play

let defaults = {};
try {
  const response = await fetch("/api/bootstrap");
  if (!response.ok) throw new Error("catalog unavailable");
  const initial = await response.json();
  defaults = initial.defaults;
  catalog = initial.tracks;
  nowPlayingFile = initial.nowPlayingFile || "";
} catch {
  log("Initial catalog could not be read");
}
await loadLibrary();

try {
  const stored = JSON.parse(localStorage.getItem(storageKey));
  prefs = settings({ ...(liveLaunch && !stored ? { mode: "Resonance" } : {}),
    ...stored, slots: { ...defaults, ...stored?.slots } });
  // a slot added after the player was first used (fishing, venture, moghouse in 0.2.0): its bundled default
  for (const slot of SLOTS) if (!prefs.slots[slot] && defaults[slot] && !(stored?.slots && slot in stored.slots))
    prefs.slots[slot] = defaults[slot];
} catch {
  prefs = settings({ slots: defaults });
  log("Stored settings could not be read");
}

function log(event, detail) {
  journal.push({ at: new Date().toISOString(), event, ...(detail ? { detail } : {}) });
  if (journal.length > 300) journal.shift();
}

function notice(message, action = null) {
  $("notice-text").textContent = message;
  const button = $("notice-action");
  button.hidden = !action;
  if (action) {
    button.textContent = action.label;
    button.onclick = () => {
      button.hidden = true;
      action.run();
    };
  }
}

let saveFailed = false;
function save() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(prefs));
    saveFailed = false;
  } catch {
    saveFailed = true;
    notice("Settings and playlists could not be saved on this PC (the browser's storage is full or blocked).");
  }
  renderSaved();
}

async function loadLibrary() {
  try {
    const response = await fetch("/api/library");
    if (!response.ok) throw new Error("library unavailable");
    library = await response.json();
  } catch {
    library = { sets: [], tracks: {} };
  }
}

const errors = (target, message) => {
  log("Audio fallback", { target: target.channel, reason: message });
  if (message === "Use Enable audio to allow playback") {
    enabled = false;
    notice("Your browser stopped the music from starting.", { label: "Start music", run: start });
  }
};

const music = new Mixer({
  loading() { pending = true; renderStatus(); },
  settled(target) {
    pending = false;
    selected = target;
    if (target) lastPlayed = target;
    renderStatus();
  },
  changed(target) {
    pending = false;
    selected = target;
    if (target) lastPlayed = target;
    log("Music changed", { source: target?.ownership ?? "silence", channel: target?.channel ?? "" });
    renderStatus();
  },
  ended(target) {
    if (target.channel === "album") {
      nextAlbum(prefs, 1, true, queue());
      apply(false, queue().length === 1);
    } else if (target.channel === "radio") {
      radio.next(radioPool(prefs, library));
      radioState.position = 0;
      apply(false, radioPool(prefs, library).length === 1);
    }
  },
  error: errors,
  failed(target) {
    failed.add(target.key + ":" + target.id);
    if (target.channel === "radio") {
      // an unplayable Radio track is skipped; after a whole round of failures Radio stops with a message
      const pool = radioPool(prefs, library);
      if ([...failed].filter(key => key.startsWith("radio/")).length >= pool.length) {
        radioState.paused = true;
        notice("None of the Radio tracks could be played.");
      } else radio.next(pool);
      radioState.position = 0;
    }
    reconcile();
  }
});

const ambience = new Mixer({ changed() {}, ended() {}, error: errors });

function queue() {
  return queueOf(prefs, library);
}

function radioContext() {
  return { id: radio.current(), index: radio.index, position: radioState.position, paused: radioState.paused };
}

function plan(now = performance.now()) {
  return select(prefs, game, now, emergency, { queue: queue(), radio: radioContext() });
}

function checkpoint() {
  if (prefs.listen === "playlist" && !prefs.paused && selected?.channel === "album"
      && selected.key === "album/" + prefs.cursor && selected.id === queue()[prefs.cursor]) {
    const position = music.position(selected.key);
    if (Number.isFinite(position)) prefs.position = Math.round(position * 1000) / 1000;
  }
  if (prefs.listen === "radio" && !radioState.paused && selected?.channel === "radio"
      && selected.id === radio.current()) {
    const position = music.position(selected.key);
    if (Number.isFinite(position)) radioState.position = Math.round(position * 1000) / 1000;
  }
}

function volumes() {
  const v = prefs.volume;
  return { ...v, activity: v.exploration, zone: v.exploration, radio: v.album };
}

function reconcile(retry = false) {
  clearTimeout(graceTimer);
  const now = performance.now();
  const chosen = plan(now);
  if (chosen.phase === "grace") {
    graceTimer = setTimeout(reconcile, Math.max(1, game.endedAt + prefs.grace * 1000 - now));
  } else if (prefs.listen === "game" && game.fishedAt !== null && !game.game.fishing) {
    // the fishing tune's hold runs out by itself
    graceTimer = setTimeout(reconcile, Math.max(1, game.fishedAt + FISHING_HOLD * 1000 - now + 5));
  }
  music.setVolume(volumes());
  ambience.setVolume(volumes());
  const planKey = JSON.stringify(chosen.stack.map(target => [target.key, target.id]));
  if (retry || planKey !== previousPlan) {
    for (const key of [...failed]) if (!key.startsWith("radio/")) failed.delete(key);
  }
  if (retry) failed.clear();
  previousPlan = planKey;
  if (enabled) {
    // In live mode the game itself plays its own music, so only VanaSync's own tracks play here.
    const stack = chosen.stack.filter(target => !failed.has(target.key + ":" + target.id)
      && (!live || target.ownership === "custom"));
    const fade = emergency || game.game.cutscene ? 0 : prefs.fade;
    if (game.game.cutscene && selected && selected.key !== "cutscene") music.stop();
    music.reconcile(stack, catalog, fade, retry);
    ambience.reconcile(chosen.ambience ? [chosen.ambience] : [], catalog, fade, retry);
  }
  renderStatus();
}

// ---------- what the player shows ----------

function capabilities() {
  const addon = game.game.addon || "";
  const newer = live && addon >= "0.2.0";
  return { battle: live ? "Automatic" : "Not connected", fishing: newer ? "Automatic" : "Manual only",
    venture: newer ? "Automatic" : "Manual only", mog: newer ? "Automatic" : "Not connected" };
}

function playingCredit() {
  return selected && catalog[selected.id] ? credit(selected.id, library, catalog) : null;
}

function isPaused() {
  return (prefs.listen === "playlist" && prefs.paused) || (prefs.listen === "radio" && radioState.paused);
}

function renderStatus() {
  const chosen = plan();
  const { phase, kind, stack } = chosen;
  $("phase").textContent = game.game.cutscene ? "Cutscene" : phaseNames[phase];
  $("indicator").dataset.phase = game.game.cutscene ? "" : phase;
  $("arrangement").textContent = phase === "exploration" ? "" : kind[0].toUpperCase() + kind.slice(1);
  $("listen-badge").textContent = listenNames[prefs.listen];
  const playing = playingCredit();
  // paused: the track Playlist / Radio stopped on (only that list's own track, never one from somewhere else)
  const own = { playlist: "album", radio: "radio" }[prefs.listen];
  const paused = !playing && isPaused() && lastPlayed?.channel === own && catalog[lastPlayed.id]
    ? credit(lastPlayed.id, library, catalog) : null;
  const title = !enabled ? "Music not started" : playing ? playing.title : paused ? paused.title
    : pending ? "Loading audio" : live ? "The game’s own music" : "No audio playing";
  if ($("track").textContent !== title) $("track").textContent = title;
  $("artist").textContent = (playing || paused)?.artist ? "by " + (playing || paused).artist : "";
  const desired = stack[0];
  let status;
  if (!enabled) status = "Press Start music once to let VanaSync play.";
  else if (emergency) status = "Game music only. Press Start music to return to your choice.";
  else if (pending) status = "Changing tracks";
  else if (paused) status = "Paused";
  else if (playing) {
    const where = { battle: "Battle music", activity: prefs.listen === "game" ? "Game Sync · " + (selected.key.endsWith("fishing")
      ? "Fishing" : "Ventures") : listenNames[prefs.listen], zone: "Game Sync · Mog House", album: "Playlist",
      radio: "Radio", exploration: "", ambience: "" }[selected.channel] ?? "";
    status = where || "Playing";
  } else if (desired?.ownership === "custom" && desired.id && !catalog[desired.id])
    status = "That track is missing. Pick another in Music library, or the game’s own music plays.";
  else if (desired?.key === "album/empty") status = "This playlist is empty: add a track below.";
  else if (desired?.key === "radio/empty" || (prefs.listen === "radio" && !radioPool(prefs, library).length))
    status = "Choose at least one album for Radio below.";
  else if (prefs.listen === "radio" && radioState.paused) status = "Radio is paused: press Play.";
  else if (prefs.listen === "playlist" && prefs.paused) status = "Paused: press Resume.";
  else status = live ? "The game’s own music is playing." : "No VanaSync music right now.";
  $("transport-status").textContent = status;
  $("enable").hidden = enabled && !emergency;
  $("enable").textContent = emergency ? "Return to my music" : "Start music";
  $("back-to-game").hidden = prefs.listen === "game";
  // the one window title everything follows: what really plays now
  const shown = playing ? windowTitle(playing) : paused ? windowTitle(paused, true) : "VanaSync";
  if (document.title !== shown) document.title = shown;
  writeNowPlaying(playing ? nowPlayingText(playing) : paused ? nowPlayingText(paused, true) : "");
  renderConnection();
  $("position").textContent = clock(prefs.position);
  const now = radio.current();
  $("radio-now").textContent = now && catalog[now] ? credit(now, library, catalog).title : "";
}

function renderConnection() {
  const caps = capabilities();
  $("connection-dot").dataset.on = String(live);
  $("connection-text").textContent = live ? "Connected to the game"
    : liveLaunch ? "Not connected to the game. Music you choose here still plays."
    : "Not connected to the game (test page). Music you choose here still plays.";
  for (const key of ["battle", "fishing", "venture", "mog"]) $("auto-" + key).textContent = caps[key];
  for (const button of document.querySelectorAll("[data-listen]")) {
    const on = button.dataset.listen === prefs.listen;
    button.setAttribute("aria-checked", String(on));
    button.tabIndex = on ? 0 : -1;
  }
  $("simulator").hidden = live;
}

async function writeNowPlaying(text) {
  if (!prefs.nowPlaying || text === lastNowPlaying) return;
  lastNowPlaying = text;
  try {
    await fetch("/api/nowplaying", { method: "POST", headers: { "X-VanaSync": "1", "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: true, text }) });
  } catch {
    lastNowPlaying = null;
  }
}

function clock(value) {
  const seconds = Math.floor(value);
  return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
}

function owning() {
  return enabled && !emergency && !pending && selected?.ownership === "custom";
}

async function reportOwner() {
  const own = live && owning();
  if (own === lastOwn && !own) return;
  lastOwn = own;
  try {
    await fetch("/api/owner", { method: "POST", headers: { "X-VanaSync": "1",
      "Content-Type": "application/json" }, body: JSON.stringify({ own }) });
  } catch {
    lastOwn = null;
  }
}

const gameFields = ["engaged", "members", "alliance", "zone", "cutscene", "fishing", "venture", "mog"];

async function pollGame() {
  if (livePolling || disposed) return;
  livePolling = true;
  try {
    const response = await fetch("/api/game");
    const data = response.ok ? await response.json() : { live: false };
    if (data.live !== live) {
      live = data.live === true;
      log(live ? "Game connected" : "Game disconnected");
      document.body.classList.toggle("live", live);
      for (const id of gameFields) $(id).disabled = live;
      if (!live) {
        // Hand music back to the game: no battle, no cutscene, nothing the game was doing.
        game.update({ ...game.game, engaged: false, cutscene: false, fishing: false, venture: false, mog: false },
          performance.now());
        game.forgetFishing();
        lastLive = "";
      }
      reconcile();
    }
    if (live && data.state) {
      const key = JSON.stringify(data.state);
      if (key !== lastLive) {
        lastLive = key;
        checkpoint();
        game.update(data.state, performance.now());
        for (const [id, value] of Object.entries(data.state)) {
          if (!$(id)) continue;
          if (typeof value === "boolean") $(id).checked = value;
          else $(id).value = value;
        }
        log("Game state changed", { ...game.game });
        reconcile();
      }
    }
  } catch {
    // Host closed; nothing to do until it comes back.
  } finally {
    livePolling = false;
    reportOwner();
  }
}

function apply(capture = true, retry = false) {
  if (capture) checkpoint();
  save();
  renderSettings();
  reconcile(retry);
}

function option(label, value) {
  return new Option(label, value);
}

function titleOf(id) {
  return catalog[id] ? credit(id, library, catalog).title : "";
}

function trackOptions() {
  return Object.keys(catalog).sort((a, b) => titleOf(a).localeCompare(titleOf(b)))
    .map(id => option(titleOf(id) + (library.tracks[id]?.artist ? " — " + library.tracks[id].artist : ""), id));
}

function renderAssignments() {
  for (const slot of SLOTS) {
    const field = $("slot-" + slot);
    const current = prefs.slots[slot];
    const entries = [option("Unassigned", ""), ...trackOptions()];
    if (current && !catalog[current]) entries.push(option("Missing file (assignment kept)", current));
    field.replaceChildren(...entries);
    field.value = current;
  }
}

// ---------- Playlist Mode ----------

function activePlaylist() {
  return prefs.active.startsWith("pl:") ? prefs.playlists.find(p => "pl:" + p.id === prefs.active) : null;
}

function albums() {
  return library.sets.filter(set => set.group === "album"
    && Object.values(library.tracks).some(track => track.set === set.id));
}

function renderLists() {
  const field = $("active-list");
  const groups = [];
  const listed = albums();
  if (listed.length) {
    const group = document.createElement("optgroup");
    group.label = "Albums";
    group.append(...listed.map(set => option(set.id + " · " + set.name + (set.artist ? " — " + set.artist : ""),
      "set:" + set.id)));
    groups.push(group);
  }
  if (prefs.playlists.length) {
    const group = document.createElement("optgroup");
    group.label = "My playlists";
    group.append(...prefs.playlists.map(p => option(p.name, "pl:" + p.id)));
    groups.push(group);
  }
  if (!groups.length) groups.push(option("Nothing yet: make a playlist", ""));
  field.replaceChildren(...groups);
  field.value = prefs.active;
  const own = activePlaylist();
  $("pl-edit-row").hidden = !own;
  $("pl-add").hidden = !own;
  $("pl-import-box").hidden = !own;
  if (own && document.activeElement !== $("pl-name")) $("pl-name").value = own.name;
  $("pl-pick").replaceChildren(...trackOptions());
  renderPlaylist();
}

function renderSaved() {
  $("pl-saved").textContent = activePlaylist() ? (saveFailed ? "Not saved: this browser refused to store it."
    : "Saved on this PC") : "";
  $("pl-saved").dataset.failed = String(saveFailed);
}

function renderPlaylist() {
  const own = activePlaylist();
  const tracks = queue();
  const items = tracks.map((id, index) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    const info = catalog[id] ? credit(id, library, catalog) : null;
    name.textContent = info ? info.title + (info.artist ? " — " + info.artist : "") : "Missing file";
    if (!info) name.className = "missing";
    item.append(name);
    item.setAttribute("aria-current", String(index === prefs.cursor));
    if (own) {
      for (const [text, label, delta] of [["↑", "Move earlier", -1], ["↓", "Move later", 1], ["Remove", "Remove", 0]]) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text;
        button.setAttribute("aria-label", label + " track " + (index + 1));
        button.disabled = index + delta < 0 || index + delta >= tracks.length;
        button.onclick = () => editTrack(own, index, delta);
        item.append(button);
      }
    }
    return item;
  });
  $("playlist").replaceChildren(...items);
  const empty = $("playlist-empty");
  empty.hidden = tracks.length > 0;
  empty.textContent = own ? "This playlist is empty. Add a track below, or import songs."
    : prefs.active ? "This album has no tracks on this PC yet." : "Make a playlist to start.";
}

function editTrack(own, index, delta) {
  checkpoint();
  const tracks = own.tracks;
  if (!delta) {
    tracks.splice(index, 1);
    if (index === prefs.cursor) prefs.position = 0;
    if (index < prefs.cursor || prefs.cursor >= tracks.length) prefs.cursor = Math.max(0, prefs.cursor - 1);
  } else {
    const next = index + delta;
    [tracks[index], tracks[next]] = [tracks[next], tracks[index]];
    if (prefs.cursor === index) prefs.cursor = next;
    else if (prefs.cursor === next) prefs.cursor = index;
  }
  renderPlaylist();
  apply(false);
}

function chooseList(value) {
  checkpoint();
  if (value === prefs.active) return;
  prefs.active = value;
  prefs.cursor = 0;
  prefs.position = 0;
  renderLists();
  apply(false);
}

function newPlaylist() {
  if (prefs.playlists.length >= 50) return notice("You have 50 playlists, the most this player keeps.");
  const id = newPlaylistId(prefs);
  prefs.playlists.push({ id, name: "Playlist " + (prefs.playlists.length + 1), tracks: [] });
  chooseList("pl:" + id);
  renderLists();
  $("pl-name").focus();
  $("pl-name").select();
}

function deletePlaylist() {
  const own = activePlaylist();
  if (!own) return;
  checkpoint();
  const at = prefs.playlists.indexOf(own);
  const wasPlaying = prefs.listen === "playlist";
  prefs.playlists.splice(at, 1);
  undo = { list: own, at, cursor: prefs.cursor, position: prefs.position };
  // the deleted playlist stops; the next list is chosen, paused, so nothing starts by surprise
  prefs.active = prefs.playlists.length ? "pl:" + prefs.playlists[Math.min(at, prefs.playlists.length - 1)].id
    : albums().length ? "set:" + albums()[0].id : "";
  prefs.cursor = 0;
  prefs.position = 0;
  if (wasPlaying) prefs.paused = true;
  renderLists();
  apply(false);
  notice("Deleted “" + own.name + "”. The songs themselves are still in your library.", { label: "Undo", run: () => {
    if (!undo) return;
    prefs.playlists.splice(Math.min(undo.at, prefs.playlists.length), 0, undo.list);
    prefs.active = "pl:" + undo.list.id;
    prefs.cursor = undo.cursor;
    prefs.position = undo.position;
    undo = null;
    renderLists();
    apply(false);
    notice("“" + prefs.playlists.find(p => "pl:" + p.id === prefs.active).name + "” is back.");
  } });
}

// ---------- Radio ----------

function renderRadio() {
  const box = $("radio-albums");
  const choices = albums().map(set => ({ key: set.id, label: set.id + " · " + set.name
    + (set.artist ? " — " + set.artist : ""), help: null }));
  const mine = Object.values(library.tracks).filter(t => t.origin === "import" && radioEligible(t)).length;
  if (mine) choices.push({ key: "mine", label: "My listening music (" + mine + ")", help: "mine" });
  box.replaceChildren(...choices.map(choice => {
    const label = document.createElement("label");
    label.className = "check";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = prefs.radio.includes(choice.key);
    input.onchange = () => {
      prefs.radio = input.checked ? [...new Set([...prefs.radio, choice.key])] : prefs.radio.filter(k => k !== choice.key);
      syncRadio();
      apply(false);
    };
    label.append(input, " " + choice.label);
    return label;
  }));
  const empty = $("radio-empty");
  empty.hidden = choices.length > 0 && prefs.radio.length > 0;
  empty.textContent = !choices.length
    ? "No listening albums are on this PC yet. Artist albums arrive with VanaSync updates; your own imports can be marked as listening music in Music library > My imports."
    : "Tick at least one album.";
  $("radio-pause").textContent = radioState.paused ? "Play" : "Pause";
  $("radio-interrupt").checked = prefs.radioInterrupt;
}

function syncRadio() {
  const pool = radioPool(prefs, library);
  radio.sync(pool);
  if (pool.length && !radio.current()) radio.start(pool);
  if (!pool.length) radioState.paused = true;
}

// ---------- Music library ----------

function renderLibrary() {
  const root = $("library");
  const parts = [];
  const section = (title, help) => {
    const head = document.createElement("h3");
    head.textContent = title;
    if (help) head.append(" ", helpButton(help, "About " + title));
    parts.push(head);
  };
  const list = ids => {
    const ol = document.createElement("ol");
    ol.append(...ids.map(id => {
      const li = document.createElement("li");
      const info = credit(id, library, catalog);
      li.textContent = info.title + (info.artist ? " — " + info.artist : "");
      return li;
    }));
    parts.push(ol);
  };
  const inSet = set => Object.entries(library.tracks).filter(([, t]) => t.set === set.id)
    .sort((a, b) => a[1].no - b[1].no).map(([id]) => id);
  // Gameplay soundtrack: Battle Themes, the activities, Zone Music. Never in Radio.
  const gameplay = library.sets.filter(set => set.group === "gameplay");
  for (const set of gameplay.filter(s => s.section !== "zone")) {
    section(set.id + " · " + set.name);
    list(inSet(set));
  }
  section("Zone Music", "mog");
  const zones = document.createElement("div");
  zones.className = "zones";
  const zoneSelect = (key, label, inherit) => {
    const field = document.createElement("select");
    field.id = "zone-" + key.replace(":", "-");
    field.append(option(inherit, ""), option("The game’s own music", "native"), ...trackOptions());
    const value = prefs.zones[key] ?? "";
    if (value && value !== "native" && !catalog[value]) field.append(option("Missing file (choice kept)", value));
    field.value = value;
    field.onchange = () => {
      if (field.value) prefs.zones[key] = field.value;
      else delete prefs.zones[key];
      apply();
    };
    const wrap = document.createElement("label");
    wrap.append(label, field);
    return wrap;
  };
  const mogDefault = prefs.slots.moghouse && catalog[prefs.slots.moghouse] ? titleOf(prefs.slots.moghouse) : "none";
  zones.append(zoneSelect("mog", "All Mog Houses", "Mog House theme (" + mogDefault + ")"));
  const apply_all = document.createElement("button");
  apply_all.type = "button";
  apply_all.textContent = "Use “All Mog Houses” everywhere";
  apply_all.title = "Clears every house's own choice, so each one plays the All Mog Houses choice.";
  apply_all.onclick = () => {
    const own = Object.keys(prefs.zones).filter(k => k.startsWith("mog:"));
    for (const key of own) delete prefs.zones[key];
    notice(own.length ? own.length + " Mog House choice" + (own.length > 1 ? "s" : "") + " cleared." : "No house had a choice of its own.");
    apply();
    renderLibrary();
  };
  zones.append(apply_all);
  const byNation = {};
  for (const house of MOG_HOUSES) (byNation[house.nation] ??= []).push(house);
  for (const [nation, houses] of Object.entries(byNation)) {
    const group = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Mog Houses · " + nation;
    group.append(summary, ...houses.map(h => zoneSelect("mog:" + h.zone, h.name, "Same as All Mog Houses")));
    zones.append(group);
  }
  parts.push(zones);
  for (const set of library.sets.filter(s => s.group === "album")) {
    section(set.id + " · " + set.name + (set.artist ? " — " + set.artist : ""));
    const ids = inSet(set);
    if (ids.length) list(ids);
    else {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = "Not on this PC yet.";
      parts.push(p);
    }
  }
  const imports = Object.entries(library.tracks).filter(([, t]) => t.origin === "import");
  section("My imports", "import");
  if (!imports.length) {
    const p = document.createElement("p");
    p.className = "hint";
    p.textContent = "Songs you import (Playlist > Import songs) show here. MP3 only; they stay on this PC.";
    parts.push(p);
  }
  for (const [id, track] of imports) parts.push(creditCard(id, track, false));
  root.replaceChildren(...parts);
}

function helpButton(key, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "help";
  button.dataset.help = key;
  button.setAttribute("aria-label", label);
  button.textContent = "?";
  return button;
}

// An imported song's credits: what its tags said, what the player corrected, and whether it is listening music
// (Radio may play it). fresh: just imported, with Keep / Remove.
function creditCard(id, track, fresh) {
  const card = document.createElement("form");
  card.className = "credit";
  card.onsubmit = event => event.preventDefault();
  const head = document.createElement("p");
  head.textContent = (catalog[id] ?? track.file ?? "") + (fresh ? " · check the credits" : "");
  card.append(head);
  const tagged = track.tagged ?? {};
  const fields = {};
  for (const [key, label] of [["title", "Title"], ["artist", "Artist"], ["album", "Album"], ["track", "Track number"]]) {
    const input = document.createElement("input");
    input.maxLength = 200;
    input.value = track[key] || (key === "title" ? trackTitle(catalog[id] ?? track.file ?? "") : "");
    input.placeholder = key === "artist" ? "Artist not provided" : "";
    fields[key] = input;
    const wrap = document.createElement("label");
    wrap.append(label, input);
    card.append(wrap);
  }
  if (!tagged.artist) {
    const warn = document.createElement("p");
    warn.className = "hint";
    warn.textContent = "This file has no Artist tag. Type the artist or group to credit, or leave it empty.";
    card.append(warn);
  }
  const listening = document.createElement("label");
  listening.className = "check";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = track.role === "listening";
  listening.append(box, " Listening music (Radio may play it)");
  card.append(listening);
  const row = document.createElement("div");
  row.className = "row";
  const keep = document.createElement("button");
  keep.type = "button";
  keep.textContent = fresh ? "Keep" : "Save credits";
  keep.onclick = async () => {
    const edit = {};
    for (const [key, input] of Object.entries(fields)) {
      const value = input.value.trim();
      if (value && value !== (tagged[key] || "")) edit[key] = value;
    }
    const ok = await post("/api/meta", { id, edit, listening: box.checked });
    notice(ok ? "Credits saved." : "The credits could not be saved.");
    await refreshLibrary(true);
  };
  row.append(keep);
  if (fresh) {
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Remove from VanaSync";
    cancel.onclick = async () => {
      const ok = await post("/api/remove", { id });
      if (ok) for (const list of prefs.playlists) list.tracks = list.tracks.filter(t => t !== id);
      notice(ok ? "Removed. Your own file was not touched." : "It could not be removed.");
      card.remove();
      await refreshLibrary(true);
      apply(false);
    };
    row.append(cancel);
  }
  card.append(row);
  return card;
}

async function post(path, body) {
  try {
    const response = await fetch(path, { method: "POST", headers: { "X-VanaSync": "1", "Content-Type": "application/json" },
      body: JSON.stringify(body) });
    return response.ok;
  } catch {
    return false;
  }
}

// ---------- settings ----------

function place() {
  const player = $("player");
  const available = Math.max(280, document.documentElement.clientWidth - 16);
  const scale = Math.min(prefs.scale, available / player.offsetWidth);
  const centered = (document.documentElement.clientWidth - player.offsetWidth) / 2;
  const left = centered - (scale - 1) * player.offsetWidth / 2;
  const right = left + scale * player.offsetWidth;
  const horizontal = Math.max(8 - left, Math.min(available + 8 - right, prefs.x));
  const vertical = Math.max(-player.offsetTop + 8, Math.min(innerHeight - 125, prefs.y));
  player.style.transform = "translate(" + horizontal + "px," + vertical + "px) scale(" + scale + ")";
  player.style.opacity = prefs.transparency;
  return [horizontal, vertical];
}

function renderSettings() {
  for (const id of ["mode", "override", "grace", "fade", "scale", "transparency"])
    $(id).value = prefs[id];
  for (const id of ["locked", "sync", "interrupt", "repeat"]) $(id).checked = prefs[id];
  $("now-playing").checked = prefs.nowPlaying;
  $("now-playing-file").textContent = prefs.nowPlaying && nowPlayingFile ? "File: " + nowPlayingFile : "";
  for (const [channel, id] of Object.entries(volumeIds)) $(id).value = prefs.volume[channel];
  for (const action of Object.keys(KEYS)) $("key-" + action).value = prefs.keys[action];
  $("drag").classList.toggle("locked", prefs.locked);
  $("quick-lock").textContent = prefs.locked ? "Unlock position" : "Lock position";
  $("deck").hidden = prefs.collapsed;
  $("collapse").textContent = prefs.collapsed ? "+" : "−";
  $("collapse").setAttribute("aria-label", prefs.collapsed ? "Expand player" : "Collapse player");
  $("collapse").setAttribute("aria-expanded", String(!prefs.collapsed));
  for (const name of ["game", "playlist", "radio"]) $("panel-" + name).hidden = prefs.listen !== name;
  $("panel-activity").hidden = !["fishing", "venture"].includes(prefs.listen);
  if (["fishing", "venture"].includes(prefs.listen)) {
    const id = prefs.slots[prefs.listen];
    $("activity-text").textContent = (prefs.listen === "fishing" ? "Fishing music" : "Venture music")
      + (id && catalog[id] ? ": " + titleOf(id) : "") + ". It keeps playing until you choose something else.";
    const missing = $("activity-missing");
    missing.hidden = !!(id && catalog[id]);
    missing.textContent = "That tune is not in your library. Pick one in More settings > Track assignments; the game’s own music plays meanwhile.";
  }
  $("pause").textContent = prefs.paused ? "Resume" : "Pause";
  for (const id of ["previous", "pause", "next"]) $(id).disabled = !queue().length;
  renderRadio();
  renderSaved();
  place();
  for (const [index, row] of [...$("playlist").children].entries())
    row.setAttribute("aria-current", String(index === prefs.cursor));
}

async function refreshLibrary(force = false) {
  const before = JSON.stringify(library);
  await loadLibrary();
  if (force || JSON.stringify(library) !== before) {
    renderLists();
    renderLibrary();
    syncRadio();
    renderSettings();
  }
}

async function refreshCatalog() {
  if (polling || disposed) return;
  polling = true;
  try {
    const response = await fetch("/api/tracks");
    if (!response.ok) throw new Error("catalog unavailable");
    const next = await response.json();
    if (JSON.stringify(next) !== JSON.stringify(catalog)) {
      checkpoint();
      catalog = next;
      await refreshLibrary(true);
      renderAssignments();
      reconcile();
    }
  } catch {
    if (Object.keys(catalog).length) {
      checkpoint();
      catalog = {};
      renderAssignments();
      renderLists();
      log("Catalog connection lost");
      reconcile();
    }
  } finally {
    polling = false;
  }
}

async function importTracks(event) {
  const field = event.currentTarget;
  const files = [...field.files];
  const own = activePlaylist();
  field.disabled = true;
  let imported = 0;
  const problems = [];
  const fresh = [];
  try {
    for (const file of files) {
      if (!/\.mp3$/i.test(file.name)) {
        problems.push(file.name + ": only MP3 files can be added");
        continue;
      }
      if (own && own.tracks.length >= 200) {
        problems.push(file.name + ": a playlist holds 200 tracks");
        continue;
      }
      try {
        const response = await fetch("/api/tracks", { method: "POST", body: file,
          headers: { "Content-Type": "application/octet-stream", "X-VanaSync": "1",
            "X-Filename": encodeURIComponent(file.name) } });
        const answer = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(answer.error === "Not an MP3 file"
          ? "this is not really an MP3 (renamed?)" : answer.error || "it was refused");
        catalog[answer.id] = answer.filename;
        if (own && !own.tracks.includes(answer.id)) own.tracks.push(answer.id);
        if (!answer.existed) fresh.push(answer.id);
        imported++;
      } catch (error) {
        problems.push(file.name + ": " + error.message);
      }
    }
    notice(imported + " imported" + (problems.length ? " · " + problems.join("; ") : ""));
    log("Import completed", { imported, rejected: problems.length });
    await refreshLibrary(true);
    renderAssignments();
    apply();
    // the credits of each new song, to check before it is kept
    const box = $("pl-import-box");
    for (const id of fresh) if (library.tracks[id]) box.append(creditCard(id, library.tracks[id], true));
  } finally {
    field.value = "";
    field.disabled = false;
  }
}

function restore() {
  checkpoint();
  save();
  emergency = true;
  enabled = true;
  music.stop();
  ambience.stop();
  log("Emergency restoration requested");
  reconcile();
}

function start() {
  checkpoint();
  enabled = true;
  emergency = false;
  notice("");
  apply(false, true);
}

function setListen(value) {
  if (!LISTEN.includes(value)) return;
  checkpoint();
  prefs.listen = value;
  if (value === "radio") {
    syncRadio();
    if (radioPool(prefs, library).length) radioState.paused = false;
  }
  if (value === "playlist" && queue().length) prefs.paused = false;
  if (value === "game") game.forgetFishing();   // fresh: only what the game says from now on
  if (!enabled && liveLaunch) enabled = true;
  apply(false);
}

function toggleAlbum() {
  setListen(prefs.listen === "playlist" ? "game" : "playlist");
}

function toggleCollapse() {
  prefs.collapsed = !prefs.collapsed;
  apply();
}

// ---------- help: hover, keyboard focus and tap ----------

let helpFor = null;
function showHelp(button) {
  const pop = $("help-pop");
  pop.textContent = HELP[button.dataset.help] ?? "";
  pop.hidden = false;
  helpFor = button;
  button.setAttribute("aria-describedby", "help-pop");
  button.setAttribute("aria-expanded", "true");
  const box = button.getBoundingClientRect();
  const width = Math.min(300, innerWidth - 16);
  pop.style.maxWidth = width + "px";
  pop.style.left = Math.max(8, Math.min(box.left, innerWidth - width - 8)) + "px";
  const below = box.bottom + 6;
  pop.style.top = (below + pop.offsetHeight > innerHeight ? Math.max(8, box.top - pop.offsetHeight - 6) : below) + "px";
}
function hideHelp() {
  if (!helpFor) return;
  helpFor.removeAttribute("aria-describedby");
  helpFor.setAttribute("aria-expanded", "false");
  helpFor = null;
  $("help-pop").hidden = true;
}
document.addEventListener("click", event => {
  const button = event.target.closest?.(".help");
  if (button) {
    event.preventDefault();
    event.stopPropagation();
    if (helpFor === button) hideHelp();
    else showHelp(button);
    return;
  }
  hideHelp();
  $("quick").hidden = true;
}, true);
document.addEventListener("focusin", event => {
  if (event.target.classList?.contains("help")) showHelp(event.target);
  else hideHelp();
});
document.addEventListener("mouseover", event => {
  const button = event.target.closest?.(".help");
  if (button && helpFor !== button) showHelp(button);
});
document.addEventListener("mouseout", event => {
  const button = event.target.closest?.(".help");
  if (button && helpFor === button && document.activeElement !== button
      && !button.contains(event.relatedTarget)) hideHelp();
});

// ---------- wiring ----------

for (const slot of SLOTS) {
  const field = document.createElement("select");
  field.id = "slot-" + slot;
  const label = document.createElement("label");
  label.append(slotLabels[slot], field);
  $("slots").append(label);
  field.onchange = () => {
    prefs.slots[slot] = field.value;
    apply();
    renderLibrary();
  };
}

const shortcutValues = ["", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
  ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];
for (const action of Object.keys(KEYS)) {
  const field = $("key-" + action);
  field.replaceChildren(...shortcutValues.map(key => option(key || "Disabled", key)));
  field.onchange = () => {
    if (field.value && Object.entries(prefs.keys).some(([other, key]) => other !== action && key === field.value)) {
      notice("That shortcut is already assigned.");
      renderSettings();
      return;
    }
    prefs.keys[action] = field.value;
    apply();
  };
}

for (const id of ["mode", "override", "grace", "fade", "locked", "sync", "interrupt", "repeat",
    "scale", "transparency"]) {
  const field = $(id);
  field.addEventListener(field.type === "range" ? "input" : "change", () => {
    checkpoint();
    const value = field.type === "checkbox" ? field.checked
      : ["range", "number"].includes(field.type) ? field.valueAsNumber : field.value;
    prefs = settings({ ...prefs, [id]: value });
    apply(false);
  });
}
$("radio-interrupt").onchange = () => {
  checkpoint();
  prefs.radioInterrupt = $("radio-interrupt").checked;
  apply(false);
};
$("now-playing").onchange = async () => {
  prefs.nowPlaying = $("now-playing").checked;
  lastNowPlaying = null;
  if (!prefs.nowPlaying) {
    // switched off: the file is emptied once, so a stream does not keep showing an old song
    await fetch("/api/nowplaying", { method: "POST", headers: { "X-VanaSync": "1", "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: true, text: "" }) }).catch(() => {});
  }
  apply();
};
for (const [channel, id] of Object.entries(volumeIds)) {
  $(id).oninput = () => {
    prefs.volume[channel] = $(id).valueAsNumber;
    apply();
  };
}
for (const id of gameFields) {
  $(id).onchange = () => {
    checkpoint();
    const members = Math.max(1, Math.min(18, Math.floor($("members").valueAsNumber || 1)));
    const zone = Math.max(1, Math.min(9999, Math.floor($("zone").valueAsNumber || 1)));
    $("members").value = members;
    $("zone").value = zone;
    game.update({ engaged: $("engaged").checked, alliance: $("alliance").checked,
      cutscene: $("cutscene").checked, members, zone, fishing: $("fishing").checked,
      venture: $("venture").checked, mog: $("mog").checked, addon: VERSION }, performance.now());
    log("Simulator state changed", { ...game.game });
    save();
    reconcile();
  };
}
for (const button of document.querySelectorAll("[data-listen]")) {
  button.onclick = () => setListen(button.dataset.listen);
  button.onkeydown = event => {
    const order = [...document.querySelectorAll("[data-listen]")];
    const at = order.indexOf(button);
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const next = order[(at + step + order.length) % order.length];
    setListen(next.dataset.listen);
    next.focus();
  };
}
$("back-to-game").onclick = () => setListen("game");
$("album-import").onchange = event => importTracks(event);
$("enable").onclick = start;
$("restore").onclick = restore;
$("collapse").onclick = toggleCollapse;
$("active-list").onchange = () => chooseList($("active-list").value);
$("pl-new").onclick = newPlaylist;
$("pl-delete").onclick = deletePlaylist;
$("pl-name").oninput = () => {
  const own = activePlaylist();
  if (!own) return;
  own.name = $("pl-name").value.replace(/[\u0000-\u001f\u007f]/g, "").slice(0, 80) || "Playlist";
  save();
  for (const opt of $("active-list").options) if (opt.value === "pl:" + own.id) opt.textContent = own.name;
};
$("pl-add-button").onclick = () => {
  const own = activePlaylist();
  const id = $("pl-pick").value;
  if (!own || !id) return;
  if (own.tracks.length >= 200) return notice("A playlist holds 200 tracks.");
  own.tracks.push(id);
  renderPlaylist();
  apply();
};
$("pause").onclick = () => {
  checkpoint();
  prefs.paused = !prefs.paused;
  if (!prefs.paused && prefs.listen !== "playlist") prefs.listen = "playlist";
  apply(false);
};
for (const [id, step] of [["previous", -1], ["next", 1]]) {
  $(id).onclick = () => {
    nextAlbum(prefs, step, false, queue());
    apply(false, queue().length === 1);
  };
}
$("radio-pause").onclick = () => {
  checkpoint();
  syncRadio();
  if (!radioPool(prefs, library).length) return notice("Choose at least one album for Radio first.");
  radioState.paused = !radioState.paused;
  apply(false);
};
$("radio-next").onclick = () => {
  const pool = radioPool(prefs, library);
  if (!pool.length) return;
  radio.next(pool);
  radioState.position = 0;
  apply(false, pool.length === 1);
};

$("drag").onpointerdown = event => {
  if (prefs.locked || event.button !== 0 || event.target.closest("button")) return;
  const [x, y] = place();
  drag = { pointer: event.pointerId, x: event.clientX - x, y: event.clientY - y };
  $("drag").setPointerCapture(event.pointerId);
};
$("drag").onpointermove = event => {
  if (drag?.pointer !== event.pointerId) return;
  prefs.x = event.clientX - drag.x;
  prefs.y = event.clientY - drag.y;
  place();
};
function finishDrag(event) {
  if (drag?.pointer !== event.pointerId) return;
  drag = null;
  [prefs.x, prefs.y] = place();
  save();
}
$("drag").onpointerup = finishDrag;
$("drag").onpointercancel = finishDrag;
$("drag").onlostpointercapture = finishDrag;
$("reset-position").onclick = () => {
  prefs.x = prefs.y = 0;
  apply();
};
$("player").oncontextmenu = event => {
  if (event.target.closest("input, select")) return;
  event.preventDefault();
  $("quick").hidden = false;
  $("quick").style.left = Math.max(0, Math.min(event.clientX, innerWidth - $("quick").offsetWidth)) + "px";
  $("quick").style.top = Math.max(0, Math.min(event.clientY, innerHeight - $("quick").offsetHeight)) + "px";
  $("quick-lock").focus();
};
$("quick-lock").onclick = () => {
  prefs.locked = !prefs.locked;
  apply();
};
$("quick-settings").onclick = () => {
  prefs.collapsed = false;
  apply();
  $("settings-section").open = true;
  $("settings-section").querySelector("summary").focus();
};
$("quick-restore").onclick = restore;
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    $("quick").hidden = true;
    hideHelp();
  }
  if (event.repeat || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey
      || event.target.closest("input, select, textarea, [contenteditable]")) return;
  const key = event.key.toUpperCase();
  const actions = { collapse: toggleCollapse, album: toggleAlbum, emergency: restore };
  for (const [action, value] of Object.entries(prefs.keys)) {
    if (key === value) {
      event.preventDefault();
      actions[action]();
      return;
    }
  }
});
$("report").onclick = () => {
  const data = JSON.stringify({ version: VERSION, source: live ? "live" : "simulator", events: journal }, null, 2);
  const download = document.createElement("a");
  const url = URL.createObjectURL(new Blob([data], { type: "application/json" }));
  download.href = url;
  download.download = "VanaSync-diagnostics.json";
  download.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
window.addEventListener("resize", place);
const catalogTimer = setInterval(refreshCatalog, 1500);
const gameTimer = setInterval(pollGame, 250);
const positionTimer = setInterval(() => {
  const earlier = prefs.position;
  checkpoint();
  if (prefs.position !== earlier) save();
  renderStatus();
}, 1000);
window.addEventListener("pagehide", () => {
  checkpoint();
  save();
  disposed = true;
  clearInterval(catalogTimer);
  clearInterval(positionTimer);
  clearInterval(gameTimer);
  clearTimeout(graceTimer);
  music.stop(false);
  ambience.stop(false);
});
window.addEventListener("pageshow", event => {
  if (event.persisted) location.reload();
});

if (liveLaunch) enabled = true; // launched by XI Forever Offline with autoplay allowed
syncRadio();
renderLists();
renderLibrary();
renderSettings();
renderAssignments();
refreshCatalog();
pollGame();
reconcile();
