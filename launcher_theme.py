"""Limited-time looks for the launcher: its colours, the tint of its painted buttons and an opening theme.

Everything is a dated file in assets\\press, named like the limited-time banners (name__until-YEAR-MONTH-DAY):
    vaporwave__until-2026-12-02.json    the look: colours for the launcher's palette, and its own buttons ("art": a folder of pictures
                                        that stand in for the ones in assets\\ui, name for name; or a tint for the usual ones)
    theme__until-2026-12-02.mp3         the opening theme: played once when the launcher opens (.mp3 or .wav); a MUSIC switch sits on the banner
Up to and including the date in the name they are used; the day after, the launcher has its own look again and is silent, by itself.
config.json:  "limited_look": false  turns the look and the music off on this PC;  "theme_music": false  is the MUSIC switch.

The three files that define the launcher's colours (launcher_gui.pyw, launcher_widgets.py, launcher_coop_gui.py) each call colours()
right after their own, and launcher_gui's main() calls start(app). Nothing in here can stop the launcher: any problem at all means the
usual look and no sound."""
import atexit
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk

HERE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))  # the kit folder
PRESS = os.path.join(HERE, "assets", "press")
UNTIL_TAG = "__until-"
TINTED = ("ui", "buttons")       # the folders of assets whose pictures a look may replace or tint
BUTTON_KINDS = {"play": "play", "stop": "stop", "dual": "dualbox"}     # assets\\buttons\\<kind>\\ holds variants of these assets\\ui pictures
SOUNDS = (".mp3", ".wav")
VOLUME = 0.55


def today():
    """Today on this PC, written 2026-12-02 (a function of its own so the tests can pick the day)."""
    return time.strftime("%Y-%m-%d")


def until(name):
    """The last day a dated file is used: the date after __until- in its name. "" when it has none, "0" (over) when it cannot be read."""
    low = name.lower()
    cut = low.find(UNTIL_TAG)
    if cut < 0:
        return ""
    day = low[cut + len(UNTIL_TAG):cut + len(UNTIL_TAG) + 10]
    return day if len(day) == 10 and day[4] == "-" and day[7] == "-" and (day[:4] + day[5:7] + day[8:]).isdigit() else "0"


def dated(endings):
    """The files in assets\\press with one of these endings whose date has not passed, by name (full paths)."""
    try:
        names = sorted(n for n in os.listdir(PRESS) if n.lower().endswith(endings) and until(n) >= today())
    except OSError:
        return []
    return [os.path.join(PRESS, n) for n in names]


def config():
    try:
        with open(os.path.join(HERE, "config.json"), encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(key, value):
    """Changes one value in config.json and keeps the rest (None takes the key out), the way the launcher itself does."""
    path = os.path.join(HERE, "config.json")
    with open(path, encoding="utf-8-sig") as handle:
        cfg = json.load(handle)
    if value is None:
        cfg.pop(key, None)
    else:
        cfg[key] = value
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(cfg, handle, indent=2)


def is_colour(value):
    return isinstance(value, str) and len(value) == 7 and value[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in value[1:])


def load_look():
    """The look in date today: the first dated .json in assets\\press that holds a "colours" table. None when there is none (or it is switched off)."""
    if config().get("limited_look") is False:
        return None
    for path in dated((".json",)):
        try:
            with open(path, encoding="utf-8-sig") as handle:
                look = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(look, dict) and isinstance(look.get("colours"), dict):
            look["colours"] = {k: v.lower() for k, v in look["colours"].items() if is_colour(v)}
            look["file"] = os.path.basename(path)
            return look
    return None


def colours(names):
    """The look's colours for the names this file defines (BG, PANEL, GOLD ...): {} when no look is in date, so nothing changes."""
    if LOOK is None:
        return {}
    return {key: value for key, value in LOOK["colours"].items() if key in names}


# ---------- the tint of the painted buttons ----------
def _luts(ramp):
    """A ramp [[0, "#140630"], [0.5, "#ff46be"], [1, "#ffffff"]] as three 256-entry tables: grey level -> red, green, blue."""
    stops = sorted((float(p), tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))) for p, c in ramp if is_colour(c))
    if len(stops) < 2:
        raise ValueError("a tint needs at least two colours")
    tables = [[], [], []]
    for level in range(256):
        t = level / 255.0
        lo, hi = stops[0], stops[-1]
        for a, b in zip(stops, stops[1:]):
            if a[0] <= t <= b[0]:
                lo, hi = a, b
                break
        k = 0.0 if hi[0] == lo[0] else min(1.0, max(0.0, (t - lo[0]) / (hi[0] - lo[0])))
        for i in range(3):
            tables[i].append(int(round(lo[1][i] + (hi[1][i] - lo[1][i]) * k)))
    return tables


