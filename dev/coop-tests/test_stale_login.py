"""A login row that a crash left behind does not keep a character "in the game" (2026-11-27, Quaiton: the launcher said
"Quaiton is in the game right now. Log out first." with the world asleep, so he could not go to The Hub).

launcher_passport.in_game() with a stand-in database cursor: no database, no config file, nothing is written.
test_passport.py has the same two cases against a real scratch database (it needs MariaDB).

  python test_stale_login.py
"""
import inspect
import os
import sys

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)

import launcher_passport as pp          # noqa: E402
import launcher_squad_backup as sb      # noqa: E402

passed = failed = 0


def check(ok, label):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print("FAIL:", label)


class Cursor:
    """Answers the one question in_game asks (is there a login row for this character) and writes down every statement."""

    def __init__(self, logged_in):
        self.logged_in, self.seen, self.rows = set(logged_in), [], []

    def execute(self, sql, params=()):
        self.seen.append((" ".join(sql.split()), tuple(params)))
        text = sql.lstrip().upper()
        if text.startswith("SELECT") and "ACCOUNTS_SESSIONS" in text:
            self.rows = [(1,)] if params[0] in self.logged_in else []
        elif text.startswith("DELETE") and "ACCOUNTS_SESSIONS" in text:
            self.logged_in.discard(params[0])
            self.rows = []
        else:
            raise AssertionError("a statement in_game should not make: " + sql)

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def deletes(self):
        return [entry for entry in self.seen if entry[0].upper().startswith("DELETE")]


def with_map_server(running, work):
    real = pp.map_server_running
    pp.map_server_running = lambda: running
    try:
        return work()
    finally:
        pp.map_server_running = real


print("== in_game")
cur = Cursor(logged_in=[])
check(with_map_server(True, lambda: pp.in_game(cur, 7)) is False and cur.deletes() == [], "no login row: not in the game, nothing removed")
cur = Cursor(logged_in=[])
check(with_map_server(False, lambda: pp.in_game(cur, 7)) is False and cur.deletes() == [], "no login row, world asleep: the same")

cur = Cursor(logged_in=[7])
check(with_map_server(True, lambda: pp.in_game(cur, 7)) is True, "a login row and the world awake: in the game")
check(cur.deletes() == [] and 7 in cur.logged_in, "and the row is left alone")

cur = Cursor(logged_in=[7, 8])
check(with_map_server(False, lambda: pp.in_game(cur, 7)) is False, "a login row and the world asleep: not in the game (left behind by a crash)")
check(cur.deletes() == [("DELETE FROM accounts_sessions WHERE charid = ?", (7,))], "the leftover row is removed, for that character only")
check(8 in cur.logged_in and 7 not in cur.logged_in, "another character's row stays")
check(with_map_server(False, lambda: pp.in_game(cur, 7)) is False and len(cur.deletes()) == 1, "asked again: still not in the game, nothing more removed")

print("== is the world awake?")
import launcher_core            # noqa: E402

asked = []
real = launcher_core.is_running
try:
    launcher_core.is_running = lambda name: asked.append(name) or True
    check(pp.map_server_running() is True and asked == ["xi_map"], "awake when xi_map runs (asked for xi_map)")
    launcher_core.is_running = lambda name: False
    check(pp.map_server_running() is False, "asleep when it does not")

    def broken(name):
        raise OSError("no process list")

    launcher_core.is_running = broken
    check(pp.map_server_running() is True, "when that cannot be checked, a login row is trusted")
finally:
    launcher_core.is_running = real

print("== who asks it")
depart, restore = inspect.getsource(pp.depart), inspect.getsource(pp.restore_backup)
check("if in_game(cur, charid):" in depart and "is_online(" not in depart, "leaving for another world (depart)")
check("if in_game(cur, charid):" in restore and "is_online(" not in restore, "putting a character backup back (restore_backup)")
check("pp.in_game(cur, charid)" in inspect.getsource(sb.restore) and "pp.is_online(" not in inspect.getsource(sb.restore),
      "putting a squad backup back (launcher_squad_backup.restore)")
# a host's own checks on its visitors stay as they were: its world is running, so its login rows are true
for name in ("remove_guest",):
    source = inspect.getsource(getattr(pp, name))
    check("is_online(" in source and "in_game(" not in source, f"{name} (a host and its visitors) is unchanged")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
