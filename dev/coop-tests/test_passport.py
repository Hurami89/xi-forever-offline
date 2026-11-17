"""Tests for launcher_passport.py on two scratch databases (see cooptest.py). Run: python test_passport.py"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cooptest as ct
import launcher_passport as pp

HOME_ACC, HOME_CHAR = 1000, 21828
BOT_ACC, BOT_CHAR = pp.BOT_ACCOUNT_BASE + 5, pp.BOT_CHAR_BASE + 5


def setUpModule():
    try:
        ct.drop_worlds()
    except Exception as e:
        raise unittest.SkipTest(f"no database to test on ({e})")


def tearDownModule():
    ct.drop_worlds()


class PassportTests(unittest.TestCase):
    def setUp(self):
        self.home = ct.make_world(ct.HOME_DB)
        self.host = ct.make_world(ct.HOST_DB)
        ct.make_account(self.home, HOME_ACC, "homeplayer")
        ct.make_character(self.home, HOME_ACC, HOME_CHAR, "Visitor")
        ct.make_account(self.host, HOME_ACC, "hostplayer")
        ct.make_character(self.host, HOME_ACC, HOME_CHAR, "Hostess", linkshell=False)      # the same ids on purpose
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for conn in (self.home, self.host):
            conn.rollback()
            conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # helpers
    def q(self, conn, sql, params=()):
        rows = ct.run(conn, sql, params)
        conn.rollback()
        return rows

    def arrive(self, data, guest_id="g1", login="guestone"):
        return pp.import_guest(self.host, data, guest_id, "key-" + guest_id, login, "pw-" + guest_id, stamp={"world": "Host"})

    def visit(self):
        data, nonce = pp.depart(self.home, HOME_CHAR, {"address": "10.0.0.2"})
        guest = self.arrive(data)
        return data, nonce, guest

    # --- leaving home ---
    def test_same_layout_in_both_worlds(self):
        self.assertEqual(pp.schema_signature(self.home), pp.schema_signature(self.host))

    def test_depart_locks_and_leaves_world_things_home(self):
        data, nonce = pp.depart(self.home, HOME_CHAR, {"address": "10.0.0.2"})
        passport = pp.unpack(data)
        self.assertEqual((passport["kind"], passport["name"], passport["nonce"], passport["generation"]), ("visit", "Visitor", nonce, 1))
        away_acc = self.q(self.home, "SELECT id, status FROM accounts WHERE login = ?", (pp.AWAY_LOGIN,))[0]
        self.assertEqual(self.q(self.home, "SELECT accid FROM chars WHERE charid = ?", (HOME_CHAR,))[0][0], away_acc[0])
        self.assertEqual(away_acc[1], 0)                                   # nobody can log in to it
        inv = passport["tables"]["char_inventory"]
        items = [r[inv["cols"].index("itemId")] for r in inv["rows"]]
        self.assertNotIn(515, items)
        self.assertIn(65535, items)
        eq = passport["tables"]["char_equip"]
        self.assertEqual([r[eq["cols"].index("equipslotid")] for r in eq["rows"]], [0])
        names = [r[passport["tables"]["char_vars"]["cols"].index("varname")] for r in passport["tables"]["char_vars"]["rows"]]
        self.assertEqual(sorted(names), ["SQUAD_FOLLOW", "TrustEngageType", "[Quest]Progress"])
        self.assertEqual(passport["summary"]["gil"], 1000)
        self.assertEqual(passport["summary"]["level"], 30)
        self.assertEqual([a["name"] for a in pp.away_list(self.home)], ["Visitor"])
        with self.assertRaises(pp.PassportError):
            pp.depart(self.home, HOME_CHAR, {})                            # already away

    def test_depart_refused_while_in_game_and_for_bots(self):
        ct.run(self.home, "INSERT INTO accounts_sessions (accid, charid, session_key, server_addr, server_port, client_addr) "
                          "VALUES (?, ?, 'k', 0, 0, 0)", (HOME_ACC, HOME_CHAR))
        self.home.commit()
        with self.assertRaises(pp.PassportError):
            pp.depart(self.home, HOME_CHAR, {})
        self.assertEqual(self.q(self.home, "SELECT accid FROM chars WHERE charid = ?", (HOME_CHAR,))[0][0], HOME_ACC)
        self.assertEqual(pp.away_list(self.home), [])
        ct.make_account(self.home, BOT_ACC, "bot5")
        ct.make_character(self.home, BOT_ACC, BOT_CHAR, "Botty")
        with self.assertRaises(pp.PassportError):
            pp.depart(self.home, BOT_CHAR, {})

    # --- arriving ---
    def test_arrival_is_a_faithful_copy_on_a_guest_account(self):
        data, _nonce, guest = self.visit()
        self.assertFalse(guest["again"])
        self.assertNotEqual(guest["charid"], HOME_CHAR)                    # that id is the host's own character here
        self.assertLess(guest["accid"], pp.BOT_ACCOUNT_BASE)
        self.assertGreaterEqual(guest["accid"], 1000)
        acc = self.q(self.host, "SELECT login, status, LEFT(password, 1) FROM accounts WHERE id = ?", (guest["accid"],))[0]
        self.assertEqual(acc, ("guestone", 1, "*"))
        row = self.q(self.host, "SELECT accid, charname, gmlevel, pos_zone, playtime, missions FROM chars WHERE charid = ?", (guest["charid"],))[0]
        self.assertEqual(row[:5], (guest["accid"], "Visitor", 0, 238, 4321))
        self.assertEqual(bytes(row[5]), bytes(range(40)))
        # every travelling row arrived exactly, and nothing else
        cur = self.host.cursor()
        there = pp._read(cur, pp.local_layout(cur), guest["charid"])
        cur.close(); self.host.rollback()
        sent = pp.unpack(data)["tables"]
        for table in pp.TABLES:
            self.assertEqual(sorted(map(repr, there[table]["rows"])), sorted(map(repr, sent[table]["rows"])), table)
        self.assertEqual(self.q(self.host, "SELECT value FROM char_vars WHERE charid = ? AND varname = 'COOP_GUEST'", (guest["charid"],)), [(1,)])
        again = self.arrive(data)                                          # the same passport twice: nothing new
        self.assertTrue(again["again"])
        self.assertEqual(again["charid"], guest["charid"])
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM chars WHERE charname = 'Visitor'")[0][0], 1)
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM accounts")[0][0], 2)

    def test_same_id_is_kept_when_it_is_free(self):
        ct.run(self.host, "DELETE FROM chars WHERE charid = ?", (HOME_CHAR,))
        self.host.commit()
        _data, _nonce, guest = self.visit()
        self.assertEqual(guest["charid"], HOME_CHAR)

    def test_name_clash(self):
        data, _nonce = pp.depart(self.home, HOME_CHAR, {})
        ct.run(self.host, "UPDATE chars SET charname = 'Visitor' WHERE charid = ?", (HOME_CHAR,))
        self.host.commit()
        with self.assertRaises(pp.PassportError):
            self.arrive(data)
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM accounts")[0][0], 1)       # nothing half-made
        ct.run(self.host, "UPDATE chars SET charname = 'Hostess' WHERE charid = ?", (HOME_CHAR,))
        ct.make_account(self.host, BOT_ACC, "bot5")
        ct.make_character(self.host, BOT_ACC, BOT_CHAR, "Visitor", linkshell=False)             # a bot has the name
        guest = self.arrive(data)
        self.assertEqual(guest["renamed_bot"], "Visitora")
        self.assertEqual(self.q(self.host, "SELECT charname FROM chars WHERE charid = ?", (BOT_CHAR,))[0][0], "Visitora")

    def test_guest_limit(self):
        data, _nonce = pp.depart(self.home, HOME_CHAR, {})
        with self.assertRaises(pp.PassportError):
            pp.import_guest(self.host, data, "g1", "k", "guestone", "pw", max_guests=0)

    # --- playing there, checkpoints, going home ---
    def play(self, charid):
        """What a session in the host's world leaves in its database."""
        h = self.host
        ct.run(h, "UPDATE char_inventory SET quantity = quantity + 500 WHERE charid = ? AND location = 0 AND slot = 0", (charid,))
        ct.run(h, "INSERT INTO char_inventory (charid, location, slot, itemId, quantity) VALUES (?, 0, 3, 17000, 1)", (charid,))   # in the pearl's old slot
        ct.run(h, "INSERT INTO char_inventory (charid, location, slot, itemId, quantity, extra) VALUES (?, 0, 4, 515, 1, ?)", (charid, b"\x09" * 24))
        ct.run(h, "INSERT INTO char_equip (charid, slotid, equipslotid, containerid) VALUES (?, 4, 17, 0)", (charid,))
        ct.run(h, "UPDATE char_stats SET mlvl = 33 WHERE charid = ?", (charid,))
        ct.run(h, "UPDATE char_jobs SET war = 33 WHERE charid = ?", (charid,))
        ct.run(h, "INSERT INTO char_vars (charid, varname, value) VALUES (?, '[Quest]New', 7), (?, 'COOP_X', 9)", (charid, charid))
        ct.run(h, "UPDATE chars SET pos_zone = 100, playtime = 9999 WHERE charid = ?", (charid,))
        h.commit()

    def test_round_trip(self):
        _data, nonce, guest = self.visit()
        self.play(guest["charid"])
        check, gen = pp.export_guest(self.host, "g1")
        self.assertEqual((gen, pp.unpack(check)["kind"], pp.unpack(check)["nonce"]), (2, "checkpoint", nonce))
        ct.run(self.host, "INSERT INTO accounts_sessions (accid, charid, session_key, server_addr, server_port, client_addr) "
                          "VALUES (?, ?, 'k', 0, 0, 0)", (guest["accid"], guest["charid"]))
        self.host.commit()
        with self.assertRaises(pp.PassportError):                          # still in the game
            pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        ct.run(self.host, "DELETE FROM accounts_sessions WHERE charid = ?", (guest["charid"],))
        self.host.commit()
        final, gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        self.assertEqual(gen, 3)
        record = pp.guest_list(self.host)[0]
        self.assertEqual(record["state"], "left")
        self.assertTrue(os.path.exists(record["final_file"]))
        self.assertEqual(self.q(self.host, "SELECT status FROM accounts WHERE id = ?", (guest["accid"],))[0][0], 0)
        again, gen2 = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)       # asked twice: the same passport
        self.assertEqual((again, gen2), (final, 3))
        with self.assertRaises(pp.PassportError):
            pp.export_guest(self.host, "g1")                                # no checkpoints after leaving

        result = pp.come_home(self.home, final, backup_dir=self.tmp)
        self.assertFalse(result["already"])
        self.assertEqual(result["changes"]["gil"], 500)
        self.assertEqual(result["changes"]["levels"], 3)
        self.assertTrue(os.path.exists(result["backup"]))
        row = self.q(self.home, "SELECT accid, charname, pos_zone, playtime, gmlevel FROM chars WHERE charid = ?", (HOME_CHAR,))[0]
        self.assertEqual(row, (HOME_ACC, "Visitor", 100, 9999, 0))
        inv = {(r[0], r[1]): r[2] for r in self.q(self.home, "SELECT location, slot, itemId FROM char_inventory WHERE charid = ?", (HOME_CHAR,))}
        self.assertEqual(inv[(0, 3)], 17000)                               # what was found there
        pearls = [k for k, v in inv.items() if v == 515]
        self.assertEqual(len(pearls), 1)                                   # the home pearl only, moved to a free slot
        self.assertNotEqual(pearls[0], (0, 3))
        self.assertEqual(self.q(self.home, "SELECT extra FROM char_inventory WHERE charid = ? AND itemId = 515", (HOME_CHAR,))[0][0][:1], b"\x05")
        self.assertEqual(self.q(self.home, "SELECT COUNT(*) FROM char_equip WHERE charid = ? AND equipslotid IN (16, 17)", (HOME_CHAR,))[0][0], 0)
        self.assertEqual(self.q(self.home, "SELECT quantity FROM char_inventory WHERE charid = ? AND location = 0 AND slot = 0", (HOME_CHAR,))[0][0], 1500)
        names = dict(self.q(self.home, "SELECT varname, value FROM char_vars WHERE charid = ?", (HOME_CHAR,)))
        self.assertEqual(names, {"[Quest]Progress": 3, "TrustEngageType": 1, "[Quest]New": 7, "SQUAD_FOLLOW": 1, "[Bots]LS": 4})
        self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 33)
        self.assertEqual(pp.away_list(self.home), [])
        # the same passport again, and the older checkpoint: no change
        self.assertTrue(pp.come_home(self.home, final)["already"])
        self.assertTrue(pp.come_home(self.home, check)["already"])
        self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 33)
        # the host says goodbye: character and account are gone, the host's own character is untouched
        self.assertTrue(pp.remove_guest(self.host, "g1"))
        self.assertEqual(self.q(self.host, "SELECT charname FROM chars ORDER BY charid"), [("Hostess",)])
        self.assertEqual(self.q(self.host, "SELECT login FROM accounts"), [("hostplayer",)])
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM char_inventory WHERE charid = ?", (guest["charid"],))[0][0], 0)
        self.assertFalse(pp.remove_guest(self.host, "g1"))
        self.assertEqual(pp.guest_list(self.host), [])

    def test_pearl_stays_put_when_its_slot_is_free(self):
        _data, _nonce, guest = self.visit()
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        pp.come_home(self.home, final)
        self.assertEqual(self.q(self.home, "SELECT location, slot FROM char_inventory WHERE charid = ? AND itemId = 515", (HOME_CHAR,)), [(0, 3)])
        self.assertEqual(self.q(self.home, "SELECT slotid, containerid FROM char_equip WHERE charid = ? AND equipslotid = 16", (HOME_CHAR,)), [(3, 0)])

    def test_visit_again_after_going_home(self):
        _data, _nonce, guest = self.visit()
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        pp.come_home(self.home, final)
        pp.remove_guest(self.host, "g1")
        # someone else now has the old guest's account id: a later visit must not touch it
        ct.make_account(self.host, guest["accid"], "newcomer")
        data2, nonce2 = pp.depart(self.home, HOME_CHAR, {})
        guest2 = self.arrive(data2, guest_id="g2", login="guesttwo")
        self.assertFalse(guest2["again"])
        self.assertEqual(self.q(self.host, "SELECT login FROM accounts WHERE id = ?", (guest["accid"],)), [("newcomer",)])
        with self.assertRaises(pp.PassportError):                          # the first visit's passport is spent
            pp.come_home(self.home, final)
        final2, _gen = pp.export_guest(self.host, "g2", final=True, save_dir=self.tmp)
        self.assertFalse(pp.come_home(self.home, final2)["already"])

    # --- when the host is gone ---
    def test_take_back_as_it_was(self):
        _data, _nonce, guest = self.visit()
        self.play(guest["charid"])
        result = pp.take_back(self.home, HOME_CHAR)
        self.assertFalse(result["already"])
        self.assertEqual(self.q(self.home, "SELECT accid, pos_zone FROM chars WHERE charid = ?", (HOME_CHAR,))[0], (HOME_ACC, 238))
        self.assertEqual(self.q(self.home, "SELECT quantity FROM char_inventory WHERE charid = ? AND slot = 0 AND location = 0", (HOME_CHAR,))[0][0], 1000)
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)       # the host turns up later
        self.assertTrue(pp.come_home(self.home, final)["already"])
        self.assertEqual(self.q(self.home, "SELECT pos_zone FROM chars WHERE charid = ?", (HOME_CHAR,))[0][0], 238)

    def test_take_back_from_a_checkpoint(self):
        _data, _nonce, guest = self.visit()
        self.play(guest["charid"])
        check, _gen = pp.export_guest(self.host, "g1")
        ct.run(self.host, "UPDATE char_stats SET mlvl = 40 WHERE charid = ?", (guest["charid"],))      # played on after it
        self.host.commit()
        result = pp.take_back(self.home, HOME_CHAR, checkpoint=check, backup_dir=self.tmp)
        self.assertEqual(result["changes"]["levels"], 3)
        self.assertEqual(self.q(self.home, "SELECT accid FROM chars WHERE charid = ?", (HOME_CHAR,))[0][0], HOME_ACC)
        self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 33)
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        self.assertTrue(pp.come_home(self.home, final)["already"])
        self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 33)
        # a stale copy that is still "active" on the host is replaced when the character visits again
        ct.run(self.host, "UPDATE coop_guest SET state = 'active' WHERE guest_id = 'g1'")
        ct.run(self.host, "UPDATE accounts SET status = 1 WHERE id = ?", (guest["accid"],))
        self.host.commit()
        data2, _n = pp.depart(self.home, HOME_CHAR, {})
        guest2 = self.arrive(data2, guest_id="g2", login="guesttwo")
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM chars WHERE charname = 'Visitor'")[0][0], 1)
        self.assertEqual(self.q(self.host, "SELECT mlvl FROM char_stats WHERE charid = ?", (guest2["charid"],))[0][0], 33)
        self.assertEqual([g["guest_id"] for g in pp.guest_list(self.host)], ["g2"])

    # --- things that must be refused ---
    def test_other_versions_and_other_worlds_are_refused(self):
        data, _nonce = pp.depart(self.home, HOME_CHAR, {})
        ct.run(self.host, "ALTER TABLE char_points ADD COLUMN new_points INT NOT NULL DEFAULT 0")
        self.host.commit()
        with self.assertRaises(pp.PassportError):
            self.arrive(data)
        ct.run(self.host, "ALTER TABLE char_points DROP COLUMN new_points")
        self.host.commit()
        guest = self.arrive(data)
        with self.assertRaises(pp.PassportError):
            pp.come_home(self.host, data)                                  # a visit passport is not a return
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        with self.assertRaises(pp.PassportError):
            pp.come_home(self.host, final)                                 # ...and it belongs to another world
        with self.assertRaises(pp.PassportError):
            pp.import_guest(self.home, data, "g9", "k", "guestnine", "pw")     # its own world is not a place to visit
        self.assertTrue(guest["charid"])

    def test_tampered_passports(self):
        data, _nonce = pp.depart(self.home, HOME_CHAR, {})
        passport = pp.unpack(data)
        bad = dict(passport, tables=dict(passport["tables"]))
        bad["tables"]["accounts; DROP TABLE chars"] = {"cols": ["id"], "rows": [[1]]}
        with self.assertRaises(pp.PassportError):
            self.arrive(pp.pack(bad))
        bad = dict(passport, tables=dict(passport["tables"]))
        block = passport["tables"]["chars"]
        bad["tables"]["chars"] = {"cols": block["cols"][:-1] + ["gmlevel"], "rows": [block["rows"][0][:-1] + [5]]}
        with self.assertRaises(pp.PassportError):
            self.arrive(pp.pack(bad))
        with self.assertRaises(pp.PassportError):
            pp.unpack(pp.pack(dict(passport, name="Robert'); DROP")))
        with self.assertRaises(pp.PassportError):
            pp.unpack(b"not a zip")
        sneaky = dict(passport, tables=dict(passport["tables"]))                # world things hidden in a visit passport
        vars_block = passport["tables"]["char_vars"]
        row = [None] * len(vars_block["cols"])
        row[vars_block["cols"].index("varname")], row[vars_block["cols"].index("value")] = "COOP_GUEST", 0
        if "expiry" in vars_block["cols"]:
            row[vars_block["cols"].index("expiry")] = 0
        sneaky["tables"]["char_vars"] = {"cols": vars_block["cols"], "rows": vars_block["rows"] + [row]}
        guest = self.arrive(pp.pack(sneaky))
        self.assertEqual(self.q(self.host, "SELECT value FROM char_vars WHERE charid = ? AND varname = 'COOP_GUEST'", (guest["charid"],)), [(1,)])
        self.assertEqual(self.q(self.host, "SELECT gmlevel FROM chars WHERE charid = ?", (guest["charid"],))[0][0], 0)
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM chars")[0][0], 2)

    # --- squad mates travel with their character ---
    def squads(self):
        """Home: Kasumi (slot 1) and Gio (slot 2). The host has three mates of its own, so the visitors get other numbers."""
        ct.make_squad(self.host, HOME_CHAR, [(1, "Momo", 1, 50), (2, "Kyo", 3, 50), (4, "Rin", 6, 50)], unlocks=(900,))
        ct.run(self.home, "INSERT INTO squad_mate (charid, slot, name, mjob) VALUES (999, 1, 'Other', 1)")      # somebody else's mate
        home = ct.make_squad(self.home, HOME_CHAR, [(1, "Kasumi", 1, 30), (2, "Gio", 3, 28)], unlocks=(100, 200))
        ct.run(self.home, "INSERT INTO char_vars (charid, varname, value) VALUES (?, 'SQUAD_AI_777', 5), (?, ?, 7)",
               (HOME_CHAR, HOME_CHAR, f"SQUAD_WS_{home[2]}"))
        self.home.commit()
        return home

    def mates(self, conn, charid):
        return {r[0]: r[1:] for r in self.q(conn, "SELECT m.slot, m.id, m.name, m.mjob, j.level FROM squad_mate m "
                                                  "LEFT JOIN squad_job j ON j.squad_id = m.id AND j.job = m.mjob WHERE m.charid = ? ORDER BY m.slot", (charid,))}

    def vars(self, conn, charid, like="SQUAD%"):
        return dict(self.q(conn, "SELECT varname, value FROM char_vars WHERE charid = ? AND varname LIKE ?", (charid, like)))

    def test_squad_travels_and_is_renumbered(self):
        home = self.squads()
        data, _nonce, guest = self.visit()
        passport = pp.unpack(data)
        self.assertEqual([(m["slot"], m["name"], m["job"], m["level"]) for m in passport["summary"]["squad"]],
                         [(1, "Kasumi", "WAR", 30), (2, "Gio", "WHM", 28)])
        there = self.mates(self.host, guest["charid"])
        self.assertEqual({slot: row[1:] for slot, row in there.items()}, {1: ("Kasumi", 1, 30), 2: ("Gio", 3, 28)})
        self.assertTrue(all(row[0] not in home.values() or row[0] > 3 for row in there.values()))      # new numbers there
        self.assertNotEqual(there[1][0], home[1])
        self.assertEqual(self.vars(self.host, guest["charid"]),
                         {f"SQUAD_AI_{there[1][0]}": 21, f"SQUAD_LOOK_{there[1][0]}": 1, f"SQUAD_AI_{there[2][0]}": 22,
                          f"SQUAD_LOOK_{there[2][0]}": 1, f"SQUAD_WS_{there[2][0]}": 7, "SQUAD_FOLLOW": 1})      # the stray SQUAD_AI_777 is gone
        self.assertEqual(self.q(self.host, "SELECT job, level, exp FROM squad_job WHERE squad_id = ? ORDER BY job", (there[1][0],)), [(1, 30, 250), (2, 10, 0)])
        self.assertEqual(self.q(self.host, "SELECT job, slot, itemid FROM squad_equip WHERE squad_id = ?", (there[2][0],)), [(3, 0, 16535)])
        self.assertEqual(self.q(self.host, "SELECT itemid FROM squad_unlock WHERE charid = ? ORDER BY itemid", (guest["charid"],)), [(100,), (200,)])
        # the host's own squad is untouched
        self.assertEqual({s: r[1:] for s, r in self.mates(self.host, HOME_CHAR).items()}, {1: ("Momo", 1, 50), 2: ("Kyo", 3, 50), 4: ("Rin", 6, 50)})
        self.assertEqual(self.q(self.host, "SELECT itemid FROM squad_unlock WHERE charid = ?", (HOME_CHAR,)), [(900,)])

        # in the friend's world: Kasumi gains three levels, Gio is dismissed for good, a new mate joins, a new piece of gear
        h, kasumi, gio = self.host, there[1][0], there[2][0]
        ct.run(h, "UPDATE squad_job SET level = 33, exp = 40 WHERE squad_id = ? AND job = 1", (kasumi,))
        ct.run(h, "UPDATE char_vars SET value = 12 WHERE charid = ? AND varname = ?", (guest["charid"], f"SQUAD_AI_{kasumi}"))
        for table in ("squad_job", "squad_equip"):
            ct.run(h, f"DELETE FROM {table} WHERE squad_id = ?", (gio,))
        ct.run(h, "DELETE FROM squad_mate WHERE id = ?", (gio,))
        h.commit()
        fresh = ct.make_squad(h, guest["charid"], [(3, "Nyx", 6, 12)], unlocks=(300,))[3]
        check, _gen = pp.export_guest(self.host, "g1")
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        result = pp.come_home(self.home, final, backup_dir=self.tmp)
        back = self.mates(self.home, HOME_CHAR)
        self.assertEqual({slot: row[1:] for slot, row in back.items()}, {1: ("Kasumi", 1, 33), 3: ("Nyx", 6, 12)})
        self.assertEqual(back[1][0], home[1])                                # Kasumi kept her number at home
        self.assertNotIn(back[3][0], (home[1], home[2]))                    # the new mate got a number of its own
        self.assertTrue(fresh)
        self.assertEqual(self.vars(self.home, HOME_CHAR),
                         {f"SQUAD_AI_{home[1]}": 12, f"SQUAD_LOOK_{home[1]}": 1, f"SQUAD_AI_{back[3][0]}": 23, f"SQUAD_LOOK_{back[3][0]}": 1, "SQUAD_FOLLOW": 1})
        self.assertEqual(self.q(self.home, "SELECT job, level, exp FROM squad_job WHERE squad_id = ? ORDER BY job", (home[1],)), [(1, 33, 40), (2, 10, 0)])
        self.assertEqual(self.q(self.home, "SELECT COUNT(*) FROM squad_job WHERE squad_id = ?", (home[2],))[0][0], 0)       # Gio's rows went with him
        self.assertEqual(self.q(self.home, "SELECT itemid FROM squad_unlock WHERE charid = ? ORDER BY itemid", (HOME_CHAR,)), [(100,), (200,), (300,)])
        self.assertEqual(self.q(self.home, "SELECT name FROM squad_mate WHERE charid = 999"), [("Other",)])
        told = {m["name"]: (m["gained"], m["new"]) for m in result["changes"]["mates"]}
        self.assertEqual(told, {"Kasumi": (3, False), "Nyx": (0, True)})
        self.assertTrue(pp.come_home(self.home, check)["already"])
        # the pre-return backup holds the squad as it was, and puts it back by slot
        pp.restore_backup(self.home, open(result["backup"], "rb").read())
        again = self.mates(self.home, HOME_CHAR)
        self.assertEqual({slot: row[1:] for slot, row in again.items()}, {1: ("Kasumi", 1, 30), 2: ("Gio", 3, 28)})
        self.assertEqual(again[1][0], home[1])
        self.assertEqual(self.vars(self.home, HOME_CHAR)[f"SQUAD_WS_{again[2][0]}"], 7)
        self.assertEqual(self.vars(self.home, HOME_CHAR)[f"SQUAD_AI_{again[2][0]}"], 22)
        self.assertEqual(len(self.q(self.home, "SELECT 1 FROM squad_unlock WHERE charid = ?", (HOME_CHAR,))), 2)

    def test_squad_comes_back_from_a_checkpoint(self):
        home = self.squads()
        _data, _nonce, guest = self.visit()
        there = self.mates(self.host, guest["charid"])
        ct.run(self.host, "UPDATE squad_job SET level = 31 WHERE squad_id = ? AND job = 1", (there[1][0],))
        self.host.commit()
        check, _gen = pp.export_guest(self.host, "g1")
        ct.run(self.host, "UPDATE squad_job SET level = 40 WHERE squad_id = ? AND job = 1", (there[1][0],))
        self.host.commit()
        pp.take_back(self.home, HOME_CHAR, checkpoint=check)
        back = self.mates(self.home, HOME_CHAR)
        self.assertEqual({slot: row for slot, row in back.items()}, {1: (home[1], "Kasumi", 1, 31), 2: (home[2], "Gio", 3, 28)})
        # taking back without any copy leaves the squad exactly as it was
        data2, _n = pp.depart(self.home, HOME_CHAR, {})
        pp.take_back(self.home, HOME_CHAR)
        self.assertEqual(self.mates(self.home, HOME_CHAR), back)
        self.assertEqual(self.vars(self.home, HOME_CHAR)[f"SQUAD_AI_{home[1]}"], 21)
        self.assertTrue(data2)

    def test_squad_blocks_that_must_be_refused(self):
        self.squads()
        data, _nonce = pp.depart(self.home, HOME_CHAR, {})
        passport = pp.unpack(data)
        mates = passport["squad"]["squad_mate"]
        twice = dict(passport, squad=dict(passport["squad"], squad_mate={"cols": mates["cols"], "rows": mates["rows"] + [mates["rows"][0]]}))
        with self.assertRaises(pp.PassportError):
            self.arrive(pp.pack(twice))
        other = dict(passport, squad=dict(passport["squad"], squad_mate={"cols": mates["cols"] + ["charid"], "rows": [r + [HOME_CHAR] for r in mates["rows"]]}))
        with self.assertRaises(pp.PassportError):                          # a column this world does not expect (the owner)
            self.arrive(pp.pack(other))
        with self.assertRaises(pp.PassportError):                          # a squad left out of a passport that should have one
            self.arrive(pp.pack(dict(passport, squad=None)))
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM squad_mate")[0][0], 3)       # only the host's own three
        ct.run(self.host, "ALTER TABLE squad_job ADD COLUMN merits INT NOT NULL DEFAULT 0")     # another version of the squad tables
        self.host.commit()
        with self.assertRaises(pp.PassportError):
            self.arrive(data)
        ct.run(self.host, "ALTER TABLE squad_job DROP COLUMN merits")
        self.host.commit()
        named = dict(passport, squad=dict(passport["squad"], squad_mate={"cols": mates["cols"], "rows": [
            [("Bad Name!" if c == "name" else v) for c, v in zip(mates["cols"], mates["rows"][0])]] + mates["rows"][1:]}))
        with self.assertRaises(pp.PassportError):                          # a name the game would never have allowed
            self.arrive(pp.pack(named))
        # rows for a mate that is not in the passport are left out; the rest arrives
        jobs = passport["squad"]["squad_job"]
        stray = [(987654 if c == "squad_id" else v) for c, v in zip(jobs["cols"], jobs["rows"][0])]
        extra = dict(passport, squad=dict(passport["squad"], squad_job={"cols": jobs["cols"], "rows": jobs["rows"] + [stray]}))
        guest = self.arrive(pp.pack(extra))
        self.assertFalse(guest["again"])
        self.assertEqual(len(self.mates(self.host, guest["charid"])), 2)
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM squad_job WHERE squad_id = 987654")[0][0], 0)
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM squad_job WHERE squad_id NOT IN (SELECT id FROM squad_mate)")[0][0], 0)

    # --- what the first co-op build wrote (format 1: squads stayed home) is still understood ---
    def as_first_build(self, data, conn):
        """A passport of today rewritten the way the first co-op build wrote it: no squad, squad settings left home."""
        passport = pp.unpack(data)
        cur = conn.cursor()
        layout = pp.local_layout(cur)
        cur.close()
        conn.rollback()
        variables = passport["tables"]["char_vars"]
        i = variables["cols"].index("varname")
        variables["rows"] = [r for r in variables["rows"] if not r[i].startswith("SQUAD_")]
        passport.pop("squad", None)
        passport["summary"].pop("squad", None)
        passport.update(format=pp.OLD_FORMAT, schema=pp.layout_signature(layout, fmt=pp.OLD_FORMAT))
        return pp.pack(passport)

    def test_a_visit_that_began_with_the_first_build_leaves_the_squad_alone(self):
        home = self.squads()
        before_vars = self.vars(self.home, HOME_CHAR)
        data, _nonce = pp.depart(self.home, HOME_CHAR, {})
        ct.run(self.home, "UPDATE coop_away SET squad = 0 WHERE charid = ?", (HOME_CHAR,))      # as that build recorded the trip
        self.home.commit()
        with self.assertRaises(pp.PassportError):                          # a new visit needs both worlds on today's version
            self.arrive(self.as_first_build(data, self.home))
        guest = self.arrive(data)
        ct.run(self.host, "DELETE FROM squad_job WHERE squad_id IN (SELECT id FROM squad_mate WHERE charid = ?)", (guest["charid"],))
        ct.run(self.host, "DELETE FROM squad_mate WHERE charid = ?", (guest["charid"],))          # (that build brought no squad)
        ct.run(self.host, "DELETE FROM char_vars WHERE charid = ? AND varname LIKE 'SQUAD%'", (guest["charid"],))
        ct.run(self.host, "UPDATE char_stats SET mlvl = 33 WHERE charid = ?", (guest["charid"],))
        self.host.commit()
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        self.assertEqual(pp.unpack(final)["summary"]["squad"], [])
        for passport in (final, self.as_first_build(final, self.host)):     # the host updated meanwhile, or it did not
            result = pp.come_home(self.home, passport, backup_dir=self.tmp)
            self.assertEqual(result["changes"].get("mates"), [])
            self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 33)
            self.assertEqual({slot: row for slot, row in self.mates(self.home, HOME_CHAR).items()},
                             {1: (home[1], "Kasumi", 1, 30), 2: (home[2], "Gio", 3, 28)})
            self.assertEqual(self.vars(self.home, HOME_CHAR), before_vars)
            self.assertEqual(len(self.q(self.home, "SELECT 1 FROM squad_unlock WHERE charid = ?", (HOME_CHAR,))), 2)
            ct.run(self.home, "UPDATE coop_away SET state = 'away' WHERE charid = ?", (HOME_CHAR,))       # (once more, the other way)
            self.home.commit()

    def test_a_first_build_passport_cannot_end_a_visit_the_squad_went_on(self):
        home = self.squads()
        _data, _nonce, guest = self.visit()
        final, _gen = pp.export_guest(self.host, "g1", final=True, save_dir=self.tmp)
        with self.assertRaises(pp.PassportError):
            pp.come_home(self.home, self.as_first_build(final, self.host))
        self.assertEqual(self.q(self.home, "SELECT state FROM coop_away WHERE charid = ?", (HOME_CHAR,)), [("away",)])
        self.assertEqual(sorted(self.mates(self.home, HOME_CHAR)), [1, 2])
        self.assertFalse(pp.come_home(self.home, final)["already"])
        self.assertEqual(self.mates(self.home, HOME_CHAR)[1][0], home[1])
        self.assertTrue(guest)

    def test_a_backup_from_the_first_build_is_restored_without_touching_the_squad(self):
        home = self.squads()
        saved = self.as_first_build(pp.backup_character(self.home, HOME_CHAR), self.home)
        full = pp.unpack(pp.backup_character(self.home, HOME_CHAR))["tables"]["char_vars"]          # (that build's backups held every variable)
        old = pp.unpack(saved)
        old["tables"]["char_vars"] = full
        saved = pp.pack(old)
        ct.run(self.home, "UPDATE char_stats SET mlvl = 1 WHERE charid = ?", (HOME_CHAR,))
        ct.run(self.home, "UPDATE squad_job SET level = 35 WHERE squad_id = ? AND job = 1", (home[1],))
        self.home.commit()
        pp.restore_backup(self.home, saved)
        self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 30)
        self.assertEqual(self.mates(self.home, HOME_CHAR)[1], (home[1], "Kasumi", 1, 35))            # the squad is as it was left
        self.assertEqual(self.vars(self.home, HOME_CHAR)[f"SQUAD_AI_{home[1]}"], 21)

    def test_the_away_table_of_the_first_build_gets_its_new_column(self):
        pp.ensure_tables(self.home)
        ct.run(self.home, "ALTER TABLE coop_away DROP COLUMN squad")
        self.home.commit()
        pp.ensure_tables(self.home)
        pp.ensure_tables(self.home)
        self.assertEqual(self.q(self.home, "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() "
                                           "AND table_name = 'coop_away' AND column_name = 'squad'")[0][0], 1)
        pp.depart(self.home, HOME_CHAR, {})
        self.assertEqual(self.q(self.home, "SELECT squad FROM coop_away WHERE charid = ?", (HOME_CHAR,)), [(1,)])

    # --- the rest ---
    def test_backup_and_restore(self):
        saved = pp.backup_character(self.home, HOME_CHAR)
        ct.run(self.home, "UPDATE char_stats SET mlvl = 1 WHERE charid = ?", (HOME_CHAR,))
        ct.run(self.home, "DELETE FROM char_inventory WHERE charid = ? AND slot > 0", (HOME_CHAR,))
        ct.run(self.home, "DELETE FROM char_vars WHERE charid = ?", (HOME_CHAR,))
        self.home.commit()
        pp.restore_backup(self.home, saved)
        self.assertEqual(self.q(self.home, "SELECT mlvl FROM char_stats WHERE charid = ?", (HOME_CHAR,))[0][0], 30)
        self.assertEqual(self.q(self.home, "SELECT COUNT(*) FROM char_inventory WHERE charid = ?", (HOME_CHAR,))[0][0], 5)
        self.assertEqual(self.q(self.home, "SELECT COUNT(*) FROM char_vars WHERE charid = ?", (HOME_CHAR,))[0][0], 4)
        with self.assertRaises(pp.PassportError):
            pp.restore_backup(self.host, saved)                             # another world

    def test_leaving_a_party_and_things_left_behind(self):
        _data, _nonce, guest = self.visit()
        ct.run(self.host, "INSERT INTO accounts_parties (charid, partyid, partyflag, allianceid) VALUES (?, ?, 4, 0), (?, ?, 0, 0)",
               (guest["charid"], guest["charid"], HOME_CHAR, guest["charid"]))
        ct.run(self.host, "INSERT INTO delivery_box (charid, charname, box, slot, itemid, itemsubid, quantity, extra, senderid, sender, received, sent) "
                          "VALUES (?, 'Visitor', 1, 8, 4112, 0, 3, NULL, 0, 'AH-Jeuno', 0, 0)", (guest["charid"],))
        self.host.commit()
        self.assertEqual(pp.guest_holdings(self.host, guest["charid"]), {"auctions": 0, "delivery": 1})
        pp.remove_guest(self.host, "g1")
        self.assertEqual(self.q(self.host, "SELECT charid, partyflag & 4 FROM accounts_parties"), [(HOME_CHAR, 4)])
        self.assertEqual(self.q(self.host, "SELECT COUNT(*) FROM delivery_box")[0][0], 0)

    def test_world_identity(self):
        a, b = pp.world_identity(self.home, "Hurami's world"), pp.world_identity(self.host)
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(pp.world_identity(self.home)["id"], a["id"])
        self.assertEqual(a["name"], "Hurami's world")
        pp.set_world_name(self.home, "  <b>Vana</b> ")
        self.assertEqual(pp.world_identity(self.home)["name"], "bVanab")


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1], verbosity=1)
