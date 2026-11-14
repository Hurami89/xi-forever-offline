"""Tests for the launcher side of the squad greetings: defaults, per-mate overrides, and the generated Lua.

Run with: python test_greetings_launcher.py
Nothing here touches the real squad-data or server files.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import launcher_squad as sq  # noqa: E402


class GreetingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.defaults = base / "squad_greetings_default.json"
        self.user = base / "squad_greetings_user.json"
        self.lua = base / "squad_greetings_data.lua"
        self.defaults.write_text(json.dumps({
            "Kasumi": {"spawn": ["Ready.", "So this is {zone}.", "Ready as {job}."], "levelup": ["Level {level}."]},
            "Kyo": {"spawn": ["Quite."], "death": ["How undignified."]},
        }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_built_in_lines_are_used_until_something_is_edited(self):
        data = sq.greeting_data(self.defaults, self.user)
        self.assertEqual(data["Kasumi"]["spawn"], ["Ready.", "So this is {zone}.", "Ready as {job}."])
        self.assertEqual(data["Kasumi"]["levelup"], ["Level {level}."])
        self.assertEqual(data["Kyo"]["death"], ["How undignified."])
        self.assertEqual(data["Kyo"]["weaponskill"], [])

    def test_a_mate_edit_replaces_only_that_moment(self):
        self.user.write_text(json.dumps({"Kasumi": {"spawn": ["Mine now."]}}), encoding="utf-8")
        data = sq.greeting_data(self.defaults, self.user)
        self.assertEqual(data["Kasumi"]["spawn"], ["Mine now."])
        self.assertEqual(data["Kasumi"]["levelup"], ["Level {level}."], "the untouched moment keeps its built-in line")
        self.assertEqual(data["Kyo"]["spawn"], ["Quite."], "another mate is untouched")

    def test_clearing_a_moment_means_the_voice_lines(self):
        self.user.write_text(json.dumps({"Kasumi": {"spawn": []}}), encoding="utf-8")
        data = sq.greeting_data(self.defaults, self.user)
        self.assertEqual(data["Kasumi"]["spawn"], [],
                         "an empty list is an explicit choice: no per-mate greetings, so the voice pool is used")

    def test_save_cleans_the_lines(self):
        sq.save_greetings(self.user, "Kasumi", {"spawn": ["  Ready.  ", "", "two\nlines", "x" * 200]})
        saved = json.loads(self.user.read_text(encoding="utf-8"))
        self.assertEqual(saved["Kasumi"]["spawn"], ["Ready.", "two lines", "x" * 160])
        self.assertEqual(saved["Kasumi"]["death"], [])

    def test_save_keeps_the_other_mates_and_moments(self):
        sq.save_greetings(self.user, "Kyo", {"spawn": ["Hm."]})
        sq.save_greetings(self.user, "Kasumi", {"spawn": ["Ready."], "levelup": ["Level {level}."]})
        data = sq.greeting_data(self.defaults, self.user)
        self.assertEqual(data["Kyo"]["spawn"], ["Hm."])
        self.assertEqual(data["Kasumi"]["levelup"], ["Level {level}."])
        self.assertEqual(data["Kasumi"]["death"], [], "not edited, and there was no built-in line")

    def test_reset_drops_the_edit_and_the_built_in_lines_return(self):
        sq.save_greetings(self.user, "Kasumi", {"spawn": ["Mine."]})
        sq.clear_greetings(self.user, "Kasumi")
        self.assertEqual(sq.greeting_data(self.defaults, self.user)["Kasumi"]["spawn"], ["Ready.", "So this is {zone}.", "Ready as {job}."])
        self.assertNotIn("Kasumi", json.loads(self.user.read_text(encoding="utf-8")))

    def test_rename_keeps_a_mate_own_lines(self):
        sq.save_greetings(self.user, "Kasumi", {"spawn": ["Mine."]})
        sq.rename_greetings(self.user, "Kasumi", "Kas")
        data = sq.greeting_data(self.defaults, self.user)
        self.assertEqual(data["Kas"]["spawn"], ["Mine."])
        self.assertNotIn("Kasumi", json.loads(self.user.read_text(encoding="utf-8")),
                         "the edit is not left under the old name")

    def test_lua_output_has_a_marker_quotes_lines_and_skips_empty_moments(self):
        sq.save_greetings(self.user, "Kyo", {"spawn": ["It's fine.", "Back \\ slash."], "death": ["Ouch."]})
        data = sq.greeting_data(self.defaults, self.user)
        clean = sq.write_greetings_lua(self.lua, {**data, "Nobody": {"spawn": []}})
        text = self.lua.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(sq.GREETINGS_MARKER))
        self.assertIn("Kyo = {", text)
        self.assertIn("spawn = {", text)
        self.assertIn("It\\'s fine.", text)
        self.assertIn("Back \\\\ slash.", text)
        self.assertNotIn("weaponskill", text, "moments with no lines are left out so the voice lines are used")
        self.assertEqual(clean["Kyo"]["spawn"], ["It's fine.", "Back \\ slash."])
        self.assertNotIn("Nobody", clean, "a mate with no lines of their own is left out")


if __name__ == "__main__":
    unittest.main(verbosity=2)
