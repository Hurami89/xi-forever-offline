"""Local VanaSync simulator host. Python standard library only."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import tempfile
import threading
import socket
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

APP = Path(__file__).resolve().parent / "app"
PACK = APP.parent / "battle-pack"
SHARED = APP.parent / "catalog.json"   # (2026-11-27) the numbered sets: gameplay soundtrack vs listening albums


def _load_tags():
    """tags.py beside this file (the launcher loads server.py by path, so a plain import would not find it)."""
    spec = importlib.util.spec_from_file_location("vanasync_tags", APP.parent / "tags.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tags = _load_tags()
DEFAULT_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VanaSync"
FORMATS = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
           ".flac": "audio/flac", ".m4a": "audio/mp4", ".opus": "audio/ogg",
           ".aac": "audio/aac", ".webm": "audio/webm"}
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/core.js": ("core.js", "text/javascript; charset=utf-8"),
          "/audio.js": ("audio.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
ID = re.compile(r"[a-f0-9]{32}")
MAX_IMPORT = 128 * 1024 * 1024
META = "meta.json"          # (2026-11-27) beside an imported track: its tags and the player's corrections
NOW_PLAYING = "NowPlaying.txt"
TEXT_LIMIT = 200


def clean_text(value):
    """A tag or a correction: text without control characters, at most TEXT_LIMIT characters ("" for anything else)."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]", "", value).strip()[:TEXT_LIMIT]


