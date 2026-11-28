import test from "node:test";
import assert from "node:assert/strict";
import { settings, CombatState, arrangement, select, trackTitle, nextAlbum } from "../app/core.js";

const id = "1".repeat(32);
const combat = (state, now, fields) => state.update({ ...state.game, ...fields }, now);

test("automatic group boundaries and manual overrides", () => {
  const prefs = settings();
  for (const [members, alliance, expected] of [[1, false, "solo"], [2, false, "party"],
    [6, false, "party"], [7, false, "alliance"], [2, true, "alliance"]]) {
    assert.equal(arrangement(prefs, { members, alliance }), expected);
    for (const override of ["solo", "party", "alliance"])
      assert.equal(arrangement({ ...prefs, override }, { members, alliance }), override);
  }
});

test("grace stays armed across zone and composition updates, and cancels on re-entry", () => {
  const state = new CombatState();
  const prefs = settings({ mode: "Resonance" });
  combat(state, 10, { engaged: true });
  combat(state, 100, { engaged: false });
  combat(state, 200, { members: 3, zone: 2 });
  assert.equal(select(prefs, state, 5099).phase, "grace");
  assert.equal(select(prefs, state, 5099).stack[0].key, "party");
  assert.equal(select(prefs, state, 5100).stack[0].key, "exploration");
  combat(state, 500, { engaged: true });
  assert.equal(select(prefs, state, 9000).phase, "combat");
  combat(state, 9100, { engaged: false });
  assert.equal(select({ ...prefs, grace: 0 }, state, 9100).phase, "exploration");
});

test("soundtrack switching and emergency fallback order", () => {
  const prefs = settings({ mode: "Resonance", sync: true, slots: { solo: id, ambience: id } });
  const state = new CombatState();
  combat(state, 1, { engaged: true });
  const plan = select(prefs, state, 1);
  assert.deepEqual(plan.stack.map(t => t.key), ["solo", "nativeSolo"]);
  assert.equal(plan.stack[0].match, plan.stack[1].match);
  assert.equal(select({ ...prefs, mode: "Vanilla" }, state, 1).stack[0].key, "nativeSolo");
  assert.deepEqual(select({ ...prefs, mode: "Off" }, state, 1).stack, []);
  const emergency = select({ ...prefs, mode: "Off" }, state, 1, true);
  assert.equal(emergency.stack[0].key, "nativeSolo");
  assert.equal(emergency.ambience, null);
});

test("album survives zoning, yields to cutscene or optional battle, resumes saved position", () => {
  const prefs = settings({ albumOn: true, album: [id], position: 17.5, mode: "Resonance" });
  const state = new CombatState();
  combat(state, 1, { zone: 3, engaged: true });
  assert.equal(select(prefs, state, 1).stack[0].position, 17.5);
  assert.equal(select({ ...prefs, interrupt: true }, state, 1).stack[0].key, "solo");
  combat(state, 2, { cutscene: true });
  assert.equal(select(prefs, state, 2).stack[0].key, "cutscene");
  combat(state, 3, { cutscene: false, engaged: false });
  assert.equal(select(prefs, state, 3).stack[0].key, "album/0");
  assert.equal(select({ ...prefs, listen: "game" }, state, 3).stack[0].key, "solo");
  assert.deepEqual(select({ ...prefs, paused: true }, state, 3).stack, []);
});

test("album track order, wrap, and end-of-album pause", () => {
  const prefs = settings({ album: [id, "2".repeat(32)], position: 10 });
  nextAlbum(prefs, 1, true);
  assert.deepEqual([prefs.cursor, prefs.position, prefs.paused], [1, 0, false]);
  nextAlbum(prefs, 1, true);
  assert.deepEqual([prefs.cursor, prefs.paused], [0, true]);
  prefs.repeat = true;
  prefs.paused = false;
  nextAlbum(prefs, -1);
  nextAlbum(prefs, 1, true);
  assert.deepEqual([prefs.cursor, prefs.paused], [0, false]);
});

