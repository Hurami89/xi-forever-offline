"""Tests for installer/xifo_setup.py (no network, no window). Run: python dev/installer-tests/test_xifo_setup.py"""
import hashlib
import io
import os
import sys
import tempfile
import unittest
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KIT, "installer"))
import xifo_setup as S  # noqa: E402


def kit_zip(extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("XI Forever Offline/", "")
        z.writestr("XI Forever Offline/XI Forever Offline.exe", b"MZ")
        z.writestr("XI Forever Offline/assets/ui/icon.png", b"png")
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Setup(unittest.TestCase):
    def test_sums(self):
        h = "a" * 64
        self.assertEqual(S.published_sums(f"{h}  xi-forever-offline-v0.3.14-win64.zip\nnot a line\n"), {h})

    def test_install_unpacks_without_the_top_folder(self):
        data = kit_zip()
        sums = hashlib.sha256(data).hexdigest() + "  xi-forever-offline-v9-win64.zip\n"
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "XIForeverOffline")
            seen = []
            S.install(target, seen.append, lambda f, t=None: None, sums_text=sums, opener=lambda u: Response(data))
            self.assertTrue(os.path.isfile(os.path.join(target, "XI Forever Offline.exe")))
            self.assertTrue(os.path.isfile(os.path.join(target, "assets", "ui", "icon.png")))
            self.assertFalse(os.path.exists(os.path.join(target, "XI Forever Offline")))
            self.assertFalse(os.path.exists(os.path.join(target, "_setup_download.zip")), "the download is removed")

    def test_wrong_checksum_stops(self):
        data = kit_zip()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                S.install(os.path.join(d, "x"), print, lambda f, t=None: None, sums_text="b" * 64 + "  other.zip",
                          opener=lambda u: Response(data))
            self.assertFalse(os.path.exists(os.path.join(d, "x", "XI Forever Offline.exe")))

    def test_no_writing_outside_the_folder(self):
        data = kit_zip({"XI Forever Offline/../../evil.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                S.install(os.path.join(d, "x"), print, lambda f, t=None: None, sums_text="", opener=lambda u: Response(data))
            self.assertFalse(os.path.exists(os.path.join(d, "evil.txt")))

    def test_folder_checks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(S.folder_problem(os.path.join(d, "new")))
            busy = os.path.join(d, "busy")
            os.makedirs(busy)
            open(os.path.join(busy, "photo.jpg"), "w").close()
            self.assertIn("other files", S.folder_problem(busy))
            old = os.environ.get("ProgramFiles")
            os.environ["ProgramFiles"] = d
            try:
                self.assertIn("protects", S.folder_problem(os.path.join(d, "XIFO")))
            finally:
                if old is None:
                    os.environ.pop("ProgramFiles")
                else:
                    os.environ["ProgramFiles"] = old


if __name__ == "__main__":
    unittest.main()
