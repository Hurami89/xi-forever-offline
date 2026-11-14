"""Clean up what deleted characters left behind (FFXI Offline kit).

When a character is deleted in game, the character itself goes, but some things are stored outside it:
squad mates and other rows linked to its character id, its unsold auction house listings, per-character
addon folders (Name_ID), and Crystal Boy claims / play time / saves (folders named after the character).

  python cleanup_characters.py            show what would be removed - changes nothing
  python cleanup_characters.py --apply    remove it (everything is backed up first)
  python cleanup_characters.py --restore C:\\FFXISOLO\\backups\\char-cleanup-YYYYMMDD-HHMMSS   put it all back

Only things belonging to characters that no longer exist are touched. Characters that still exist
(for example the GM character) keep everything. Run it BEFORE making new characters with the old names.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CHAR_COLUMNS = ("charid", "char_id")
FOLDER_RE = re.compile(r"^([A-Za-z]{3,15})_(\d+)$")


def load_config(here=HERE):
    with open(os.path.join(here, "config.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def connect(cfg):
    import mariadb

    return mariadb.connect(host=cfg.get("db_host", "127.0.0.1"), port=int(cfg.get("db_port", 3306)),
                           user=cfg["db_user"], password=cfg["db_pass"], database=cfg["db_name"])


def query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    cur.close()
    return rows, cols


def char_tables(conn):
    """(table, column) for every table with a character id column, except chars itself."""
    try:
        rows, _ = query(conn, "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                              "WHERE TABLE_SCHEMA = DATABASE() AND LOWER(COLUMN_NAME) IN ('charid', 'char_id')")
        found = [(t, c) for t, c in rows]
    except Exception:  # sqlite, for tests
        tables, _ = query(conn, "SELECT name FROM sqlite_master WHERE type = 'table'")
        found = []
        for (t,) in tables:
            cols, _ = query(conn, f"PRAGMA table_info({t})")
            found += [(t, c[1]) for c in cols if str(c[1]).lower() in CHAR_COLUMNS]
    return sorted((t, c) for t, c in found if t.lower() != "chars")


def existing_chars(conn):
    rows, _ = query(conn, "SELECT charid, charname FROM chars")
    return {int(i): str(n) for i, n in rows}


def find_db(conn):
    """{label: (sql where, params, table)} with row counts, for things linked to characters that no longer exist."""
    found = []
    for table, col in char_tables(conn):
        where = f"`{col}` > 0 AND `{col}` NOT IN (SELECT charid FROM chars)"
        n = query(conn, f"SELECT COUNT(*) FROM `{table}` WHERE {where}")[0][0][0]
        if n:
            found.append((table, where, int(n)))
    # unsold auction house listings by deleted characters (the simulator's own listings have seller 0)
    try:
        where = "seller > 0 AND sale = 0 AND seller NOT IN (SELECT charid FROM chars)"
        n = query(conn, f"SELECT COUNT(*) FROM `auction_house` WHERE {where}")[0][0][0]
        if n:
            found.append(("auction_house", where, int(n)))
    except Exception:
        pass
    return found


def find_files(ashita_dir, chars):
    """Per-character folders of characters that no longer exist: addon Name_ID folders and Crystal Boy claims/saves."""
    ids, names = set(chars), {n.lower() for n in chars.values()}
    addons = os.path.join(ashita_dir, "config", "addons")
    out = []
    if not os.path.isdir(addons):
        return out
    base_depth = addons.rstrip(os.sep).count(os.sep)
    for root, dirs, _files in os.walk(addons):
        depth = root.rstrip(os.sep).count(os.sep) - base_depth
        for d in list(dirs):
            m = FOLDER_RE.match(d)
            if m and int(m.group(2)) not in ids:
                out.append(os.path.join(root, d))
                dirs.remove(d)
        if depth >= 3:
            dirs[:] = []
    cb = os.path.join(addons, "crystalboy")
    for sub in ("claims", "saves"):
        folder = os.path.join(cb, sub)
        if os.path.isdir(folder):
            for d in sorted(os.listdir(folder)):
                path = os.path.join(folder, d)
                if os.path.isdir(path) and not FOLDER_RE.match(d) and d.lower() not in names:
                    out.append(path)
    return sorted(set(out))


def report(found, files, chars, ashita_dir):
    lines = ["Characters that still exist (kept): " + (", ".join(f"{n} ({i})" for i, n in sorted(chars.items())) or "none")]
    lines.append("")
    if found:
        lines.append("Database rows linked to deleted characters:")
        for table, _w, n in found:
            label = " (unsold listings)" if table == "auction_house" else ""
            lines.append(f"  {table}{label}: {n}")
    else:
        lines.append("Database: nothing left over.")
    lines.append("")
    if files:
        lines.append("Folders of deleted characters (moved to the backup, not deleted):")
        for path in files:
            lines.append("  " + os.path.relpath(path, ashita_dir))
    else:
        lines.append("Folders: nothing left over.")
    return "\n".join(lines)


def apply(conn, found, files, ashita_dir, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    saved = {"ashita_dir": ashita_dir, "tables": {}, "files": []}
    # save every row first, then delete
    for table, where, _n in found:
        rows, cols = query(conn, f"SELECT * FROM `{table}` WHERE {where}")
        saved["tables"].setdefault(table, {"columns": cols, "rows": []})["rows"] += [list(r) for r in rows]
    with open(os.path.join(backup_dir, "rows.json"), "w", encoding="utf-8") as f:
        json.dump(saved, f, default=str)
    cur = conn.cursor()
    for table, where, _n in found:
        cur.execute(f"DELETE FROM `{table}` WHERE {where}")
    conn.commit()
    cur.close()
    for path in files:
        rel = os.path.relpath(path, ashita_dir)
        target = os.path.join(backup_dir, "files", rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(path, target)
        saved["files"].append(rel)
    with open(os.path.join(backup_dir, "rows.json"), "w", encoding="utf-8") as f:
        json.dump(saved, f, default=str)
    return saved


def restore(conn, backup_dir):
    with open(os.path.join(backup_dir, "rows.json"), "r", encoding="utf-8") as f:
        saved = json.load(f)
    cur = conn.cursor()
    count = 0
    for table, data in saved["tables"].items():
        cols = data["columns"]
        sql = f"INSERT INTO `{table}` (" + ", ".join(f"`{c}`" for c in cols) + ") VALUES (" + ", ".join("?" for _ in cols) + ")"
        for row in data["rows"]:
            cur.execute(sql, row)
            count += 1
    conn.commit()
    cur.close()
    moved = 0
    for rel in saved["files"]:
        src, dst = os.path.join(backup_dir, "files", rel), os.path.join(saved["ashita_dir"], rel)
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            moved += 1
    return count, moved


def server_running():
    if os.name != "nt":
        return False
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq xi_map.exe"], capture_output=True, text=True).stdout
    return "xi_map.exe" in out


def main(argv=None):
    p = argparse.ArgumentParser(description="Clean up what deleted characters left behind.")
    p.add_argument("--apply", action="store_true", help="remove it (backed up first)")
    p.add_argument("--restore", metavar="BACKUP_FOLDER", help="put a cleanup back")
    args = p.parse_args(argv)
    cfg = load_config()
    ashita_dir = cfg.get("ashita_dir", r"C:\Ashita-v4beta-main")
    if (args.apply or args.restore) and server_running():
        sys.exit("The server is running. Press STOP in the launcher (and close the game), then try again.")
    conn = connect(cfg)
    if args.restore:
        rows, moved = restore(conn, args.restore)
        print(f"Put back {rows} database rows and {moved} folders.")
        return
    chars = existing_chars(conn)
    found, files = find_db(conn), find_files(ashita_dir, chars)
    print(report(found, files, chars, ashita_dir))
    if not args.apply:
        print("\nNothing was changed. To remove these: python cleanup_characters.py --apply")
        return
    if not found and not files:
        print("\nNothing to clean up.")
        return
    backup_dir = os.path.join(HERE, "backups", "char-cleanup-" + time.strftime("%Y%m%d-%H%M%S"))
    apply(conn, found, files, ashita_dir, backup_dir)
    print(f"\nDone. Backup: {backup_dir}")
    print(f"To undo: python cleanup_characters.py --restore \"{backup_dir}\"")


if __name__ == "__main__":
    main()
