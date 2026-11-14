#!/usr/bin/env python3
"""Hides every Voidwatch NPC (Planar Rifts, Riftworn Pyxis chests, the Voidwatch Officer, the Atmacite Refiner...).

  python make_no_voidwatch.py            build the module from your server's own zone data and switch it on
  python make_no_voidwatch.py --undo     switch it off and remove it
  python make_no_voidwatch.py --status   say whether it is on and how many NPCs it hides

Why: Voidwatch is not implemented on this server, but its NPCs are in the zone data (each is tagged  content: voidwatch).  Rifts show up
in the field and do nothing. This reads your server's zone files, finds every NPC with that tag, and writes a small module that makes them
invisible when you zone in. It does not depend on how the server treats the tag, and it needs no rebuild: restart the server (STOP, PLAY).
Nothing in the zone data is edited, so server updates are not affected.
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = "custom/lua/no_voidwatch.lua"
MARKER = "-- Written by make_no_voidwatch.py"


def say(text=""):
    print(text, flush=True)


def find_voidwatch_npcs(zones_dir):
    """{zone id: [(npc id, name)]} for every NPC whose zone-data entry says  content: voidwatch.
    An NPC's id carries its zone: the zone number is bits 12-20 (so 17297502 belongs to zone 127, Behemoth's Dominion)."""
    found = {}
    for zone in sorted(os.listdir(zones_dir)):
        path = os.path.join(zones_dir, zone, "npcs.yaml")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
        current, block = None, []

        def flush():
            if current is None:
                return
            text = "\n".join(block)
            tag = re.search(r"^\s+content:\s*['\"]?([A-Za-z_]+)", text, re.M)
            if tag and tag.group(1).lower() == "voidwatch":
                name = re.search(r"^\s+display_name:\s*(.+?)\s*$", text, re.M)
                found.setdefault((current >> 12) & 0x1FF, []).append((current, name.group(1).strip("'\"") if name else "?"))

        for line in lines:
            m = re.match(r"^  (\d+):\s*$", line)
            if m:
                flush()
                current, block = int(m.group(1)), []
            else:
                block.append(line)
        flush()
    return found


def lua_text(found):
    rows = []
    for zone_id in sorted(found):
        ids = ", ".join(str(i) for i, _ in sorted(found[zone_id]))
        names = sorted({n for _, n in found[zone_id]})
        rows.append(f"    [{zone_id}] = {{ {ids} }},   -- {', '.join(names)}")
    total = sum(len(v) for v in found.values())
    return f"""{MARKER} from this server's own zone data: {total} Voidwatch NPCs in {len(found)} zones.
-- Voidwatch is not implemented here, so its NPCs only stand around doing nothing. This makes them invisible when you zone in.
-- Remove it with:  python make_no_voidwatch.py --undo
-----------------------------------
require('modules/module_utils')
-----------------------------------
local m = Module:new('no_voidwatch')

local HIDDEN =
{{
{chr(10).join(rows)}
}}

-- The server's own events hide NPCs with INVISIBLE (a note in starlight_celebration.lua says DISAPPEAR did not work there)
local function hide(zoneId)
    local hidden = xi.status.INVISIBLE or xi.status.DISAPPEAR
    for _, id in ipairs(HIDDEN[zoneId] or {{}}) do
        local npc = GetNPCByID(id)
        if npc then
            npc:setStatus(hidden)
        end
    end
end

m:addOverride('xi.player.onGameIn', function(player, firstLogin, zoning)
    super(player, firstLogin, zoning)

    local zoneId = player:getZoneID()
    if HIDDEN[zoneId] then
        hide(zoneId)
        if player.timer then
            player:timer(3000, function() hide(zoneId) end)    -- again a moment later, in case something shows them once the zone has started
        end
    end
end)

