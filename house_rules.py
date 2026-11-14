"""House-rule changes to the game's item data (FFXI Offline kit). The launcher runs apply() before it starts the servers.

  python house_rules.py     apply them now (the map server must be stopped; it reads item data when it starts)

Chariot Band: 3 charges, 15 hours between uses (the rest of its rules are in modules/custom/late/exp_band.lua).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (sql, params, what) - each one safe to run again
RULES = [
    ("UPDATE item_usable SET maxCharges = ?, reuseDelay = ? WHERE itemid = ?", (3, 15 * 3600, 15761),
     "Chariot Band: 3 charges, 15 hours between uses"),
]


def load_config(here=HERE):
    with open(os.path.join(here, "config.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def connect(cfg):
    import mariadb

    return mariadb.connect(host=cfg.get("db_host", "127.0.0.1"), port=int(cfg.get("db_port", 3306)),
                           user=cfg["db_user"], password=cfg["db_pass"], database=cfg["db_name"])


def apply(cfg, conn=None):
    """Returns the rules that changed something."""
    own = conn is None
    conn = conn or connect(cfg)
    changed = []
    try:
        cur = conn.cursor()
        for sql, params, what in RULES:
            cur.execute(sql, params)
            if cur.rowcount:
                changed.append(what)
        conn.commit()
        cur.close()
    finally:
        if own:
            conn.close()
    return changed


if __name__ == "__main__":
    done = apply(load_config())
    print("\n".join(done) if done else "Already applied - nothing to change.")
    sys.exit(0)
