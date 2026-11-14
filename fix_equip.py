"""Find and remove broken "what this character wears" rows (FFXI Offline kit).

A row in char_equip says "equip slot X wears the item in bag Y, slot Z". When that row points at nothing, at a bag
that does not exist, or at an item that cannot go in that slot, the map server warns - and for a linkshell slot with a
bag that does not exist it crashed while you were logging in (2026-11-07). This removes only such rows; the item itself
stays in the bag (bots put their gear back on when they log in, you can re-equip yours).

  python fix_equip.py            show what is broken - changes nothing
  python fix_equip.py --apply    remove those rows (backed up first, to backups\\equip-fix-YYYYMMDD-HHMMSS.json)

The launcher runs the --apply step by itself before it starts the servers.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LINKSHELL_ITEMS = (513, 514, 515)  # Linkshell, Pearlsack, Linkpearl

QUERY = """
SELECT e.charid, e.equipslotid, e.slotid, e.containerid, i.itemid, q.slot, c.charname
FROM char_equip e
LEFT JOIN char_inventory i ON i.charid = e.charid AND i.location = e.containerid AND i.slot = e.slotid
LEFT JOIN item_equipment q ON q.itemId = i.itemid
LEFT JOIN chars c ON c.charid = e.charid
WHERE e.slotid <> 0
"""


def load_config(here=HERE):
    with open(os.path.join(here, "config.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def connect(cfg):
    import mariadb

    return mariadb.connect(host=cfg.get("db_host", "127.0.0.1"), port=int(cfg.get("db_port", 3306)),
                           user=cfg["db_user"], password=cfg["db_pass"], database=cfg["db_name"])


def why_broken(equip_slot, item_id, slot_mask):
    """None when the row is fine, else the reason."""
    if item_id is None:
        return "points at an empty or missing bag slot"
    if equip_slot >= 16:
        return None if item_id in LINKSHELL_ITEMS else f"linkshell slot holds item {item_id}"
    if slot_mask is None:
        return f"item {item_id} is not equipment"
    if not (int(slot_mask) & (1 << equip_slot)):
        return f"item {item_id} cannot go in equip slot {equip_slot}"
    return None


def find_broken(conn):
    cur = conn.cursor()
    cur.execute(QUERY)
    out = []
    for charid, eslot, slot, cont, item, mask, name in cur.fetchall():
        reason = why_broken(int(eslot), None if item is None else int(item), mask)
        if reason:
            out.append({"charid": int(charid), "name": name or "?", "equipslotid": int(eslot), "slotid": int(slot),
                        "containerid": int(cont), "reason": reason})
    cur.close()
    return out


def remove(conn, rows, backup_dir):
    if not rows:
        return None
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(backup_dir, time.strftime("equip-fix-%Y%m%d-%H%M%S.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)
    cur = conn.cursor()
    for r in rows:
        cur.execute("DELETE FROM char_equip WHERE charid = ? AND equipslotid = ? AND slotid = ? AND containerid = ?",
                    (r["charid"], r["equipslotid"], r["slotid"], r["containerid"]))
    conn.commit()
    cur.close()
    return path


def repair(cfg, here=HERE, conn=None):
    """For the launcher: removes broken rows, returns (how many, characters, backup file)."""
    own = conn is None
    conn = conn or connect(cfg)
    try:
        rows = find_broken(conn)
        path = remove(conn, rows, os.path.join(here, "backups"))
        return len(rows), sorted({r["name"] for r in rows}), path
    finally:
        if own:
            conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="remove the broken rows (backed up first)")
    a = ap.parse_args()
    conn = connect(load_config())
    rows = find_broken(conn)
    if not rows:
        print("Nothing broken: every equipped item points at a real item that fits its slot.")
        return 0
    for r in rows:
        print(f"{r['name']:<16} equip slot {r['equipslotid']:>2}  bag {r['containerid']:>3} slot {r['slotid']:>3}  - {r['reason']}")
    print(f"\n{len(rows)} broken row(s) on {len({r['charid'] for r in rows})} character(s).")
    if a.apply:
        path = remove(conn, rows, os.path.join(HERE, "backups"))
        print(f"Removed. Backup: {path}")
    else:
        print("Nothing changed. Run again with --apply to remove them.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