return m
"""


def paths(cfg):
    server = cfg["server_dir"]
    return (server, os.path.join(server, "data", "zones"), os.path.join(server, "modules", "init.txt"),
            os.path.join(server, "modules", "custom", "lua", "no_voidwatch.lua"))


def registered(init_text):
    """None if the entry is not in init.txt, False if it is there but switched off (commented), True if on."""
    m = re.search(r"(?m)^[ \t]*(#[ \t]*)?" + re.escape(ENTRY) + r"[ \t]*\r?$", init_text)
    if not m:
        return None
    return m.group(1) is None


def register(init_path):
    with open(init_path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()
    state = registered(text)
    if state is True:
        return False
    backup = init_path + ".before-no-voidwatch"
    if not os.path.exists(backup):
        shutil.copy2(init_path, backup)
    newline = "\r\n" if "\r\n" in text else "\n"
    if state is False:
        text = re.sub(r"(?m)^([ \t]*)#[ \t]*(" + re.escape(ENTRY) + r")([ \t]*\r?)$", r"\1\2\3", text, count=1)
    else:
        text = text.rstrip("\r\n") + newline + ENTRY + newline
    with open(init_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def unregister(init_path):
    with open(init_path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()
    if registered(text) is None:
        return False
    text = re.sub(r"(?m)^[ \t]*(#[ \t]*)?" + re.escape(ENTRY) + r"[ \t]*\r?\n?", "", text, count=1)
    with open(init_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def build(cfg):
    server, zones_dir, init_path, module_path = paths(cfg)
    if not os.path.isdir(zones_dir):
        raise RuntimeError("I can not find the zone data at " + zones_dir + " (check server_dir in config.json).")
    if not os.path.isfile(init_path):
        raise RuntimeError("I can not find " + init_path + ", so I can not switch the module on.")
    found = find_voidwatch_npcs(zones_dir)
    total = sum(len(v) for v in found.values())
    if total == 0:
        say("No NPC in your zone data is tagged voidwatch, so there is nothing to hide.")
        return 0
    os.makedirs(os.path.dirname(module_path), exist_ok=True)
    with open(module_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(lua_text(found))
    changed = register(init_path)
    names = {}
    for entries in found.values():
        for _, name in entries:
            names[name] = names.get(name, 0) + 1
    say(f"Found {total} Voidwatch NPCs in {len(found)} zones:")
    for name, count in sorted(names.items(), key=lambda kv: -kv[1]):
        say(f"   {count:3d}  {name}")
    say("Module written: " + module_path)
    say("Switched on in modules/init.txt." if changed else "It was already switched on in modules/init.txt.")
    say("Now restart the server (STOP, then PLAY). They are hidden when you zone in.")
    return 0


def undo(cfg):
    server, _zones, init_path, module_path = paths(cfg)
    removed = unregister(init_path) if os.path.isfile(init_path) else False
    existed = os.path.isfile(module_path)
    if existed:
        os.remove(module_path)
    say("Removed from modules/init.txt." if removed else "It was not in modules/init.txt.")
    say("Module file deleted." if existed else "There was no module file.")
    say("Restart the server (STOP, then PLAY) and the Voidwatch NPCs are back to how the zone data has them.")
    return 0


def status(cfg):
    server, _zones, init_path, module_path = paths(cfg)
    state = None
    if os.path.isfile(init_path):
        with open(init_path, "r", encoding="utf-8-sig", newline="") as f:
            state = registered(f.read())
    if state and os.path.isfile(module_path):
        with open(module_path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        say("On. " + first.replace(MARKER + " from this server's own zone data: ", "It hides "))
    elif state is None:
        say("Off: it is not in modules/init.txt.")
    elif state is False:
        say("Off: it is in modules/init.txt but switched off.")
    else:
        say("Broken: it is switched on in modules/init.txt but the module file is missing. Run  python make_no_voidwatch.py  again.")
    return 0


def main(argv):
    with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    if "server_dir" not in cfg:
        raise SystemExit("config.json has no server_dir, so I can not find your server.")
    if "--undo" in argv:
        return undo(cfg)
    if "--status" in argv:
        return status(cfg)
    return build(cfg)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except RuntimeError as problem:
        print("\n" + str(problem))
        sys.exit(1)