test("settings round trip sanitizes invalid values and names retain Unicode", () => {
  const prefs = settings({ grace: -3, slots: { party: id, solo: "../file" },
    keys: { album: "F2" }, transparency: 10, volume: { album: 0 } });
  assert.equal(prefs.grace, 0);
  assert.equal(prefs.slots.party, id);
  assert.equal(prefs.slots.solo, "");
  assert.equal(prefs.keys.album, "");
  assert.equal(prefs.transparency, 1);
  assert.equal(prefs.volume.album, 0);
  assert.deepEqual(settings(JSON.parse(JSON.stringify(prefs))), prefs);
  assert.equal(trackTitle("戦闘・Party (Mix).Final.WAV"), "戦闘・Party (Mix).Final");
});

test("copy numbers at the end of a file name are not shown", () => {
  for (const [file, title] of [
    ["Choose to Fight (Special Battle Theme XIFO Exclusive).mp3", "Choose to Fight (Special Battle Theme XIFO Exclusive)"],
    ["Choose to Fight (Special Battle Theme XIFO Exclusive) (1).mp3", "Choose to Fight (Special Battle Theme XIFO Exclusive)"],
    ["Against the Odds (Solo Battle Theme) (1).mp3", "Against the Odds (Solo Battle Theme)"],
    ["Track (2) (1).mp3", "Track"],
    ["Beyond the Veil (Party Battle Theme).mp3", "Beyond the Veil (Party Battle Theme)"],
    ["Night Song (Remix).ogg", "Night Song (Remix)"], ["Encore (Live) (3).wav", "Encore (Live)"],
    ["Symphony No. 5.mp3", "Symphony No. 5"], ["Level 99 Blues.mp3", "Level 99 Blues"],
    ["Opus (1999).mp3", "Opus (1999)"], ["07 (2) Road.mp3", "07 (2) Road"], ["Take(1).mp3", "Take(1)"],
    ["(1).mp3", "(1)"], ["noextension", "noextension"]])
    assert.equal(trackTitle(file), title);
});

test("100,000 simulator updates fit a 2 second regression budget", () => {
  const state = new CombatState();
  const prefs = settings({ mode: "Resonance" });
  const start = performance.now();
  for (let i = 0; i < 100000; i++) {
    combat(state, i, { engaged: i % 3 === 0, members: 1 + i % 18 });
    select(prefs, state, i);
  }
  const elapsed = performance.now() - start;
  assert.ok(elapsed < 2000, String(elapsed));
});

// ---- (0.2.0, 2026-11-27) J's usability, Mog House and Radio updates ----
import { zoneMusic, queueOf, radioPool, radioEligible, shuffleRound, Radio, credit, windowTitle, nowPlayingText,
  newPlaylistId, FISHING_HOLD, MOG_HOUSES } from "../app/core.js";

const A = "a".repeat(32), B = "b".repeat(32), C = "c".repeat(32), MH = "d".repeat(32), FI = "e".repeat(32), VE = "f".repeat(32);
const slots = { moghouse: MH, fishing: FI, venture: VE, exploration: A, solo: B };

test("an old single album list becomes the playlist 'My album' and Album Mode becomes Playlist", () => {
  const prefs = settings({ albumOn: true, album: [A, B], cursor: 1, interrupt: true });
  assert.equal(prefs.listen, "playlist");
  assert.deepEqual(prefs.playlists, [{ id: "palbum", name: "My album", tracks: [A, B] }]);
  assert.equal(prefs.active, "pl:palbum");
  assert.equal(prefs.interrupt, true);                       // an existing battle-switch choice is kept
  assert.equal(settings({}).interrupt, false);              // a new profile: off
  assert.equal(settings({}).radioInterrupt, false);
  const again = settings(JSON.parse(JSON.stringify(prefs)));
  assert.deepEqual(again, prefs);
  // deleting every playlist does not bring the old list back
  assert.deepEqual(settings({ ...prefs, playlists: [] }).playlists, []);
  // bad entries are dropped, names cleaned
  const odd = settings({ playlists: [{ id: "p1", name: " Night\u0007 ", tracks: [A, "../x", B] }, { id: "p1", name: "dup" },
    { id: "../p", name: "bad" }], active: "pl:nope", listen: "dance", zones: { mog: MH, "mog:241": "native", "mog:x": A, cave: A } });
  assert.deepEqual(odd.playlists, [{ id: "p1", name: "Night", tracks: [A, B] }]);
  assert.equal(odd.active, "pl:p1");
  assert.equal(odd.listen, "game");
  assert.deepEqual(odd.zones, { mog: MH, "mog:241": "native" });
});

