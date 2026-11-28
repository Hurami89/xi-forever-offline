import http.client
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Catalog, GameBridge, MAX_IMPORT, PACK, load_shared, tags

# (2026-11-27) the smallest thing that is really an MP3: one MPEG-1 Layer III frame header (128 kbit/s, 44.1 kHz)
MP3 = b"\xff\xfb\x90\x64" + bytes(412)


def id3(title=None, artist=None, album=None, track=None, version=3):
    """An ID3v2.3/2.4 tag with UTF-8 / UTF-16 text frames, in front of MP3."""
    frames = b""
    for name, value in (("TIT2", title), ("TPE1", artist), ("TALB", album), ("TRCK", track)):
        if value is None:
            continue
        body = (b"\x03" + value.encode("utf-8")) if version == 4 else (b"\x01" + value.encode("utf-16"))
        size = len(body)
        size_bytes = (bytes([(size >> 21) & 127, (size >> 14) & 127, (size >> 7) & 127, size & 127])
                      if version == 4 else size.to_bytes(4, "big"))
        frames += name.encode() + size_bytes + b"\x00\x00" + body
    n = len(frames)
    return (b"ID3" + bytes([version, 0, 0]) + bytes([(n >> 21) & 127, (n >> 14) & 127, (n >> 7) & 127, n & 127])
            + frames + MP3)


class GameBridgeOpenTest(unittest.TestCase):
    # (2026-11-26) "/vanasync open" in game: the add-on's snapshot carries "open": true
    SNAPSHOT = b'{"v":1,"engaged":false,"cutscene":false,"members":1,"alliance":false,"zone":230,"open":true}'

    def test_only_a_real_open_flag_counts_and_the_snapshot_is_unchanged(self):
        self.assertTrue(GameBridge.asks_open(self.SNAPSHOT))
        self.assertFalse(GameBridge.asks_open(self.SNAPSHOT.replace(b',"open":true', b'')))
        self.assertFalse(GameBridge.asks_open(b'{"v":1,"open":"true"}'))
        self.assertFalse(GameBridge.asks_open(b'["open", true]'))
        self.assertFalse(GameBridge.asks_open(b'not json "open"'))
        state = GameBridge.parse(self.SNAPSHOT)
        self.assertEqual(state["zone"], 230)
        self.assertNotIn("open", state)

    def test_taken_once_and_page_age(self):
        bridge = GameBridge(0)
        self.assertFalse(bridge.take_open())
        bridge.open_asked = True
        self.assertTrue(bridge.take_open())
        self.assertFalse(bridge.take_open())
        self.assertIsNone(bridge.page_age())
        bridge.seen_page()
        self.assertLess(bridge.page_age(), 1)


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        self.catalog = Catalog(Path(self.data.name))

    def test_identity_survives_rename_and_ambiguous_entries_fail_closed(self):
        track_id, _, _ = self.catalog.add("戦闘・A.Final.MP3", 3, io.BytesIO(b"abc"))
        track = self.catalog.find(track_id)
        track.rename(track.with_name("戦闘・新名.MP3"))
        self.assertEqual(self.catalog.list(), {track_id: "戦闘・新名.MP3"})
        track.write_bytes(b"another file")
        self.assertIsNone(self.catalog.find(track_id))
        track.unlink()
        self.assertEqual(self.catalog.find(track_id).read_bytes(), b"abc")

    def test_invalid_names_sizes_and_partial_data(self):
        for name in ("../a.mp3", "C:\\a.mp3", "NUL.mp3", "CON .mp3", "a.html", "a.mp3."):
            with self.assertRaises(ValueError, msg=name):
                self.catalog.add(name, 1, io.BytesIO(b"x"))
        for size in (0, MAX_IMPORT + 1, 2):
            with self.assertRaises(ValueError):
                self.catalog.add("ok.mp3", size, io.BytesIO(b"x"))
        self.assertEqual(self.catalog.list(), {})
        self.assertEqual(list(self.catalog.tracks.iterdir()), [])

    def test_hardlinked_track_is_not_served(self):
        track_id, _, _ = self.catalog.add("track.mp3", 1, io.BytesIO(b"x"))
        target = self.catalog.find(track_id)
        link = Path(self.data.name) / "elsewhere.mp3"
        link.hardlink_to(target)
        self.assertIsNone(self.catalog.find(track_id))

    @unittest.skipUnless(PACK.is_dir(), "Source-only build")
    def test_bundled_tracks_seed_once_under_stable_ids(self):
        defaults = self.catalog.seed_battle_pack()
        self.assertEqual(set(defaults), {"solo", "party", "alliance", "fishing", "venture", "moghouse"})
        # (2026-11-26) the extras (Choose to Fight, J's in-game fishing and Ventures tunes) are in the catalog too, under no slot
        listed = self.catalog.list()
        self.assertTrue(set(defaults.values()) <= set(listed))
        extra = sorted(name for track, name in listed.items() if track not in defaults.values())
        self.assertEqual(extra, ["Choose to Fight (Special Battle Theme XIFO Exclusive).mp3"])
        # (2026-11-27) J's activity and Mog House tunes have slots of their own
        self.assertEqual(listed[defaults["fishing"]], "Just One More Cast.mp3")
        self.assertEqual(listed[defaults["venture"]], "Beyond the Next Hill.mp3")
        self.assertEqual(listed[defaults["moghouse"]], "A Place to Call Home (Mog House Theme).mp3")
        original = self.catalog.find(defaults["solo"])
        original.rename(original.with_name("My Solo.mp3"))
        self.assertEqual(self.catalog.seed_battle_pack(), defaults)
        self.assertEqual(self.catalog.find(defaults["solo"]).name, "My Solo.mp3")


class HTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.data.cleanup)
        script = Path(__file__).resolve().parents[1] / "server.py"
        cls.server = subprocess.Popen(
            [sys.executable, str(script), "--port", "0", "--no-open", "--no-bundled",
             "--data", cls.data.name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cls.addClassCleanup(cls.shutdown)
        line = cls.server.stdout.readline()
        cls.origin = line.strip().split()[-1]
        cls.port = urlsplit(cls.origin).port

    @classmethod
    def shutdown(cls):
        cls.server.terminate()
        cls.server.communicate(timeout=5)

    def request(self, path, method="GET", headers=None, payload=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, body=payload, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_origin_rebinding_path_and_content_guards(self):
        self.assertEqual(self.request("/", headers={"Host": "outside.example"})[0], 403)
        self.assertEqual(self.request("/", headers={"Origin": "null"})[0], 403)
        self.assertEqual(self.request("/api/tracks", "POST")[0], 403)
        self.assertEqual(self.request("/media/../../server.py")[0], 404)
        self.assertEqual(self.request("/media/%2e%2e%2fserver.py")[0], 404)
        self.assertEqual(self.request("/server.py")[0], 404)
        status, headers, _ = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def upload(self, name, payload):
        import json
        headers = {"Origin": self.origin, "X-VanaSync": "1", "X-Filename": quote(name),
                   "Content-Type": "application/octet-stream"}
        status, _, body = self.request("/api/tracks", "POST", headers, payload)
        return status, json.loads(body)

    def post(self, path, record):
        import json
        headers = {"Origin": self.origin, "X-VanaSync": "1", "Content-Type": "application/json"}
        status, _, body = self.request(path, "POST", headers, json.dumps(record).encode())
        return status, json.loads(body)

    def test_unicode_upload_and_media_range_requests(self):
        name = "出陣・Battle.Mix.MP3"
        payload = MP3[:4] + b"123456"
        status, record = self.upload(name, payload)
        self.assertEqual(status, 201)
        self.assertEqual(record["filename"], name)
        path = "/media/" + record["id"]
        self.assertEqual(self.request(path, "HEAD")[2], b"")
        status, headers, body = self.request(path, headers={"Range": "bytes=6-7"})
        self.assertEqual((status, headers["Content-Range"], body), (206, "bytes 6-7/10", b"34"))
        self.assertEqual(self.request(path, headers={"Range": "bytes=-2"})[2], b"56")
        self.assertEqual(self.request(path, headers={"Range": "bytes=12-"})[0], 416)

    def test_only_real_mp3s_are_imported(self):
        # (2026-11-27, J's Radio handoff) new imports: MP3 only, checked by content, with a clear answer
        for name, payload, message in (("song.wav", b"RIFF....WAVE", "Only MP3 files can be added"),
                                       ("renamed.mp3", b"RIFF....WAVEfmt " + bytes(64), "Not an MP3 file"),
                                       ("text.mp3", b"invalid audio test bytes", "Not an MP3 file")):
            status, record = self.upload(name, payload)
            self.assertEqual((status, record["error"]), (400, message), name)

    def test_tags_are_read_kept_and_corrected_and_the_same_song_is_one_track(self):
        import json
        song = id3("Sky\u2019s Edge (Live)", "Nox & JØ", "First Light", "3/11")
        status, record = self.upload("sky (1).mp3", song)
        self.assertEqual(status, 201)
        self.assertEqual(record["tags"], {"title": "Sky\u2019s Edge (Live)", "artist": "Nox & JØ",
                                          "album": "First Light", "track": "3/11"})
        self.assertFalse(record["existed"])
        again = self.upload("sky copy.mp3", song)[1]
        self.assertEqual((again["id"], again["existed"]), (record["id"], True))
        library = json.loads(self.request("/api/library")[2])
        entry = library["tracks"][record["id"]]
        self.assertEqual((entry["origin"], entry["title"], entry["artist"], entry["role"]),
                         ("import", "Sky\u2019s Edge (Live)", "Nox & JØ", ""))
        status, _ = self.post("/api/meta", {"id": record["id"], "edit": {"artist": "NOX"}, "listening": True})
        self.assertEqual(status, 200)
        entry = json.loads(self.request("/api/library")[2])["tracks"][record["id"]]
        self.assertEqual((entry["title"], entry["artist"], entry["role"], entry["tagged"]["artist"]),
                         ("Sky\u2019s Edge (Live)", "NOX", "listening", "Nox & JØ"))
        # no tags at all: nothing is made up
        bare = self.upload("bare.mp3", MP3 + b"bare")[1]
        entry = json.loads(self.request("/api/library")[2])["tracks"][bare["id"]]
        self.assertEqual((entry["title"], entry["artist"]), ("", ""))
        self.assertEqual(self.post("/api/meta", {"id": "0" * 32, "listening": True})[0], 400)

    def test_now_playing_file(self):
        status, record = self.post("/api/nowplaying", {"enabled": True, "text": "A Place \u2014 jnull\n\x07"})
        self.assertEqual(status, 200)
        self.assertEqual(Path(record["file"]).read_text(encoding="utf-8"), "A Place \u2014 jnull\n")
        self.post("/api/nowplaying", {"enabled": True, "text": ""})
        self.assertEqual(Path(record["file"]).read_text(encoding="utf-8"), "")


class TagTest(unittest.TestCase):
    def test_versions_and_fallbacks(self):
        self.assertEqual(tags.read_tags(io.BytesIO(id3("T", "A", version=4))),
                         {"title": "T", "artist": "A", "album": "", "track": ""})
        v1 = MP3 + b"TAG" + b"Old Song".ljust(30, b"\0") + b"Someone".ljust(30, b"\0") + bytes(30 + 4 + 28) + b"\0\x07\0"
        self.assertEqual(tags.read_tags(io.BytesIO(v1)),
                         {"title": "Old Song", "artist": "Someone", "album": "", "track": "7"})
        self.assertTrue(tags.is_mp3(io.BytesIO(id3("T"))))
        self.assertFalse(tags.is_mp3(io.BytesIO(b"ID3\x03\0\0\0\0\0\x10" + bytes(16))))   # a tag and nothing after it

    @unittest.skipUnless(PACK.is_dir(), "Source-only build")
    def test_bundled_files_are_mp3s(self):
        for path in PACK.glob("*.mp3"):
            with path.open("rb") as handle:
                self.assertTrue(tags.is_mp3(handle), path.name)


class SharedCatalogTest(unittest.TestCase):
    def test_every_bundled_track_has_one_numbered_set(self):
        import json
        shared, sets = load_shared()
        manifest = json.loads(PACK.with_suffix(".json").read_text(encoding="utf-8"))
        bundled = [manifest[s]["sha256"][:32] for s in ("solo", "party", "alliance")] + \
                  [e["sha256"][:32] for e in manifest["extras"]]
        self.assertEqual(sorted(bundled), sorted(shared))
        self.assertEqual([s["id"] for s in sets], ["G001", "G002", "G003", "G004", "A001"])
        self.assertTrue(all(t["group"] == "gameplay" and t["role"] for t in shared.values()))
        self.assertTrue(all(t["no"] >= 1 and t["title"] and t["artist"] for t in shared.values()))


if __name__ == "__main__":
    unittest.main()
