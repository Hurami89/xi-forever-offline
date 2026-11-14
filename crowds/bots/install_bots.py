"""Installs the bot players (steps 4.1 + 4.2: the roster) on the FFXI Offline server.

  python install_bots.py            install / update (safe to run again)
  python install_bots.py --undo     stop loading it (comments the init.txt lines; rebuild again afterwards)
  python install_bots.py --status

It copies bots.cpp (C++, needs a rebuild), bots.lua and bots_life.lua to server\\modules\\custom, lists bots.cpp
and bots.lua in modules\\init.txt (backup init.txt.before-bots), updates the crowd files (they make room for the
bots and ignore them), and adds "Bot players", "Bot roster" and "Bots online" to the launcher's Rates page
(backups *.before-bots). Your squad mates are not touched.
After installing: rebuild with -Reconfigure (a new .cpp file), then STOP and PLAY.
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))   # ...\FFXISOLO (this file is in FFXISOLO\crowds\bots)
LINES = ["custom/cpp/bots.cpp", "custom/lua/bots.lua"]
COMMENT = "# Bot players (step 4): real characters with no game window (bots.cpp needs a rebuild)"


def server_dir():
    try:
        with open(os.path.join(KIT, "config.json"), encoding="utf-8-sig") as f:
            return json.load(f).get("server_dir") or r"C:\ffxi-local\server"
    except (OSError, ValueError):
        return r"C:\ffxi-local\server"


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def register(server):
    path = os.path.join(server, "modules", "init.txt")
    text = read(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    stripped = [l.strip() for l in lines]
    changed = False
    for entry in LINES:
        if entry in stripped:
            continue
        if "# " + entry in stripped:
            lines[stripped.index("# " + entry)] = entry
            changed = True
            continue
        at = len(lines)
        for i, l in enumerate(lines):
            if l.strip() == "custom/late":
                at = i
                while at > 0 and lines[at - 1].strip().startswith("#"):
                    at -= 1
                break
        block = ([COMMENT] if COMMENT not in lines else []) + [entry]
        if block[0] == COMMENT:
            block.append("")
        lines[at:at] = block
        stripped = [l.strip() for l in lines]
        changed = True
    if not changed:
        return "modules/init.txt: already loads the bot players"
    backup = path + (".before-growth" if marker else ".before-bots")
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    write(path, nl.join(lines))
    return "modules/init.txt: bot players added (backup init.txt.before-bots)"


def unregister(server):
    path = os.path.join(server, "modules", "init.txt")
    text = read(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    n = 0
    for i, l in enumerate(lines):
        if l.strip() in LINES:
            lines[i] = "# " + l.strip()
            n += 1
    write(path, nl.join(lines))
    return f"modules/init.txt: {n} bot line(s) switched off. Rebuild (rebuild.ps1 -Reconfigure), then STOP and PLAY."


# Launcher: CONFIG > Rates > "Bot players" / "Bot roster" / "Bots online" (written to bots_config.lua at every PLAY)
MARKER = "bots_online"
CORE_PATCHES = [
    ('RATE_DEFAULTS.update({"crowds_field": True, "crowds_field_parties": 1})   # field parties (crowds_field.lua)\n',
     'RATE_DEFAULTS.update({"bots": True, "bots_roster": 100, "bots_online": 50})   # bot players (bots.lua, bots_life.lua)\n',
     "after"),
    ('                rates["crowds_field_parties"] = max(0, min(3, int(saved["crowds_field_parties"])))\n'
     '            except (TypeError, ValueError):\n'
     '                pass\n',
     '        if "bots" in saved:\n'
     '            rates["bots"] = bool(saved["bots"])\n'
     '        for key, lo, hi in (("bots_roster", 0, 600), ("bots_online", 0, 550)):\n'
     '            if key in saved:\n'
     '                try:\n'
     '                    rates[key] = max(lo, min(hi, int(saved[key])))\n'
     '                except (TypeError, ValueError):\n'
     '                    pass\n',
     "after"),
    ('                         ("crowds_field", True), ("crowds_field_parties", 1)):\n',
     '                         ("crowds_field", True), ("crowds_field_parties", 1),\n'
     '                         ("bots", True), ("bots_roster", 100), ("bots_online", 50)):\n',
     "replace"),
    ('            "true" if rates.get("crowds_field", True) else "false", max(0, min(3, int(rates.get("crowds_field_parties", 1) or 0)))))\n',
     '    with open(os.path.join(module_dir, "bots_config.lua"), "w", encoding="utf-8", newline="\\n") as f:\n'
     '        f.write("-- Written by the FFXI Solo launcher (Rates tab). Do not edit: it is rewritten every launch.\\n")\n'
     '        f.write("return { enabled = %s, roster = %d, online = %d }\\n" % (\n'
     '            "true" if rates.get("bots", True) else "false", max(0, min(600, int(rates.get("bots_roster", 100) or 0))),\n'
     '            max(0, min(550, int(rates.get("bots_online", 50) or 0)))))\n',
     "after"),
]
GUI_PATCHES = [
    ('        ttk.Spinbox(inner, from_=0, to=3, increment=1, textvariable=self.crowds_field_parties, width=8).grid(row=n + 10, column=1, padx=6, pady=2)\n',
     '        self.bots = tk.BooleanVar(value=rates.get("bots", True))\n'
     '        tk.Checkbutton(inner, text="Bot players: real characters (no game window) living in the nation towns - /sea, /check, invite them",\n'
     '                       variable=self.bots, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,\n'
     '                       wraplength=520, justify="left").grid(row=n + 11, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n'
     '        tk.Label(inner, text="Bot roster (characters, 0-600)", bg=BG, fg=FG, anchor="w", width=38).grid(\n'
     '            row=n + 12, column=0, sticky="w", padx=6, pady=2)\n'
     '        self.bots_roster = tk.StringVar(value=str(rates.get("bots_roster", 100)))\n'
     '        ttk.Spinbox(inner, from_=0, to=600, increment=50, textvariable=self.bots_roster, width=8).grid(row=n + 12, column=1, padx=6, pady=2)\n'
     '        tk.Label(inner, text="Bots online at a time (0-550)", bg=BG, fg=FG, anchor="w", width=38).grid(\n'
     '            row=n + 13, column=0, sticky="w", padx=6, pady=2)\n'
     '        self.bots_online = tk.StringVar(value=str(rates.get("bots_online", 50)))\n'
     '        ttk.Spinbox(inner, from_=0, to=550, increment=10, textvariable=self.bots_online, width=8).grid(row=n + 13, column=1, padx=6, pady=2)\n',
     "after"),
    ('            rates["crowds_field_parties"] = 1\n',
     '        rates["bots"] = bool(self.bots.get())\n'
     '        for key, var, lo, hi, default in (("bots_roster", self.bots_roster, 0, 600, 100), ("bots_online", self.bots_online, 0, 550, 50)):\n'
     '            try:\n'
     '                rates[key] = max(lo, min(hi, int(float(var.get()))))\n'
     '            except (TypeError, ValueError):\n'
     '                rates[key] = default\n',
     "after"),
]


# Launcher: "Bots grow while you are away" (off / realistic / fast), written to bots_config.lua as growth = '...'
GROWTH_MARKER = "bots_growth"
GROWTH_CORE_PATCHES = [
    ('RATE_DEFAULTS.update({"bots": True, "bots_roster": 100, "bots_online": 50})   # bot players (bots.lua, bots_life.lua)\n',
     'RATE_DEFAULTS.update({"bots_growth": "realistic"})   # bots grow while you are away (bots_growth.lua)\n',
     "after"),
    ('        f.write("return { enabled = %s, roster = %d, online = %d }\\n" % (\n'
     '            "true" if rates.get("bots", True) else "false", max(0, min(600, int(rates.get("bots_roster", 100) or 0))),\n'
     '            max(0, min(550, int(rates.get("bots_online", 50) or 0)))))\n',
     '        growth = rates.get("bots_growth", "realistic")\n'
     '        growth = growth if growth in ("off", "realistic", "fast") else "realistic"\n'
     '        f.write("return { enabled = %s, roster = %d, online = %d, growth = \'%s\' }\\n" % (\n'
     '            "true" if rates.get("bots", True) else "false", max(0, min(600, int(rates.get("bots_roster", 100) or 0))),\n'
     '            max(0, min(550, int(rates.get("bots_online", 50) or 0))), growth))\n',
     "replace"),
    ('        if "bots" in saved:\n'
     '            rates["bots"] = bool(saved["bots"])\n',
     '        if saved.get("bots_growth") in ("off", "realistic", "fast"):\n'
     '            rates["bots_growth"] = saved["bots_growth"]\n',
     "after"),
    ('                         ("bots", True), ("bots_roster", 100), ("bots_online", 50)):\n',
     '                         ("bots", True), ("bots_roster", 100), ("bots_online", 50), ("bots_growth", "realistic")):\n',
     "replace"),
]
GROWTH_GUI_PATCHES = [
    ('        ttk.Spinbox(inner, from_=0, to=550, increment=10, textvariable=self.bots_online, width=8).grid(row=n + 13, column=1, padx=6, pady=2)\n',
     '        tk.Label(inner, text="Bots grow while you are away", bg=BG, fg=FG, anchor="w", width=38).grid(row=n + 14, column=0, sticky="w", padx=6, pady=2)\n'
     '        self.bots_growth = tk.StringVar(value=rates.get("bots_growth", "realistic"))\n'
     '        ttk.Combobox(inner, values=["off", "realistic", "fast"], state="readonly", textvariable=self.bots_growth,\n'
     '                     width=8).grid(row=n + 14, column=1, padx=6, pady=2)\n',
     "after"),
    ('        rates["bots"] = bool(self.bots.get())\n',
     '        growth = self.bots_growth.get()\n'
     '        rates["bots_growth"] = growth if growth in ("off", "realistic", "fast") else "realistic"\n',
     "after"),
]


def patch_file(path, patches, label, marker=None):
    """Applies every patch or none."""
    text = read(path)
    if (marker or MARKER) in text:
        return f"{label}: already has the {'growth' if marker else 'bot'} settings"
    crlf = "\r\n" in text
    work = text.replace("\r\n", "\n")
    for anchor, add, where in patches:
        count = work.count(anchor)
        if count != 1:
            return f"{label}: NOT changed - this launcher version looks different than expected (a line was found {count} times)."
        if where == "replace":
            work = work.replace(anchor, add, 1)
        else:
            work = work.replace(anchor, anchor + add, 1)
    if crlf:
        work = work.replace("\n", "\r\n")
    backup = path + (".before-growth" if marker else ".before-bots")
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    write(path, work)
    return f"{label}: {'growth' if marker else 'bot'} settings added (backup {os.path.basename(backup)})"


def write_config(server, kit):
    rates = {}
    try:
        with open(os.path.join(kit, "rates.json"), encoding="utf-8-sig") as f:
            rates = json.load(f)
    except (OSError, ValueError):
        pass
    enabled = bool(rates.get("bots", True))
    try:
        roster = max(0, min(600, int(rates.get("bots_roster", 100))))
        online = max(0, min(550, int(rates.get("bots_online", 50))))
    except (TypeError, ValueError):
        roster, online = 100, 50
    growth = rates.get("bots_growth", "realistic")
    growth = growth if growth in ("off", "realistic", "fast") else "realistic"
    path = os.path.join(server, "modules", "custom", "lua", "bots_config.lua")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- Written by the FFXI Solo launcher (Rates tab). Do not edit: it is rewritten every launch.\n")
        f.write("return { enabled = %s, roster = %d, online = %d, growth = '%s' }\n" % ("true" if enabled else "false", roster, online, growth))
    return f"bots_config.lua: {'on' if enabled else 'off'}, roster {roster}, {online} online at a time, growth {growth}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--server", default=None)
    ap.add_argument("--kit", default=KIT)
    args = ap.parse_args()
    server = args.server or server_dir()
    if args.undo:
        print(unregister(server))
        return 0
    if args.status:
        stripped = [l.strip() for l in read(os.path.join(server, "modules", "init.txt")).splitlines()]
        for entry in LINES:
            print(f"{entry:<22}: {'loaded' if entry in stripped else 'not loaded'}, file {'present' if os.path.exists(os.path.join(server, 'modules', entry)) else 'MISSING'}")
        return 0
    for name, sub in (("bots.cpp", "cpp"), ("bots.lua", "lua"), ("bots_life.lua", "lua"), ("bots_hunt.lua", "lua"), ("bots_craft.lua", "lua"), ("bots_quests.lua", "lua"), ("bots_chat.lua", "lua"), ("bots_party.lua", "lua"), ("bots_jobs.lua", "lua"), ("bots_ls.lua", "lua"), ("bots_growth.lua", "lua"), ("bots_gear.lua", "lua"), ("bots_bcnm.lua", "lua"), ("bots_invite.lua", "lua")):
        dest = os.path.join(server, "modules", "custom", sub)
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(os.path.join(HERE, name), os.path.join(dest, name))
        print(f"copied {name} to modules/custom/{sub}")
    for name in ("crowds.lua", "crowds_chat.lua", "crowds_field.lua"):   # make room for the bots, ignore them as "players"
        src = os.path.join(os.path.dirname(HERE), name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(server, "modules", "custom", "lua", name))
    print("updated crowds.lua, crowds_chat.lua, crowds_field.lua (bots take crowd places; they do not count as you)")
    for name, patches in (("launcher_core.py", CORE_PATCHES), ("launcher_gui.pyw", GUI_PATCHES)):
        p = os.path.join(args.kit, name)
        print(patch_file(p, patches, name) if os.path.exists(p) else f"{name}: not found - skipped")
    for name, patches in (("launcher_core.py", GROWTH_CORE_PATCHES), ("launcher_gui.pyw", GROWTH_GUI_PATCHES)):
        p = os.path.join(args.kit, name)
        print(patch_file(p, patches, name, GROWTH_MARKER) if os.path.exists(p) else f"{name}: not found - skipped")
    print(write_config(server, args.kit))
    import subprocess
    build = subprocess.run([sys.executable, os.path.join(HERE, "build_bots_craft.py"), "--server", server, "--kit", args.kit])
    if build.returncode != 0:
        print("build_bots_craft.py failed (see above): the bots will not craft until it works.")
    gear = subprocess.run([sys.executable, os.path.join(HERE, "build_bots_gear.py"), "--server", server, "--kit", args.kit])
    if gear.returncode != 0:
        print("build_bots_gear.py failed (see above): the bots will keep their starting gear until it works.")
    print(register(server))
    print("")
    print("Next: close the launcher, rebuild with -Reconfigure, then open the launcher and PLAY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