def write_atomic(path, text):
    """UTF-8 text written to a temporary file in the same folder, then put in place in one step."""
    handle, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_shared():
    """catalog.json: {track id: details} and the list of sets (without their tracks). Broken or missing: empty."""
    try:
        raw = json.loads(SHARED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, []
    tracks, sets = {}, []
    for entry in raw.get("sets") or []:
        if not isinstance(entry, dict) or not re.fullmatch(r"[GA]\d{3}", str(entry.get("id", ""))):
            continue
        group = "album" if entry.get("group") == "album" else "gameplay"
        sets.append({"id": entry["id"], "group": group, "name": clean_text(entry.get("name")) or entry["id"],
                     "section": clean_text(entry.get("section")), "artist": clean_text(entry.get("artist"))})
        for track in entry.get("tracks") or []:
            if not isinstance(track, dict) or not ID.fullmatch(str(track.get("id", ""))):
                continue
            if track["id"] in tracks:       # one track, one set: the first one listed wins
                continue
            no = track.get("no")
            tracks[track["id"]] = {"set": entry["id"], "group": group, "no": no if isinstance(no, int) else 0,
                                   "title": clean_text(track.get("title")), "artist": clean_text(track.get("artist")),
                                   "album": sets[-1]["name"] if group == "album" else "",
                                   "role": clean_text(track.get("role")) or ("listening" if group == "album" else "")}
    return tracks, sets


def safe_entry(path, kind):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return (kind(info.st_mode) and
            not (getattr(info, "st_file_attributes", 0) & 0x400) and
            (kind is not stat.S_ISREG or info.st_nlink == 1))


class Catalog:
    def __init__(self, root):
        self.root = root
        self.tracks = root / "tracks"
        self.tracks.mkdir(parents=True, exist_ok=True)
        if not safe_entry(self.tracks, stat.S_ISDIR):
            raise ValueError("Invalid tracks directory")
        self.lock = threading.Lock()

    def find(self, track_id):
        if not ID.fullmatch(track_id):
            return None
        folder = self.tracks / track_id
        if not safe_entry(folder, stat.S_ISDIR):
            return None
        tracks = [p for p in folder.iterdir() if p.suffix.lower() in FORMATS
                  and safe_entry(p, stat.S_ISREG)]
        return tracks[0] if len(tracks) == 1 else None

    def list(self):
        with self.lock:
            return {folder.name: path.name for folder in self.tracks.iterdir()
                    if (path := self.find(folder.name)) is not None}

    def add(self, filename, size, reader, track_id=None, mp3_only=False):
        """Copy one file into the catalog. track_id given: bundled. Otherwise (a player's import, 2026-11-27) the id
        comes from the file's content, so importing the same song again finds the copy already there; mp3_only refuses
        anything that is not really an MP3 (renamed files too), and the file's tags are kept beside it (meta.json).
        Returns (id, tags or None, already_there)."""
        if mp3_only and Path(filename).suffix.lower() != ".mp3":
            raise ValueError("Only MP3 files can be added")
        if (not 0 < size <= MAX_IMPORT or len(filename) > 240
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', filename)
                or filename.endswith((" ", "."))
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])",
                                filename.split(".")[0].rstrip())
                or Path(filename).suffix.lower() not in FORMATS):
            raise ValueError("Unsupported filename, format or size")
        bundled = track_id is not None
        with tempfile.TemporaryDirectory(prefix=".import-", dir=self.tracks) as temporary:
            stage = Path(temporary) / "ready"
            stage.mkdir()
            digest = hashlib.sha256()
            with (stage / filename).open("xb") as output:
                remaining = size
                while remaining:
                    chunk = reader.read(min(remaining, 256 * 1024))
                    if not chunk:
                        raise ValueError("Incomplete import")
                    output.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            found = None
            if not bundled:
                with (stage / filename).open("rb") as check:
                    if mp3_only and not tags.is_mp3(check):
                        raise ValueError("Not an MP3 file")
                    if Path(filename).suffix.lower() == ".mp3":
                        found = tags.read_tags(check)
                track_id = digest.hexdigest()[:32]
                record = {"origin": "import", "tags": found or {}, "edit": {}, "listening": False}
                (stage / META).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            with self.lock:
                if not bundled and self.find(track_id) is not None:
                    return track_id, (self.meta(track_id).get("tags") or found), True
                stage.rename(self.tracks / track_id)
        return track_id, found, False

    def meta(self, track_id):
        """meta.json of an imported track ({} for bundled tracks and anything unreadable)."""
        if not ID.fullmatch(track_id):
            return {}
        path = self.tracks / track_id / META
        if not safe_entry(path, stat.S_ISREG):
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def set_meta(self, track_id, edit=None, listening=None):
        """The player's own corrections (title, artist, album, track) and whether an import is listening music
        (Radio may play it). Only for imports: the bundled tracks' credits come from catalog.json."""
        with self.lock:
            record = self.meta(track_id)
            if record.get("origin") != "import" or self.find(track_id) is None:
                raise ValueError("Not an imported track")
            if edit is not None:
                record["edit"] = {k: clean_text(edit.get(k)) for k in ("title", "artist", "album", "track")
                                  if clean_text(edit.get(k))}
            if listening is not None:
                record["listening"] = listening is True
            write_atomic(self.tracks / track_id / META, json.dumps(record, ensure_ascii=False))
        return record

    def remove(self, track_id):
        """Take an import out of the catalog again (the "Cancel" of an import's credits check). Bundled tracks stay.
        Only the catalog's own copy goes; the player's original file was never touched."""
        with self.lock:
            if self.meta(track_id).get("origin") != "import" or self.find(track_id) is None:
                raise ValueError("Not an imported track")
            folder = self.tracks / track_id
            for entry in folder.iterdir():
                entry.unlink()
            folder.rmdir()

    def library(self, shared):
        """Every playable track with its credits: catalog.json first, then the player's corrections, then the file's
        own tags, then the file name. Imports that nobody classified have no role (never in Radio)."""
        out = {}
        for track_id, filename in self.list().items():
            known = shared.get(track_id)
            if known:
                out[track_id] = {**known, "file": filename, "origin": "bundled"}
                continue
            record = self.meta(track_id)
            edit, found = record.get("edit") or {}, record.get("tags") or {}
            pick = lambda key: clean_text(edit.get(key)) or clean_text(found.get(key))
            out[track_id] = {"file": filename, "origin": "import", "set": "", "group": "",
                             "no": 0, "title": pick("title"), "artist": pick("artist"), "album": pick("album"),
                             "track": pick("track"), "tagged": {k: clean_text(found.get(k)) for k in
                                                                ("title", "artist", "album", "track")},
                             "role": "listening" if record.get("listening") is True else ""}
        return out

    def seed_battle_pack(self):
        manifest_path = PACK.with_suffix(".json")
        if not manifest_path.is_file():
            return {}
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
        defaults = {}
        # (2026-11-26, J's Choose to Fight update) "extras": bundled tracks that belong to no slot. They are seeded into
        # the catalog like the three themes, so they show in the library and can be picked, and no assignment changes.
        extras = records.get("extras") or []
        if not isinstance(extras, list):
            raise ValueError("Invalid bundled battle manifest")
        for slot, record in [(s, records[s]) for s in ("solo", "party", "alliance")] + [(None, e) for e in extras]:
            filename = record["file"]
            digest = record["sha256"]
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("Invalid bundled battle manifest")
            track_id = digest[:32]
            if filename != Path(filename).name or "/" in filename or "\\" in filename:
                raise ValueError("Invalid bundled filename")
            # (2026-11-27) an extra may name its slot too: fishing, venture, moghouse
            slot = slot or (record.get("slot") if record.get("slot") in ("fishing", "venture", "moghouse") else None)
            if slot is not None:
                defaults[slot] = track_id
            marker = self.root / (".seeded-" + track_id)
            if marker.exists():
                continue
            if safe_entry(self.tracks / track_id, stat.S_ISDIR):
                marker.touch()
                continue
            source = PACK / filename
            try:
                if not safe_entry(source, stat.S_ISREG):
                    continue
                with source.open("rb") as handle:
                    if sha256_of(handle) != digest:
                        print(f"Bundled {slot or filename} file failed verification", flush=True)
                        continue
                    handle.seek(0)
                    self.add(filename, os.fstat(handle.fileno()).st_size, handle, track_id)
                marker.touch()
            except (OSError, ValueError):
                print(f"Bundled {slot or filename} file could not be copied", flush=True)
        return defaults


