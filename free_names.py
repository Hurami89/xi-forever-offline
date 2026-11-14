#!/usr/bin/env python3
"""Frees the names of characters you deleted in the game, so you can make new characters with the same names.

Why: the server never really deletes a character. It only takes it off your account (chars.accid = 0, and the old account
goes into original_accid, so it could be recovered). Its row, and its name, stay in the database, and the server refuses a
new character with a name that is still in the table ("Name already in use").

  python free_names.py            shows the deleted characters (changes nothing)
  python free_names.py --apply    renames each deleted character to Del<id><name>, e.g. Del4Hurami, which frees the name
  python free_names.py --undo     puts the old names back (only where nobody has taken the name again)

The deleted characters are not removed: their levels, items, squad mates and so on stay attached to the old character
under its new name, untouched. A new character gets a new id and starts clean. Every rename is written to
free_names-log.txt next to this script.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "free_names-log.txt")


def say(text=""):
    print(text, flush=True)


def connect(cfg):
    import mariadb
    return mariadb.connect(host=cfg.get("db_host", "127.0.0.1"), port=int(cfg.get("db_port", 3306)),
                           user=cfg["db_user"], password=cfg["db_pass"], database=cfg["db_name"])


def deleted(conn):
    cur = conn.cursor()
    cur.execute("SELECT charid, charname, original_accid FROM chars WHERE accid = 0 ORDER BY charid")
    rows = [(int(r[0]), str(r[1]), r[2]) for r in cur.fetchall()]
    cur.close()
    return rows


def name_taken(conn, name, except_id):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chars WHERE charname = ? AND charid <> ?", (name, except_id))
    n = cur.fetchone()[0]
    cur.close()
    return n > 0


def freed_name(charid, name):
    return ("Del" + str(charid) + name)[:15]


def show(conn):
    rows = deleted(conn)
    if not rows:
        say("No deleted characters are waiting in the database. Every name not used by a living character is free.")
        return 0
    say("Deleted characters still in the database (their names are blocked):")
    for charid, name, acc in rows:
        state = "name already freed" if name.startswith("Del" + str(charid)) else "blocks the name " + name
        say(f"   id {charid:<5} {name:<16} {state}")
    say()
    say("To free the names:   python free_names.py --apply")
    return 0


def apply(conn):
    rows = [r for r in deleted(conn) if not r[1].startswith("Del" + str(r[0]))]
    if not rows:
        say("Nothing to do: every deleted character's name is already free.")
        return 0
    cur = conn.cursor()
    done = []
    for charid, name, _ in rows:
        new = freed_name(charid, name)
        cur.execute("UPDATE chars SET charname = ? WHERE charid = ? AND accid = 0", (new, charid))
        done.append((charid, name, new))
    conn.commit()
    cur.close()
    with open(LOG, "a", encoding="utf-8") as f:
        for charid, name, new in done:
            f.write(f"{charid}\t{name}\t{new}\n")
    for charid, name, new in done:
        say(f"   {name} (id {charid}) -> {new}")
    say()
    say("Done. Those names are free: make your new characters in the game (no restart needed).")
    return 0


def undo(conn):
    if not os.path.exists(LOG):
        say("There is no free_names-log.txt, so there is nothing to undo.")
        return 0
    with open(LOG, "r", encoding="utf-8") as f:
        entries = [line.rstrip("\n").split("\t") for line in f if line.count("\t") == 2]
    cur = conn.cursor()
    for charid, name, new in entries:
        if name_taken(conn, name, int(charid)):
            say(f"   {name}: a new character uses that name now, so {new} keeps its name")
            continue
        cur.execute("UPDATE chars SET charname = ? WHERE charid = ? AND charname = ?", (name, int(charid), new))
        if cur.rowcount:
            say(f"   {new} -> {name}")
    conn.commit()
    cur.close()
    return 0


def main(argv, connect_fn=connect):
    with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    try:
        conn = connect_fn(cfg)
    except Exception as problem:
        say("I could not reach the database (" + str(problem)[:100] + ").")
        say("Is the server's database running? Start the server once from the launcher (PLAY), then try again.")
        return 1
    try:
        if "--apply" in argv:
            return apply(conn)
        if "--undo" in argv:
            return undo(conn)
        return show(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
