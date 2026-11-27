"""The launcher puts the in-game Ventures window into Ashita and switches it on once:
    python3 dev/ventures/test_venture_install.py
"""
import os
import sys
import tempfile
import time
import unittest

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, KIT)
import launcher_setup as S  # noqa: E402


def write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


class Install(unittest.TestCase):
    def setUp(self):
        self.kit, self.ashita = tempfile.mkdtemp(), tempfile.mkdtemp()
        write(os.path.join(self.kit, "addons-src", "venture", "venture.lua"), "-- venture")
        write(os.path.join(self.kit, "addons-src", "venture", "assets", "bg", "ronfaure.png"), "picture one")
        write(os.path.join(self.kit, "addons-src", "venture", "venture.lua.before-x"), "old")
        write(os.path.join(self.ashita, "config", "boot", "phoenixsolo.ini"), "[ashita.boot]\nscript      = default.txt\n")
        write(os.path.join(self.ashita, "scripts", "default.txt"), "/load addons\n/addon load servermenu\n")
        self.said = []

    def script(self):
        names = [n for n in os.listdir(os.path.join(self.ashita, "scripts")) if n != "default.txt"]
        return read(os.path.join(self.ashita, "scripts", names[0])) if names else ""

    def test_it_is_one_of_the_kits_own_addons(self):
        self.assertIn("venture", S.OWN_ADDONS)
        with open(os.path.join(KIT, ".gitignore"), encoding="utf-8") as f:
            self.assertIn("!/addons-src/venture/", f.read().split())

    def test_copied_and_unchanged_pictures_left_alone(self):
        S.install_own_addons(self.kit, self.ashita)
        dst = os.path.join(self.ashita, "addons", "venture")
        self.assertEqual(read(os.path.join(dst, "venture.lua")), "-- venture")
        self.assertFalse(os.path.exists(os.path.join(dst, "venture.lua.before-x")))
        pic = os.path.join(dst, "assets", "bg", "ronfaure.png")
        self.assertEqual(read(pic), "picture one")
        # the same size and time: not written again (a mark put into the copy survives the next PLAY)
        stamp = os.stat(pic)
        write(pic, "PICTURE ONE")
        os.utime(pic, (stamp.st_atime, stamp.st_mtime))
        S.install_own_addons(self.kit, self.ashita)
        self.assertEqual(read(pic), "PICTURE ONE")
        # an update brings a new picture of the same size: copied
        src = os.path.join(self.kit, "addons-src", "venture", "assets", "bg", "ronfaure.png")
        write(src, "picture two")
        os.utime(src, (time.time() + 60, time.time() + 60))
        S.install_own_addons(self.kit, self.ashita)
        self.assertEqual(read(pic), "picture two")

    def test_switched_on_once(self):
        self.assertFalse(S.enable_venture(self.kit, self.ashita, "phoenixsolo.ini", log=self.said.append), "nothing to switch on before it is copied")
        S.install_own_addons(self.kit, self.ashita)
        self.assertTrue(S.enable_venture(self.kit, self.ashita, "phoenixsolo.ini", log=self.said.append))
        self.assertIn("/addon load venture", self.script())
        self.assertIn("/addon load servermenu", self.script(), "what was on stays on")
        self.assertTrue(any("/venture" in line for line in self.said))
        self.assertTrue(os.path.exists(os.path.join(self.ashita, "config", "addons", "venture", "enabled-once.txt")))
        # the player switches it off: the next PLAY leaves it off
        import launcher_core as core
        core.ScriptManager(self.ashita, "phoenixsolo.ini").set("addon", "venture", False)
        self.assertFalse(S.enable_venture(self.kit, self.ashita, "phoenixsolo.ini", log=self.said.append))
        self.assertNotIn("/addon load venture", self.script())

    def test_a_kit_without_the_window(self):
        os.remove(os.path.join(self.kit, "addons-src", "venture", "venture.lua"))
        self.assertFalse(S.enable_venture(self.kit, self.ashita, "phoenixsolo.ini", log=self.said.append))


if __name__ == "__main__":
    unittest.main(verbosity=1)
