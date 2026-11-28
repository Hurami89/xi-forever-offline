"""ah_sim.py: an item an NPC shop sells is never priced or bought above the shop's price, and famous items Horizon has no
price for use ah_famous_prices.json (2026-11-27, the user). A stand-in database (sqlite in memory); nothing is written
outside a temporary folder.
  python test_ah_npc_prices.py
"""
import json
import os
import random
import sqlite3
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)
import ah_sim  # noqa: E402

passed = failed = 0


def check(ok, label):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print("FAIL:", label)


class Conn:
    """Answers ah_sim's own SQL on sqlite (the same tables, in memory)."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE item_basic (itemid INT, name TEXT, stackSize INT, BaseSell INT, aH INT);
            CREATE TABLE item_equipment (itemId INT, level INT, ilevel INT, su_level INT);
            CREATE TABLE auction_house (id INTEGER PRIMARY KEY, itemid INT, stack INT, seller INT, seller_name TEXT,
                date INT, price INT, buyer_name TEXT, sale INT, sell_date INT);
        """)

    def cursor(self):
        return self.db.cursor()


def run_sql(conn, sql, params=()):
    cur = conn.db.cursor()
    cur.execute(sql.replace("%s", "?"), params)
    return cur.fetchall()


ah_sim.query = run_sql
ah_sim.execute = lambda conn, sql, params=(): (run_sql(conn, sql, params), conn.db.commit())
ah_sim.out_of_era_scrolls = lambda conn, era: set()

tmp = tempfile.mkdtemp()
real_here = ah_sim.HERE


def files(npc, famous):
    for name, items in ((ah_sim.NPC_PRICE_FILE, npc), (ah_sim.FAMOUS_PRICE_FILE, famous)):
        path = os.path.join(tmp, name)
        if items is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "w") as f:
                json.dump({"items": {str(k): v for k, v in items.items()}}, f)


real_load = ah_sim.load_id_prices
ah_sim.load_id_prices = lambda name, here=None: real_load(name, tmp)
ah_sim.price_rate = lambda here=None: 1.0

conn = Conn()
rows = [
    (16640, "bronze_axe", 1, 50, 1),          # an NPC sells it for 316, Horizon says 2000
    (17319, "bone_arrow", 99, 1, 1),          # an NPC sells it for 5, Horizon's stack price 1300
    (17440, "kraken_club", 1, 2000, 1),       # no Horizon price, no NPC: a famous item
    (4112, "potion", 12, 70, 1),              # an NPC sells it for 910, Horizon 600: Horizon stands
    (5000, "odd_thing", 1, 400, 1),           # a "shop price" below what an NPC pays: not trusted
]
for r in rows:
    conn.db.execute("INSERT INTO item_basic VALUES (?, ?, ?, ?, ?)", r)
for itemid, level in ((16640, 1), (17440, 70)):
    conn.db.execute("INSERT INTO item_equipment VALUES (?, ?, 0, 0)", (itemid, level))
conn.db.commit()
market = {"items": {16640: [2000, None], 17319: [1300, 9900], 4112: [600, None], 5000: [3000, None]}}
settings = json.loads(json.dumps(ah_sim.DEFAULTS))
settings["era"]["stock_all_visible"] = True

print("== prices")
files({16640: 316, 17319: 5, 4112: 910, 5000: 100}, {17440: 5000000})
items = ah_sim.eligible_items(conn, settings, market)
axe, arrow, club, potion, odd = (items[i] for i in (16640, 17319, 17440, 4112, 5000))
check(axe.fair == 316 and axe.source == "npc" and axe.cap == 316, f"bronze axe: the shop's 316, not Horizon's 2000 ({axe.fair})")
check(arrow.fair == 5 and arrow.stack_fair == 5 * 99, f"bone arrows: 5 each, a stack 495 ({arrow.fair}, {arrow.stack_fair})")
check(club.fair == 5000000 and club.source == "famous", f"Kraken Club: the famous price ({club.fair})")
check(potion.fair == 600 and potion.source == "horizon" and potion.cap == 910, "potion: Horizon's lower price stands, the shop's is the cap")
check(odd.cap is None and odd.fair == 3000, "a shop price below the vendor's buy price is not trusted")

print("== listings never above the shop")
rng = random.Random(4)
check(all(ah_sim.listing_price(axe, False, settings, rng) <= 316 for _ in range(200)), "the price jitter never lifts the axe above 316")
check(all(ah_sim.listing_price(arrow, True, settings, rng) <= 495 for _ in range(200)), "nor a stack of arrows above 495")

print("== the market never buys above the shop")
now = 10_000_000


def listing(itemid, price, stack=0):
    cur = conn.db.execute("INSERT INTO auction_house (itemid, stack, seller, seller_name, date, price, buyer_name, sale, sell_date) "
                          "VALUES (?, ?, 1, 'Me', ?, ?, NULL, 0, 0)", (itemid, stack, now - 99999, price))
    conn.db.commit()
    return cur.lastrowid


over = listing(16640, 400)
fair = listing(16640, 300)
stack_over = listing(17319, 600, 1)
for _ in range(5):
    ah_sim.buy_player_listings(conn, settings, items, now, random.Random(1))
sold = {r[0]: r[1] for r in conn.db.execute("SELECT id, sale FROM auction_house")}
check(sold[over] == 0, "an axe listed at 400 (the shop asks 316): never bought")
check(sold[fair] == 300, "one listed at 300: bought")
check(sold[stack_over] == 0, "a stack of arrows at 600 (the shop: 495): never bought")

print("== without the files: as before")
files(None, None)
items = ah_sim.eligible_items(conn, settings, market)
check(items[16640].fair == 2000 and items[16640].cap is None and items[17440].source != "famous", "no files: Horizon and the estimate, no cap")

print("== a new set of rules restocks")
check(ah_sim.PRICE_RULES in ah_sim.price_stamp({"source": "x", "fetched": 1}), "the price stamp carries the rules' version")

print(f"\npassed {passed}, failed {failed}")
sys.exit(1 if failed else 0)
