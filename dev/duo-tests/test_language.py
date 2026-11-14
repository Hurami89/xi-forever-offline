import os, sys, tempfile, io, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import setup_dualbox as sd
root = tempfile.mkdtemp(); ash = os.path.join(root, "Ashita"); boot = os.path.join(ash, "config", "boot"); os.makedirs(boot)
def ini(lang, extra=""): return f"[ashita.boot]\r\nfile = x\r\nscript = a.txt\r\n\r\n[ashita.language]\r\nplayonline = 2\r\nashita = {lang}\r\n\r\n[ffxi.registry]\r\n0001 = 1920\r\n{extra}"
open(os.path.join(boot, "phoenixsolo.ini"), "w", newline="").write(ini(1)); open(os.path.join(boot, "phoenixsolo2.ini"), "w", newline="").write(ini(1))
open(os.path.join(boot, "phoenixsolo_gm.ini"), "w", newline="").write(ini(2))
cfg = {"ashita_dir": ash, "ashita_boot": "phoenixsolo.ini", "ashita_boot2": "phoenixsolo2.ini", "ashita_boot_gm": "phoenixsolo_gm.ini"}
def run(*words):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): sd.language_command(cfg, list(words))
    return buf.getvalue()
r = lambda name: open(os.path.join(boot, name), newline="").read()
out = run(); assert "ashita = 1 (Japanese)" in out and "ashita = 2 (English)" in out and out.count("playonline = 2") == 3, out
main_before = r("phoenixsolo.ini")
out = run("english"); assert "second: phoenixsolo2.ini is now ashita = 2" in out and "gm: phoenixsolo_gm.ini was already english" in out, out
assert "main:" not in out and sd.read_language(os.path.join(boot, "phoenixsolo2.ini")) == {"playonline": 2, "ashita": 2} and r("phoenixsolo.ini") == main_before
assert r("phoenixsolo2.ini") == ini(2) and r("phoenixsolo_gm.ini") == ini(2) and not os.path.exists(os.path.join(boot, "phoenixsolo_gm.ini.before-language"))   # an already-correct file is not touched, line endings and all
assert "ashita = 1" in open(os.path.join(boot, "phoenixsolo2.ini.before-language")).read()
assert "Nothing needed changing" in run("english")
out = run("english", "--all"); assert "main: phoenixsolo.ini is now ashita = 2" in out and r("phoenixsolo.ini") == ini(2)
assert "now ashita = 1" in run("japanese", "--all") and r("phoenixsolo.ini") == ini(1)
open(os.path.join(boot, "phoenixsolo2.ini"), "w", newline="").write("[ashita.boot]\nscript = a.txt\n")
assert sd.set_ashita_language(os.path.join(boot, "phoenixsolo2.ini"), 2) and sd.read_language(os.path.join(boot, "phoenixsolo2.ini"))["ashita"] == 2
open(os.path.join(boot, "phoenixsolo_gm.ini"), "w", newline="").write("[ashita.boot]\nscript = a.txt\n[ashita.language]\nplayonline = 2\n[ffxi.registry]\n0001 = 1\n")
assert sd.set_ashita_language(os.path.join(boot, "phoenixsolo_gm.ini"), 2); t = r("phoenixsolo_gm.ini")
assert sd.read_language(os.path.join(boot, "phoenixsolo_gm.ini")) == {"playonline": 2, "ashita": 2} and "[ffxi.registry]\n0001 = 1" in t and t.count("ashita = 2") == 1
try: sd.language_command(cfg, ["klingon"]); assert False
except RuntimeError as e: assert "english" in str(e)
print("language command OK")