test("Game Sync: battle first, then fishing (with its hold), the Ventures window, a Mog House, then the game", () => {
  const prefs = settings({ mode: "Resonance", slots });
  const state = new CombatState();
  combat(state, 0, { zone: 241, mog: true });
  assert.equal(select(prefs, state, 0).stack[0].key, "zone/mog");
  assert.equal(select(prefs, state, 0).stack[0].id, MH);
  combat(state, 1, { venture: true });
  assert.equal(select(prefs, state, 1).stack[0].key, "activity/venture");
  combat(state, 2, { fishing: true });
  assert.equal(select(prefs, state, 2).stack[0].id, FI);
  combat(state, 3, { fishing: false });                      // between casts: still fishing music
  assert.equal(select(prefs, state, 3 + FISHING_HOLD * 1000 - 10).stack[0].id, FI);
  assert.equal(select(prefs, state, 3 + FISHING_HOLD * 1000 + 10).stack[0].id, VE);
  combat(state, 5, { engaged: true });                       // a fight: battle music, fishing hold ends
  assert.equal(select(prefs, state, 5).stack[0].key, "solo");
  combat(state, 6, { engaged: false });
  assert.equal(select({ ...prefs, grace: 0 }, state, 7).stack[0].id, VE);
  combat(state, 8, { cutscene: true });
  assert.equal(select(prefs, state, 8).stack[0].key, "cutscene");
  combat(state, 9, { cutscene: false, venture: false, mog: false });
  assert.equal(select(prefs, state, 9 + 5000).stack[0].key, "exploration");   // after the post-combat 5 s
  assert.equal(select(prefs, state, 9 + 5000).stack[0].ownership, "native");
});

test("Mog House music: the house's own choice, then All Mog Houses, then the bundled theme; native means the game's", () => {
  const prefs = settings({ slots });
  assert.equal(zoneMusic(prefs, { mog: false, zone: 241 }), null);
  assert.equal(zoneMusic(prefs, { mog: true, zone: 241 }).id, MH);
  prefs.zones.mog = A;
  assert.equal(zoneMusic(prefs, { mog: true, zone: 241 }).id, A);
  prefs.zones["mog:241"] = "native";
  assert.equal(zoneMusic(prefs, { mog: true, zone: 241 }).native, true);
  assert.equal(zoneMusic(prefs, { mog: true, zone: 230 }).id, A);
  const state = new CombatState();
  combat(state, 0, { zone: 241, mog: true });
  assert.equal(select({ ...prefs, mode: "Off" }, state, 0).stack.length, 0);   // the game's music: nothing of ours
  combat(state, 1, { zone: 9999, mog: true });                                 // a Mog House not in the list
  assert.equal(select(prefs, state, 1).stack[0].id, A);
  assert.equal(new Set(MOG_HOUSES.map(h => h.zone)).size, MOG_HOUSES.length);
});

test("chosen by hand: Fishing / Venture stay through fights and zones; playlists and Radio follow their battle switch", () => {
  const state = new CombatState();
  combat(state, 0, { engaged: true, mog: true });
  const prefs = settings({ mode: "Resonance", slots, listen: "fishing" });
  assert.equal(select(prefs, state, 0).stack[0].id, FI);
  assert.equal(select({ ...prefs, listen: "venture" }, state, 0).stack[0].id, VE);
  const list = settings({ mode: "Resonance", slots, listen: "playlist", playlists: [{ id: "p1", name: "x", tracks: [A] }] });
  assert.equal(select(list, state, 0, false, { queue: [A] }).stack[0].key, "album/0");
  assert.equal(select({ ...list, interrupt: true }, state, 0, false, { queue: [A] }).stack[0].key, "solo");
  const radioPrefs = { ...list, listen: "radio" };
  const ctx = { radio: { id: C, index: 2, position: 12, paused: false } };
  assert.equal(select(radioPrefs, state, 0, false, ctx).stack[0].key, "radio/2");
  assert.equal(select(radioPrefs, state, 0, false, ctx).stack[0].position, 12);
  assert.equal(select({ ...radioPrefs, radioInterrupt: true }, state, 0, false, ctx).stack[0].key, "solo");
  assert.equal(select({ ...radioPrefs, radioInterrupt: true }, state, 0, false,
    { radio: { ...ctx.radio, paused: true } }).stack.length, 0);         // paused by the player: nothing forced
  assert.equal(select(radioPrefs, state, 0, false, { radio: { id: null, paused: false } }).stack[0].key, "radio/empty");
});

