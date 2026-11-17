"""Shared set-up for the co-op tests: two scratch databases ("home" and "host") with the same character tables as a
real game database, and a made-up character. The real database is only read (its table layouts are copied).

  python test_passport.py                     uses config.json of the kit (db_host, db_port, db_user, db_pass, db_name)
  COOP_TEST_DB=socket:/run/mysqld/mysqld.sock:xi python test_passport.py     a local MariaDB socket and a template database

The database user must be allowed to create databases (the scratch ones are named coop_test_home / coop_test_host and
are dropped again at the end). If it is not, the tests are skipped.
"""
import json, os, re, sys

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)

HOME_DB, HOST_DB = "coop_test_home", "coop_test_host"
CLONE_LIKE = ("char%", "account%", "auction_house%", "delivery_box", "squad\\_%", "zone_settings")
TRIGGERS = ("char_insert", "char_delete", "account_delete", "session_delete")


def settings():
    spec = os.environ.get("COOP_TEST_DB", "")
    if spec.startswith("socket:"):
        _s, sock, template = spec.split(":", 2)
        return {"unix_socket": sock, "user": os.environ.get("COOP_TEST_USER", "root")}, template
    with open(os.path.join(KIT, "config.json"), encoding="utf-8-sig") as handle:
        cfg = json.load(handle)
    return {"host": cfg.get("db_host", "127.0.0.1"), "port": int(cfg.get("db_port", 3306)), "user": cfg["db_user"],
            "password": cfg["db_pass"]}, cfg["db_name"]


def connect(database=None):
    import mariadb
    args, _template = settings()
    if database:
        args = dict(args, database=database)
    return mariadb.connect(autocommit=False, **args)


def make_world(name):
    """An empty copy of the character tables (and their triggers) of the template database."""
    _args, template = settings()
    admin = connect()
    cur = admin.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
    cur.execute(f"CREATE DATABASE `{name}` DEFAULT CHARACTER SET utf8mb4")
    tables = set()
    for pattern in CLONE_LIKE:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = ? AND table_name LIKE ?", (template, pattern))
        tables.update(r[0] for r in cur.fetchall())
    for table in sorted(t for t in tables if not t.startswith("coop_")):
        cur.execute(f"CREATE TABLE `{name}`.`{table}` LIKE `{template}`.`{table}`")
    bodies = []
    for trigger in TRIGGERS:
        cur.execute(f"SHOW CREATE TRIGGER `{template}`.`{trigger}`")
        row = cur.fetchone()
        bodies.append(re.sub(r"CREATE\s+DEFINER\s*=\s*\S+\s+TRIGGER", "CREATE TRIGGER", row[2], count=1))
    admin.commit()
    cur.close()
    admin.close()
    world = connect(name)
    cur = world.cursor()
    for body in bodies:
        cur.execute(body)
    world.commit()
    cur.close()
    return world


def drop_worlds():
    admin = connect()
    cur = admin.cursor()
    for name in (HOME_DB, HOST_DB):
        cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
    admin.commit()
    admin.close()


def run(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall() if cur.description else None
    cur.close()
    return rows


def make_account(conn, accid, login):
    run(conn, "INSERT INTO accounts (id, login, password, timecreate, timelastmodify, status, priv) VALUES (?, ?, 'x', NOW(), NOW(), 1, 1)",
        (accid, login))
    conn.commit()


def make_character(conn, accid, charid, name, level=30, gil=1000, linkshell=True):
    """A character with a bit of everything: gear, a worn linkpearl, skills, spells, quest and world variables."""
    run(conn, "INSERT INTO chars (charid, accid, charname, nation, pos_zone, pos_x, pos_y, pos_z, missions, keyitems, playtime) "
              "VALUES (?, ?, ?, 2, 238, -12.5, 0.25, 33.125, ?, ?, 4321)", (charid, accid, name, bytes(range(40)), b"\x01\x02\xff"))
    run(conn, "INSERT INTO char_stats (charid, hp, mp, mjob, sjob, mlvl, slvl) VALUES (?, 500, 80, 1, 2, ?, ?)", (charid, level, level // 2))
    run(conn, "INSERT INTO char_look (charid, face, race, size) VALUES (?, 3, 5, 1)", (charid,))
    run(conn, "UPDATE char_jobs SET war = ?, mnk = ? WHERE charid = ?", (level, level // 2, charid))
    run(conn, "UPDATE char_exp SET war = 1234 WHERE charid = ?", (charid,))
    run(conn, "UPDATE char_storage SET inventory = 30, safe = 50 WHERE charid = ?", (charid,))
    run(conn, "UPDATE char_inventory SET quantity = ? WHERE charid = ? AND location = 0 AND slot = 0", (gil, charid))
    run(conn, "INSERT INTO char_inventory (charid, location, slot, itemId, quantity, signature, extra) VALUES (?, 0, 1, 16535, 1, 'Maker', ?)",
        (charid, b"\x00" * 24))
    run(conn, "INSERT INTO char_inventory (charid, location, slot, itemId, quantity) VALUES (?, 0, 2, 4112, 12)", (charid,))
    run(conn, "INSERT INTO char_inventory (charid, location, slot, itemId, quantity) VALUES (?, 1, 1, 12345, 1)", (charid,))
    run(conn, "UPDATE char_equip SET slotid = 1, equipslotid = 0, containerid = 0 WHERE charid = ?", (charid,))
    if linkshell:
        run(conn, "INSERT INTO char_inventory (charid, location, slot, itemId, quantity, extra) VALUES (?, 0, 3, 515, 1, ?)",
            (charid, b"\x05\x00\x00\x00" + b"\x11" * 20))
        run(conn, "INSERT INTO char_equip (charid, slotid, equipslotid, containerid) VALUES (?, 3, 16, 0)", (charid,))
    for skill, value in ((1, 90), (3, 55), (48, 12)):
        run(conn, "INSERT INTO char_skills (charid, skillid, value, `rank`) VALUES (?, ?, ?, 0)", (charid, skill, value))
    for spell in (1, 2, 3):
        run(conn, "INSERT INTO char_spells (charid, spellid) VALUES (?, ?)", (charid, spell))
    for var, value in (("[Quest]Progress", 3), ("TrustEngageType", 1), ("SQUAD_AI_5", 21), ("[Bots]LS", 4)):
        run(conn, "INSERT INTO char_vars (charid, varname, value) VALUES (?, ?, ?)", (charid, var, value))
    conn.commit()


def rows_of(conn, table, charid, order):
    out = run(conn, f"SELECT * FROM `{table}` WHERE charid = ? ORDER BY {order}", (charid,))
    conn.rollback()
    return out