def tint(image, art):
    """A picture washed towards the look: its light and dark are mapped onto the look's ramp, then mixed with the picture itself."""
    from PIL import Image
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    grey = rgb.convert("L")
    red, green, blue = art["_luts"]
    mapped = Image.merge("RGB", (grey.point(red), grey.point(green), grey.point(blue)))
    out = Image.blend(rgb, mapped, min(1.0, max(0.0, float(art.get("mix", 0.7))))).convert("RGBA")
    out.putalpha(rgba.getchannel("A"))
    return out


def _wants_tint(path):
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    return len(parts) >= 3 and "assets" in parts and any(parts[i] == "assets" and parts[i + 1] in TINTED for i in range(len(parts) - 1))


def swapped(path, art):
    """The look's own picture for one of the launcher's: the file of the same name in the look's folder (assets\\press\\<art "folder">),
    for a picture from assets\\ui, or for a PLAY / STOP / DUALBOX variant from assets\\buttons. None when the look has none for it."""
    folder = os.path.basename(str(art.get("folder") or ""))
    if not folder:
        return None
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    for i in range(len(parts) - 2):
        if parts[i] != "assets":
            continue
        name = None
        if parts[i + 1] == "ui" and i + 3 == len(parts):
            name = parts[-1]
        elif parts[i + 1] == "buttons" and i + 4 == len(parts) and parts[i + 2] in BUTTON_KINDS:
            stem = os.path.splitext(parts[-1])[0].lower()
            state = next((s for s in ("_hover", "_off") if stem.endswith(s)), "")
            name = BUTTON_KINDS[parts[i + 2]] + state + ".png"
        if name:
            candidate = os.path.join(PRESS, folder, name)
            return candidate if os.path.isfile(candidate) else None
    return None


_RealPhotoImage = tk.PhotoImage


class TintedPhotoImage(_RealPhotoImage):
    """tk.PhotoImage, but a picture loaded from assets\\ui or assets\\buttons is the look's own one when it has one (same name in its
    folder), and otherwise takes the look's tint when it has a tint. Still a real PhotoImage."""

    def __init__(self, name=None, cnf={}, master=None, **kw):
        path = kw.get("file")
        other = None
        if path and LOOK is not None and LOOK.get("art"):
            try:
                other = swapped(str(path), LOOK["art"])
            except Exception:
                other = None
        if other:
            kw = dict(kw, file=other)
        elif path and LOOK is not None and LOOK.get("art") and LOOK["art"].get("_luts") and _wants_tint(str(path)):
            try:
                import base64
                import io
                from PIL import Image
                buffer = io.BytesIO()
                with Image.open(path) as picture:
                    tint(picture, LOOK["art"]).save(buffer, "PNG")
                kw = {k: v for k, v in kw.items() if k != "file"}
                kw["data"] = base64.b64encode(buffer.getvalue())
            except Exception:
                kw = dict(kw, file=path)                # any trouble: the picture as it is
        _RealPhotoImage.__init__(self, name, cnf, master, **kw)


def install():
    """Puts the look's picture loader in tk.PhotoImage's place while a look with its own buttons, or a tint, is in date."""
    if LOOK is None or not isinstance(LOOK.get("art"), dict):
        return False
    art = LOOK["art"]
    if art.get("ramp"):
        try:                                            # a tint needs Pillow; without it the usual pictures stay as they are
            import PIL.Image  # noqa: F401
            art["_luts"] = _luts(art["ramp"])
        except Exception:
            art.pop("_luts", None)
    has_folder = bool(art.get("folder")) and os.path.isdir(os.path.join(PRESS, os.path.basename(str(art["folder"]))))
    if not has_folder and not art.get("_luts"):
        return False
    tk.PhotoImage = TintedPhotoImage
    return True


def uninstall():
    tk.PhotoImage = _RealPhotoImage


