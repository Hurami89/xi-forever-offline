"""Tests for the launcher's item icon cache.

Run with: python test_item_icons.py
Nothing here downloads from the real site or needs a game window.
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import launcher_icons as icons  # noqa: E402

PNG = icons.PNG_MAGIC + b"\x00" * 32


class FakeResponse(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class IconCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.assets = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bad_item_ids_do_not_become_paths(self):
        self.assertIsNone(icons.icon_path(self.assets, 0))
        self.assertIsNone(icons.icon_path(self.assets, -3))
        self.assertIsNone(icons.icon_path(self.assets, "onion_sword"))
        self.assertEqual(icons.cache_dir(self.assets), str(self.assets / "item-icons"))

    def test_only_png_payloads_are_accepted(self):
        self.assertTrue(icons.looks_like_png(PNG))
        self.assertFalse(icons.looks_like_png(b"<html>not found</html>"))
        self.assertFalse(icons.looks_like_png(b""))
        self.assertFalse(icons.looks_like_png(icons.PNG_MAGIC + b"x" * icons.MAX_BYTES))

    def test_a_good_icon_is_written_once(self):
        target = icons.icon_path(self.assets, 16482)
        with mock.patch.object(icons.urllib.request, "urlopen", return_value=FakeResponse(PNG)) as open_url:
            self.assertTrue(icons.fetch_icon(16482, target))
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(Path(target).read_bytes(), PNG)

    def test_the_https_url_is_tried_when_http_fails(self):
        target = icons.icon_path(self.assets, 16482)
        with mock.patch.object(icons.urllib.request, "urlopen", side_effect=[OSError("no http"), FakeResponse(PNG)]) as open_url:
            self.assertTrue(icons.fetch_icon(16482, target))
        self.assertEqual(open_url.call_count, 2)

    def test_bad_or_missing_icons_leave_no_file_behind(self):
        target = icons.icon_path(self.assets, 16482)
        with mock.patch.object(icons.urllib.request, "urlopen", return_value=FakeResponse(b"<html>404</html>")):
            self.assertFalse(icons.fetch_icon(16482, target))
        self.assertFalse(os.path.exists(target))
        with mock.patch.object(icons.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertFalse(icons.fetch_icon(16482, target))
        self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main(verbosity=2)