def sha256_of(handle):
    """hashlib.file_digest (Python 3.11+), with the same result on older Pythons."""
    if hasattr(hashlib, "file_digest"):
        return hashlib.file_digest(handle, "sha256").hexdigest()
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


class GameBridge:
    """Live game state from the XI Forever Offline add-on over loopback UDP.

    The add-on sends a small JSON snapshot several times a second. Each reply
    says whether the player tab is really playing a VanaSync mix, so the add-on
    only fades the game's own music while VanaSync owns it.
    """
    FRESH = 3.0
    OWNER_FRESH = 2.0
    OPEN_QUIET = 10.0   # one "/vanasync open" in game is one window: later requests are ignored this long

    def __init__(self, port):
        self.lock = threading.Lock()
        self.state = None
        self.received = 0.0
        self.owner = False
        self.owner_at = 0.0
        self.open_asked = False
        self.open_taken = -self.OPEN_QUIET
        self.page_at = None
        self.sock = None
        if port:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("127.0.0.1", port))
            self.sock.settimeout(0.5)
            threading.Thread(target=self.run, daemon=True).start()

    @staticmethod
    def parse(data):
        raw = json.loads(data.decode("utf-8"))
        if not isinstance(raw, dict) or raw.get("v") != 1:
            raise ValueError("bad snapshot")
        members = raw.get("members")
        zone = raw.get("zone")
        if (not isinstance(members, int) or isinstance(members, bool)
                or not isinstance(zone, int) or isinstance(zone, bool)):
            raise ValueError("bad snapshot")
        # (2026-11-27) fishing: the character is fishing now; venture: the Ventures window is open; mog: inside a Mog
        # House (the zone-in's Mog House state). Older add-ons do not send them: false.
        return {"engaged": raw.get("engaged") is True, "alliance": raw.get("alliance") is True,
                "cutscene": raw.get("cutscene") is True,
                "members": max(1, min(18, members)), "zone": max(0, min(9999, zone)),
                "fishing": raw.get("fishing") is True, "venture": raw.get("venture") is True,
                "mog": raw.get("mog") is True, "addon": clean_text(raw.get("addon"))[:16]}

    @staticmethod
    def asks_open(data):
        """True when a snapshot carries "open": true: the player typed /vanasync open in game."""
        if b'"open"' not in data:
            return False
        try:
            raw = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return False
        return isinstance(raw, dict) and raw.get("open") is True

    def run(self):
        while True:
            try:
                data, address = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                return
            if address[0] != "127.0.0.1":
                continue
            try:
                state = self.parse(data)
            except (ValueError, UnicodeDecodeError):
                continue
            asks = self.asks_open(data)
            now = time.monotonic()
            with self.lock:
                self.state, self.received = state, now
                own = self.owner and now - self.owner_at < self.OWNER_FRESH
                if asks and now - self.open_taken > self.OPEN_QUIET:
                    self.open_asked = True
            try:
                self.sock.sendto(json.dumps({"own": own}).encode(), address)
            except OSError:
                pass

    def snapshot(self):
        with self.lock:
            age = time.monotonic() - self.received if self.state else None
            return {"live": age is not None and age < self.FRESH, "state": self.state,
                    "age": None if age is None else round(age, 3)}

    def set_owner(self, own):
        with self.lock:
            self.owner, self.owner_at = bool(own), time.monotonic()

    def take_open(self):
        """True once after the add-on asked for the player window. Whoever hosts the window (the launcher) asks this."""
        with self.lock:
            asked, self.open_asked = self.open_asked, False
            if asked:
                self.open_taken = time.monotonic()
            return asked

    def seen_page(self):
        with self.lock:
            self.page_at = time.monotonic()

    def page_age(self):
        """Seconds since a player page last asked for the game's state; None when none ever did."""
        with self.lock:
            return None if self.page_at is None else time.monotonic() - self.page_at

    def close(self):
        if self.sock:
            self.sock.close()


