import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { access, mkdtemp, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const [referencePath, screenshotPath] = process.argv.slice(2);
if (!referencePath) throw new Error("Pass a local MP3 you may use as the simulator reference.");
const root = dirname(dirname(fileURLToPath(import.meta.url)));
// (0.2.0) VANASYNC_EDGE may name Chrome too (the cloud check runs google-chrome); VANASYNC_PYTHON python3 on Linux
const edge = process.env.VANASYNC_EDGE || join(process.env["ProgramFiles(x86)"] || "", "Microsoft", "Edge", "Application", "msedge.exe");
const temp = await mkdtemp(join(tmpdir(), "vanasync-edge-"));
const profile = join(temp, "profile");
const data = join(temp, "catalog");
const downloads = join(temp, "downloads");
const server = spawn(process.env.VANASYNC_PYTHON || "python",
  [join(root, "server.py"), "--port", "0", "--no-open", "--data", data],
  { stdio: ["ignore", "pipe", "inherit"] });
let browser;
let socket;
const exceptions = [];
const delay = ms => new Promise(done => setTimeout(done, ms));
const request = (url, options = {}) => fetch(url, { ...options, signal: AbortSignal.timeout(4000) });

async function until(fn, label, timeout = 10000) {
  const end = Date.now() + timeout;
  let last;
  while (Date.now() < end) {
    try {
      last = await fn();
      if (last) return last;
    } catch (error) {
      last = error.message;
    }
    await delay(75);
  }
  throw new Error("Timed out: " + label + " [" + String(last) + "]");
}

try {
  let output = "";
  server.stdout.on("data", chunk => { output += chunk; });
  const origin = await until(() => output.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0], "host startup");
  console.log("Local host started");
  const { defaults, tracks } = await (await request(origin + "/api/bootstrap")).json();
  // (0.2.0) a bundled track shows its credit from catalog.json, not its file name
  const shelf = (await (await request(origin + "/api/library")).json()).tracks;
  const names = Object.fromEntries(Object.entries(defaults).map(([slot, id]) => [slot, shelf[id].title]));
  const refBytes = await readFile(referencePath);
  async function importReference(name, bytes) {
    const response = await request(origin + "/api/tracks", { method: "POST", body: bytes,
      headers: { "Content-Type": "application/octet-stream", "X-VanaSync": "1",
        Origin: origin, "X-Filename": encodeURIComponent(name) } });
    assert.equal(response.status, 201);
    return (await response.json()).id;
  }
  const reference = await importReference("Simulator Reference.mp3", refBytes);
  // (0.2.0) imports must really be MP3s: a frame header and then nothing an MP3 decoder can use
  const corrupt = await importReference("Decode failure test.mp3",
    Buffer.concat([Buffer.from([0xff, 0xfb, 0x90, 0x64]), Buffer.alloc(2000, 0x5a)]));
  // a song with an ID3v1 title and artist: the same audio, so another file and another catalog id
  const v1 = (song, artist) => Buffer.concat([refBytes, Buffer.from("TAG"), Buffer.from(song.padEnd(30, "\0"), "latin1"),
    Buffer.from(artist.padEnd(30, "\0"), "latin1"), Buffer.alloc(30 + 4 + 28), Buffer.from([0, 1, 0])]);
  await access(edge);
  browser = spawn(edge, ["--headless=new", "--no-first-run", "--disable-background-networking",
    "--remote-debugging-port=0", "--window-size=1240,1000", "--user-data-dir=" + profile,
    ...(process.getuid?.() === 0 ? ["--no-sandbox"] : []), "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] });
  let browserOutput = "";
  browser.stderr.on("data", chunk => { browserOutput += chunk; });
  const debugPort = await until(async () => {
    if (browser.exitCode !== null) throw new Error(browserOutput.slice(-500));
    return (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0];
  }, "local Edge startup");
  console.log("Edge debug port ready");
  const target = await until(async () => (await (await request("http://127.0.0.1:" + debugPort + "/json/list")).json())
    .find(candidate => candidate.type === "page"), "Edge tab");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((done, reject) => {
    const timeout = setTimeout(() => reject(new Error("Edge debugging websocket timeout")), 5000);
    socket.addEventListener("open", () => clearTimeout(timeout));
    socket.addEventListener("open", done);
    socket.addEventListener("error", reject);
  });
  console.log("Edge tab attached");
  let sequence = 0;
  const requests = new Map();
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") {
      const details = message.params.exceptionDetails;
      exceptions.push(details.exception?.description || details.text);
    }
    if (!requests.has(message.id)) return;
    const { done, reject, timer } = requests.get(message.id);
    clearTimeout(timer);
    requests.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else done(message.result);
  });
  function call(method, params = {}) {
    const id = ++sequence;
    return new Promise((done, reject) => {
      const timer = setTimeout(() => {
        requests.delete(id);
        reject(new Error("Edge command timed out: " + method));
      }, 4000);
      requests.set(id, { done, reject, timer });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async function run(expression) {
    const result = await call("Runtime.evaluate", { expression, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
  }
  const get = id => "document.getElementById(" + JSON.stringify(id) + ")";
  const read = (id, property = "textContent") => run(get(id) + "." + property);
  const click = id => run(get(id) + ".click()");
  const set = (id, value, property = "value", event = "change") =>
    run(get(id) + "." + property + "=" + JSON.stringify(value) + ";" + get(id)
      + ".dispatchEvent(new Event(" + JSON.stringify(event) + ",{bubbles:true}));"
      + "document.getElementById('phase').textContent");
  async function title(value) {
    try {
      await until(async () => (await read("track")) === value, "title " + value);
    } catch (error) {
      throw new Error(error.message + " observed " + JSON.stringify(await run(
        "[...['track','transport-status','phase','notice','arrangement'].map(id => document.getElementById(id).textContent),"
        + "...['mode','override','members','engaged','alliance'].map(id => {const el=document.getElementById(id);return [el.value,el.checked]})]"
      )));
    }
  }
  const phase = value => until(async () => (await read("phase")) === value, "phase " + value);
  const prefs = () => run("JSON.parse(localStorage.getItem('vanasync.settings.v1'))");
  const report = description => console.log("PASS " + description);
  async function capture() {
    if (!screenshotPath) return;
    const frame = await call("Page.captureScreenshot", { format: "png" });
    await writeFile(resolve(screenshotPath), Buffer.from(frame.data, "base64"));
  }
  await call("Runtime.enable");
  await call("Page.enable");
  await call("Page.addScriptToEvaluateOnNewDocument", { source:
    "window.testAudio=[]; const NativeAudio=window.Audio; window.Audio=function(){const audio=new NativeAudio();window.testAudio.push(audio);return audio;};" });
  await call("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloads });
  await call("Page.navigate", { url: origin });
  console.log("Player navigation issued");
  const listen = value => run("document.querySelector('[data-listen=" + JSON.stringify(value) + "]').click()");
  const docTitle = value => until(async () => (await run("document.title")) === value, "window title " + value);
  async function files(selector, paths) {
    const { root: docNode } = await call("DOM.getDocument");
    const { nodeId } = await call("DOM.querySelector", { nodeId: docNode.nodeId, selector });
    await call("DOM.setFileInputFiles", { nodeId, files: paths });
  }
  await until(async () => (await read("slot-solo", "value")) === defaults.solo, "bundled slot assignments");
  assert.equal(await read("grace", "value"), "5");
  assert.equal(await read("mode", "value"), "Vanilla");
  assert.equal(await read("simulator", "open"), false);            // (0.2.0) the test inputs are folded away
  assert.equal(await read("settings-section", "open"), false);
  for (const slot of ["fishing", "venture", "moghouse"]) assert.equal(await read("slot-" + slot, "value"), defaults[slot]);
  await set("slot-exploration", reference);
  await set("slot-nativeSolo", reference);
  await set("slot-cutscene", reference);
  assert.equal(await read("enable"), "Start music");
  await click("enable");
  assert.equal(await read("enable", "hidden"), true);              // one obvious start; gone once music may play
  await title("Simulator Reference");
  await set("mode", "Resonance");
  await set("engaged", true, "checked");
  await title(names.solo);
  await phase("Combat");
  await set("members", "4");
  await title(names.party);
  await capture();
  await set("alliance", true, "checked");
  await title(names.alliance);
  await set("override", "solo");
  await title(names.solo);
  await set("members", "1");
  await set("alliance", false, "checked");
  await set("override", "auto");
  report("Bundled MP3 playback, automatic Solo/Party/Alliance, and manual override");
  await set("mode", "Vanilla");
  await title("Simulator Reference");
  await set("mode", "Off");
  await title("No audio playing");
  await set("mode", "Resonance");
  await title(names.solo);
  assert.equal(await set("engaged", false, "checked"), "Post-combat");
  assert.equal(await read("track"), names.solo);
  const audioCount = await run("window.testAudio.length");
  await delay(400);
  await set("engaged", true, "checked");
  await phase("Combat");
  assert.equal(await read("track"), names.solo);
  assert.equal(await run("window.testAudio.length"), audioCount);
  await set("engaged", false, "checked");
  await title("Simulator Reference");
  await phase("Exploration");
  report("Vanilla and Off switching, rapid re-engagement, and five-second exploration restore");
  assert.equal(await set("engaged", true, "checked"), "Combat");
  await title(names.solo);
  const soloPath = join(data, "tracks", defaults.solo, tracks[defaults.solo]);
  const renamed = "戦闘・Against the Odds (Final).MP3";
  await rename(soloPath, join(dirname(soloPath), renamed));
  await delay(2000);
  assert.equal(await read("track"), names.solo);                  // the catalog's credit, not the file name
  assert.equal((await prefs()).slots.solo, defaults.solo);
  await rename(join(dirname(soloPath), renamed), join(dirname(soloPath), "temporarily-missing.bin"));
  await title("Simulator Reference");
  await set("slot-solo", corrupt);
  await title("Simulator Reference");
  await rename(join(dirname(soloPath), "temporarily-missing.bin"), soloPath);
  await until(async () => await run("[..." + get("slot-solo") + ".options].some(item => item.value === "
    + JSON.stringify(defaults.solo) + " && !item.text.startsWith('Missing file'))"),
    "restored catalog entry");
  await set("slot-solo", defaults.solo);
  await title(names.solo);
  await docTitle("VanaSync — " + names.solo + " — jnull");     // the catalog's credit, artist included
  await click("restore");
  await title("Simulator Reference");
  assert.match(await read("transport-status"), /Game music only/);
  assert.equal(await read("enable", "hidden"), false);
  await click("enable");
  await title(names.solo);
  report("Unicode rename, retained assignment, missing and corrupt audio fallback, and Game music only");
  await set("grace", "0");
  await set("engaged", false, "checked");
  await title("Simulator Reference");

  // ---- (0.2.0) Game Sync: fishing, the Ventures window, Mog Houses ----
  const fishingTitle = "Just One More Cast", ventureTitle = "Beyond the Next Hill";
  const mogTitle = "A Place to Call Home (Mog House Theme)";
  await set("fishing", true, "checked");
  await title(fishingTitle);
  await docTitle("VanaSync — Just One More Cast — jnull");
  const casts = await run("window.testAudio.length");
  await set("fishing", false, "checked");                         // between two casts
  await delay(1500);
  await set("fishing", true, "checked");
  assert.equal(await read("track"), fishingTitle);
  assert.equal(await run("window.testAudio.length"), casts);        // the tune did not restart
  await set("engaged", true, "checked");                          // a fight while fishing: battle music
  await title(names.solo);
  await set("engaged", false, "checked");
  await set("fishing", false, "checked");
  await title(fishingTitle);                                      // back to fishing for the hold
  await set("venture", true, "checked");
  await set("mog", true, "checked");
  await until(async () => (await read("track")) === ventureTitle, "fishing hold runs out, Ventures window", 26000);
  await set("venture", false, "checked");
  await title(mogTitle);
  await set("zone", "241");
  await run("document.getElementById('library-section').open = true");
  await set("zone-mog-241", "native");                            // Windurst Woods: the game's own music
  await title("Simulator Reference");
  await set("zone", "230");
  await title(mogTitle);                                          // Southern San d'Oria still has the theme
  await set("mog", false, "checked");
  await title("Simulator Reference");
  report("Game Sync: fishing (no restart between casts, hold, battle first), Ventures window, Mog Houses per house");

  // ---- Fishing / Venture chosen by hand ----
  await listen("fishing");
  await title(fishingTitle);
  assert.equal(await read("back-to-game", "hidden"), false);
  await set("engaged", true, "checked");
  await delay(400);
  assert.equal(await read("track"), fishingTitle);                // chosen by hand: no battle switch
  await set("engaged", false, "checked");
  await listen("venture");
  await title(ventureTitle);
  await click("back-to-game");
  await title("Simulator Reference");
  assert.equal((await prefs()).listen, "game");
  report("Fishing and Venture by hand, through a fight, and Return to Game Sync");

  // ---- Playlist Mode ----
  // (headless Chrome on Linux drops file-input paths with "・" in them; the host's Unicode names are tested in test_server)
  const one = join(temp, "01 Album test.mp3");
  const two = join(temp, "02 Album test.mp3");
  const wav = join(temp, "Not allowed.wav");
  await writeFile(one, v1("Album test 01", ""));
  await writeFile(two, v1("Album test 02", "Nox"));
  await writeFile(wav, "RIFF....WAVE");
  await listen("playlist");
  assert.match(await read("playlist-empty"), /Make a playlist/);
  await click("pl-new");
  await until(async () => (await prefs()).playlists.length === 1, "new playlist");
  await set("pl-name", "Night 夜", "value", "input");
  await files("#album-import", [one, two, wav]);
  await until(async () => (await prefs()).playlists[0].tracks.length === 2, "playlist import");
  await until(async () => /only MP3 files/.test(await read("notice-text")), "the WAV is refused with a reason");
  await until(async () => await run("document.querySelectorAll('#pl-import-box form.credit').length") === 2, "credit checks");
  assert.match(await run("document.querySelector('#pl-import-box form.credit').textContent"), /no Artist tag/);
  await title("Album test 01");                                   // the first track, in import order
  await docTitle("VanaSync — Album test 01");                     // no artist tag: no artist in the title
  await set("zone", "2");
  await set("engaged", true, "checked");
  await delay(400);
  assert.equal(await read("track"), "Album test 01");              // switch is off: the playlist goes on
  await until(async () => (await prefs()).position >= 1, "playlist checkpoint");
  const before = (await prefs()).position;
  await set("interrupt", true, "checked");
  await title(names.solo);                                        // switched on mid-fight: battle music
  assert.ok((await prefs()).position >= before);
  await set("engaged", false, "checked");
  await title("Album test 01");
  await until(async () => (await prefs()).position > before + 0.1, "playlist resumed where it stopped");
  await set("cutscene", true, "checked");
  await title("Simulator Reference");
  await set("cutscene", false, "checked");
  await title("Album test 01");
  await click("next");
  await title("Album test 02");
  await docTitle("VanaSync — Album test 02 — Nox");
  await click("previous");
  await title("Album test 01");
  await click("pause");
  await docTitle("Paused — VanaSync — Album test 01");
  await click("pause");
  await title("Album test 01");
  // delete, Undo: the songs stay in the library
  await click("pl-delete");
  await until(async () => (await prefs()).playlists.length === 0, "playlist deleted");
  assert.equal(await read("notice-action"), "Undo");
  await click("notice-action");
  await until(async () => (await prefs()).playlists.length === 1, "Undo brings it back");
  assert.equal((await prefs()).playlists[0].name, "Night 夜");
  assert.equal((await prefs()).playlists[0].tracks.length, 2);
  report("Playlists: new, name, MP3-only import with credit checks, order, battle switch off/on mid-fight, resume, cutscene, pause title, delete and Undo");

  // ---- Radio ----
  await listen("radio");
  assert.match(await read("radio-empty"), /No listening albums/);
  const cards = "document.querySelectorAll('#pl-import-box form.credit')";
  await run("(() => { for (const f of [..." + cards + "]) { f.querySelector('input[type=checkbox]').checked = true;"
    + " [...f.querySelectorAll('button')].find(b => b.textContent === 'Keep').click(); } })()");
  await until(async () => await run("document.querySelectorAll('#radio-albums input').length") === 1, "My listening music offered");
  await run("document.querySelector('#radio-albums input').click()");
  await click("radio-pause");
  await until(async () => ["Album test 01", "Album test 02"].includes(await read("track")), "Radio plays");
  const first = await read("track");
  await set("engaged", true, "checked");
  await delay(400);
  assert.equal(await read("track"), first);                       // Radio: no battle switch unless asked for
  await set("engaged", false, "checked");
  await click("radio-next");
  await until(async () => (await read("track")) !== first, "Radio next");
  const pool = (await call("Runtime.evaluate", { returnByValue: true, awaitPromise: true, expression: "(async () => { const m = await import('/core.js'); const l = await (await fetch('/api/library')).json();"
    + " return m.radioPool({ radio: ['mine', 'G001', 'G002', 'G003', 'G004'] }, l).map(id => l.tracks[id].title); })()" })).result.value;
  assert.deepEqual(pool.sort(), ["Album test 01", "Album test 02"]);    // gameplay sets never enter Radio
  report("Radio: listening imports only, shuffle across the pool, Next, no battle switch, gameplay excluded");

  // ---- Now Playing file, help ----
  await run("document.getElementById('settings-section').open = true");
  await set("now-playing", true, "checked");
  const nowFile = join(data, "NowPlaying.txt");
  await until(async () => /^Album test 0[12]( — Nox)?\n$/.test(await readFile(nowFile, "utf8")), "Now Playing file");
  await click("radio-pause");
  await until(async () => (await readFile(nowFile, "utf8")).startsWith("(Paused) Album test"), "paused in the file");
  await set("now-playing", false, "checked");
  await until(async () => (await readFile(nowFile, "utf8")) === "", "emptied when switched off");
  await call("Emulation.setFocusEmulationEnabled", { enabled: true });   // a headless window has no focus of its own
  await run("document.querySelector('.help[data-help=listen]').focus()");
  assert.equal(await read("help-pop", "hidden"), false);
  assert.match(await read("help-pop"), /Game Sync lets the game choose/);
  await run("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))");
  assert.equal(await read("help-pop", "hidden"), true);
  await run("document.querySelector('.help[data-help=radio]').click()");
  assert.equal(await read("help-pop", "hidden"), false);
  await run("document.querySelector('.help[data-help=radio]').click()");
  assert.equal(await read("help-pop", "hidden"), true);
  report("Now Playing file (playing, paused, cleared) and help by keyboard focus, Escape and tap");

  // ---- settings and the rest, then a reload ----
  await listen("playlist");
  await set("repeat", true, "checked");
  await set("scale", "1.1", "value", "input");
  await set("transparency", "0.8", "value", "input");
  await set("album", "0.37", "value", "input");
  await set("key-collapse", "K");
  await run("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'k',bubbles:true}))");
  assert.equal(await read("deck", "hidden"), true);
  await click("collapse");
  async function dragHeader() {
    await run("window.scrollTo(0,0)");
    const [x, y] = await run("(()=>{const box=document.getElementById('drag').getBoundingClientRect();return [box.left+50,box.top+24]})()");
    await call("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await call("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", buttons: 1, clickCount: 1 });
    await call("Input.dispatchMouseEvent", { type: "mouseMoved", x: x + 60, y: y + 30, buttons: 1 });
    await call("Input.dispatchMouseEvent", { type: "mouseReleased", x: x + 60, y: y + 30, button: "left", clickCount: 1 });
    await call("Input.dispatchMouseEvent", { type: "mouseMoved", x: x + 60, y: y + 30 });
  }
  await dragHeader();
  await until(async () => (await prefs()).x > 20, "saved drag position");
  const moved = (await prefs()).x;
  await run(get("drag") + ".dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,clientX:300,clientY:200}))");
  assert.equal(await read("quick", "hidden"), false);
  await click("quick-lock");
  assert.equal((await prefs()).locked, true);
  await dragHeader();
  assert.equal((await prefs()).x, moved);
  await click("report");
  await until(async () => (await readdir(downloads)).includes("VanaSync-diagnostics.json"), "diagnostics download");
  const diagnostics = JSON.parse(await readFile(join(downloads, "VanaSync-diagnostics.json"), "utf8"));
  assert.equal(diagnostics.source, "simulator");
  assert.equal(diagnostics.version, "0.2.0");
  await call("Page.reload");
  await until(async () => (await read("key-collapse", "value")) === "K", "saved settings after reload");
  assert.equal(await read("mode", "value"), "Resonance");
  assert.equal(await read("repeat", "checked"), true);
  assert.equal(await read("album", "value"), "0.37");
  assert.equal((await prefs()).x, moved);
  assert.equal((await prefs()).playlists[0].name, "Night 夜");
  assert.equal((await prefs()).zones["mog:241"], "native");
  assert.equal(await run("getComputedStyle(document.getElementById('player')).opacity"), "0.8");
  await click("enable");
  await until(async () => ["Album test 01", "Album test 02"].includes(await read("track")), "playlist after reload");
  await click("back-to-game");
  await title("Simulator Reference");
  assert.equal(await read("mode", "value"), "Resonance");
  report("Settings, keys, drag and lock, diagnostics, and everything saved across a reload");
  assert.deepEqual(exceptions, []);
  if (screenshotPath) {
    await set("engaged", true, "checked");
    await set("override", "party");
    await title(names.party);
    await capture();
  }
} catch (error) {
  console.error(error);
  if (exceptions.length) console.error(exceptions);
  process.exitCode = 1;
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ id: 2147483647, method: "Browser.close" }));
    socket.close();
  }
  server.kill();
  browser?.stderr.destroy();
  server.stdout.destroy();
  await delay(250);
  if (browser?.exitCode === null) browser.kill();
  await rm(temp, { recursive: true, force: true, maxRetries: 4, retryDelay: 250 });
}
