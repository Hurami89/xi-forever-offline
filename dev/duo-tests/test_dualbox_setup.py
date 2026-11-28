#!/usr/bin/env python3
"""The DUALBOX button sets the second window up itself (2026-11-27, Vinci Alessandro: the old message sent players to
PowerShell with "python setup_dualbox.py setup", and a player's PC has no Python).

    python test_dualbox_setup.py [kit folder]        (default: two folders up from this file)

Everything runs in a made-up kit in a temp folder: a made-up config.json and Ashita folder, the real setup_dualbox.py
and launcher_core.py, and the real setup_second / start_second methods cut out of launcher_gui.pyw and run on a
stand-in launcher (no window is opened, no game, no database). Nothing of the real kit is read except those files.
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

KIT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
passed = failed = 0


def check(ok, label):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print("FAIL:", label)


def section(name):
    print("\n== " + name)


def make_kit(root, autobot=True, script=True):
    """A made-up install: the two real program files, a boot file with a login line, two add-on folders."""
    kit, ashita = os.path.join(root, "kit"), os.path.join(root, "Ashita")
    os.makedirs(os.path.join(kit, "logs"))
    os.makedirs(os.path.join(ashita, "config", "boot"))
    os.makedirs(os.path.join(ashita, "scripts"))
    os.makedirs(os.path.join(ashita, "addons", "xiui"))
    if autobot:
        os.makedirs(os.path.join(ashita, "addons", "autobot"))
        open(os.path.join(ashita, "addons", "autobot", "autobot.lua"), "w").write("-- stand-in\n")
    shutil.copy2(os.path.join(KIT, "launcher_core.py"), kit)
    if script:
        shutil.copy2(os.path.join(KIT, "setup_dualbox.py"), kit)
    with open(os.path.join(ashita, "config", "boot", "xiforever.ini"), "w", newline="") as f:
        f.write("[ashita.launcher]\r\nautoclose = 1\r\n\r\n[ashita.boot]\r\nfile = .\\\\bootloader\\\\xiloader.exe\r\n"
                "command = --server 127.0.0.1 --user player1 --pass first-secret --hide\r\nscript = default.txt\r\n\r\n"
                "[ffxi.registry]\r\n0001 = 1920\r\n0002 = 1080\r\n")
    with open(os.path.join(kit, "config.json"), "w") as f:      # a made-up one; port 1 so nothing is ever reached
        json.dump({"ashita_dir": ashita, "ashita_boot": "xiforever.ini", "game_user": "player1", "db_host": "127.0.0.1",
                   "db_port": 1, "db_user": "nobody", "db_pass": "nothing", "db_name": "nowhere"}, f)
    return kit, ashita


def load(kit, name):
    """A module from the made-up kit (its HERE points there)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name + "_under_test_" + str(abs(hash(kit))), os.path.join(kit, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    old = list(sys.path)
    sys.path.insert(0, kit)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = old
    return module


# ---------- 1. AutoBot is only downloaded when it is missing ----------
section("AutoBot: only a missing one is downloaded")
with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=True)
    sd = load(kit, "setup_dualbox")
    cfg = json.load(open(os.path.join(kit, "config.json")))
    calls = []
    lines = sd.install_autobot(cfg, fetch=lambda target: calls.append(target) or True)
    check(calls == [] and len(lines) == 1 and "already" in lines[0], "AutoBot in the Ashita folder: nothing is downloaded")
    check(sd.autobot_installed(cfg) is True, "autobot_installed sees it")
    try:
        sd.install_autobot(cfg, install_plugin=True, fetch=lambda target: calls.append(target) or False)
        check(False, "'plugin' still downloads")
    except RuntimeError:
        check(len(calls) == 1, "'plugin' still downloads (the Movement plugin comes out of the download)")

