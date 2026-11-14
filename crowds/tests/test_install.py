"""Installer + launcher checks on COPIES of the real kit and server files (stand-in Tk, no real window).
Usage: python test_install.py <real kit dir> <real server dir with modules/init.txt, sql, data, navmeshes>"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

KIT_SRC, SERVER_SRC = sys.argv[1], sys.argv[2]
CROWDS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(name, cond, detail=""):
    global fails
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)))
    if not cond:
        fails += 1


tmp = tempfile.mkdtemp()
kit = os.path.join(tmp, "FFXISOLO")
server = os.path.join(tmp, "server")
os.makedirs(os.path.join(kit, "crowds"))
for name in ("launcher_core.py", "launcher_gui.pyw", "rates.json"):
    shutil.copy2(os.path.join(KIT_SRC, name), kit)
for name in ("crowds.lua", "crowds_chat.lua", "crowds_chat_data.lua", "crowds_field.lua", "build_crowds_data.py", "navcheck.py", "install_crowds.py", "crowd_chat_ai.py"):
    shutil.copy2(os.path.join(CROWDS, name), os.path.join(kit, "crowds"))
with open(os.path.join(kit, "config.json"), "w") as f:
    json.dump({"server_dir": server}, f)
os.makedirs(os.path.join(server, "modules", "custom", "lua"))
shutil.copy2(os.path.join(SERVER_SRC, "modules", "init.txt"), os.path.join(server, "modules"))
for sub in ("sql", "data", "navmeshes", "scripts"):
    os.symlink(os.path.join(SERVER_SRC, sub), os.path.join(server, sub))
init_before = open(os.path.join(server, "modules", "init.txt"), encoding="utf-8").read()
core_before = open(os.path.join(kit, "launcher_core.py"), encoding="utf-8").read()

run = lambda *a: subprocess.run([sys.executable, os.path.join(kit, "crowds", "install_crowds.py")] + list(a), capture_output=True, text=True)
r = run()
print(r.stdout[-1500:], r.stderr[-1500:])
check("installer exits 0", r.returncode == 0, r.returncode)
lua = os.path.join(server, "modules", "custom", "lua")
check("crowds.lua copied", os.path.exists(os.path.join(lua, "crowds.lua")))
check("crowds_data.lua built", os.path.getsize(os.path.join(lua, "crowds_data.lua")) > 50000)
init = open(os.path.join(server, "modules", "init.txt"), encoding="utf-8").read()
active = [l.strip() for l in init.splitlines() if l.strip() and not l.strip().startswith("#")]
check("init.txt loads crowds.lua once", active.count("custom/lua/crowds.lua") == 1)
check("custom/late is still the last line", active[-1] == "custom/late", active[-3:])
check("every other init.txt line unchanged", [l for l in init.splitlines() if "crowds" not in l.lower() and l.strip()] ==
      [l for l in init_before.splitlines() if l.strip()])
check("init.txt backup made", os.path.exists(os.path.join(server, "modules", "init.txt.before-crowds")))
cfg = open(os.path.join(lua, "crowds_config.lua")).read()
check("config written from rates.json (on, 30, chat on normal, AI on by default)", "enabled = true, per_zone = 30, chat = true, chat_amount = 'normal', chat_ai = true" in cfg, cfg)
check("chat files copied", os.path.exists(os.path.join(lua, "crowds_chat.lua")) and os.path.exists(os.path.join(lua, "crowds_chat_data.lua")))

r2 = run()
check("second run changes nothing in init.txt", open(os.path.join(server, "modules", "init.txt"), encoding="utf-8").read() == init)
check("second run reports already patched", "already has the crowd settings" in r2.stdout and "already has the crowd chat settings" in r2.stdout and "already has the field party settings" in r2.stdout, r2.stdout)

# launcher core: load/save/apply
sys.path.insert(0, kit)
import launcher_core as core  # noqa: E402
check("core imports after the patch", hasattr(core, "clean_crowd_size"))
rates = core.load_rates(kit)
check("defaults: crowds on, 30", rates["crowds"] is True and rates["crowds_per_zone"] == 30, rates.get("crowds"))
check("chat defaults: on, normal, AI on", rates["crowds_chat"] is True and rates["crowds_chat_amount"] == "normal" and rates["crowds_chat_ai"] is True)
rates["crowds"], rates["crowds_per_zone"] = False, 7
rates["crowds_chat_amount"], rates["crowds_chat_ai"] = "busy", False
check("field defaults: on, 1 per area", rates["crowds_field"] is True and rates["crowds_field_parties"] == 1)
core.save_rates(kit, rates)
again = core.load_rates(kit)
check("saved choice survives a reload", again["crowds"] is False and again["crowds_per_zone"] == 7)
check("sizes are clamped", core.clean_crowd_size("99") == 40 and core.clean_crowd_size("-3") == 0 and core.clean_crowd_size("abc") == 30)
msgs = core.apply_rates(server, again)
cfg = open(os.path.join(lua, "crowds_config.lua")).read()
check("PLAY writes crowds_config.lua (off, 7, busy, AI off, field on 1)", "enabled = false, per_zone = 7, chat = true, chat_amount = 'busy', chat_ai = false, field = true, field_parties = 1" in cfg, cfg)
check("no crowd error message on PLAY", not any("crowds" in m for m in msgs), msgs)
pre = core.apply_preset(again, "Fast")
check("a preset keeps the crowd choice", pre["crowds"] is False and pre["crowds_per_zone"] == 7 and pre["crowds_chat_amount"] == "busy" and pre["crowds_chat_ai"] is False)
check("saved chat choice survives a reload", again["crowds_chat_amount"] == "busy" and again["crowds_chat_ai"] is False)
active = [l.strip() for l in open(os.path.join(server, "modules", "init.txt"), encoding="utf-8").read().splitlines() if l.strip() and not l.strip().startswith("#")]
check("after PLAY (fast-travel guard ran) crowds still loaded and custom/late still last", "custom/lua/crowds.lua" in active and active[-1] == "custom/late")


# launcher window: stand-in Tk (logic only, never looks)
class W:
    def __init__(self, *a, **k):
        self.kw = k

    def __getattr__(self, n):
        return lambda *a, **k: W()


class Var:
    def __init__(self, value=None, **k):
        self.v = value

    def get(self):
        return self.v

    def set(self, x):
        self.v = x


tk = types.ModuleType("tkinter")
for n in ("Frame", "Label", "Button", "Canvas", "Text", "Checkbutton", "Toplevel", "Entry", "Listbox", "Scrollbar", "Spinbox", "Radiobutton"):
    setattr(tk, n, type(n, (W,), {}))
tk.StringVar = Var
tk.BooleanVar = Var
tk.IntVar = Var
tk.Tk = type("Tk", (W,), {})
ttk = types.ModuleType("tkinter.ttk")
for n in ("Style", "Scrollbar", "Combobox", "Treeview", "Spinbox", "Frame", "Label", "Button", "Entry", "Progressbar", "Notebook"):
    setattr(ttk, n, type(n, (W,), {}))
mods = {"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": types.ModuleType("m"), "tkinter.simpledialog": types.ModuleType("s"),
        "tkinter.filedialog": types.ModuleType("f")}
tk.ttk, tk.messagebox, tk.simpledialog, tk.filedialog = ttk, mods["tkinter.messagebox"], mods["tkinter.simpledialog"], mods["tkinter.filedialog"]
sys.modules.update(mods)
sys.modules.setdefault("mariadb", types.ModuleType("mariadb"))
loader = importlib.machinery.SourceFileLoader("lg", os.path.join(kit, "launcher_gui.pyw"))
spec = importlib.util.spec_from_loader("lg", loader)
lg = importlib.util.module_from_spec(spec)
loader.exec_module(lg)
tab = lg.RatesTab(W(), dict(again))
check("Rates page has the crowd switch and size", "crowds" in tab.__dict__ and "crowds_size" in tab.__dict__)
check("Rates page shows the saved values", tab.crowds.get() is False and tab.crowds_size.get() == "7")
tab.crowds.set(True)
tab.crowds_size.set("22")
got = tab.collect()
check("Rates page collects them", got["crowds"] is True and got["crowds_per_zone"] == 22, (got.get("crowds"), got.get("crowds_per_zone")))
check("Rates page has the chat switch, amount and AI switch", all(k in tab.__dict__ for k in ("crowds_chat", "crowds_chat_amount", "crowds_chat_ai")))
tab.crowds_chat_amount.set("quiet"); tab.crowds_chat_ai.set(True); tab.crowds_chat.set(False)
got = tab.collect()
tab.crowds_field.set(False); tab.crowds_field_parties.set("2")
got2 = tab.collect()
check("Rates page has and collects the field party switch and count", got2["crowds_field"] is False and got2["crowds_field_parties"] == 2)
check("Rates page collects the chat choices", got["crowds_chat"] is False and got["crowds_chat_amount"] == "quiet" and got["crowds_chat_ai"] is True)
# the AI helper is started with the servers only when wanted, and stopped at cleanup
class FakeApp:
    pass
app = FakeApp()
app.logfiles, app.said = [], []
app.say = lambda t: app.said.append(t)
started = []
real_popen = lg.subprocess.Popen
class P:
    def __init__(self, args, **k): started.append(args); self.done = False
    def poll(self): return None if not self.done else 0
    def terminate(self): self.done = True
lg.subprocess.Popen = P
lg.LOGS = tmp
app.rates = {"crowds": True, "crowds_chat": True, "crowds_chat_ai": True}
lg.App.start_crowd_chat_ai(app)
check("AI helper starts with the servers when switched on", started and started[-1][-1].endswith("crowd_chat_ai.py"), started)
n = len(started)
app.rates = {"crowds": True, "crowds_chat": True, "crowds_chat_ai": False}
lg.App.start_crowd_chat_ai(app)
check("AI helper does not start when AI chatter is off", len(started) == n)
lg.subprocess.Popen = real_popen
src = open(os.path.join(kit, "launcher_gui.pyw"), encoding="utf-8").read()
check("launcher stops the AI helper at cleanup", "crowd_ai.terminate()" in src and src.count("self.start_crowd_chat_ai()") == 1)

# undo
r3 = run("--undo")
active = [l.strip() for l in open(os.path.join(server, "modules", "init.txt"), encoding="utf-8").read().splitlines() if l.strip() and not l.strip().startswith("#")]
check("--undo stops loading crowds.lua", "custom/lua/crowds.lua" not in active)
r4 = run()
active = [l.strip() for l in open(os.path.join(server, "modules", "init.txt"), encoding="utf-8").read().splitlines() if l.strip() and not l.strip().startswith("#")]
check("installing again switches it back on (once)", active.count("custom/lua/crowds.lua") == 1 and active[-1] == "custom/late")
r5 = run("--status")
check("--status runs", r5.returncode == 0 and "loaded by modules/init.txt       : yes" in r5.stdout, r5.stdout)

# a launcher that looks different is left alone
odd = os.path.join(tmp, "odd")
os.makedirs(os.path.join(odd, "crowds"))
open(os.path.join(odd, "launcher_core.py"), "w").write(core_before.replace('"defaults_version": 2})', '"defaults_version": 3})'))
spec2 = importlib.util.spec_from_file_location("ic", os.path.join(kit, "crowds", "install_crowds.py"))
ic = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ic)
msg = ic.patch_file(os.path.join(odd, "launcher_core.py"), ic.CORE_PATCHES, "launcher_core.py")
# an already patched launcher with the first version's label gets the new label
old_gui = open(os.path.join(kit, "launcher_gui.pyw"), encoding="utf-8").read().replace("walking around in towns and outposts", "walking around in town (Southern San d'Oria for now)")
open(os.path.join(kit, "launcher_gui.pyw"), "w", encoding="utf-8").write(old_gui)
r6 = run()
check("first-version label updated on re-install", "towns and outposts" in open(os.path.join(kit, "launcher_gui.pyw"), encoding="utf-8").read() and "for now" not in open(os.path.join(kit, "launcher_gui.pyw"), encoding="utf-8").read(), r6.stdout)
check("unexpected launcher version: not changed", "NOT changed" in msg and "crowds" not in open(os.path.join(odd, "launcher_core.py")).read(), msg)

print("\n%s" % ("all passed" if fails == 0 else "%d FAILED" % fails))
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if fails else 0)
