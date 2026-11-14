"""Makes bots_craft_data.lua for the bot players' crafting and auction house (step 4.4b).

  python build_bots_craft.py [--server C:\\ffxi-local\\server] [--kit C:\\FFXISOLO]

Reads the server's own tables (read-only): sql/synth_recipes.sql (era recipes: no Abyssea and later, no key-item
recipes, one craft only), sql/item_basic.sql (stack sizes, vendor prices, AH categories). Fair prices come from the
AH simulator's market data (ah_prices.json in the kit) when known, else the vendor price x 4 (the AH simulator's
default). Writes server/modules/custom/lua/bots_craft_data.lua.
"""
import argparse
import json
import os
import re
import sys

ERA_TAGS = {"NULL", "ROTZ", "COP", "TOAU"}
CRAFTS = ["wood", "smith", "gold", "cloth", "leather", "bone", "alchemy", "cook"]
CRYSTALS = set(range(4096, 4104))


def sql_rows(path, table):
    rows = []
    prefix = "INSERT INTO `%s` VALUES (" % table
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith(prefix):
                continue
            body = line[len(prefix):].split(");", 1)[0]
            rows.append([p.strip().strip("'") for p in re.findall(r"'(?:[^'\\]|\\.)*'|[^,]+", body)])
    return rows


def server_dir(kit):
    try:
        with open(os.path.join(kit, "config.json"), encoding="utf-8-sig") as f:
            return json.load(f).get("server_dir") or r"C:\ffxi-local\server"
    except (OSError, ValueError):
        return r"C:\ffxi-local\server"