with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=False)
    sd = load(kit, "setup_dualbox")
    cfg = json.load(open(os.path.join(kit, "config.json")))
    check(sd.autobot_installed(cfg) is False, "no AutoBot: autobot_installed says so")

    def no_git(target):
        raise FileNotFoundError(2, "The system cannot find the file specified")
    try:
        sd.install_autobot(cfg, fetch=no_git)
        check(False, "no git: a plain message")
    except RuntimeError as e:
        check("Could not download AutoBot" in str(e) and "git" in str(e), "no git on the PC: a plain message, not a Windows error")
    except OSError:
        check(False, "no git: a plain message (the Windows error came through)")

    def fake_download(target):
        os.makedirs(os.path.join(target, "addons", "autobot"))
        open(os.path.join(target, "addons", "autobot", "autobot.lua"), "w").write("-- downloaded\n")
        return True
    lines = sd.install_autobot(cfg, fetch=fake_download)
    check(os.path.isfile(os.path.join(ashita, "addons", "autobot", "autobot.lua")) and "copied" in lines[0], "a missing AutoBot is downloaded and copied in")


# ---------- 2. the real script, started the way the button starts it ----------
section("setup_dualbox.py setup, as a program")
with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=True)
    env = dict(os.environ, PATH="")                                   # no git anywhere
    done = subprocess.run([sys.executable, os.path.join(kit, "setup_dualbox.py"), "setup"], cwd=kit, capture_output=True, text=True, env=env)
    out = done.stdout + done.stderr
    boot2 = os.path.join(ashita, "config", "boot", "xiforever2.ini")
    check(os.path.isfile(boot2), "the second boot file is made")
    text = open(boot2, newline="").read() if os.path.isfile(boot2) else ""
    check("--user player2" in text and "first-secret" not in text and "script = dualbox.txt" in text, "it logs in as the second account and runs dualbox.txt")
    first = open(os.path.join(ashita, "config", "boot", "xiforever.ini"), newline="").read()
    check("--user player1 --pass first-secret" in first and "script = default.txt" in first, "the first boot file is untouched")
    script = open(os.path.join(ashita, "scripts", "dualbox.txt")).read() if os.path.isfile(os.path.join(ashita, "scripts", "dualbox.txt")) else ""
    check("/load addons" in script and "/addon load autobot" in script and "/addon load xiui" in script, "dualbox.txt loads the add-ons plugin, AutoBot and XIUI")
    cfg = json.load(open(os.path.join(kit, "config.json")))
    check(cfg.get("ashita_boot2") == "xiforever2.ini" and cfg.get("game_user2") == "player2" and str(cfg.get("game_pass2", "")).startswith("p2-"),
          "config.json has the three new settings")
    check(cfg.get("game_pass2", "") not in out, "the new password is not printed")
    check("already in your Ashita folder" in out and "Could not download AutoBot" not in out, "no download is tried when AutoBot is there")
    notes = [line for line in out.splitlines() if line.strip().startswith("!!")]
    check(len(notes) == 1 and done.returncode == 1, "the only problem is the database of this made-up kit: " + repr(notes))
    check("DUALBOX" in out or "problem" in out, "the last line names the DUALBOX button or the problem count")


with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=True)
    os.makedirs(os.path.join(kit, "mariadb", "bin"))                   # a real kit has the database server in a folder of this name
    done = subprocess.run([sys.executable, os.path.join(kit, "setup_dualbox.py"), "setup"], cwd=kit, capture_output=True, text=True,
                          env=dict(os.environ, PATH=""))
    out = done.stdout + done.stderr
    check("has no attribute" not in out, "a Python without the database driver: no \"module 'mariadb' has no attribute 'connect'\"")
    notes = [line for line in out.splitlines() if line.strip().startswith("!!")]
    check(len(notes) == 1, "one plain note about the account instead: " + repr(notes))


# ---------- 3. the launcher's own methods, cut out of launcher_gui.pyw ----------
section("the DUALBOX button (the real methods on a stand-in launcher)")
source = open(os.path.join(KIT, "launcher_gui.pyw"), encoding="utf-8").read()
tree = ast.parse(source)
wanted = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in ("setup_second", "start_second", "ensure_second_account"):
        wanted[node.name] = ast.get_source_segment(source, node)
check(set(wanted) == {"setup_second", "start_second", "ensure_second_account"}, "the three methods are in launcher_gui.pyw")
check("Open PowerShell, go to" not in source and "run:   python setup_dualbox.py setup" not in source,
      "no message sends the player to PowerShell with python any more")


