"""The Mog Garden follows Seekers of Adoulin (2026-11-27, shamwow_guy: trapped in a Mog Garden whose Moogle vanished).
settings/main.lua ENABLE_MOG_GARDEN is 0 unless the expansion is on; with 0 the server takes the Mog House menu's
"Mog Garden" as the way out to the area you came in from (src/map/packets/c2s/0x05e_maprect.cpp). No screen needed.
Run:  python -I dev\\launcher-tests\\test_mog_garden.py"""
import os
import shutil
import sys
import tempfile

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, KIT)
import launcher_core as core

checks = 0


def ok(condition, what):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(what)


MAIN = ("xi = xi or {}\nxi.settings = xi.settings or {}\nxi.settings.main = {\n    ENABLE_SOA          = 1,\n"
        "    ENABLE_MOG_GARDEN   = 1, -- Enables Access to Mog Garden, will send player to the area they entered from if disabled.\n"
        "    EXPLORER_MOOGLE_LV  = 10,\n}\n")
MAIN_OLD = "xi = xi or {}\nxi.settings = xi.settings or {}\nxi.settings.main = {\n    ENABLE_SOA          = 1,\n}\n"
LOGIN = "xi.settings.login = {\n}\n"
MAP = "xi.settings.map = {\n    EXP_RATE = 1.000,\n    SPEED_LIMIT = 80,\n}\n"


def write_server(main_text):
    root = tempfile.mkdtemp(prefix="mog-garden-")
    default = os.path.join(root, "settings", "default")
    os.makedirs(default)
    for name, text in (("main.lua", main_text), ("login.lua", LOGIN), ("map.lua", MAP)):
        with open(os.path.join(default, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return root


def line(root, key):
    with open(os.path.join(root, "settings", "main.lua"), encoding="utf-8") as f:
        for row in f.read().splitlines():
            if row.strip().startswith(key):
                return row
    return ""


# a player's world (the expansion is off by default): the garden is off
root = write_server(MAIN)
rates = dict(core.RATE_DEFAULTS)
ok(not rates.get("main.ENABLE_SOA"), "Seekers of Adoulin is off by default")
core.apply_rates(root, rates)
ok("= 0," in line(root, "ENABLE_MOG_GARDEN"), "a player's world: ENABLE_MOG_GARDEN = 0 (" + line(root, "ENABLE_MOG_GARDEN") + ")")
ok("-- Enables Access to Mog Garden" in line(root, "ENABLE_MOG_GARDEN"), "the comment after the value is left alone")
ok("= 0," in line(root, "ENABLE_SOA"), "and the expansion itself is written as off")
shutil.rmtree(root)

# the expansion switched on (a GM's own world): the garden is on again
for on in (1, True, "1", 1.0):
    root = write_server(MAIN)
    rates = dict(core.RATE_DEFAULTS)
    rates["main.ENABLE_SOA"] = on
    try:
        core.apply_rates(root, rates)
        ok("= 1," in line(root, "ENABLE_MOG_GARDEN"), f"Seekers of Adoulin on ({on!r}): ENABLE_MOG_GARDEN = 1 (" + line(root, "ENABLE_MOG_GARDEN") + ")")
    finally:
        shutil.rmtree(root)

for off in (0, False, "0", 0.0):
    root = write_server(MAIN)
    rates = dict(core.RATE_DEFAULTS)
    rates["main.ENABLE_SOA"] = off
    try:
        core.apply_rates(root, rates)
        ok("= 0," in line(root, "ENABLE_MOG_GARDEN"), f"Seekers of Adoulin off ({off!r}): ENABLE_MOG_GARDEN = 0 (" + line(root, "ENABLE_MOG_GARDEN") + ")")
    finally:
        shutil.rmtree(root)

# a server whose defaults do not have the key: nothing is added to its settings
root = write_server(MAIN_OLD)
core.apply_rates(root, dict(core.RATE_DEFAULTS))
with open(os.path.join(root, "settings", "main.lua"), encoding="utf-8") as f:
    ok("ENABLE_MOG_GARDEN" not in f.read(), "a server without the key: the key is not added")
shutil.rmtree(root)

print(f"PASS {checks}")