const library = { tracks: {
  [A]: { set: "A001", group: "album", no: 2, role: "listening", origin: "bundled", title: "Two", artist: "JØ × NOX" },
  [B]: { set: "A001", group: "album", no: 1, role: "listening", origin: "bundled", title: "One", artist: "JØ × NOX" },
  [C]: { set: "", group: "", origin: "import", role: "listening", title: "Mine", artist: "" },
  [MH]: { set: "G004", group: "gameplay", no: 1, role: "zone-moghouse", origin: "bundled", title: "Home" },
  [FI]: { set: "", group: "", origin: "import", role: "", title: "Unclassified" },
  [VE]: { set: "A002", group: "gameplay", role: "listening", origin: "bundled", title: "Odd" }
} };

test("albums play in their own order; Radio takes listening music only, never gameplay or unclassified tracks", () => {
  assert.deepEqual(queueOf(settings({ active: "set:A001" }), library), [B, A]);
  const own = settings({ playlists: [{ id: "p1", name: "x", tracks: [MH, C] }], active: "pl:p1" });
  assert.deepEqual(queueOf(own, library), [MH, C]);               // a playlist may hold anything, in its order
  assert.deepEqual(radioPool(settings({ radio: ["A001"] }), library), [A, B].sort());
  assert.deepEqual(radioPool(settings({ radio: ["A001", "mine", "G004", "A002"] }), library), [A, B, C].sort());
  assert.deepEqual(radioPool(settings({ radio: [] }), library), []);
  assert.equal(radioEligible(library.tracks[MH]), false);
  assert.equal(radioEligible(library.tracks[FI]), false);
  assert.equal(radioEligible(library.tracks[VE]), false);         // a gameplay set, whatever its role says
});

test("Radio: no repeat within a round, no repeat across a round's edge, follows the albums chosen", () => {
  let seed = 1;
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const pool = ["1", "2", "3", "4", "5"].map(n => n.repeat(32));
  const radio = new Radio();
  radio.start(pool, random);
  let last = null;
  for (let round = 0; round < 200; round++) {
    const heard = [radio.current()];
    for (let i = 1; i < pool.length; i++) heard.push(radio.next(pool, random));
    assert.equal(new Set(heard).size, pool.length);
    assert.notEqual(heard[0], last);
    last = heard[heard.length - 1];
    radio.next(pool, random);
    heard.length = 0;
    radio.index = 0; radio.round = [radio.current()].concat(radio.round.slice(1));
  }
  radio.sync(pool.slice(0, 2), random);
  assert.ok(radio.round.every(id => pool.slice(0, 2).includes(id)));
  radio.sync([], random);
  assert.equal(radio.current(), null);
  assert.equal(new Radio().next([], random), null);
  assert.deepEqual(shuffleRound([pool[0]], pool[0], random), [pool[0]]);
});

test("credits, window title and Now Playing text never make up an artist", () => {
  const catalog = { [A]: "two.mp3", [C]: "My Song (1).mp3", [FI]: "file only.mp3" };
  assert.deepEqual(credit(A, library, catalog), { title: "Two", artist: "JØ × NOX" });
  assert.deepEqual(credit(FI, { tracks: { [FI]: { title: "" } } }, catalog), { title: "file only", artist: "" });
  assert.equal(windowTitle({ title: "Two", artist: "JØ × NOX" }), "VanaSync — Two — JØ × NOX");
  assert.equal(windowTitle({ title: "Mine", artist: "" }), "VanaSync — Mine");
  assert.equal(windowTitle({ title: "Mine", artist: "" }, true), "Paused — VanaSync — Mine");
  assert.equal(windowTitle(null), "VanaSync");
  assert.equal(nowPlayingText({ title: "Two", artist: "JØ × NOX" }), "Two — JØ × NOX");
  assert.equal(nowPlayingText({ title: "Two", artist: "" }, true), "(Paused) Two");
  assert.equal(nowPlayingText(null), "");
  const prefs = settings({ playlists: [{ id: "pabc", name: "x", tracks: [] }] });
  assert.match(newPlaylistId(prefs), /^p[a-z0-9]{1,16}$/);
});