# ---------- the opening theme ----------
class Player:
    """Plays one sound file without waiting for it: Windows' own player (winmm), on Linux whichever of ffplay / mpv / mpg123 / cvlc is there."""
    ALIAS = "xifo_theme"

    def __init__(self):
        self.proc, self.open = None, False

    def _mci(self, command):
        answer = ctypes.create_unicode_buffer(128)
        return ctypes.windll.winmm.mciSendStringW(command, answer, 127, 0), answer.value

    def play(self, path, volume=VOLUME):
        self.stop()
        try:
            if os.name == "nt":
                short = ctypes.create_unicode_buffer(600)          # the short 8.3 path: the old player trips over long or unusual ones
                if ctypes.windll.kernel32.GetShortPathNameW(path, short, 600):
                    path = short.value
                kind = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
                if self._mci(f'open "{path}" type {kind} alias {self.ALIAS}')[0]:
                    return False
                self.open = True
                self._mci(f"setaudio {self.ALIAS} volume to {int(max(0.0, min(1.0, volume)) * 1000)}")
                if self._mci(f"play {self.ALIAS}")[0]:
                    self.stop()
                    return False
                return True
            percent = str(int(max(0.0, min(1.0, volume)) * 100))
            for command in (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", percent], ["mpv", "--no-video", "--really-quiet", "--volume=" + percent],
                            ["mpg123", "-q"], ["cvlc", "--play-and-exit", "--quiet"]):
                if shutil.which(command[0]):
                    self.proc = subprocess.Popen(command + [path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
        except Exception:
            self.stop()
        return False

    def playing(self):
        try:
            if os.name == "nt":
                return self.open and self._mci(f"status {self.ALIAS} mode")[1] == "playing"
            return self.proc is not None and self.proc.poll() is None
        except Exception:
            return False

    def stop(self):
        try:
            if os.name == "nt":
                if self.open:
                    self._mci(f"stop {self.ALIAS}")
                    self._mci(f"close {self.ALIAS}")
            elif self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass
        self.proc, self.open = None, False


PLAYER = Player()
atexit.register(PLAYER.stop)


def music_file():
    """The opening theme in date today (the first dated .mp3 / .wav in assets\\press), or None."""
    if config().get("limited_look") is False:
        return None
    found = dated(SOUNDS)
    return found[0] if found else None


def start(app):
    """Called once the launcher's window is up: plays the opening theme (once, not while the game is running) and puts a small MUSIC
    switch on the banner. The music stops when the game starts or the switch is turned off; the switch is remembered in config.json."""
    path = music_file()
    if not path:
        return None
    names = colours({"PANEL": 1, "GOLD": 1, "DIM": 1}) if LOOK else {}
    panel, lit, dim = names.get("PANEL", "#101c28"), names.get("GOLD", "#e6be64"), names.get("DIM", "#8aa0ad")
    state = {"on": config().get("theme_music") is not False}
    label = None
    stage = getattr(app, "stage", None)
    if stage is not None:
        label = tk.Label(stage, bg=panel, font=("Segoe UI" if os.name == "nt" else "DejaVu Sans", 8, "bold"), padx=7, pady=2, cursor="hand2")
        label.place(relx=1.0, rely=1.0, anchor="se", x=-6, y=-6)
        label.lift()

    def show():
        if label is not None:
            label.configure(text="♪ MUSIC ON" if state["on"] else "♪ MUSIC OFF", fg=lit if state["on"] else dim)

    def watch():
        if not PLAYER.playing():
            return
        if getattr(app, "running", False):            # the game has its own music
            PLAYER.stop()
            return
        app.after(500, watch)

    def play():
        if state["on"] and not getattr(app, "running", False) and PLAYER.play(path):
            app.after(500, watch)

    def toggle(_event=None):
        state["on"] = not state["on"]
        try:
            save("theme_music", None if state["on"] else False)
        except Exception:
            pass                                      # not remembered, but it does what was asked now
        if state["on"]:
            play()
        else:
            PLAYER.stop()
        show()

    if label is not None:
        label.bind("<Button-1>", toggle)
    show()
    app.after(700, play)
    return toggle


# ---------- set up when the launcher first asks for it ----------
try:
    LOOK = load_look()
    install()
except Exception:
    LOOK = None