class Boxes:
    def __init__(self, answer=True):
        self.answer, self.calls = answer, []

    def askyesno(self, title, text):
        self.calls.append(("ask", text))
        return self.answer

    def showinfo(self, title, text):
        self.calls.append(("info", text))

    def showerror(self, title, text):
        self.calls.append(("error", text))

    def kinds(self):
        return [kind for kind, _text in self.calls]


def launcher(kit, ashita, boxes, running=True, windows=1):
    """A stand-in for the launcher window with the two real methods on it."""
    core_real = load(kit, "launcher_core")
    core = types.SimpleNamespace(py_cmd=core_real.py_cmd, NO_WINDOW=getattr(core_real, "NO_WINDOW", 0), load_config=core_real.load_config,
                                 is_running=lambda name: running, count_running=lambda name: windows)
    space = {"os": os, "subprocess": subprocess, "core": core, "messagebox": boxes, "HERE": kit, "LOGS": os.path.join(kit, "logs")}
    exec("class App:\n" + "\n".join("    " + line if line else line for line in "\n\n".join(wanted[name] for name in sorted(wanted)).splitlines()), space)
    app = space["App"].__new__(space["App"])
    app.cfg = {"ashita_boot": "xiforever.ini"}                          # the copy the launcher read at its start: no second window yet
    app.ashita, app.running, app.said, app.launched, app.second_scripts = ashita, running, [], [], "old list"
    app.say = app.said.append
    app.update_idletasks = lambda: None
    app.launch_extra = lambda boot, log: app.launched.append((boot, log))
    return app


old_path = list(sys.path)
with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=True)
    sys.path.insert(0, kit)                                             # start_second imports setup_dualbox, as in the real launcher
    sys.modules.pop("setup_dualbox", None)

    boxes = Boxes(answer=False)
    app = launcher(kit, ashita, boxes)
    app.start_second()
    check(boxes.kinds() == ["ask"] and app.launched == [] and not os.path.exists(os.path.join(ashita, "config", "boot", "xiforever2.ini")),
          "answering No: nothing is set up and no window opens")
    check("python" not in boxes.calls[0][1].lower() and "powershell" not in boxes.calls[0][1].lower(), "the question does not mention PowerShell or python")
    check("character creation" in boxes.calls[0][1], "the question says the second window needs a character of its own")

    boxes = Boxes(answer=True)
    app = launcher(kit, ashita, boxes)
    app.start_second()
    check(os.path.isfile(os.path.join(ashita, "config", "boot", "xiforever2.ini")), "answering Yes: the second boot file is made")
    check(app.launched == [("xiforever2.ini", "ashita2.log")], "and the second window is opened right after: " + repr(app.launched))
    check(app.cfg.get("ashita_boot2") == "xiforever2.ini" and app.cfg.get("game_user2") == "player2" and app.cfg.get("game_pass2"),
          "the launcher takes the three new settings over")
    check(boxes.kinds() == ["ask", "info"] and "!!" in boxes.calls[1][1], "the setup's one note (the made-up database) is shown, not hidden")
    check(app.second_scripts is None, "the Addons page reads the second window's list again")
    log = os.path.join(kit, "logs", "dualbox-setup.log")
    check(os.path.isfile(log) and "The second boot file" in open(log).read(), "what the setup printed is kept in logs/dualbox-setup.log")
    check(app.cfg.get("game_pass2", "x") not in open(log).read() and all(app.cfg.get("game_pass2", "x") not in text for _k, text in boxes.calls),
          "the new password is in no message and not in the log")

    boxes = Boxes(answer=True)
    app2 = launcher(kit, ashita, boxes)
    app2.start_second()
    check(boxes.kinds() == [] and app2.launched == [("xiforever2.ini", "ashita2.log")], "next start of the launcher: no question, the window just opens")

    boxes = Boxes(answer=True)
    app3 = launcher(kit, ashita, boxes, running=False)
    app3.start_second()
    check(boxes.kinds() == ["info"] and "PLAY first" in boxes.calls[0][1] and app3.launched == [], "without PLAY: still asks for PLAY first")

    boxes = Boxes(answer=True)
    app4 = launcher(kit, ashita, boxes, windows=2)
    app4.start_second()
    check(boxes.kinds() == ["info"] and "already open" in boxes.calls[0][1] and app4.launched == [], "a second window already open: said so")
    sys.path[:] = old_path

