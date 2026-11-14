"""Item icons for the launcher.

The pictures are the same public 32x32 item icons the TitanXI addons use
(static.ffxiah.com/images/icon/<item id>.png). They are cached under
assets/item-icons so a mate's gear shows immediately on later launches.

The launcher never waits for the network to draw a page: a missing icon is
shown as an empty tile, and the picture appears when its download finishes.
"""
import os
import queue
import threading
import urllib.request

ICON_SIZE = 24
ICON_URLS = (
    "http://static.ffxiah.com/images/icon/{}.png",
    "https://static.ffxiah.com/images/icon/{}.png",
)
MAX_BYTES = 64 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def cache_dir(assets_root):
    return os.path.join(assets_root, "item-icons")


def icon_path(assets_root, item_id):
    """Where one item's cached picture lives. Bad ids are refused, not turned into a path."""
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return None
    if item_id <= 0:
        return None
    return os.path.join(cache_dir(assets_root), str(item_id) + ".png")


def looks_like_png(data):
    return bool(data) and len(data) <= MAX_BYTES and data.startswith(PNG_MAGIC)


def fetch_icon(item_id, path, timeout=6):
    """Downloads one icon to path. Returns True on success. Never raises."""
    if not path:
        return False
    target = path
    os.makedirs(os.path.dirname(target), exist_ok=True)
    for template in ICON_URLS:
        try:
            request = urllib.request.Request(template.format(item_id), headers={"User-Agent": "FFXI-Solo-Launcher"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if getattr(response, "status", 200) != 200:
                    continue
                data = response.read(MAX_BYTES + 1)
            if not looks_like_png(data):
                continue
            temp = target + ".tmp"
            with open(temp, "wb") as handle:
                handle.write(data)
            os.replace(temp, target)
            return True
        except Exception:
            continue
    return False


class ItemIcons:
    """Loads and downloads item pictures for one Tk widget.

    get(item_id, callback) returns a Tk picture when it is already on disk, and
    otherwise returns None and calls callback(picture or None) later on the Tk
    thread. Downloads are limited to one per item and run in the background.
    """

    def __init__(self, widget, assets_root, size=ICON_SIZE, interval=80):
        self.widget = widget
        self.assets_root = assets_root
        self.size = int(size)
        self.interval = int(interval)
        self.pictures = {}
        self.failed = set()
        self.pending = set()
        self.waiting = {}
        self.done = queue.Queue()
        self.closed = False
        self._after = None
        try:
            self._after = widget.after(self.interval, self._drain)
        except Exception:
            self._after = None

    def get(self, item_id, callback=None):
        key = self._key(item_id)
        if key is None:
            return None
        picture = self.pictures.get(key)
        if picture is not None:
            return picture
        if key in self.failed:
            return None
        path = icon_path(self.assets_root, key)
        if path and os.path.isfile(path):
            picture = self._load(path)
            if picture is not None:
                self.pictures[key] = picture
                return picture
            try:
                os.remove(path)               # a half-written or corrupt cache file is fetched again
            except OSError:
                pass
        if callback is not None:
            self.waiting.setdefault(key, []).append(callback)
        if path and key not in self.pending:
            self.pending.add(key)
            threading.Thread(target=self._fetch, args=(key, path), daemon=True).start()
        return None

    def close(self):
        self.closed = True
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        self.waiting.clear()

    def _key(self, item_id):
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return None
        return item_id if item_id > 0 else None

    def _load(self, path):
        """A Tk picture scaled to the tile size. Pillow keeps the pixel art sharp; without it, use a whole-number shrink."""
        try:
            from PIL import Image, ImageTk
        except ImportError:
            Image = ImageTk = None
        try:
            if ImageTk is not None:
                image = Image.open(path).convert("RGBA")
                if image.size != (self.size, self.size):
                    image = image.resize((self.size, self.size), Image.LANCZOS)
                return ImageTk.PhotoImage(image)
            import tkinter as tk
            picture = tk.PhotoImage(file=path)
            if picture.width() > self.size:
                factor = max(2, int(round(picture.width() / float(self.size))))
                picture = picture.subsample(factor, factor)
            return picture
        except Exception:
            return None

    def _fetch(self, key, path):
        try:
            ok = fetch_icon(key, path)
        except Exception:
            ok = False
        self.done.put((key, path if ok else None))

    def _drain(self):
        if self.closed:
            return
        while True:
            try:
                key, path = self.done.get_nowait()
            except queue.Empty:
                break
            self.pending.discard(key)
            picture = self._load(path) if path else None
            if picture is not None:
                self.pictures[key] = picture
            else:
                self.failed.add(key)
            for callback in self.waiting.pop(key, ()):
                try:
                    callback(picture)
                except Exception:
                    pass
        try:
            self._after = self.widget.after(self.interval, self._drain)
        except Exception:
            self._after = None