def lua_str(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=os.path.dirname(os.path.dirname(here)))
    ap.add_argument("--server", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    server = args.server or server_dir(args.kit)

    items = {}
    for r in sql_rows(os.path.join(server, "sql", "item_basic.sql"), "item_basic"):
        try:
            iid = int(r[0])
            stack = int(r[6]) if r[6].isdigit() else 1
            ah = r[8] not in ("0", "@NONE")
            items[iid] = {"name": r[2], "stack": max(1, stack), "sell": int(r[-1]) if r[-1].isdigit() else 0, "ah": ah}
        except (ValueError, IndexError):
            continue

    market = {}
    try:
        with open(os.path.join(args.kit, "ah_prices.json"), encoding="utf-8-sig") as f:
            for k, v in json.load(f).get("items", {}).items():
                if v and (v[0] or (len(v) > 1 and v[1])):
                    market[int(k)] = (v[0], v[1] if len(v) > 1 else None)
    except (OSError, ValueError):
        pass

    def fair(iid):
        """(single price, stack price) in gil"""
        info = items.get(iid, {"sell": 0, "stack": 1})
        single, stack = market.get(iid, (None, None))
        if not single and stack and info["stack"] > 1:
            single = max(1, stack // info["stack"])
        if not single:
            single = max(20, info["sell"] * 4)
        if not stack and info["stack"] > 1:
            stack = single * info["stack"]
        return int(single), int(stack or 0)

    recipes, used, made = [], set(), set()
    for r in sql_rows(os.path.join(server, "sql", "synth_recipes.sql"), "synth_recipes"):
        try:
            desynth, keyitem = int(r[1]), int(r[2])
            skills = [int(x) for x in r[3:11]]
            crystal = int(r[11])
            ingredients = [int(x) for x in r[13:21] if int(x) != 0]
            result, qty, name, tag = int(r[21]), int(r[25]), r[29], (r[30] or "NULL").upper()
        except (ValueError, IndexError):
            continue
        if desynth or keyitem or tag not in ERA_TAGS or crystal not in CRYSTALS or not ingredients or result == 0:
            continue
        crafts = [i for i, s in enumerate(skills) if s > 0]
        if len(crafts) != 1 or skills[crafts[0]] > 100:
            continue
        if result not in items or any(i not in items for i in ingredients):
            continue
        recipes.append((crafts[0] + 1, skills[crafts[0]], crystal, ingredients, result, max(1, qty), name))
        made.add(result)
        used.update(ingredients)
        used.add(crystal)
        used.add(result)

    # fishing (the minigame is skipped): what bites in the port towns, from the server's own fishing tables
    FISH_ZONES = [232, 236, 240, 248, 249, 252, 246, 50, 26]
    fishing = {}
    used.update(i for i in (17391, 17396) if i in items)  # willow fishing rod, little worm
    try:
        fish = {}
        for r in sql_rows(os.path.join(server, "sql", "fishing_fish.sql"), "fishing_fish"):
            fid, skill = int(r[0]), int(r[2])
            legendary, keyitem, quest_only, disabled = int(r[18]), int(r[23]), int(r[26]), int(r[28])
            if not legendary and not keyitem and not quest_only and not disabled:
                fish[fid] = skill
        groups = {}
        for r in sql_rows(os.path.join(server, "sql", "fishing_group.sql"), "fishing_group"):
            groups.setdefault(int(r[0]), []).append((int(r[1]), int(r[2])))
        for r in sql_rows(os.path.join(server, "sql", "fishing_catch.sql"), "fishing_catch"):
            zid, gid = int(r[0]), int(r[2])
            if zid in FISH_ZONES:
                for fid, rarity in groups.get(gid, []):
                    if fid in fish and fid in items:
                        fishing.setdefault(zid, {})[fid] = (fish[fid], rarity)
                        used.add(fid)
    except (OSError, ValueError, IndexError) as exc:
        print("fishing data skipped:", exc)

    recipes.sort(key=lambda x: (x[0], x[1]))
    out_path = args.out or os.path.join(server, "modules", "custom", "lua", "bots_craft_data.lua")
    lines = [
        "-- Generated by build_bots_craft.py from the server's own synth_recipes.sql and item_basic.sql (era recipes,",
        "-- one craft each). Fair prices: the AH simulator's market data when known, else vendor price x 4.",
        "local d = {}",
        "-- crafts: 1 wood 2 smith 3 gold 4 cloth 5 leather 6 bone 7 alchemy 8 cook",
        "-- { craft, level, crystal, { ingredients }, result, quantity, name }",
        "d.recipes = {",
    ]
    for c, lvl, cr, ing, res, qty, name in recipes:
        lines.append("    { %d, %d, %d, { %s }, %d, %d, %s }," % (c, lvl, cr, ", ".join(str(i) for i in ing), res, qty, lua_str(name)))
    lines += ["}", "", "-- [item id] = { single price, stack price, stack size, auction house ok (1/0) }", "d.items = {"]
    for iid in sorted(used):
        single, stack = fair(iid)
        info = items[iid]
        lines.append("    [%d] = { %d, %d, %d, %d }," % (iid, single, stack, info["stack"], 1 if info["ah"] else 0))
    lines += ["}", "", "-- crafted items (made by some recipe)", "d.made = {"]
    lines.append("    " + ", ".join("[%d] = true" % i for i in sorted(made)))
    lines += ["}", "", "-- fishing: [zone] = { { item id, skill level, rarity (higher = more common) }, ... }", "d.fishing = {"]
    for zid in sorted(fishing):
        lines.append("    [%d] = { %s }," % (zid, ", ".join("{ %d, %d, %d }" % (f, sk, ra) for f, (sk, ra) in sorted(fishing[zid].items()))))
    lines += ["}", "", "return d", ""]
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    per = {}
    for r in recipes:
        per[r[0]] = per.get(r[0], 0) + 1
    print("fishing: %d zones" % len(fishing))
    print("bots_craft_data.lua: %d era recipes (%s), %d items with prices (%d from market data) -> %s" % (
        len(recipes), ", ".join("%s %d" % (CRAFTS[k - 1], v) for k, v in sorted(per.items())), len(used),
        len([i for i in used if i in market]), out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
