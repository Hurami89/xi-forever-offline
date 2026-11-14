"""Installs the ambient crowds (player-like adventurers in towns) on the FFXI Offline server.

  python install_crowds.py            install / update (safe to run again)
  python install_crowds.py --status   show what is installed
  python install_crowds.py --undo     switch the module off in modules/init.txt (files are kept)

What it does:
  1. copies crowds.lua to <server>/modules/custom/lua/
  2. builds <server>/modules/custom/lua/crowds_data.lua (outfits + spots) from the server's own files (build_crowds_data.py)
  3. adds the line custom/lua/crowds.lua to <server>/modules/init.txt (backup init.txt.before-crowds)
  4. adds the "Ambient crowds" switch and "Crowd size" to the launcher's Rates page (backups *.before-crowds)
  5. writes crowds_config.lua from your current launcher settings
No C++ change: no rebuild. Restart the server (STOP, then PLAY) to load it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # ...\FFXISOLO\crowds
KIT = os.path.dirname(HERE)                                 # ...\FFXISOLO
INIT_LINE = "custom/lua/crowds.lua"
INIT_COMMENT = "# Ambient crowds: player-like adventurers in towns (switch and size: launcher, CONFIG > Rates)"
MARKER = "crowds_per_zone"

CORE_PATCHES = [
    # (anchor, text, where)  where = "after" | "before"
    ('                      "defaults_version": 2})\n',
     'RATE_DEFAULTS.update({"crowds": True, "crowds_per_zone": 30})   # ambient crowds (modules/custom/lua/crowds.lua)\n',
     "after"),
    ('def load_rates(here):\n',
     'def clean_crowd_size(value):\n'
     '    """Ambient crowds: adventurers per area, 0-40 (anything else falls back to 30)."""\n'
     '    try:\n'
     '        return max(0, min(40, int(round(float(str(value).strip().replace(",", "."))))))\n'
     '    except ValueError:\n'
     '        return 30\n'
     '\n'
     '\n',
     "before"),
    ('        rates["claim_shield"] = False  # the claim shield stays off on this solo server (its switch was removed)\n',
     '        if "crowds" in saved:\n'
     '            rates["crowds"] = bool(saved["crowds"])\n'
     '        if "crowds_per_zone" in saved:\n'
     '            rates["crowds_per_zone"] = clean_crowd_size(saved["crowds_per_zone"])\n',
     "after"),
    ('    out["conquest_sim"] = rates.get("conquest_sim", True)\n',
     '    out["crowds"] = rates.get("crowds", True)\n'
     '    out["crowds_per_zone"] = rates.get("crowds_per_zone", 30)\n',
     "after"),
    ('    # Fast travel from the Home Point crystals: always on, whatever an update did to init.txt\n',
     '    # Ambient crowds (modules/custom/lua/crowds.lua) read their switch and size from this small file\n'
     '    try:\n'
     '        module_dir = os.path.join(server_dir, "modules", "custom", "lua")\n'
     '        os.makedirs(module_dir, exist_ok=True)\n'
     '        with open(os.path.join(module_dir, "crowds_config.lua"), "w", encoding="utf-8", newline="\\n") as f:\n'
     '            f.write("-- Written by the FFXI Solo launcher (Rates tab). Do not edit: it is rewritten every launch.\\n")\n'
     '            f.write("return { enabled = %s, per_zone = %d }\\n" % ("true" if rates.get("crowds", True) else "false",\n'
     '                                                             clean_crowd_size(rates.get("crowds_per_zone", 30))))\n'
     '    except OSError as problem:\n'
     '        messages.append(f"crowds_config.lua: could not be written ({problem})")\n',
     "before"),
]

# Phase 2 (chat): added on top of the crowd settings above
CHAT_MARKER = "crowds_chat_amount"
CORE_CHAT_PATCHES = [
    ('   # ambient crowds (modules/custom/lua/crowds.lua)\n',
     'RATE_DEFAULTS.update({"crowds_chat": True, "crowds_chat_amount": "normal", "crowds_chat_ai": True})   # crowd chat (crowds_chat.lua)\n',
     "after"),
    ('def clean_crowd_size(value):\n',
     'def write_crowds_config(server_dir, rates):\n'
     '    """Ambient crowds + chat settings for modules/custom/lua/crowds.lua (rewritten every launch)."""\n'
     '    amount = rates.get("crowds_chat_amount", "normal")\n'
     '    amount = amount if amount in ("quiet", "normal", "busy") else "normal"\n'
     '    module_dir = os.path.join(server_dir, "modules", "custom", "lua")\n'
     '    os.makedirs(module_dir, exist_ok=True)\n'
     '    with open(os.path.join(module_dir, "crowds_config.lua"), "w", encoding="utf-8", newline="\\n") as f:\n'
     '        f.write("-- Written by the FFXI Solo launcher (Rates tab). Do not edit: it is rewritten every launch.\\n")\n'
     '        f.write("return { enabled = %s, per_zone = %d, chat = %s, chat_amount = \'%s\', chat_ai = %s }\\n" % (\n'
     '            "true" if rates.get("crowds", True) else "false", clean_crowd_size(rates.get("crowds_per_zone", 30)),\n'
     '            "true" if rates.get("crowds_chat", True) else "false", amount,\n'
     '            "true" if rates.get("crowds_chat_ai", True) else "false"))\n'
     '\n'
     '\n',
     "before"),
    ('            rates["crowds_per_zone"] = clean_crowd_size(saved["crowds_per_zone"])\n',
     '        for key in ("crowds_chat", "crowds_chat_ai"):\n'
     '            if key in saved:\n'
     '                rates[key] = bool(saved[key])\n'
     '        if saved.get("crowds_chat_amount") in ("quiet", "normal", "busy"):\n'
     '            rates["crowds_chat_amount"] = saved["crowds_chat_amount"]\n',
     "after"),
    ('    out["crowds"] = rates.get("crowds", True)\n',
     '    for key, default in (("crowds_chat", True), ("crowds_chat_amount", "normal"), ("crowds_chat_ai", True)):\n'
     '        out[key] = rates.get(key, default)\n',
     "after"),
    ('        messages.append(f"crowds_config.lua: could not be written ({problem})")\n',
     '    try:\n'
     '        write_crowds_config(server_dir, rates)   # the full file, with the chat settings\n'
     '    except OSError as problem:\n'
     '        messages.append(f"crowds_config.lua (chat): could not be written ({problem})")\n',
     "after"),
]
GUI_CHAT_PATCHES = [
    ('        ttk.Spinbox(inner, from_=0, to=40, increment=1, textvariable=self.crowds_size, width=8).grid(row=n + 5, column=1, padx=6, pady=2)\n',
     '        self.crowds_chat = tk.BooleanVar(value=rates.get("crowds_chat", True))\n'
     '        tk.Checkbutton(inner, text="Crowd chat: party-wanted shouts, people selling crafted items, small talk near you",\n'
     '                       variable=self.crowds_chat, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,\n'
     '                       wraplength=520, justify="left").grid(row=n + 6, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n'
     '        tk.Label(inner, text="Chat amount", bg=BG, fg=FG, anchor="w", width=38).grid(row=n + 7, column=0, sticky="w", padx=6, pady=2)\n'
     '        self.crowds_chat_amount = tk.StringVar(value=rates.get("crowds_chat_amount", "normal"))\n'
     '        ttk.Combobox(inner, values=["quiet", "normal", "busy"], state="readonly", textvariable=self.crowds_chat_amount,\n'
     '                     width=8).grid(row=n + 7, column=1, padx=6, pady=2)\n'
     '        self.crowds_chat_ai = tk.BooleanVar(value=rates.get("crowds_chat_ai", True))\n'
     '        tk.Checkbutton(inner, text="AI chatter: your local Ollama model writes some of the small talk (runs quietly in the background)",\n'
     '                       variable=self.crowds_chat_ai, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,\n'
     '                       wraplength=520, justify="left").grid(row=n + 8, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n',
     "after"),
    ('        rates["crowds_per_zone"] = core.clean_crowd_size(self.crowds_size.get())\n',
     '        rates["crowds_chat"] = bool(self.crowds_chat.get())\n'
     '        amount = self.crowds_chat_amount.get()\n'
     '        rates["crowds_chat_amount"] = amount if amount in ("quiet", "normal", "busy") else "normal"\n'
     '        rates["crowds_chat_ai"] = bool(self.crowds_chat_ai.get())\n',
     "after"),
    ('        self.start_squad_chat()\n',
     '        self.start_crowd_chat_ai()\n',
     "after"),
    ('    def start_ah_sim(self):\n',
     '    def start_crowd_chat_ai(self):\n'
     '        # Crowd chat AI helper (crowds/crowd_chat_ai.py): keeps a pool of AI-written small talk for the town crowds.\n'
     '        script = os.path.join(HERE, "crowds", "crowd_chat_ai.py")\n'
     '        rates = self.rates\n'
     '        if not (rates.get("crowds", True) and rates.get("crowds_chat", True) and rates.get("crowds_chat_ai", True)) or not os.path.exists(script):\n'
     '            return\n'
     '        try:\n'
     '            log = open(os.path.join(LOGS, "crowd-chat-ai.log"), "wb")\n'
     '            self.logfiles.append(log)\n'
     '            self.crowd_ai_proc = subprocess.Popen([sys.executable, "-u", script], cwd=os.path.dirname(script), stdout=log,\n'
     '                                                  stderr=subprocess.STDOUT, creationflags=core.NO_WINDOW)\n'
     '            self.say("Crowd chat AI helper started.")\n'
     '        except Exception as e:\n'
     '            self.say(f"Crowd chat AI helper did not start: {e}")\n'
     '\n',
     "before"),
    ('        ah = getattr(self, "ah_proc", None)\n',
     '        crowd_ai = getattr(self, "crowd_ai_proc", None)\n'
     '        if crowd_ai is not None:\n'
     '            try:\n'
     '                if crowd_ai.poll() is None:\n'
     '                    crowd_ai.terminate()\n'
     '            except Exception:\n'
     '                pass\n'
     '            self.crowd_ai_proc = None\n',
     "before"),
]

# Phase 3 (field parties): added on top of the chat settings
FIELD_MARKER = "crowds_field_parties"
CORE_FIELD_PATCHES = [
    ('   # crowd chat (crowds_chat.lua)\n',
     'RATE_DEFAULTS.update({"crowds_field": True, "crowds_field_parties": 1})   # field parties (crowds_field.lua)\n',
     "after"),
    ('            rates["crowds_chat_amount"] = saved["crowds_chat_amount"]\n',
     '        if "crowds_field" in saved:\n'
     '            rates["crowds_field"] = bool(saved["crowds_field"])\n'
     '        if "crowds_field_parties" in saved:\n'
     '            try:\n'
     '                rates["crowds_field_parties"] = max(0, min(3, int(saved["crowds_field_parties"])))\n'
     '            except (TypeError, ValueError):\n'
     '                pass\n',
     "after"),
    ('    for key, default in (("crowds_chat", True), ("crowds_chat_amount", "normal"), ("crowds_chat_ai", True)):\n',
     '    for key, default in (("crowds_chat", True), ("crowds_chat_amount", "normal"), ("crowds_chat_ai", True),\n'
     '                         ("crowds_field", True), ("crowds_field_parties", 1)):\n',
     "replace"),
    ('chat_ai = %s }\\n" % (\n',
     'chat_ai = %s, field = %s, field_parties = %d }\\n" % (\n',
     "replace"),
    ('            "true" if rates.get("crowds_chat_ai", True) else "false"))\n',
     '            "true" if rates.get("crowds_chat_ai", True) else "false",\n'
     '            "true" if rates.get("crowds_field", True) else "false", max(0, min(3, int(rates.get("crowds_field_parties", 1) or 0)))))\n',
     "replace"),
]
GUI_FIELD_PATCHES = [
    ('                       wraplength=520, justify="left").grid(row=n + 8, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n',
     '        self.crowds_field = tk.BooleanVar(value=rates.get("crowds_field", True))\n'
     '        tk.Checkbutton(inner, text="Field parties: adventurer parties camping and fighting monsters out in the field (away from you)",\n'
     '                       variable=self.crowds_field, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,\n'
     '                       wraplength=520, justify="left").grid(row=n + 9, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n'
     '        tk.Label(inner, text="Field parties per area (0-3)", bg=BG, fg=FG, anchor="w", width=38).grid(\n'
     '            row=n + 10, column=0, sticky="w", padx=6, pady=2)\n'
     '        self.crowds_field_parties = tk.StringVar(value=str(rates.get("crowds_field_parties", 1)))\n'
     '        ttk.Spinbox(inner, from_=0, to=3, increment=1, textvariable=self.crowds_field_parties, width=8).grid(row=n + 10, column=1, padx=6, pady=2)\n',
     "after"),
    ('        rates["crowds_chat_ai"] = bool(self.crowds_chat_ai.get())\n',
     '        rates["crowds_field"] = bool(self.crowds_field.get())\n'
     '        try:\n'
     '            rates["crowds_field_parties"] = max(0, min(3, int(float(self.crowds_field_parties.get()))))\n'
     '        except (TypeError, ValueError):\n'
     '            rates["crowds_field_parties"] = 1\n',
     "after"),
]

GUI_PATCHES = [
    ('                       wraplength=520, justify="left").grid(row=n + 3, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n',
     '        self.crowds = tk.BooleanVar(value=rates.get("crowds", True))\n'
     '        tk.Checkbutton(inner, text="Ambient crowds: adventurers resting, shopping and walking around in towns and outposts",\n'
     '                       variable=self.crowds, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,\n'
     '                       wraplength=520, justify="left").grid(row=n + 4, column=0, columnspan=2, sticky="w", padx=6, pady=2)\n'
     '        tk.Label(inner, text="Crowd size (adventurers per area, 0-40)", bg=BG, fg=FG, anchor="w", width=38).grid(\n'
     '            row=n + 5, column=0, sticky="w", padx=6, pady=2)\n'
     '        self.crowds_size = tk.StringVar(value=str(rates.get("crowds_per_zone", 30)))\n'
     '        ttk.Spinbox(inner, from_=0, to=40, increment=1, textvariable=self.crowds_size, width=8).grid(row=n + 5, column=1, padx=6, pady=2)\n',
     "after"),
    ('        rates["conquest_sim"] = bool(self.conquest_sim.get())\n',
     '        rates["crowds"] = bool(self.crowds.get())\n'
     '        rates["crowds_per_zone"] = core.clean_crowd_size(self.crowds_size.get())\n',
     "after"),
]


WHAT = {MARKER: "crowd settings", CHAT_MARKER: "crowd chat settings", FIELD_MARKER: "field party settings"}
BACKUP = {MARKER: ".before-crowds", CHAT_MARKER: ".before-crowd-chat", FIELD_MARKER: ".before-crowd-field"}


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def patch_file(path, patches, label, marker=MARKER):
    """Applies every patch or none. Returns a message."""
    text = read(path)
    if marker in text:
        old = "walking around in town (Southern San d'Oria for now)"
        if old in text:   # first version's label
            write(path, text.replace(old, "walking around in towns and outposts"))
            return f"{label}: already has the crowd settings (label updated: towns and outposts)"
        return f"{label}: already has the {WHAT.get(marker, 'crowd settings')}"
    crlf = "\r\n" in text
    work = text.replace("\r\n", "\n")
    for anchor, add, where in patches:
        count = work.count(anchor)
        if count != 1:
            return f"{label}: NOT changed - this launcher version looks different than expected (a line was found {count} times)."
        if where == "replace":
            work = work.replace(anchor, add, 1)
        else:
            work = work.replace(anchor, anchor + add if where == "after" else add + anchor, 1)
    if crlf:
        work = work.replace("\n", "\r\n")
    backup = path + BACKUP.get(marker, ".before-crowds")
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    write(path, work)
    what = WHAT.get(marker, "crowd settings")
    return f"{label}: {what} added (backup {os.path.basename(backup)})"


def init_lines(server):
    path = os.path.join(server, "modules", "init.txt")
    return path, read(path)


def register(server):
    path, text = init_lines(server)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    active = [l.strip() for l in lines]
    if INIT_LINE in active:
        return "modules/init.txt: already loads crowds.lua"
    if "# " + INIT_LINE in active:
        lines[active.index("# " + INIT_LINE)] = INIT_LINE
        write(path, nl.join(lines))
        return "modules/init.txt: crowds.lua switched back on"
    # before the "Loaded LAST" block (custom/late must stay the last line)
    at = len(lines)
    for i, l in enumerate(lines):
        if l.strip() == "custom/late":
            at = i
            while at > 0 and lines[at - 1].strip().startswith("#"):
                at -= 1
            break
    block = [INIT_COMMENT, INIT_LINE, ""]
    lines[at:at] = block
    backup = path + ".before-crowds"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    write(path, nl.join(lines))
    return "modules/init.txt: crowds.lua added (backup init.txt.before-crowds)"


def unregister(server):
    path, text = init_lines(server)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    changed = False
    for i, l in enumerate(lines):
        if l.strip() == INIT_LINE:
            lines[i] = "# " + INIT_LINE
            changed = True
    if changed:
        write(path, nl.join(lines))
        return "modules/init.txt: crowds.lua switched off (line commented out). Restart the server."
    return "modules/init.txt: crowds.lua was not active"


def write_config(server, kit):
    rates = {}
    try:
        with open(os.path.join(kit, "rates.json"), "r", encoding="utf-8-sig") as f:
            rates = json.load(f)
    except (OSError, ValueError):
        pass
    enabled = bool(rates.get("crowds", True))
    try:
        size = max(0, min(40, int(rates.get("crowds_per_zone", 30))))
    except (TypeError, ValueError):
        size = 30
    chat = bool(rates.get("crowds_chat", True))
    amount = rates.get("crowds_chat_amount", "normal")
    amount = amount if amount in ("quiet", "normal", "busy") else "normal"
    chat_ai = bool(rates.get("crowds_chat_ai", True))
    fld = bool(rates.get("crowds_field", True))
    try:
        fparties = max(0, min(3, int(rates.get("crowds_field_parties", 1))))
    except (TypeError, ValueError):
        fparties = 1
    path = os.path.join(server, "modules", "custom", "lua", "crowds_config.lua")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- Written by the FFXI Solo launcher (Rates tab). Do not edit: it is rewritten every launch.\n")
        f.write("return { enabled = %s, per_zone = %d, chat = %s, chat_amount = '%s', chat_ai = %s, field = %s, field_parties = %d }\n"
                % ("true" if enabled else "false", size, "true" if chat else "false", amount, "true" if chat_ai else "false",
                   "true" if fld else "false", fparties))
    return (f"crowds_config.lua: {'on' if enabled else 'off'}, {size} per area, chat {'on' if chat else 'off'} ({amount}), "
            f"AI chatter {'on' if chat_ai else 'off'}, field parties {'on' if fld else 'off'} ({fparties} per area)")


def server_dir(kit):
    try:
        with open(os.path.join(kit, "config.json"), "r", encoding="utf-8-sig") as f:
            return json.load(f).get("server_dir") or r"C:\ffxi-local\server"
    except (OSError, ValueError):
        return r"C:\ffxi-local\server"


def status(server, kit):
    lua_dir = os.path.join(server, "modules", "custom", "lua")
    _, text = init_lines(server)
    active = [l.strip() for l in text.splitlines()]
    print("crowds.lua in modules/custom/lua :", "yes" if os.path.exists(os.path.join(lua_dir, "crowds.lua")) else "NO")
    print("crowds_data.lua                  :", "yes" if os.path.exists(os.path.join(lua_dir, "crowds_data.lua")) else "NO")
    print("loaded by modules/init.txt       :", "yes" if INIT_LINE in active else "NO")
    for name in ("launcher_core.py", "launcher_gui.pyw"):
        p = os.path.join(kit, name)
        text = read(p) if os.path.exists(p) else ""
        print(f"{name:<33}:", ("has the crowd settings" if MARKER in text else "NOT patched")
              + (" + chat" if CHAT_MARKER in text else " (no chat settings)")
              + (" + field parties" if FIELD_MARKER in text else " (no field party settings)"))
    cfg = os.path.join(lua_dir, "crowds_config.lua")
    print("crowds_config.lua                :", read(cfg).strip().splitlines()[-1] if os.path.exists(cfg) else "not written yet")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--server", default=None)
    ap.add_argument("--kit", default=KIT)
    args = ap.parse_args()
    kit = args.kit
    server = args.server or server_dir(kit)

    if args.status:
        status(server, kit)
        return 0
    if args.undo:
        print(unregister(server))
        return 0

    lua_dir = os.path.join(server, "modules", "custom", "lua")
    if not os.path.isdir(lua_dir):
        print("Server folder not found: " + lua_dir)
        return 1
    for name in ("crowds.lua", "crowds_chat.lua", "crowds_chat_data.lua", "crowds_field.lua"):
        shutil.copy2(os.path.join(HERE, name), os.path.join(lua_dir, name))
    print("copied crowds.lua, crowds_chat.lua, crowds_chat_data.lua, crowds_field.lua")
    build = subprocess.run([sys.executable, os.path.join(HERE, "build_crowds_data.py"), "--server", server])
    if build.returncode != 0:
        print("build_crowds_data.py failed (see above). Nothing else was changed.")
        return 1
    print(register(server))
    for name, patches, chat_patches, field_patches in (
            ("launcher_core.py", CORE_PATCHES, CORE_CHAT_PATCHES, CORE_FIELD_PATCHES),
            ("launcher_gui.pyw", GUI_PATCHES, GUI_CHAT_PATCHES, GUI_FIELD_PATCHES)):
        p = os.path.join(kit, name)
        if not os.path.exists(p):
            print(f"{name}: not found - skipped")
            continue
        print(patch_file(p, patches, name))
        print(patch_file(p, chat_patches, name, CHAT_MARKER))
        print(patch_file(p, field_patches, name, FIELD_MARKER))
    print(write_config(server, kit))
    print("")
    print("Done. No rebuild needed. Close and reopen the launcher, then STOP and PLAY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
