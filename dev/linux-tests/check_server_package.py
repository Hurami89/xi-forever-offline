"""Runs a Linux server folder the way a Linux player's launcher does, without the game: a database made with the
launcher's setup code (the game tables imported in the server's own order, an account), settings/network.lua, the
five server programs started with launcher_core.start_server, then waits for the map server's "ready to work".
    python3 dev/linux-tests/check_server_package.py <server folder> <MariaDB package folder> [work folder]
The MariaDB folder is MariaDB's Linux package unpacked (check_mariadb_package.py makes one in its work folder).
The server folder is changed: settings/network.lua is written (use a copy). Exits non-zero on failure."""
import os
import shutil
import sys
import tempfile
import time

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)
import launcher_core as core
import launcher_setup as ls


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    server, package = os.path.abspath(argv[0]), os.path.abspath(argv[1])
    work = argv[2] if len(argv) > 2 else tempfile.mkdtemp(prefix="xifo-server-")
    mdb = os.path.join(work, "mariadb")
    if not os.path.isdir(mdb):
        shutil.copytree(package, mdb, symlinks=True, ignore=shutil.ignore_patterns("data"))
    if not ls.valid_server(server):
        print(f"{server} is not a built Linux server (xi_map and sql/ are needed).")
        return 1
    port = ls.free_port(3306)
    print(ls.init_mariadb(mdb, "root-pw", port))
    db = ls.start_mariadb(mdb, port)
    procs, logs = {}, os.path.join(work, "logs")
    try:
        ls.set_root_password(mdb, port, "root-pw")
        ls.create_database(mdb, port, "root-pw", "xi-pw")
        start = time.time()
        files = ls.import_order(server)
        ls.import_sql(mdb, port, "xi-pw", files, log=print)
        print(f"Imported {len(files)} SQL files in {time.time() - start:.0f} s.")
        print(ls.create_account(mdb, port, "xi-pw", "player1", "secret1"))
        target = os.path.join(server, "settings", "network.lua")
        if os.path.exists(target):
            os.remove(target)
        print(ls.write_network_settings(server, port, "xi-pw"))
        missing = ls.ensure_triggers({"mariadb_dir": mdb, "db_port": port, "db_pass": "xi-pw"}, server)
        print("Triggers: " + ("all there" if not missing else "re-created " + ", ".join(missing)))
        cfg = {"server_dir": server}
        for name in core.SERVERS:
            procs[name], _log = core.start_server(cfg, name, logs)
            time.sleep(1)
        start, ready = time.time(), False
        while time.time() - start < 900:
            for name, proc in procs.items():
                if proc.poll() is not None:
                    print(f"{name} stopped (code {proc.returncode}). Its log:\n" + core.tail(os.path.join(logs, name + ".log"), 40))
                    return 1
            if core.map_ready(logs):
                ready = True
                break
            time.sleep(2)
        if not ready:
            print("The map server never said it was ready. Its log:\n" + core.tail(os.path.join(logs, "xi_map.log"), 40))
            return 1
        print(f"The map server is ready ({time.time() - start:.0f} s). Last lines:\n" + core.tail(os.path.join(logs, "xi_map.log"), 8))
        errors = []
        for name in core.SERVERS:
            with open(os.path.join(logs, name + ".log"), "rb") as handle:
                text = handle.read().decode("utf-8", "replace")
            errors += [f"{name}: {line.strip()}" for line in text.splitlines()
                       if "error while loading shared libraries" in line or "[critical]" in line.lower()]
        if errors:
            print("Problems in the logs:\n  " + "\n  ".join(errors[:30]))
            return 1
        print("The Linux server runs.")
        return 0
    finally:
        for proc in procs.values():
            core.kill_tree(proc)
        ls.stop_mariadb(mdb, port, "root-pw")
        if db is not None:
            db.wait(timeout=60)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
