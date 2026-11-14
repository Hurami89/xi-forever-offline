#!/usr/bin/env python3
"""Builds the starter gear for squad mates (and for !startergear) from YOUR database.

  python build_starter_gear.py            write modules/custom/lua/squad_starter_gear.lua and show the sets
  python build_starter_gear.py report     only show the sets

Weapons follow the game's own new-character list:
  Warrior Onion Sword, Monk White Belt (waist), White Mage Onion Rod, Black Mage Onion Staff, Red Mage Onion Dagger, Thief Onion Knife.
Jobs the game gives nothing to get an Onion weapon they can equip (or the cheapest plain level 1 weapon).
Armor (head, body, hands, legs, feet): the cheapest plain level 1 piece the job can wear. Rare/Ex items, costumes, event items,
anything with a script or item level, and anything newer than the 75 era is never picked.

RANDOM STARTER OUTFITS (v2): besides that fixed set, it writes a pool of plain armor for every job and slot, levels 1 to 10.
The first time a mate comes out as a job, each armor slot is drawn at random from the pieces that job can wear at the mate's
level (capped at 10), so every mate starts out looking different. The weapon stays the job's starter weapon (a mate's weapon
skills depend on its weapon type). Gear you trade them afterwards works exactly as before.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXED = {1: ("onion_sword", 0), 2: ("white_belt", 10), 3: ("onion_rod", 0), 4: ("onion_staff", 0), 5: ("onion_dagger", 0), 6: ("onion_knife", 0)}
WEAPON_PREFERENCE = ["onion_sword", "onion_dagger", "onion_knife", "onion_rod", "onion_staff"]
ARMOR_SLOTS = {4: 16, 5: 32, 6: 64, 7: 128, 8: 256}          # equipment slot index -> item slot mask
SLOT_NAMES = {0: "main", 4: "head", 5: "body", 6: "hands", 7: "legs", 8: "feet", 10: "waist"}
JOBS = {1: "WAR", 2: "MNK", 3: "WHM", 4: "BLM", 5: "RDM", 6: "THF", 7: "PLD", 8: "DRK", 9: "BST", 10: "BRD", 11: "RNG", 12: "SAM", 13: "NIN",
        14: "DRG", 15: "SMN", 16: "BLU", 17: "COR", 18: "PUP", 19: "DNC", 20: "SCH", 21: "GEO", 22: "RUN"}
RARE_OR_EX = 0x8000 | 0x4000
POOL_MAX_LEVEL = 10            # the random outfits draw from plain armor up to this level
POOL_SKIP_WORDS = ("fsh.", "fisherman", "choc", "field_", "apron", "smock", "onion")
ARMOR_MIN_ID, ARMOR_MAX_ID, WEAPON_MIN_ID, WEAPON_MAX_ID = 12000, 15999, 16000, 18199


def connect():
    import mariadb
    with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    return mariadb.connect(host=cfg.get("db_host", "127.0.0.1"), port=int(cfg.get("db_port", 3306)),
                           user=cfg["db_user"], password=cfg["db_pass"], database=cfg["db_name"]), cfg


def query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def can_wear(jobs, job):
    return (int(jobs) >> (job - 1)) & 1 == 1


def build(conn):
    rows = query(conn, "SELECT e.itemId, b.name, e.slot, e.jobs, b.BaseSell, b.aH, b.flags FROM item_equipment e JOIN item_basic b ON b.itemid = e.itemId "
                       "WHERE e.level = 1 AND e.ilevel = 0 AND e.su_level = 0 AND e.scriptType = 0")
    items = [dict(id=int(r[0]), name=r[1], slot=int(r[2]), jobs=int(r[3]), sell=int(r[4] or 0), ah=int(r[5] or 0), flags=int(r[6] or 0)) for r in rows]
    plain = [i for i in items if not (i["flags"] & RARE_OR_EX) and (i["ah"] > 0 or i["name"].startswith("onion") or i["name"] == "white_belt")]
    by_name = {i["name"]: i for i in items}

    def cheapest(candidates):
        return min(candidates, key=lambda i: (i["sell"] if i["sell"] > 0 else 10 ** 9, i["id"])) if candidates else None

    sets = {}
    for job in range(1, 23):
        picks = {}
        if job in FIXED:
            name, slot = FIXED[job]
            if name in by_name:
                picks[slot] = by_name[name]
        if 0 not in picks and job != 2:      # the Monk fights bare-handed, like in the game
            for name in WEAPON_PREFERENCE:
                item = by_name.get(name)
                if item and can_wear(item["jobs"], job) and item["slot"] & 1:
                    picks[0] = item
                    break
        if 0 not in picks and job != 2:
            weapon = cheapest([i for i in plain if i["slot"] & 1 and WEAPON_MIN_ID <= i["id"] <= WEAPON_MAX_ID and can_wear(i["jobs"], job)])
            if weapon:
                picks[0] = weapon
        for slot, mask in ARMOR_SLOTS.items():
            item = cheapest([i for i in plain if i["slot"] & mask and ARMOR_MIN_ID <= i["id"] <= ARMOR_MAX_ID and can_wear(i["jobs"], job)])
            if item:
                picks[slot] = item
        sets[job] = picks
    return sets


def build_pools(conn):
    """job -> slot -> [(item id, level, name)]: plain, era, tradeable armor of levels 1..POOL_MAX_LEVEL that covers exactly one slot."""
    rows = query(conn, "SELECT e.itemId, b.name, e.slot, e.jobs, e.level, b.aH, b.flags, e.rslot FROM item_equipment e JOIN item_basic b ON b.itemid = e.itemId "
                       "WHERE e.level >= 1 AND e.level <= ? AND e.ilevel = 0 AND e.su_level = 0 AND e.scriptType = 0", (POOL_MAX_LEVEL,))
    pools = {}
    for r in rows:
        item = dict(id=int(r[0]), name=str(r[1]), slot=int(r[2]), jobs=int(r[3]), level=int(r[4]), ah=int(r[5] or 0), flags=int(r[6] or 0), rslot=int(r[7] or 0))
        if item["flags"] & RARE_OR_EX or item["ah"] <= 0 or item["rslot"] != 0 or not (ARMOR_MIN_ID <= item["id"] <= ARMOR_MAX_ID):
            continue
        if any(word in item["name"] for word in POOL_SKIP_WORDS):            # fishing/chocobo/field (gathering) clothes, aprons, later onion gear
            continue
        for slot, mask in ARMOR_SLOTS.items():
            if item["slot"] != mask:
                continue
            for job in range(1, 23):
                if can_wear(item["jobs"], job):
                    pools.setdefault(job, {}).setdefault(slot, []).append((item["id"], item["level"], item["name"]))
    for job in pools:
        for slot in pools[job]:
            pools[job][slot].sort(key=lambda e: (e[1], e[0]))
    return pools


def report(sets):
    lines = []
    for job, picks in sets.items():
        parts = [f"{SLOT_NAMES[s]}: {picks[s]['name']}" for s in sorted(picks)]
        lines.append(f"{JOBS[job]:<4} " + ("  |  ".join(parts) if parts else "(nothing found)"))
    return "\n".join(lines)


def report_pools(pools):
    lines = []
    for job in sorted(pools):
        parts = [f"{SLOT_NAMES[s]} {len(pools[job][s])}" for s in sorted(pools[job])]
        lines.append(f"{JOBS[job]:<4} choices:  " + ", ".join(parts))
    return "\n".join(lines)


def write_lua(path, sets, pools=None):
    out = ["-- Generated by build_starter_gear.py from your database. Run the script again to rebuild it.",
           "-- job number -> { equipment slot number = item id }   (0 main, 4 head, 5 body, 6 hands, 7 legs, 8 feet, 10 waist)",
           "-- pools: job number -> slot -> { { item id, level }, ... }  plain armor a new mate's outfit is drawn from at random",
           "return", "{"]
    for job, picks in sets.items():
        body = ", ".join(f"[{s}] = {picks[s]['id']}" for s in sorted(picks))
        names = ", ".join(f"{SLOT_NAMES[s]} {picks[s]['name']}" for s in sorted(picks))
        out.append(f"    [{job}] = {{ {body} }}, -- {JOBS[job]}: {names}")
    if pools:
        out.append("    pools =")
        out.append("    {")
        for job in sorted(pools):
            out.append(f"        [{job}] = {{ -- {JOBS[job]}")
            for slot in sorted(pools[job]):
                entries = ", ".join(f"{{ {i}, {lv} }}" for i, lv, _ in pools[job][slot])
                out.append(f"            [{slot}] = {{ {entries} }}, -- {SLOT_NAMES[slot]}")
            out.append("        },")
        out.append("    },")
    out.append("}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    conn, cfg = connect()
    sets = build(conn)
    pools = build_pools(conn)
    print(report(sets))
    print()
    print("Random outfit choices per job (levels 1-%d):" % POOL_MAX_LEVEL)
    print(report_pools(pools))
    if mode == "report":
        return
    if not any(sets.values()):
        raise SystemExit("No starter gear was found, so nothing was written.")
    path = os.path.join(cfg["server_dir"], "modules", "custom", "lua", "squad_starter_gear.lua")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_lua(path, sets, pools)
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
