"""Stand-in tests for launcher_client.homepoints (no game files needed): python test_homepoints.py [kit folder]"""
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, sys.argv.pop(1) if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", ".."))
import launcher_client as lc   # noqa: E402

ERA = bytes.fromhex("011009804818801a140221")
RETAIL = bytes.fromhex("0000031003010004100302")
AT = 20


def entry(npc, middle):
    body = bytearray(40)
    struct.pack_into("<I", body, 0, npc)
    body[AT:AT + 11] = middle
    return bytes(body)


def event_file(*entries):
    return struct.pack("<I", len(entries)) + b"".join(struct.pack("<I", len(e)) for e in entries) + b"".join(entries)


class HomePointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kit = os.path.join(self.tmp.name, "kit")
        self.game = os.path.join(self.tmp.name, "game")
        os.makedirs(os.path.join(self.kit, "dat-backup"))
        os.makedirs(os.path.join(self.kit, "client-patches"))
        rows = [{"file": "ROM/1/2.DAT", "npc": n, "at": AT, "era": ERA.hex()} for n in (100, 101)]
        with open(os.path.join(self.kit, "client-patches", "homepoints.json"), "w") as h:
            json.dump({"retail": RETAIL.hex(), "entries": rows}, h)
        self.path = os.path.join(self.game, "ROM", "1", "2.DAT")
        os.makedirs(os.path.dirname(self.path))
        self.era = event_file(entry(99, b"x" * 11), entry(100, ERA), entry(101, ERA))
        self.want = event_file(entry(99, b"x" * 11), entry(100, RETAIL), entry(101, RETAIL))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        with open(self.path, "wb") as h:
            h.write(data)

    def read(self):
        with open(self.path, "rb") as h:
            return h.read()

    def test_fresh_then_nothing_to_do(self):
        self.write(self.era)
        self.assertIn("2 crystal", lc.homepoints(self.kit, self.game))
        self.assertEqual(self.read(), self.want)
        self.assertIsNone(lc.homepoints(self.kit, self.game))
        keep = os.path.join(self.kit, "backups", "homepoint-events", "ROM", "1", "2.DAT")
        with open(keep, "rb") as h:
            self.assertEqual(h.read(), self.era)

    def test_entry_copied_from_a_newer_game_is_rebuilt(self):
        newer = bytearray(self.want)
        newer[-5] ^= 0x55                                # an older launcher copied a different (newer) retail entry
        self.write(bytes(newer))
        keep = os.path.join(self.kit, "backups", "homepoint-events", "ROM", "1", "2.DAT")
        os.makedirs(os.path.dirname(keep))
        with open(keep, "wb") as h:
            h.write(self.era)
        self.assertIn("rebuilt", lc.homepoints(self.kit, self.game))
        self.assertEqual(self.read(), self.want)

    def test_unexpected_file_is_left_alone(self):
        other = event_file(entry(99, b"x" * 11), entry(100, b"y" * 11), entry(101, b"z" * 11))
        self.write(other)
        self.assertIn("skipped", lc.homepoints(self.kit, self.game))
        self.assertEqual(self.read(), other)

    def test_no_era_files_no_change(self):
        os.rmdir(os.path.join(self.kit, "dat-backup"))
        self.write(self.era)
        self.assertIn("already retail", lc.homepoints(self.kit, self.game))
        self.assertEqual(self.read(), self.era)


if __name__ == "__main__":
    unittest.main()
