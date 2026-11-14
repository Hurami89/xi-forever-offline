"""Stand-in tests for launcher_personality.py (Squad tab > Personality). Run: python test_personality.py"""
import json, os, shutil, sys, tempfile, unittest
KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)
import launcher_personality as lp


class PersonalityTests(unittest.TestCase):
    def setUp(self):
        self.kit = tempfile.mkdtemp()
        shutil.copytree(os.path.join(KIT, "squad-chat", "examples"), os.path.join(self.kit, "squad-chat", "examples"))

    def tearDown(self):
        shutil.rmtree(self.kit, ignore_errors=True)

    def test_new_sheet_takes_the_game_facts(self):
        s = lp.new_sheet("Aria", 7, "thf", 12)
        self.assertEqual((s["race"], s["sex"], s["pronouns"], s["job"], s["level"]), ("Mithra", "female", "she/her", "THF", 12))
        self.assertEqual(lp.problems(s)[0][:13], "Write at leas")

    def test_save_and_load_keep_a_backup(self):
        s = lp.new_sheet("Aria", 7, "THF", 12)
        s["personality"] = "  Sly   and kind. "
        s["chat_examples"] = ["one", "", "two"]
        s["talkativeness"] = 9
        lp.save_sheet(self.kit, s)
        got = lp.load_sheet(self.kit, "Aria")
        self.assertEqual(got["personality"], "Sly and kind.")
        self.assertEqual(got["chat_examples"], ["one", "two"])
        self.assertEqual(got["talkativeness"], 3.0)
        lp.save_sheet(self.kit, dict(got, personality="Changed."))
        self.assertTrue(os.path.exists(os.path.join(self.kit, "squad-chat", "mates", "aria.json.bak")))

    def test_examples_fill_the_name_and_keep_the_facts(self):
        found = lp.examples(self.kit)
        self.assertGreaterEqual(len(found), 5)
        title, example = found[0]
        s = lp.apply_example(lp.new_sheet("Bram", 8, "WAR", 30), example)
        self.assertEqual((s["name"], s["race"], s["job"]), ("Bram", "Galka", "WAR"))
        self.assertIn("Bram", s["backstory"])
        self.assertNotIn("{name}", json.dumps(s))
        self.assertEqual(lp.problems(s), [])

    def test_ai_request_new_then_rewrite(self):
        self.assertEqual(lp.request_ai_sheet(self.kit, "Cid", 1, "pld", 5, "Bastok"), "NEWMATE\tCid\t1\tPLD\t5\tBastok")
        lp.save_sheet(self.kit, dict(lp.new_sheet("Cid", 1, "PLD", 5), personality="x"))
        self.assertEqual(lp.request_ai_sheet(self.kit, "Cid", 1, "PLD", 5), "LORE\tCid")
        with open(os.path.join(self.kit, "squad-chat", "in.txt"), encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
