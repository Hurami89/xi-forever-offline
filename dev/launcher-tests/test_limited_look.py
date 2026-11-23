"""Limited-time looks (launcher_theme.py): a dated .json in assets\\press gives the launcher its colours and tints its painted
buttons, a dated .mp3 / .wav is the opening theme; the day after the date both are gone by themselves.

Starts the real launcher four times from a COPY of the kit (stand-in config, database driver and addons folder; nothing of the
real install is read or changed): with a look in date, with the music switched off, with "limited_look": false, and with the
date passed. No sound is made: the player is replaced by one that only notes what it was asked to do.
Needs python3-tk, Pillow and a screen:
    xvfb-run -a -s "-screen 0 1500x1000x24" python3 dev/launcher-tests/test_limited_look.py [OUTDIR for screenshots]"""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LOOK = {"name": "Test look",
        "colours": {"BG": "#201030", "PANEL": "#2A1540", "PANEL2": "#341a50", "FG": "#fff0ff", "DIM": "#b0a0d0", "BORDER": "#503080",
                    "LINE": "#6040a0", "OFF": "#8070a0", "GOLD": "#ff50c0", "GOLD_LIT": "#ff90e0", "GOLD_DIM": "#703070",
                    "PARCH": "#f0e0ff", "ACCENT": "#40e0e0", "GREEN": "#40f0b0", "RED": "#ff5080", "GREY": "#504070",
                    "NOT_A_NAME": "#123456", "BAD": "pink"},
        "art": {"folder": "t-ui", "ramp": [[0, "#100020"], [0.5, "#ff40c0"], [1, "#ffffff"]], "mix": 0.8}}
OWN, OWN_HOVER = (10, 200, 220), (9, 90, 190)        # the colours of the look's own stand-in pictures
USUAL = {"BG": "#0a1118", "GOLD": "#e6be64"}


def day(offset):
    return (datetime.date.today() + datetime.timedelta(days=offset)).isoformat()