class Server(ThreadingHTTPServer):
    def __init__(self, port, data, bundled=True, game_port=0):
        self.catalog = Catalog(data)
        self.game = GameBridge(game_port)
        self.now_playing = Path(data) / NOW_PLAYING
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        try:
            self.defaults = self.catalog.seed_battle_pack() if bundled else {}
        except (OSError, ValueError, TypeError, KeyError):
            print("Bundled battle manifest could not be loaded", flush=True)
            self.defaults = {}

    def server_close(self):
        self.game.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(15)
        super().setup()

    def log_message(self, *_):
        pass

    def allowed(self, write=False):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            return False
        return not write or (origin == self.server.origin
                             and self.headers.get("X-VanaSync") == "1")

    def headers_for(self, status, media_type, length, **extra):
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "media-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
                         "base-uri 'none'; form-action 'none'")
        for name, value in extra.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()

    def reply(self, status, payload, media_type="application/json; charset=utf-8"):
        content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.headers_for(status, media_type, len(content))
        if self.command != "HEAD":
            self.wfile.write(content)

    def do_GET(self):
        try:
            self.route_get()
        except (ConnectionError, TimeoutError):
            return
        except OSError:
            self.reply(503, {"error": "Local catalog unavailable"})

    do_HEAD = do_GET

    def route_get(self):
        if not self.allowed():
            return self.reply(403, {"error": "Invalid local origin"})
        path = self.path.partition("?")[0]
        if path in STATIC:
            name, media_type = STATIC[path]
            return self.reply(200, (APP / name).read_bytes(), media_type)
        if path == "/api/tracks":
            return self.reply(200, self.server.catalog.list())
        if path == "/api/game":
            self.server.game.seen_page()
            return self.reply(200, self.server.game.snapshot())
        if path == "/api/bootstrap":
            return self.reply(200, {"defaults": self.server.defaults, "tracks": self.server.catalog.list(),
                                    "nowPlayingFile": str(self.server.now_playing)})
        if path == "/api/library":
            shared, sets = load_shared()
            return self.reply(200, {"sets": sets, "tracks": self.server.catalog.library(shared)})
        if path.startswith("/media/"):
            track = self.server.catalog.find(path.removeprefix("/media/"))
            if track:
                try:
                    handle = track.open("rb")
                except FileNotFoundError:
                    return self.reply(404, {"error": "Track moved"})
                with handle:
                    return self.stream(handle, FORMATS[track.suffix.lower()])
        self.reply(404, {"error": "Not found"})

    def stream(self, handle, media_type):
        length = os.fstat(handle.fileno()).st_size
        start, end, status = 0, length - 1, 200
        extra = {"Accept_Ranges": "bytes"}
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d{0,18})-(\d{0,18})", requested)
            if match and match[1]:
                start = int(match[1])
                end = min(end, int(match[2])) if match[2] else end
            elif match and match[2]:
                start = max(0, length - int(match[2]))
            else:
                start = length
            if start > end:
                return self.headers_for(416, media_type, 0, Content_Range=f"bytes */{length}")
            status = 206
            extra["Content_Range"] = f"bytes {start}-{end}/{length}"
        remaining = end - start + 1
        self.headers_for(status, media_type, remaining, **extra)
        if self.command != "HEAD":
            handle.seek(start)
            while remaining:
                chunk = handle.read(min(remaining, 256 * 1024))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        try:
            if not self.allowed(write=True):
                return self.reply(403, {"error": "Invalid local origin"})
            if self.path == "/api/owner":
                size = int(self.headers.get("Content-Length", "") or 0)
                if size > 256:
                    return self.reply(413, {"error": "Too large"})
                body = json.loads(self.rfile.read(size) or b"{}")
                self.server.game.set_owner(isinstance(body, dict) and body.get("own") is True)
                return self.reply(200, {"ok": True})
            if self.path in ("/api/meta", "/api/nowplaying", "/api/remove"):
                size = int(self.headers.get("Content-Length", "") or 0)
                if size > 4096:
                    return self.reply(413, {"error": "Too large"})
                body = json.loads(self.rfile.read(size) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("bad body")
                if self.path == "/api/remove":
                    self.server.catalog.remove(str(body.get("id", "")))
                    return self.reply(200, {"ok": True})
                if self.path == "/api/meta":
                    track_id = str(body.get("id", ""))
                    edit = body.get("edit") if isinstance(body.get("edit"), dict) else None
                    listening = body.get("listening") if isinstance(body.get("listening"), bool) else None
                    self.server.catalog.set_meta(track_id, edit, listening)
                    return self.reply(200, {"ok": True})
                # Now Playing text for streaming software: "Title — Artist", "(Paused) ...", or empty when stopped
                if body.get("enabled") is True:
                    text = clean_text(body.get("text"))
                    write_atomic(self.server.now_playing, text + ("\n" if text else ""))
                return self.reply(200, {"ok": True, "file": str(self.server.now_playing)})
            if self.path != "/api/tracks":
                return self.reply(404, {"error": "Not found"})
            if (self.headers.get("Transfer-Encoding")
                    or self.headers.get_content_type() != "application/octet-stream"):
                return self.reply(415, {"error": "Unsupported upload encoding"})
            filename = unquote(self.headers.get("X-Filename", ""), errors="strict")
            size = int(self.headers.get("Content-Length", "") or 0)
            track_id, found, existed = self.server.catalog.add(filename, size, self.rfile, mp3_only=True)
            self.reply(201, {"id": track_id, "filename": self.server.catalog.list().get(track_id, filename),
                             "tags": found or {}, "existed": existed})
        except (TimeoutError, ConnectionError):
            return
        except ValueError as error:
            message = str(error)
            if message in ("Only MP3 files can be added", "Not an MP3 file", "Not an imported track"):
                return self.reply(400, {"error": message})
            self.reply(400, {"error": "Unsupported filename, format, size or incomplete upload"})
        except OSError:
            self.reply(503, {"error": "Could not write to the local catalog"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--no-bundled", action="store_true")
    parser.add_argument("--game-port", type=int, default=8766,
                        help="loopback UDP port for the game add-on (0 turns it off)")
    args = parser.parse_args()
    with Server(args.port, args.data, bundled=not args.no_bundled,
                game_port=args.game_port) as server:
        print(f"VanaSync simulator: {server.origin}", flush=True)
        print(f"Game add-on bridge: UDP {args.game_port or 'off'}", flush=True)
        if not args.no_open:
            webbrowser.open(server.origin)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
