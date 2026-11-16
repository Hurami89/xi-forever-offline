"""Stand-in tests for launcher_game.py (no Windows needed): python test_game.py [kit folder]"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, sys.argv.pop(1) if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", ".."))
import launcher_game as lg   # noqa: E402

RETAIL_V = r"C:\Program Files (x86)\PlayOnline\SquareEnix\PlayOnlineViewer"
RETAIL_F = r"C:\Program Files (x86)\PlayOnline\SquareEnix\FINAL FANTASY XI"


class FakeReg:
    def __init__(self, values=None):
        self.v = dict(values or {})

    def get(self, path, name):
        return self.v.get((path, name))

    def set(self, path, name, value):
        self.v[(path, name)] = value

    def delete(self, path, name):
        self.v.pop((path, name), None)


def retail():
    folder = r"SOFTWARE\PlayOnlineUS\InstallFolder"
    return FakeReg({(folder, "0001"): RETAIL_F, (folder, "1000"): RETAIL_V,
                    (rf"SOFTWARE\Classes\CLSID\{lg.POLCORE_CLSID['US']}\InprocServer32", ""): RETAIL_V + r"\polcore.dll",
                    (rf"SOFTWARE\Classes\CLSID\{lg.FFXI_CLSID}\InprocServer32", ""): RETAIL_F + r"\FFXi.dll"})


class GameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kit = self.tmp.name
        self.copy = lg.game_paths(os.path.join(self.kit, "Game"))
        self.cfg = {"game_copy": True, "pol_lang": "US", "pol_dir": self.copy["viewer"], "ffxi_client_dir": self.copy["ffxi"]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_entries_keep_file_names(self):
        reg = retail()
        want = dict(((p, n), v) for p, n, v in lg.entries("US", r"D:\G\V", r"D:\G\F", reg))
        self.assertEqual(want[(rf"SOFTWARE\Classes\CLSID\{lg.FFXI_CLSID}\InprocServer32", "")], r"D:\G\F\FFXi.dll")
        self.assertEqual(want[(r"SOFTWARE\PlayOnlineUS\InstallFolder", "1000")], r"D:\G\V")

    def _touch(self, *parts):
        path = os.path.join(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        return path

    def _polcore(self, reg):
        key = (rf"SOFTWARE\Classes\CLSID\{lg.POLCORE_CLSID['US']}\InprocServer32", "")
        return dict(((p, n), v) for p, n, v in lg.entries("US", self.copy["viewer"], self.copy["ffxi"], reg))[key]

    def test_polcore_in_viewer_com_not_patchfiles(self):
        # newer PlayOnline: polcore.dll lives in viewer\com, with an update copy under patchfiles (shujimi, 2026-11-16)
        v = self.copy["viewer"]
        self._touch(v, "patchfiles", "PlayOnlineViewer", "viewer", "com", "polcore.dll")
        live = self._touch(v, "viewer", "com", "polcore.dll")
        self.assertEqual(os.path.normpath(self._polcore(retail()).replace("\\", os.sep)), os.path.normpath(live))

    def test_polcore_keeps_registered_subfolder(self):
        reg = retail()
        reg.set(rf"SOFTWARE\Classes\CLSID\{lg.POLCORE_CLSID['US']}\InprocServer32", "", RETAIL_V + r"\viewer\com\polcore.dll")
        live = self._touch(self.copy["viewer"], "viewer", "com", "polcore.dll")
        self.assertEqual(os.path.normpath(self._polcore(reg).replace("\\", os.sep)), os.path.normpath(live))

    def test_polcore_at_top_still_works(self):
        live = self._touch(self.copy["viewer"], "polcore.dll")
        self.assertEqual(os.path.normpath(self._polcore(retail()).replace("\\", os.sep)), os.path.normpath(live))

    def test_other_server_install_restored_exactly(self):
        # a player with another private server: their own registry values come back unchanged after play
        reg = retail()
        reg.set(rf"SOFTWARE\Classes\CLSID\{lg.POLCORE_CLSID['US']}\InprocServer32", "", r"E:\Horizon\PlayOnlineViewer\viewer\com\polcore.dll")
        self._touch(self.copy["viewer"], "viewer", "com", "polcore.dll")
        before = dict(reg.v)
        state = os.path.join(self.kit, lg.STATE_FILE)
        with open(state, "w") as h:
            json.dump({"lang": "US", "viewer": self.copy["viewer"], "ffxi": self.copy["ffxi"]}, h)
        running = iter([True, False])
        lg.hold(state, reg, lambda: next(running), sleep=lambda s: None)
        self.assertEqual(reg.v, before)

    def test_no_switch_without_copy_or_when_already_pointing(self):
        reg = retail()
        self.assertFalse(lg.needs_switch({"ffxi_client_dir": RETAIL_F}, reg))
        self.assertTrue(lg.needs_switch(self.cfg, reg))
        for p, n, v in lg.entries("US", self.copy["viewer"], self.copy["ffxi"], reg):
            reg.set(p, n, v)
        self.assertFalse(lg.needs_switch(self.cfg, reg))

    def test_hold_switches_then_restores(self):
        reg, before = retail(), dict(retail().v)
        state = os.path.join(self.kit, lg.STATE_FILE)
        with open(state, "w") as h:
            json.dump({"lang": "US", "viewer": self.copy["viewer"], "ffxi": self.copy["ffxi"]}, h)
        seen = []
        running = iter([False, True, True, False])      # not yet started, two windows of play, closed

        def is_running():
            seen.append(lg.needs_switch(self.cfg, reg))  # while held, the registry points at the copy
            return next(running)
        lg.hold(state, reg, is_running, sleep=lambda s: None)
        self.assertEqual(seen[:3], [False, False, False])
        self.assertEqual(reg.v, before)
        self.assertFalse(os.path.exists(state))

    def test_hold_restores_a_value_that_was_missing(self):
        reg = retail()
        reg.delete(rf"SOFTWARE\Classes\CLSID\{lg.FFXI_CLSID}\InprocServer32", "")
        before = dict(reg.v)
        state = os.path.join(self.kit, lg.STATE_FILE)
        with open(state, "w") as h:
            json.dump({"lang": "US", "viewer": "V", "ffxi": "F"}, h)
        lg.hold(state, reg, lambda: False, sleep=lambda s: None, start_wait=2)
        self.assertEqual(reg.v, before)

    def test_recover_after_crash(self):
        reg, before = retail(), dict(retail().v)
        state = os.path.join(self.kit, lg.STATE_FILE)
        originals = [(p, n, reg.get(p, n)) for p, n, _v in lg.entries("US", "V", "F", reg)]
        for p, n, v in lg.entries("US", "V", "F", reg):
            reg.set(p, n, v)
        with open(state, "w") as h:
            json.dump({"lang": "US", "viewer": "V", "ffxi": "F", "originals": originals, "applied": True}, h)
        self.assertTrue(lg.pending_recovery(self.kit))
        self.assertTrue(lg.recover(state, reg))
        self.assertEqual(reg.v, before)
        self.assertFalse(lg.pending_recovery(self.kit))

    def test_start_switch_runs_helper_and_waits(self):
        reg = retail()
        calls = []

        def run_elevated(args):          # stands in for the elevated helper: it marks the state as applied
            calls.append(args[0])
            with open(args[1]) as h:
                s = json.load(h)
            s["applied"] = True
            with open(args[1], "w") as h:
                json.dump(s, h)
        self.assertTrue(lg.start_switch(self.kit, self.cfg, run_elevated, reg=reg, sleep=lambda s: None))
        self.assertEqual(calls, ["hold"])
        self.assertFalse(lg.start_switch(self.kit, {"ffxi_client_dir": RETAIL_F}, run_elevated, reg=reg))

    def test_start_switch_refused(self):
        with self.assertRaises(RuntimeError):
            lg.start_switch(self.kit, self.cfg, lambda a: None, reg=retail(), sleep=lambda s: None, timeout=1)
        self.assertFalse(lg.pending_recovery(self.kit))

    def test_copy_install_and_resume(self):
        src = os.path.join(self.kit, "src", "SquareEnix")
        for sub, name in (("PlayOnlineViewer", "polcore.dll"), ("FINAL FANTASY XI", "FFXiMain.dll"),
                          (os.path.join("FINAL FANTASY XI", "ROM", "0", "0"), "0.DAT")):
            os.makedirs(os.path.join(src, sub), exist_ok=True)
            with open(os.path.join(src, sub, name), "wb") as h:
                h.write(b"x" * 1000)
        logs = []
        paths = lg.copy_install(os.path.join(src, "FINAL FANTASY XI"), os.path.join(src, "PlayOnlineViewer"),
                                os.path.join(self.kit, "Game"), log=logs.append, free=10 ** 12)
        self.assertTrue(os.path.isfile(os.path.join(paths["ffxi"], "ROM", "0", "0", "0.DAT")))
        self.assertTrue(os.path.isfile(os.path.join(paths["viewer"], "polcore.dll")))
        logs.clear()
        lg.copy_install(os.path.join(src, "FINAL FANTASY XI"), os.path.join(src, "PlayOnlineViewer"),
                        os.path.join(self.kit, "Game"), log=logs.append, free=10 ** 12)
        self.assertIn("Copying 0 game files", logs[0])
        with self.assertRaises(RuntimeError):
            lg.copy_install(os.path.join(src, "FINAL FANTASY XI"), os.path.join(src, "PlayOnlineViewer"),
                            os.path.join(self.kit, "Game2"), free=1000)

    def test_detect_lang(self):
        self.assertEqual(lg.detect_lang(RETAIL_F, reg=retail()), "US")
        eu = FakeReg({(r"SOFTWARE\PlayOnlineEU\InstallFolder", "0001"): RETAIL_F})
        self.assertEqual(lg.detect_lang(RETAIL_F, reg=eu), "EU")

    def test_download_official_until_last_part(self):
        import urllib.error
        got = []

        def download(url, path, log=None, context=None):
            number = int(url.rsplit(".part", 1)[1].split(".")[0])
            if number > 5:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            got.append(os.path.basename(path))
            return path
        files = lg.download_official(self.kit, log=lambda m: None, download=download)
        self.assertEqual(got, ["FFXIFullSetup_US.part1.exe"] + [f"FFXIFullSetup_US.part{n}.rar" for n in range(2, 6)])
        self.assertEqual(len(files), 5)

    def test_download_official_missing_part_is_an_error(self):
        import urllib.error

        def download(url, path, log=None, context=None):
            if ".part3." in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            return path
        with self.assertRaises(urllib.error.HTTPError):
            lg.download_official(self.kit, log=lambda m: None, download=download)

    def test_run_official_installer_unpacks_then_runs_setup(self):
        ran = []
        unpacked = os.path.join(lg.official_folder(self.kit), "FFXIFullSetup_US")

        class Proc:
            returncode = 0

            def __init__(self, cmd, cwd=None):
                ran.append(os.path.basename(cmd[0]))
                if cmd[0].endswith(".exe") and "part1" in cmd[0]:     # the unpacker makes the setup folder
                    os.makedirs(unpacked, exist_ok=True)
                    open(os.path.join(unpacked, "FFXISetup.exe"), "w").close()

            def wait(self):
                return 0
        part1 = os.path.join(lg.official_folder(self.kit), "FFXIFullSetup_US.part1.exe")
        lg.run_official_installer(self.kit, [part1], log=lambda m: None, popen=Proc)
        self.assertEqual(ran, ["FFXIFullSetup_US.part1.exe", "FFXISetup.exe"])
        ran.clear()
        lg.run_official_installer(self.kit, [part1], log=lambda m: None, popen=Proc)   # already unpacked: setup only
        self.assertEqual(ran, ["FFXISetup.exe"])

    def test_find_viewer_sibling(self):
        ffxi = os.path.join(self.kit, "SquareEnix", "FINAL FANTASY XI")
        os.makedirs(ffxi)
        os.makedirs(os.path.join(self.kit, "SquareEnix", "PlayOnlineViewer"))
        self.assertEqual(lg.find_viewer(ffxi, reg=FakeReg()), os.path.join(self.kit, "SquareEnix", "PlayOnlineViewer"))


    def test_version_check_trick(self):
        ffxi = os.path.join(self.kit, "ffxi")
        os.makedirs(ffxi)
        self.assertEqual(lg.finish_version_check(ffxi), "unchanged")
        table = os.path.join(ffxi, lg.VTABLE)
        with open(table, "w") as f:
            f.write("old")
        self.assertTrue(lg.force_version_check(ffxi))
        self.assertFalse(os.path.exists(table))
        self.assertTrue(lg.force_version_check(ffxi))          # pressing it twice is fine
        self.assertEqual(lg.finish_version_check(ffxi), "restored")   # PlayOnline didn't rebuild it: ours goes back
        with open(table) as f:
            self.assertEqual(f.read(), "old")
        lg.force_version_check(ffxi)
        with open(table, "w") as f:                            # PlayOnline rebuilt it
            f.write("new")
        self.assertEqual(lg.finish_version_check(ffxi), "updated")
        self.assertFalse(os.path.exists(os.path.join(ffxi, lg.VTABLE_BACKUP)))
        with open(table) as f:
            self.assertEqual(f.read(), "new")

    def test_open_playonline(self):
        viewer = os.path.join(self.kit, "PlayOnlineViewer")
        ffxi = os.path.join(self.kit, "FINAL FANTASY XI")
        os.makedirs(viewer)
        os.makedirs(ffxi)
        cfg = {"ffxi_client_dir": ffxi}
        with self.assertRaises(RuntimeError):
            lg.open_playonline(cfg, start=lambda p: None, reg=FakeReg())
        open(os.path.join(viewer, "pol.exe"), "w").close()
        started = []
        self.assertEqual(lg.open_playonline(cfg, start=started.append, reg=FakeReg()), os.path.join(viewer, "pol.exe"))
        self.assertEqual(started, [os.path.join(viewer, "pol.exe")])
        other = os.path.join(self.kit, "copy-viewer")          # a game copy uses its own viewer folder
        os.makedirs(other)
        open(os.path.join(other, "pol.exe"), "w").close()
        self.assertEqual(lg.pol_exe({"ffxi_client_dir": ffxi, "pol_dir": other}, reg=FakeReg()), os.path.join(other, "pol.exe"))


if __name__ == "__main__":
    unittest.main()