def put_dated(press, offset):
    """The copy's own look and theme tune, dated `offset` days from today (any others are taken out first)."""
    for name in os.listdir(press):
        if name.lower().endswith((".json", ".mp3", ".wav")):
            os.remove(os.path.join(press, name))
    with open(os.path.join(press, f"t_look__until-{day(offset)}.json"), "w") as f:
        json.dump(LOOK, f)
    with wave.open(os.path.join(press, f"t_theme__until-{day(offset)}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)


def make_copy():
    work = tempfile.mkdtemp(prefix="xif-look-")
    kit = os.path.join(work, "kit")
    os.makedirs(kit)
    for name in os.listdir(KIT):
        path = os.path.join(KIT, name)
        if os.path.isfile(path) and (name.startswith("launcher_") and name.endswith((".py", ".pyw"))
                                     or name in ("rates.json", "thirdparty.json", "graphics.json", "gfxmod.json", "contributors.json",
                                                 "CREDITS.md", "config.example.json")):
            shutil.copy2(path, os.path.join(kit, name))
    for folder in ("ui", "press"):
        source = os.path.join(KIT, "assets", folder)
        if os.path.isdir(source):
            shutil.copytree(source, os.path.join(kit, "assets", folder))
    press = os.path.join(kit, "assets", "press")
    os.makedirs(press, exist_ok=True)
    os.makedirs(os.path.join(kit, "assets", "ui"), exist_ok=True)
    from PIL import Image
    Image.new("RGB", (60, 30), (230, 190, 100)).save(os.path.join(kit, "assets", "ui", "t_gold.png"))       # a button-like picture
    Image.new("RGB", (60, 30), (230, 190, 100)).save(os.path.join(kit, "assets", "t_plain.png"))            # the same, outside ui
    Image.new("RGB", (60, 30), (230, 190, 100)).save(os.path.join(kit, "assets", "ui", "t_swap.png"))       # one the look has its own picture for
    os.makedirs(os.path.join(kit, "assets", "buttons", "play"), exist_ok=True)                               # a PLAY variant, as on the dev PC
    Image.new("RGB", (60, 30), (230, 190, 100)).save(os.path.join(kit, "assets", "buttons", "play", "t_variant_hover.png"))
    os.makedirs(os.path.join(press, "t-ui"), exist_ok=True)                                                  # the look's own buttons
    Image.new("RGB", (60, 30), OWN).save(os.path.join(press, "t-ui", "t_swap.png"))
    Image.new("RGB", (60, 30), OWN_HOVER).save(os.path.join(press, "t-ui", "play_hover.png"))
    Image.new("RGB", (920, 368), (200, 180, 120)).save(os.path.join(press, "t_usual__center.png"))
    ashita = os.path.join(work, "ashita")
    for name in ("servermenu", "XIUI"):
        os.makedirs(os.path.join(ashita, "addons", name))
        with open(os.path.join(ashita, "addons", name, name + ".lua"), "w") as f:
            f.write(f"addon.name = '{name}';\naddon.author = 'test';\naddon.version = '1.0';\naddon.desc = 'stand-in';\n")
    os.makedirs(os.path.join(ashita, "plugins"))
    os.makedirs(os.path.join(ashita, "config", "boot"))
    os.makedirs(os.path.join(ashita, "scripts"))
    with open(os.path.join(ashita, "config", "boot", "xiforever.ini"), "w") as f:
        f.write("[ashita.boot]\nscript      = xiforever.txt\n\n[ffxi.registry]\n0001 = 1920\n0002 = 1080\n")
    with open(os.path.join(ashita, "scripts", "xiforever.txt"), "w") as f:
        f.write("# Managed by the XI: Forever Offline launcher\n/load addons\n/wait 3\n/addon load servermenu\n")
    with open(os.path.join(kit, "config.example.json"), encoding="utf-8-sig") as f:
        cfg = json.load(f)
    cfg.update({"ashita_dir": ashita, "ashita_boot": "xiforever.ini", "server_dir": os.path.join(work, "server"),
                "mariadb_dir": os.path.join(kit, "mariadb"), "banners_seen": [n for n in os.listdir(press) if "__once" in n.lower()]})
    with open(os.path.join(kit, "config.json"), "w") as f:
        json.dump(cfg, f, indent=1)
    stubs = os.path.join(work, "stubs")
    os.makedirs(stubs)
    with open(os.path.join(stubs, "mariadb.py"), "w") as f:
        f.write("class Error(Exception):\n    pass\n\n\ndef connect(*a, **k):\n    raise Error('stand-in: no database in this test')\n")
    return work


def set_config(kit, **changes):
    path = os.path.join(kit, "config.json")
    with open(path, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    for key, value in changes.items():
        if value is None:
            cfg.pop(key, None)
        else:
            cfg[key] = value
    with open(path, "w") as f:
        json.dump(cfg, f, indent=1)


def get_config(kit):
    with open(os.path.join(kit, "config.json"), encoding="utf-8-sig") as f:
        return json.load(f)


class QuietPlayer:
    """Stands in for launcher_theme.Player: no sound, just a note of what was asked."""

    def __init__(self):
        self.calls, self.on = [], False

    def play(self, path, volume=0.5):
        self.calls.append(("play", os.path.basename(path)))
        self.on = True
        return True

    def playing(self):
        return self.on

    def stop(self):
        if self.on:
            self.calls.append(("stop",))
        self.on = False


def launch(work, step, out):
    kit = os.path.join(work, "kit")
    sys.path.insert(0, kit)
    sys.path.insert(0, os.path.join(work, "stubs"))
    os.chdir(kit)
    loader = importlib.machinery.SourceFileLoader("launcher_gui", os.path.join(kit, "launcher_gui.pyw"))
    spec = importlib.util.spec_from_loader("launcher_gui", loader)
    gui = importlib.util.module_from_spec(spec)
    sys.modules["launcher_gui"] = gui
    loader.exec_module(gui)
    for name in ("showerror", "showinfo", "showwarning"):
        setattr(gui.messagebox, name, lambda *a, **k: None)
    for name in ("askyesno", "askokcancel"):
        setattr(gui.messagebox, name, lambda *a, **k: False)
    import tkinter as tk
    theme = sys.modules.get("launcher_theme")
    widgets, coop = sys.modules.get("launcher_widgets"), sys.modules.get("launcher_coop_gui")
    fails = []

    def check(ok, what):
        print(("  ok   " if ok else "  FAIL ") + what)
        if not ok:
            fails.append(what)

    check(theme is not None, "the launcher loaded launcher_theme")
    if theme is None:
        sys.exit(1)
    player = QuietPlayer()
    theme.PLAYER = player
    themed = step in ("during", "muted")
    want = {k: v.lower() for k, v in LOOK["colours"].items()} if themed else USUAL

    if step == "during":
        check(theme.until("a__until-2026-12-02.json") == "2026-12-02" and theme.until("a.json") == "" and theme.until("a__until-soon.mp3") == "0",
              "the last day is read from a file's name")
        check(theme.LOOK is not None and theme.LOOK.get("name") == "Test look", "the dated .json is the look")
        check("NOT_A_NAME" not in theme.colours(vars(gui)) and "BAD" not in theme.LOOK["colours"], "names the launcher does not have, and values that are no colour, are left out")
        luts = theme._luts(LOOK["art"]["ramp"])
        check([t[0] for t in luts] == [0x10, 0x00, 0x20] and [t[255] for t in luts] == [255, 255, 255] and len(luts[0]) == 256, "the tint's ramp runs from its first colour to its last")
        from PIL import Image
        src = Image.new("RGBA", (8, 8), (230, 190, 100, 120))
        done = theme.tint(src, dict(LOOK["art"], _luts=luts))
        check(done.size == (8, 8) and done.mode == "RGBA" and done.getpixel((0, 0))[3] == 120 and done.getpixel((0, 0))[:3] != (230, 190, 100),
              "a tinted picture keeps its size and its see-through parts, and changes colour")
        check(theme.Player().play(os.path.join(kit, "no-such-file.mp3")) in (True, False), "the real player never raises, whatever it is given")

    check(all(getattr(gui, k) == v for k, v in want.items() if hasattr(gui, k)) and gui.BG == want["BG"],
          f"launcher_gui's colours are {'the look' if themed else 'its own'}'s (BG {gui.BG}, GOLD {gui.GOLD})")
    check(widgets is not None and widgets.BG == want["BG"] and widgets.GOLD == want["GOLD"], "... and launcher_widgets' (the newer pages)")
    check(coop is None or (coop.BG == want["BG"] and coop.GOLD == want["GOLD"]), "... and the Co-op page's")
    pages = sys.modules.get("launcher_pages")
    check(pages is None or pages.GOLD == want["GOLD"], "... and launcher_pages picked them up from launcher_widgets")
    check((tk.PhotoImage is theme.TintedPhotoImage) == themed, "the tinted picture loader is " + ("in place" if themed else "not in place"))
    check((theme.music_file() is not None) == themed, "there is " + ("an" if themed else "no") + " opening theme today")

    app = gui.App()

    def settle(seconds):
        end = time.time() + seconds
        while time.time() < end:
            app.update()
            time.sleep(0.02)

    def shot(name):
        if not out:
            return
        app.lift()
        app.update()
        x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
        subprocess.run(["import", "-window", "root", "-crop", f"{w}x{h}+{x}+{y}", "+repage", os.path.join(out, name + ".png")], check=False)

    def colour_of(path):
        picture = tk.PhotoImage(file=path)
        value = picture.get(5, 5)
        return tuple(int(v) for v in (value.split() if isinstance(value, str) else value))[:3]

    gold = (230, 190, 100)
    check((colour_of(os.path.join(kit, "assets", "ui", "t_gold.png")) not in (gold, OWN)) == themed,
          "a picture from assets\\ui the look has no picture for comes out " + ("tinted" if themed else "as it is"))
    check(colour_of(os.path.join(kit, "assets", "ui", "t_swap.png")) == (OWN if themed else gold),
          "one the look has its own picture for is " + ("the look's" if themed else "the usual one"))
    check(colour_of(os.path.join(kit, "assets", "buttons", "play", "t_variant_hover.png")) == (OWN_HOVER if themed else gold),
          "a PLAY variant from assets\\buttons is " + ("the look's play_hover" if themed else "the usual one"))
    check(colour_of(os.path.join(kit, "assets", "t_plain.png")) == gold, "a picture from elsewhere in assets is left as it is")
    check(isinstance(tk.PhotoImage(file=os.path.join(kit, "assets", "ui", "t_gold.png")).subsample(2), theme._RealPhotoImage), "it is still a real Tk picture (subsample works)")
    check("launcher_theme.start(app)" in open(os.path.join(kit, "launcher_gui.pyw"), encoding="utf-8").read(), "launcher_gui's main() starts the opening theme")

    toggle = theme.start(app)
    settle(1.3)
    labels = [c for c in app.stage.winfo_children() if isinstance(c, tk.Label) and "MUSIC" in str(c.cget("text"))]
    if step == "during":
        check(player.calls == [("play", f"t_theme__until-{day(3)}.wav")], f"the opening theme was started once: {player.calls}")
        check(len(labels) == 1 and labels[0].cget("text").endswith("MUSIC ON"), "the MUSIC switch is on the banner and says ON")
        shot("look-during")
        toggle()
        settle(0.2)
        check(player.calls[-1] == ("stop",) and get_config(kit).get("theme_music") is False and labels[0].cget("text").endswith("MUSIC OFF"),
              "a click on the switch stops the music, says OFF and is remembered in config.json")
        toggle()
        settle(0.2)
        check(player.calls[-1][0] == "play" and "theme_music" not in get_config(kit), "a second click plays it again and takes the note out of config.json")
        app.running = True
        settle(1.0)
        check(player.calls[-1] == ("stop",) and not player.on, "it stops when the game is running")
        count = len(player.calls)
        settle(1.2)
        check(len(player.calls) == count, "... and stays stopped")
    elif step == "muted":
        check(player.calls == [], "music switched off earlier: nothing is played")
        check(len(labels) == 1 and labels[0].cget("text").endswith("MUSIC OFF"), "the switch is there and says OFF")
    else:
        check(toggle is None and player.calls == [] and not labels, "no music, no switch")
        shot("look-" + step)
    app.destroy()
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--launch":
        launch(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else ""
    if out:
        os.makedirs(out, exist_ok=True)
    work = make_copy()
    kit = os.path.join(work, "kit")
    press = os.path.join(kit, "assets", "press")
    bad = 0
    try:
        for step in ("during", "muted", "off", "after"):
            put_dated(press, -1 if step == "after" else 3)
            set_config(kit, theme_music=False if step == "muted" else None, limited_look=False if step == "off" else None)
            print(step)
            bad += subprocess.run([sys.executable, os.path.abspath(__file__), "--launch", work, step, out]).returncode != 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("ALL OK" if not bad else f"{bad} step(s) FAILED")
    sys.exit(1 if bad else 0)
