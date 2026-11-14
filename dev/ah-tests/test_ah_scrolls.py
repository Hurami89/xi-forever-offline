"""Stand-in tests for ah_sim.py's era filter on spell scrolls (sqlite in place of MariaDB).   python test_ah_scrolls.py"""
import os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import ah_sim as a

passed = failed = 0
def check(cond, label):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print("FAIL:", label)

def jobs(**levels):
    order = "WAR MNK WHM BLM RDM THF PLD DRK BST BRD RNG SAM NIN DRG SMN BLU COR PUP DNC SCH GEO RUN".split()
    return bytes(levels.get(j, 0) for j in order)

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE item_basic (itemid INT, subid INT, name TEXT, stackSize INT, BaseSell INT, aH INT)")
db.execute("CREATE TABLE item_equipment (itemId INT, level INT, ilevel INT, su_level INT)")
db.execute("CREATE TABLE spell_list (spellid INT, name TEXT, jobs BLOB, content_tag TEXT)")
db.execute("CREATE TABLE auction_house (itemid INT, stack INT, seller INT, seller_name TEXT, date INT, price INT, buyer_name TEXT, sale INT, sell_date INT)")
spells = [(1, "cure", jobs(WHM=1, RDM=3), None), (5, "cure_v", jobs(WHM=61), None), (6, "cure_vi", jobs(WHM=80), "ABYSSEA"),
          (43, "protect_v", jobs(WHM=76, RDM=77), None), (275, "absorb-tp", jobs(DRK=45), "TOAU"), (287, "klimaform", jobs(SCH=46), None),
          (339, "utsusemi_ni", jobs(NIN=37), "ROTZ"), (477, "regen_iv", jobs(WHM=86), "ABYSSEA"), (500, "esuna", jobs(WHM=61), "WOTG"),
          (511, "haste_ii", jobs(RDM=96), "SOA"), (119, "aurorastorm", jobs(SCH=48), None), (495, "adloquium", jobs(SCH=88), None),
          (768, "indi-regen", jobs(GEO=1), None), (288, "fire_spirit", jobs(SMN=1), None), (98, "regen_ii", jobs(WHM=44), None)]
for s in spells: db.execute("INSERT INTO spell_list VALUES (?,?,?,?)", s)
items = [(4609, 1, "scroll_of_cure", 1, 17, 30), (4613, 5, "scroll_of_cure_v", 1, 4875, 30), (4614, 6, "scroll_of_cure_vi", 1, 6670, 30),
         (4651, 43, "scroll_of_protect_v", 1, 5000, 30), (4883, 275, "scroll_of_absorb-tp", 1, 3000, 31), (4900, 287, "scroll_of_klimaform", 1, 2000, 31),
         (4952, 339, "scroll_of_utsusemi_ni", 1, 2000, 32), (5085, 477, "scroll_of_regen_iv", 1, 2400, 30), (5100, 500, "scroll_of_esuna", 1, 2000, 30),
         (4692, 847, "scroll_of_haste_ii", 1, 3000, 30), (5106, 879, "scroll_of_inundation", 1, 3000, 30), (4181, 0, "scroll_of_instant_warp", 12, 50, 33),
         (4096, 0, "fire_crystal", 12, 10, 40), (6055, 119, "aurorastorm_schema", 1, 2000, 31), (6061, 495, "adloquium_schema", 1, 2000, 31),
         (6073, 768, "plate_of_indi-regen", 1, 2000, 30), (4896, 288, "fire_spirit_pact", 1, 500, 33), (5477, 98, "warrior_die", 1, 500, 33)]
for i in items: db.execute("INSERT INTO item_basic VALUES (?,?,?,?,?,?)", i)
db.commit()

settings = a.merge(a.DEFAULTS, {})
era = settings["era"]
out = a.out_of_era_scrolls(db, era)
check(set(out) == {4614, 4651, 4900, 5085, 5100, 4692, 5106, 6055, 6061, 6073}, "out of era: Cure VI, Protect V (76+), Klimaform (SCH only), Regen IV, Esuna (WotG), Haste II, unknown spell: " + str(sorted(out)))
check(4609 not in out and 4613 not in out and 4883 not in out and 4952 not in out, "kept: Cure, Cure V (61), Absorb-TP (ToAU), Utsusemi: Ni (RoZ)")
check(6055 in out and 6061 in out and 6073 in out, "Scholar schemas (Aurorastorm, Adloquium) and Geomancer plates are out")
check(4896 not in out and 5477 not in out, "spirit pacts and Corsair dice are not spell items and are left alone")
check(4181 not in out, "Instant Warp (a scroll without a spell) is left to the other rules")
check(4692 in out, "Haste II's odd sub id (847) is matched by its name")

eligible = a.eligible_items(db, settings)
check(4614 not in eligible and 4609 in eligible and 4096 in eligible, "the simulator stocks Cure and crystals, never Cure VI")

era["allow_ids"] = [4651]
check(4651 not in a.out_of_era_scrolls(db, era), "allow_ids can let one back in (Protect V)")
era["allow_ids"] = []

hidden = dict(a.items_to_hide(db, settings))
check(set(hidden) == set(out) and hidden[4614] == 30, "the newer scrolls are hidden from the auction house menus, remembering their category")
a.hide_above_level(db, settings)
check(db.execute("SELECT aH FROM item_basic WHERE itemid = 4614").fetchone()[0] == 0 and db.execute("SELECT aH FROM item_basic WHERE itemid = 4609").fetchone()[0] == 30, "after hiding: Cure VI gone from the menus, Cure still there")
a.unhide(db)
check(db.execute("SELECT aH FROM item_basic WHERE itemid = 4614").fetchone()[0] == 30, "unhide puts them back")

db.executemany("INSERT INTO auction_house VALUES (?,?,?,?,?,?,?,?,?)", [(4614, 0, 0, "AHBot", 1, 9000, None, 0, 0), (4609, 0, 0, "AHBot", 1, 50, None, 0, 0),
               (4614, 0, 77, "Hurami", 1, 8000, None, 0, 0), (4614, 0, 0, "AHBot", 1, 9000, "Someone", 9000, 1)])
check(a.remove_ineligible_listings(db, eligible) == 1, "one item's bot listings taken down")
rows = db.execute("SELECT itemid, seller, sale FROM auction_house ORDER BY itemid, seller").fetchall()
check((4614, 77, 0) in rows and (4609, 0, 0) in rows and (4614, 0, 9000) in rows and (4614, 0, 0) not in rows,
      "the bot's unsold Cure VI is gone; your own listing, the sale history and Cure stay")
print(f"\npassed {passed}, failed {failed}")
sys.exit(1 if failed else 0)
