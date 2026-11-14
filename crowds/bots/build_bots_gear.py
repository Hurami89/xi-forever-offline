#!/usr/bin/env python3
"""Builds the gear the bot players buy as they level (bots_gear.lua) from the server's own item tables.

  python build_bots_gear.py [--server C:/ffxi-local/server] [--kit C:/FFXISOLO] [report]

Reads sql/item_equipment.sql, item_weapon.sql, item_mods.sql (plus the Phoenix module's item_equipment updates) and the
kit's ah_prices.json (the HorizonXI market: an era item list with real prices). Only gear that is on that market is used, so
everything is era, tradeable and has a fair price; levels 1-75, no item levels.

For every job and equipment slot it keeps the pieces that are an improvement on everything of a lower level (scored by what
that job wants: a Warrior STR/ACC/ATT, a White Mage MND/MP/Cure potency ...), so a bot can look up "the best thing I can
wear at my level that I can afford". Weapons stay in the job's usual weapon types. Ranged weapons and ammo are left out.
Writes modules/custom/lua/bots_gear_data.lua.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

JOBS = ["WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST", "BRD", "RNG", "SAM", "NIN", "DRG", "SMN", "BLU", "COR", "PUP"]

# equipment slot index (as the game numbers them) -> the item slot mask that fits it
SLOTS = {0: 1, 1: 2, 4: 16, 5: 32, 6: 64, 7: 128, 8: 256, 9: 512, 10: 1024, 11: 6144, 12: 6144, 13: 24576, 14: 24576, 15: 32768}
PAIRED = {11: 12, 13: 14}                   # earrings and rings: the second slot takes the next best different piece

# skills: 1 H2H, 2 dagger, 3 sword, 4 great sword, 5 axe, 6 great axe, 7 scythe, 8 polearm, 9 katana, 10 great katana,
# 11 club, 12 staff. The first listed is the job's favourite.
WEAPONS = {
    "WAR": [6, 5, 4], "MNK": [1], "WHM": [11], "BLM": [12, 11], "RDM": [3, 2], "THF": [2], "PLD": [3], "DRK": [7, 4],
    "BST": [5], "BRD": [2], "RNG": [2, 5], "SAM": [10], "NIN": [9], "DRG": [8], "SMN": [12], "BLU": [3], "COR": [3, 2],
    "PUP": [1],
}
TWO_HANDED = {1, 4, 6, 7, 8, 10, 12}
SHIELD_JOBS = {"WAR", "WHM", "RDM", "PLD", "BST", "BLU", "BLM", "SMN", "BRD", "THF", "COR", "DRK", "RNG"}
DUAL_WIELD = {"NIN"}

# mod ids (scripts/enum/mod.codegen.lua)
M = dict(DEF=1, HP=2, MP=5, STR=8, DEX=9, VIT=10, AGI=11, INT=12, MND=13, CHR=14, ATT=23, RATT=24, ACC=25, RACC=26, ENMITY=27,
         MATT=28, MDEF=29, MACC=30, EVA=68, STORETP=73, DIVINE=111, HEALING=112, ENHANCE=113, ENFEEBLE=114, ELEM=115, DARK=116,
         SUMMONING=117, SINGING=119, STRING=120, WIND=121, CRITHITRATE=165, SPELLINTERRUPT=168, FASTCAST=170, DOUBLE_ATTACK=288,
         SUBTLE_BLOW=289, CONSERVE_MP=296, TRIPLE_ATTACK=302, REFRESH=369, REGEN=370, CURE_POTENCY=374, HASTE_GEAR=384)

MELEE = dict(STR=3, DEX=3, VIT=1, AGI=1, ATT=1.5, ACC=2, HP=0.1, DEF=0.5, EVA=0.5, STORETP=2, CRITHITRATE=3, DOUBLE_ATTACK=5,
             TRIPLE_ATTACK=6, HASTE_GEAR=0.03, SUBTLE_BLOW=1, REGEN=6)
WEIGHTS = {
    "melee": MELEE,
    "tank": dict(VIT=2, DEF=1, HP=0.2, ENMITY=3, STR=1, DEX=1, ACC=1, EVA=1, MDEF=1, HASTE_GEAR=0.03, REGEN=8, MP=0.1),
    "healer": dict(MND=3, MP=0.4, HEALING=2, DIVINE=1, CURE_POTENCY=4, VIT=0.5, DEF=0.5, HP=0.05, REFRESH=25, CONSERVE_MP=2,
                   FASTCAST=3, SPELLINTERRUPT=1, ENHANCE=1, INT=0.5),
    "nuker": dict(INT=3, MP=0.4, MATT=4, MACC=3, ELEM=2, DARK=1, ENFEEBLE=1, REFRESH=25, DEF=0.3, HP=0.05, FASTCAST=2, CONSERVE_MP=2,
                  MND=0.5),
    "rdm": dict(INT=2, MND=2, MP=0.4, ENFEEBLE=2, ENHANCE=1, ELEM=1, MACC=3, MATT=1, REFRESH=25, FASTCAST=3, DEF=0.5, ACC=0.5,
                HP=0.05, STR=0.5, DEX=0.5),
    "bard": dict(CHR=3, SINGING=2, WIND=2, STRING=2, MP=0.2, DEF=0.5, HP=0.1, FASTCAST=2, MACC=2, VIT=0.5, AGI=0.5),
    "summoner": dict(MP=0.6, SUMMONING=3, REFRESH=30, INT=0.5, MND=0.5, DEF=0.5, HP=0.05, CONSERVE_MP=2, FASTCAST=1),
    "blu": dict(STR=2, DEX=1.5, INT=1, MND=0.5, MP=0.2, ACC=1.5, ATT=1, MATT=1, DEF=0.5, HP=0.1, HASTE_GEAR=0.03, VIT=1),
}
ROLE = {"WAR": "melee", "MNK": "melee", "WHM": "healer", "BLM": "nuker", "RDM": "rdm", "THF": "melee", "PLD": "tank", "DRK": "melee",
        "BST": "melee", "BRD": "bard", "RNG": "melee", "SAM": "melee", "NIN": "tank", "DRG": "melee", "SMN": "summoner", "BLU": "blu",
        "COR": "melee", "PUP": "melee"}
CASTER_WEAPON = {"healer", "nuker", "summoner", "bard"}   # their weapon is chosen for its stats more than its damage


def values(text):
    """The tuples of an INSERT ... VALUES (...),(...); line as lists of strings/numbers."""
    out, row, cur, quote, i = [], None, "", False, 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\" and i + 1 < len(text):
                cur += text[i + 1]
                i += 2
                continue
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    cur += "'"
                    i += 2
                    continue
                quote = False
            else:
                cur += ch
        elif ch == "'":
            quote = True
        elif ch == "(":
            row, cur = [], ""
        elif ch == "," and row is not None:
            row.append(cur.strip())
            cur = ""
        elif ch == ")" and row is not None:
            row.append(cur.strip())
            out.append(row)
            row, cur = None, ""
        elif row is not None:
            cur += ch
        i += 1
    return out


def rows_of(path, table):
    prefix = f"INSERT INTO `{table}`"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(prefix):
                body = line.split("VALUES", 1)[1]
                body = body.split("--", 1)[0] if "');" not in body else body
                yield from values(body)


def num(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load(server, kit):
    sql = os.path.join(server, "sql")
    equip = {}
    for r in rows_of(os.path.join(sql, "item_equipment.sql"), "item_equipment"):
        if len(r) >= 12:
            equip[num(r[0])] = dict(id=num(r[0]), name=r[1], level=num(r[2]), ilevel=num(r[3]), jobs=num(r[4]), shield=num(r[6]),
                                    script=num(r[7]), slot=num(r[8]), rslot=num(r[9]), su=num(r[11]))
    upd = os.path.join(server, "modules", "phoenix", "sql", "pxi_item_equipment.sql")
    if os.path.exists(upd):
        pat = re.compile(r"UPDATE\s+`?item_equipment`?\s+SET\s+(.+?)\s+WHERE\s+`?itemId`?\s*=\s*(\d+)", re.I)
        with open(upd, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = pat.search(line)
                if m and num(m.group(2)) in equip:
                    for part in m.group(1).split(","):
                        k, _, v = part.partition("=")
                        k = k.strip().strip("`")
                        if k in ("jobs", "level", "slot", "rslot", "ilevel", "su_level"):
                            equip[num(m.group(2))]["su" if k == "su_level" else k] = num(v.strip().strip("'"))
    weapons = {}
    for r in rows_of(os.path.join(sql, "item_weapon.sql"), "item_weapon"):
        if len(r) >= 11:
            weapons[num(r[0])] = dict(skill=num(r[2]), delay=num(r[9]), dmg=num(r[10]))
    mods = {}
    for r in rows_of(os.path.join(sql, "item_mods.sql"), "item_mods"):
        if len(r) >= 3:
            mods.setdefault(num(r[0]), {})[num(r[1])] = num(r[2])
    with open(os.path.join(kit, "ah_prices.json"), encoding="utf-8-sig") as f:
        prices = {int(k): v for k, v in (json.load(f).get("items") or {}).items()}
    return equip, weapons, mods, prices


def can_wear(item, job_index):
    return (item["jobs"] >> job_index) & 1 == 1


def score(item, job, weapons, mods):
    role = ROLE[job]
    w = WEIGHTS[role]
    item_mods = mods.get(item["id"], {})
    s = 0.0
    for name, weight in w.items():
        s += item_mods.get(M[name], 0) * weight
    wep = weapons.get(item["id"])
    if wep and item["slot"] & 1:
        if wep["delay"] > 0 and wep["dmg"] > 0:
            dps = wep["dmg"] * 240.0 / wep["delay"]              # damage per 240 delay (about a sword's speed)
            s += dps * (1.5 if role in CASTER_WEAPON else 6.0)
        if wep["skill"] in TWO_HANDED:
            s *= 1.0                                              # (the damage already says it)
    return s


def build(equip, weapons, mods, prices):
    data = {}
    for j, job in enumerate(JOBS):
        favourite = WEAPONS[job]
        per = {}
        for slot, mask in SLOTS.items():
            cands = []
            for item in equip.values():
                if not (item["slot"] & mask) or item["slot"] & ~mask & 0xFFFF and slot not in (0, 1):
                    continue
                if item["level"] < 1 or item["level"] > 75 or item["ilevel"] or item["su"] or item["rslot"]:
                    continue
                if not can_wear(item, j):
                    continue
                price = prices.get(item["id"])
                if not price or not price[0]:
                    continue
                wep = weapons.get(item["id"])
                if slot == 0:
                    if not wep or wep["skill"] not in favourite:
                        continue
                if slot == 1:
                    if item["shield"] > 0:
                        if job not in SHIELD_JOBS:
                            continue
                    elif not (job in DUAL_WIELD and wep and wep["skill"] == 9):
                        continue
                if slot not in (0, 1) and wep:
                    continue
                s = score(item, job, weapons, mods)
                if slot == 0 and wep and wep["skill"] != favourite[0]:
                    s *= 0.8                                    # its second weapon type only when clearly better
                if slot == 1 and item["shield"] > 0:
                    s += mods.get(item["id"], {}).get(M["DEF"], 0) * 0.5
                if s <= 0:
                    continue
                two = bool(wep and wep["skill"] in TWO_HANDED)
                cands.append(dict(id=item["id"], name=item["name"], level=item["level"], score=round(s, 1), price=int(price[0]), two=two))
            # keep a piece unless another one is at least as good, no higher level and no dearer (so a poor bot still has
            # a cheaper choice at its level, and a rich one the best)
            keep = []
            for c in cands:
                dominated = False
                for o in cands:
                    if o is c:
                        continue
                    if o["level"] <= c["level"] and o["score"] >= c["score"] and o["price"] <= c["price"] and (
                            o["level"] < c["level"] or o["score"] > c["score"] or o["price"] < c["price"] or o["id"] < c["id"]):
                        dominated = True
                        break
                if not dominated:
                    keep.append(c)
            keep.sort(key=lambda c: (c["level"], c["score"], c["price"]))
            if slot in PAIRED.values():
                continue
            per[slot] = keep
            if slot in PAIRED:
                # the second earring / ring: the same list; the bot takes the best two different pieces it can wear
                per[PAIRED[slot]] = keep
        data[job] = per
    return data


def write_lua(path, data):
    out = ["-- Generated by build_bots_gear.py from the server's item tables and the kit's ah_prices.json. Run it again to rebuild.",
           "-- [job][equip slot] = { { item id, level, score, price, two-handed (1/0) }, ... } by level: none is beaten by another at once lower-or-equal level, higher-or-equal score and lower-or-equal price",
           "return {"]
    for job in JOBS:
        out.append(f"    {job} = {{")
        for slot in sorted(data[job]):
            items = ", ".join(f"{{ {c['id']}, {c['level']}, {c['score']}, {c['price']}, {1 if c['two'] else 0} }}" for c in data[job][slot])
            out.append(f"        [{slot}] = {{ {items} }},")
        out.append("    },")
    out.append("}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="C:/ffxi-local/server")
    ap.add_argument("--kit", default=os.path.dirname(os.path.dirname(HERE)))
    ap.add_argument("what", nargs="?", default="write")
    args = ap.parse_args()
    equip, weapons, mods, prices = load(args.server, args.kit)
    data = build(equip, weapons, mods, prices)
    names = {i: e["name"] for i, e in equip.items()}
    total = sum(len(v) for per in data.values() for s, v in per.items())
    print(f"{len(equip)} pieces of gear read, {len(prices)} market prices; {total} picks for {len(data)} jobs")
    if args.what == "report":
        for job in ("WAR", "WHM", "BLM", "NIN"):
            for slot in (0, 1, 5, 13):
                row = data[job].get(slot, [])
                print(job, slot, ", ".join(f"{names[c['id']]}@{c['level']}({c['score']},{c['price']}g)" for c in row[:12]))
        return 0
    path = os.path.join(args.server, "modules", "custom", "lua", "bots_gear_data.lua")
    write_lua(path, data)
    print("wrote " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