# ---------- 4. the second account is made sure of at every click ----------
section("the second account (a stand-in database)")


class FakeDb:
    """The accounts table, as far as ensure_account uses it."""
    def __init__(self, rows):
        self.rows, self.commits, self.closed, self.statements = rows, 0, 0, []

    def cursor(self):
        db = self

        class Cursor:
            description = [("id",), ("login",), ("password",)]

            def execute(self, sql, params=()):
                db.statements.append(sql.split()[0])
                self.result = None
                if sql.startswith("SELECT id FROM accounts WHERE login"):
                    found = [r for r in db.rows if r["login"] == params[0]]
                    self.result = (found[0]["id"],) if found else None
                elif sql.startswith("SELECT * FROM accounts WHERE login"):
                    found = [r for r in db.rows if r["login"] == params[0]]
                    self.result = (found[0]["id"], found[0]["login"], found[0]["password"]) if found else None
                elif sql.startswith("SELECT MAX(id)"):
                    self.result = (max(r["id"] for r in db.rows if r["id"] < 21000000),)
                elif sql.startswith("INSERT INTO accounts"):
                    db.rows.append(dict(zip(("id", "login", "password"), params)))
                else:
                    raise AssertionError("unexpected statement: " + sql)

            def fetchone(self):
                return self.result

            def close(self):
                pass
        return Cursor()

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed += 1


with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=True)
    sys.path.insert(0, kit)
    sys.modules.pop("setup_dualbox", None)
    import setup_dualbox as real_setup                                  # the made-up kit's copy of the real file
    # Celaria's state: the setup ran with a Python of its own, so everything is there except the account
    subprocess.run([sys.executable, os.path.join(kit, "setup_dualbox.py"), "setup"], cwd=kit, capture_output=True, text=True, env=dict(os.environ, PATH=""))
    pass2 = json.load(open(os.path.join(kit, "config.json")))["game_pass2"]

    db = FakeDb([{"id": 1000, "login": "player1", "password": "plain-first"}, {"id": 21000005, "login": "bot5", "password": "x"}])
    real_setup.connect = lambda cfg: db
    boxes = Boxes(answer=True)
    app = launcher(kit, ashita, boxes)
    app.cfg["game_user"] = "player1"
    app.start_second()
    made = [r for r in db.rows if r["login"] == "player2"]
    check(len(made) == 1 and made[0]["id"] == 1001 and made[0]["password"] == pass2, "a missing second account is made at the click (id below the bot accounts)")
    check(db.commits == 1 and db.closed == 1, "it is saved and the connection is closed")
    check(boxes.kinds() == [] and app.launched == [("xiforever2.ini", "ashita2.log")], "no question is asked and the window opens")

    before = [dict(r) for r in db.rows]
    app = launcher(kit, ashita, Boxes())
    app.start_second()
    check(db.rows == before and db.statements.count("INSERT") == 1, "an account that exists is left alone at the next click")

    def broken(cfg):
        raise RuntimeError("no database")
    real_setup.connect = broken
    app = launcher(kit, ashita, Boxes())
    app.start_second()
    check(app.launched == [("xiforever2.ini", "ashita2.log")], "the database cannot be asked: the window still opens")

    calls = []
    real_setup.connect = lambda cfg: calls.append(1) or db
    app = launcher(kit, ashita, Boxes())
    app.cfg = {"ashita_boot": "xiforever.ini"}
    check(app.ensure_second_account() is False and calls == [], "no second account in the settings: the database is not asked")
    sys.path[:] = old_path
    sys.modules.pop("setup_dualbox", None)

with tempfile.TemporaryDirectory() as root:
    kit, ashita = make_kit(root, autobot=True, script=False)            # the setup program is missing
    sys.modules.pop("setup_dualbox", None)
    boxes = Boxes(answer=True)
    app = launcher(kit, ashita, boxes)
    app.start_second()
    check(boxes.kinds() == ["ask", "error"] and app.launched == [], "the setup fails: an error box, no window")
    check("dualbox-setup.log" in boxes.calls[-1][1], "the error box names the log file")
    check(any("not set up" in line for line in app.said), "the launcher's status line says it was not set up")

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
