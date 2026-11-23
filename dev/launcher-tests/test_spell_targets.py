"""(Yache, 2026-11-22) Wild Carrot and Magic Fruit could not be aimed at a squad mate: the game only offers an NPC in
your party (a squad mate, a Trust) as the target of a spell whose target list includes NPCs. launcher_client's sixth
step adds that target to the spells listed in client-patches/spell_targets.json, in the game's spell table.

The table here is made up for the test (the game's own file is never part of this project): same layout, invented spells.

Run: python test_spell_targets.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)
import launcher_client as lc

ENTRIES = 1024


def entry(spell_id, targets, kind=6, mp=37, cast=10):
    """One spell as the game stores it: 100 bytes, every byte turned except the three that decide by how much."""
    plain = bytearray(100)
    plain[0], plain[1] = spell_id & 0xFF, spell_id >> 8
    plain[2] = kind                                  # stored as it is
    plain[4] = 15
    plain[6], plain[7] = targets & 0xFF, targets >> 8
    plain[8] = 43
    plain[10], plain[11] = mp & 0xFF, mp >> 8        # byte 11 stored as it is
    plain[12] = cast                                 # stored as it is
    for i in range(14, 62, 2):
        plain[i], plain[i + 1] = 0xFF, 0xFF
    plain[99] = 0xFF
    turn = lc._spell_turn(plain)
    stored = bytearray(lc._turn_left(b, turn) for b in plain)
    stored[2], stored[11], stored[12] = plain[2], plain[11], plain[12]
    return bytes(stored)


def block(name, kind, body):
    size = 16 + len(body)
    assert size % 16 == 0
    return name + ((size // 16) << 7 | kind).to_bytes(4, "little") + bytes(8) + body


def spell_file(targets=None, entries=ENTRIES, with_table=True):
    targets = targets or {}
    table = b"".join(entry(i, targets.get(i, 0x20), kind=1 + i % 6, mp=i % 300, cast=4 + i % 40) for i in range(entries))
    table += bytes(-len(table) % 16)
    parts = [block(b"menu", 0x01, bytes(16)), block(b"mon_", 0x04, bytes(1024))]
    if with_table:
        parts.append(block(b"mgc_", 0x49, table))
    parts += [block(b"comm", 0x53, bytes(2048)), b"end\x00" + bytes(12)]
    return b"".join(parts)


class SpellTargets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.kit, self.game = os.path.join(self.tmp, "kit"), os.path.join(self.tmp, "game")
        os.makedirs(os.path.join(self.kit, "client-patches"))
        shutil.copy(os.path.join(KIT, "client-patches", "spell_targets.json"), os.path.join(self.kit, "client-patches"))
        os.makedirs(os.path.join(self.game, "ROM", "118"))
        self.path = os.path.join(self.game, "ROM", "118", "114.DAT")
        self.spells = json.load(open(os.path.join(KIT, "client-patches", "spell_targets.json"), encoding="utf-8"))["spells"]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, data):
        with open(self.path, "wb") as handle:
            handle.write(data)

    def targets(self, spell_id):
        data = bytearray(open(self.path, "rb").read())
        start, _count = lc._spell_table(data)
        return lc._spell_field(data, start, spell_id, lc.SPELL_TARGETS_AT)[0]

    def test_the_list_is_the_two_blue_magic_heals(self):
        self.assertEqual([(s["id"], s["name"], s["targets"]) for s in self.spells], [(578, "Wild Carrot", 5), (593, "Magic Fruit", 5)])

    def test_the_made_up_table_reads_like_the_game_s(self):
        data = bytearray(spell_file({1: 0x3F, 578: 5}))
        start, count = lc._spell_table(data)
        self.assertEqual(count, ENTRIES)
        self.assertEqual(lc._spell_field(data, start, 1, 6)[0], 0x3F)
        self.assertEqual(lc._spell_field(data, start, 578, 6)[0], 5)
        turns = {lc._spell_turn(data[start + i * 100:start + i * 100 + 100]) for i in range(ENTRIES)}
        self.assertEqual(turns, {1, 2, 5, 6, 7}, "every amount of turning is in the test table")

    def test_adds_the_npc_target_and_nothing_else(self):
        before = spell_file({1: 0x3F, 43: 0x1D, 578: 5, 593: 5, 108: 5})
        self.write(before)
        message = lc.spell_targets(self.kit, self.game)
        self.assertIn("Wild Carrot and Magic Fruit", message)
        after = open(self.path, "rb").read()
        self.assertEqual(len(after), len(before))
        self.assertEqual(sum(1 for a, b in zip(before, after) if a != b), 2, "one byte per spell")
        self.assertEqual((self.targets(578), self.targets(593)), (0x15, 0x15))
        self.assertEqual((self.targets(1), self.targets(43), self.targets(108)), (0x3F, 0x1D, 5), "other spells as they were")
        keep = os.path.join(self.kit, "backups", "spell-targets-dat", "114.DAT.original")
        self.assertEqual(open(keep, "rb").read(), before, "the file from before is kept")
        self.assertIsNone(lc.spell_targets(self.kit, self.game), "a second run has nothing to do")
        self.assertEqual(open(self.path, "rb").read(), after)
        self.assertEqual(open(keep, "rb").read(), before, "and the kept original is not replaced by the changed file")

    def test_one_done_one_to_do(self):
        self.write(spell_file({1: 0x3F, 578: 0x15, 593: 5}))
        message = lc.spell_targets(self.kit, self.game)
        self.assertIn("Magic Fruit", message)
        self.assertNotIn("Wild Carrot", message)
        self.assertEqual((self.targets(578), self.targets(593)), (0x15, 0x15))

    def test_a_file_that_is_not_what_we_expect_is_left_alone(self):
        for name, data in (("another target list", spell_file({1: 0x3F, 578: 0x20, 593: 5})),
                           ("no spell table", spell_file(with_table=False)),
                           ("a short table", spell_file({1: 0x3F}, entries=400)),
                           ("not a spell table", block(b"mgc_", 0x49, bytes(range(256)) * 400)),
                           ("rubbish", b"\x07" * 5000)):
            self.write(data)
            message = lc.spell_targets(self.kit, self.game)
            self.assertIn("left as it is", message or "", name)
            self.assertEqual(open(self.path, "rb").read(), data, name)
        self.assertFalse(os.path.exists(os.path.join(self.kit, "backups")), "nothing kept when nothing was changed")

    def test_it_is_one_of_the_game_file_steps_and_never_stops_play(self):
        self.write(spell_file({1: 0x3F, 578: 5, 593: 5}))
        said = []
        messages = lc.apply_all(self.kit, self.game, "", log=said.append)       # the other steps have nothing here and are skipped
        self.assertTrue(any("Wild Carrot and Magic Fruit" in m for m in messages))
        self.assertEqual((self.targets(578), self.targets(593)), (0x15, 0x15))
        os.remove(self.path)
        again = lc.apply_all(self.kit, self.game, "", log=said.append)          # no spell file at all: reported, not raised
        self.assertTrue(any(m.startswith("Spells on squad mates: skipped") for m in again))


if __name__ == "__main__":
    unittest.main()
