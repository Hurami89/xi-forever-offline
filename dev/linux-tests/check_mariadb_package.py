"""Checks MariaDB's own Linux package with the launcher's setup code, the way a Linux player's first-run setup uses it:
find the newest long-term-support package, download it (checksum checked), unpack it, make the database folder,
start the server, give root its password, make the game's database and user, run a query, stop.
Run on a clean Linux (the GitHub workflow uses Arch Linux, what SteamOS is built from):
    python3 dev/linux-tests/check_mariadb_package.py [work folder]
Needs the internet. Exits non-zero (with the reason) on any failure; prints any library the programs can't find."""
import os
import subprocess
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)
import launcher_setup as ls
import launcher_thirdparty as tp


def main(argv):
    work = argv[0] if argv else tempfile.mkdtemp(prefix="xifo-mariadb-")
    mdb = os.path.join(work, "mariadb")
    found = ls.resolve_mariadb(tp._get, linux=True)
    print(f"MariaDB {found['version']}: {found['name']}")
    path = tp.download_file(found["url"], os.path.join(work, "downloads", found["name"]), sha256=found.get("sha256"))
    ls.unpack_package(path, mdb)
    missing = []
    for name in ("mariadbd", "mariadb", "mariadb-admin", "mariadb-dump"):
        exe = ls.mariadb_exe(mdb, name)
        out = subprocess.run(["ldd", exe], capture_output=True, text=True, env=ls.mariadb_env(mdb)).stdout
        missing += [f"{name}: {line.strip()}" for line in out.splitlines() if "not found" in line]
    if missing:
        print("Missing libraries:\n  " + "\n  ".join(missing))
        return 1
    port = ls.free_port(3306)
    print(ls.init_mariadb(mdb, "root-pw", port))
    proc = ls.start_mariadb(mdb, port)
    try:
        ls.set_root_password(mdb, port, "root-pw")
        ls.create_database(mdb, port, "root-pw", "xi-pw")
        answer = ls.sql(mdb, port, "xi", "xi-pw", "SELECT VERSION()", database=ls.DB_NAME).strip()
        print(f"Query through the package's client: {answer}")
    finally:
        ls.stop_mariadb(mdb, port, "root-pw")
        if proc is not None:
            proc.wait(timeout=60)
    print("MariaDB's Linux package works with the launcher's setup.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
