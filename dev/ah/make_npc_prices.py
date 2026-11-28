#!/usr/bin/env python3
"""Writes ah_npc_prices.json: what NPC shops sell each item for, read from the server's own scripts. ah_sim.py never
prices an item above it, and its market never buys a player's listing above it, so nothing bought cheaply from an NPC
can be sold on at a profit. (2026-11-27, the user: "some items sold cheap from npcs were selling a lot on the ah")

  python make_npc_prices.py <server folder> [<out file>]      (default out file: ah_npc_prices.json next to ah_sim.py)

Read:
  * every NPC script in scripts/zones/*/npcs that opens a shop (xi.shop.general / nation / generalGuildStock / ...):
    each "{ xi.item.NAME, price" in it
  * scripts/globals/shop.lua (the outposts; not the curio moogles' key item prices): the same
  * scripts/data/guild_shops.lua: buyMax, the most a guild asks (only items the guild really stocks)
For each item the lowest price any shop asks is kept. Item names are turned into ids with scripts/enum/item.lua.
"""
import json
import os
import re
import sys

ENTRY = re.compile(r"\{\s*xi\.item\.([A-Z0-9_]+)\s*,\s*(\d+)([^}]*)\}")
GUILD = re.compile(r"\{\s*id\s*=\s*xi\.item\.([A-Z0-9_]+)\s*,\s*initial\s*=\s*(\d+)\s*,[^}]*?buyMax\s*=\s*(\d+)[^}]*?restockRate\s*=\s*(\d+)")
ENUM = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(\d+)\s*,", re.M)
SHOP_CALL = re.compile(r"xi\.shop\.[A-Za-z]+\s*\(")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def item_ids(server):
    return {name: int(value) for name, value in ENUM.findall(read(os.path.join(server, "scripts", "enum", "item.lua")))}


def shop_files(server):
    zones = os.path.join(server, "scripts", "zones")
    for zone in sorted(os.listdir(zones)):
        folder = os.path.join(zones, zone, "npcs")
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".lua"):
                    yield os.path.join(folder, name)
    yield os.path.join(server, "scripts", "globals", "shop.lua")


def collect(server):
    ids, prices, unknown, files = item_ids(server), {}, set(), 0

    def keep(name, price):
        itemid = ids.get(name)
        if itemid is None:
            unknown.add(name)
            return
        if price > 0 and (itemid not in prices or price < prices[itemid]):
            prices[itemid] = price

    for path in shop_files(server):
        text = read(path)
        if not SHOP_CALL.search(text):
            continue
        files += 1
        for name, price, rest in ENTRY.findall(text):
            if "keyItem" in rest:      # (the curio moogles: that price only with a Rhapsody key item)
                continue
            keep(name, int(price))
    guild = os.path.join(server, "scripts", "data", "guild_shops.lua")
    if os.path.exists(guild):
        for name, initial, buy_max, restock in GUILD.findall(read(guild)):
            if int(initial) > 0 or int(restock) > 0:       # (initial 0 and no restock: the guild never has it)
                keep(name, int(buy_max))
    return prices, unknown, files


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    server = argv[1]
    out = argv[2] if len(argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ah_npc_prices.json")
    prices, unknown, files = collect(server)
    data = {"about": "Lowest NPC shop price per item id, from the server's scripts (dev/ah/make_npc_prices.py). ah_sim.py caps "
                     "auction house prices at it.", "items": {str(k): v for k, v in sorted(prices.items())}}
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=0)
        handle.write("\n")
    print(f"{len(prices)} items from {files} shop files -> {out}")
    if unknown:
        print(f"names not in scripts/enum/item.lua (left out): {len(unknown)}: {', '.join(sorted(unknown)[:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
