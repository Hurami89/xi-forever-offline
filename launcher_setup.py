"""First-run setup for players (no GUI code here, so every step can be tested on its own).

Runs only when the kit has no config.json: it finds Final Fantasy XI, installs Ashita and the chosen add-ons from their
official releases, sets up a portable MariaDB inside the kit folder (no Windows service, no admin rights), creates the
database and the game account, writes the server's database settings, the Ashita boot file and script, rates.json and
config.json. An existing install (a config.json is present) never comes here.
"""
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import zipfile

NO_WINDOW = 0x08000000
MARIADB_SERIES = "11.4"                                # long-term support series
MARIADB_API = "https://downloads.mariadb.org/rest-api/mariadb/{series}/latest"
MARIADB_PAGE = "https://mariadb.org/download/"
BOOT_NAME = "xiforever.ini"
SCRIPT_NAME = "xiforever.txt"
DB_NAME = "xiforever"
DB_USER = "xi"

# ----- finding things -----
FFXI_REGISTRY = [(r"SOFTWARE\WOW6432Node\PlayOnlineUS\InstallFolder", "0001"),
                 (r"SOFTWARE\WOW6432Node\PlayOnlineEU\InstallFolder", "0001"),
                 (r"SOFTWARE\WOW6432Node\PlayOnline\InstallFolder", "0001"),
                 (r"SOFTWARE\PlayOnlineUS\InstallFolder", "0001"),
                 (r"SOFTWARE\PlayOnline\InstallFolder", "0001")]
FFXI_GUESSES = [r"C:\Program Files (x86)\PlayOnline\SquareEnix\FINAL FANTASY XI",
                r"C:\Program Files\PlayOnline\SquareEnix\FINAL FANTASY XI",
                r"C:\PlayOnline\SquareEnix\FINAL FANTASY XI",
                r"D:\PlayOnline\SquareEnix\FINAL FANTASY XI"]


def valid_ffxi(path):
    return bool(path) and os.path.isfile(os.path.join(path, "FFXiMain.dll"))


def find_ffxi():
    """The FINAL FANTASY XI folder from the PlayOnline registry entry, else a usual place, else None."""
    try:
        import winreg
        for key, value in FFXI_REGISTRY:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                    path = winreg.QueryValueEx(handle, value)[0]
                if valid_ffxi(path):
                    return path
            except OSError:
                continue
    except ImportError:          # not Windows (tests)
        pass
    for path in FFXI_GUESSES:
        if valid_ffxi(path):
            return path
    return None


def valid_server(path):
    return bool(path) and os.path.isfile(os.path.join(path, "xi_map.exe")) and os.path.isdir(os.path.join(path, "sql"))


def default_layout(kit):
    return {"ashita_dir": os.path.join(kit, "Ashita"), "server_dir": os.path.join(kit, "server"),
            "mariadb_dir": os.path.join(kit, "mariadb")}


def free_port(preferred=3306, tries=20):
    """preferred if nothing listens there, else the next free one (another MariaDB or MySQL may already use 3306)."""
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free port for the database near 3306.")


def new_password(length=16):
    return secrets.token_urlsafe(length)[:length]


def valid_login(name):
    """LandSandBoat logins: 3-16 letters and numbers."""
    return bool(re.fullmatch(r"[A-Za-z0-9]{3,16}", name or ""))


# ----- portable MariaDB -----
def resolve_mariadb(fetch):
    """The newest MariaDB Windows zip in the long-term support series: {"version", "url", "name", "sha256"}."""
    data = json.loads(fetch(MARIADB_API.format(series=MARIADB_SERIES)))
    releases = data.get("releases") or {}
    for version in sorted(releases, key=lambda v: [int(x) for x in re.findall(r"\d+", v)], reverse=True):
        for item in releases[version].get("files", []):
            name = item.get("file_name", "")
            if name.endswith("-winx64.zip") and "debug" not in name:
                digest = (item.get("checksum") or {}).get("sha256sum")
                return {"version": version, "url": item.get("file_download_url"), "name": name, "sha256": digest}
    raise RuntimeError(f"No MariaDB Windows zip found; download it from {MARIADB_PAGE} and unpack it into the mariadb folder.")


def unpack_single_folder(zip_path, dest):
    """Unpacks a zip whose files are all inside one top folder, without that folder."""
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            head, _, rest = info.filename.partition("/")
            if not rest or info.is_dir():
                continue
            parts = rest.split("/")
            if ".." in parts or ":" in rest:
                raise RuntimeError("refusing a path outside the folder: " + info.filename)
            target = os.path.join(dest, *parts)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def mariadb_exe(mariadb_dir, name):
    return os.path.join(mariadb_dir, "bin", name + ".exe")


def init_mariadb(mariadb_dir, root_password, port, run=subprocess.run):
    """Creates the data folder once (mariadb-install-db)."""
    data = os.path.join(mariadb_dir, "data")
    if os.path.isdir(os.path.join(data, "mysql")):
        return "The database folder already exists."
    result = run([mariadb_exe(mariadb_dir, "mariadb-install-db"), f"--datadir={data}", f"--password={root_password}",
                  f"--port={port}"], capture_output=True, text=True, creationflags=NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError("mariadb-install-db failed: " + (result.stderr or result.stdout)[-400:])
    return "Database folder created."


def start_mariadb(mariadb_dir, port, popen=subprocess.Popen, wait=30):
    """Starts the portable server in the background if nothing answers on its port. Returns the process (or None)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        if s.connect_ex(("127.0.0.1", int(port))) == 0:
            return None
    proc = popen([mariadb_exe(mariadb_dir, "mariadbd"), f"--datadir={os.path.join(mariadb_dir, 'data')}", f"--port={port}",
                  "--bind-address=127.0.0.1"], cwd=mariadb_dir, creationflags=NO_WINDOW,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(wait * 2):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", int(port))) == 0:
                return proc
        time.sleep(0.5)
    raise RuntimeError("The database did not start (see mariadb\\data\\*.err).")


def stop_mariadb(mariadb_dir, port, root_password, run=subprocess.run):
    run([mariadb_exe(mariadb_dir, "mariadb-admin"), "-h127.0.0.1", f"-P{port}", "-uroot", f"-p{root_password}", "shutdown"],
        capture_output=True, creationflags=NO_WINDOW)


def sql(mariadb_dir, port, user, password, statement, database=None, run=subprocess.run):
    """Runs SQL with the MariaDB command-line client that came in the zip (no Python database driver needed)."""
    cmd = [mariadb_exe(mariadb_dir, "mariadb"), "-h127.0.0.1", f"-P{port}", f"-u{user}", f"-p{password}", "--batch",
           "--skip-column-names", "-e", statement]
    if database:
        cmd.insert(-2, database)
    result = run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "").strip()[-500:] or "SQL failed")
    return result.stdout


def quote(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def create_database(mariadb_dir, port, root_password, db_password, run=subprocess.run):
    sql(mariadb_dir, port, "root", root_password,
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`; "
        f"CREATE USER IF NOT EXISTS {quote(DB_USER)}@'localhost' IDENTIFIED BY {quote(db_password)}; "
        f"CREATE USER IF NOT EXISTS {quote(DB_USER)}@'127.0.0.1' IDENTIFIED BY {quote(db_password)}; "
        f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO {quote(DB_USER)}@'localhost'; "
        f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO {quote(DB_USER)}@'127.0.0.1'; FLUSH PRIVILEGES;", run=run)


def import_order(server_dir):
    """The server's SQL files in the order its own tools/dbtool.py imports them: sql/*.sql sorted with triggers.sql
    last, then each module in modules/init.txt (a folder: every .sql under it, sorted)."""
    sql_dir = os.path.join(server_dir, "sql")
    files = sorted(os.path.join(sql_dir, f) for f in os.listdir(sql_dir) if f.endswith(".sql"))
    triggers = os.path.join(sql_dir, "triggers.sql")
    if triggers in files:
        files.remove(triggers)
        files.append(triggers)
    init = os.path.join(server_dir, "modules", "init.txt")
    if os.path.exists(init):
        with open(init, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                path = os.path.join(server_dir, "modules", line)
                if os.path.isdir(path):
                    found = []
                    for root, _dirs, names in os.walk(path):
                        found += [os.path.join(root, n) for n in names if n.endswith(".sql")]
                    files += sorted(found, key=lambda p: p.replace("\\", "/"))
                elif line.endswith(".sql") and os.path.exists(path):
                    files.append(path)
    return files


def import_sql(mariadb_dir, port, db_password, files, log=print, run=subprocess.run):
    for index, path in enumerate(files, 1):
        source = path.replace("\\", "/")
        if index % 20 == 1 or index == len(files):
            log(f"Database: importing {index}/{len(files)} ({os.path.basename(path)})...")
        sql(mariadb_dir, port, DB_USER, db_password,
            f"SET autocommit=0; SET unique_checks=0; SET foreign_key_checks=0; SOURCE {source}; "
            "SET unique_checks=1; SET foreign_key_checks=1; COMMIT;", database=DB_NAME, run=run)


def create_account(mariadb_dir, port, db_password, login, password, run=subprocess.run):
    """The player's game account. PASSWORD() is MariaDB's own hash: the login server accepts it and turns it into
    bcrypt the first time you log in (src/login/auth_session.cpp)."""
    if not valid_login(login):
        raise ValueError("The login must be 3-16 letters and numbers.")
    existing = sql(mariadb_dir, port, DB_USER, db_password, f"SELECT id FROM accounts WHERE login = {quote(login)}",
                   database=DB_NAME, run=run).strip()
    if existing:
        return f"The account '{login}' already exists."
    sql(mariadb_dir, port, DB_USER, db_password,
        "INSERT INTO accounts (id, login, password, timecreate, timelastmodify, status, priv) "
        f"SELECT GREATEST(1000, IFNULL(MAX(id), 0) + 1), {quote(login)}, PASSWORD({quote(password)}), NOW(), NOW(), 1, 1 FROM accounts",
        database=DB_NAME, run=run)
    return f"Created the account '{login}'."


# ----- files -----
def set_lua_values(text, values):
    """Replaces KEY = value lines in a LandSandBoat settings file (strings quoted, numbers as they are)."""
    for key, value in values.items():
        literal = str(value) if isinstance(value, int) else "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"
        text, count = re.subn(r"(?m)^(\s*" + re.escape(key) + r"\s*=\s*)('[^']*'|\"[^\"]*\"|-?\d+)", lambda m: m.group(1) + literal, text, count=1)
        if count == 0:
            raise RuntimeError(f"{key} was not found in the server's network settings.")
    return text


def write_network_settings(server_dir, port, db_password):
    """settings/network.lua with this install's database login. An existing file is never replaced."""
    target = os.path.join(server_dir, "settings", "network.lua")
    if os.path.exists(target):
        return "settings/network.lua already exists - left as it is."
    with open(os.path.join(server_dir, "settings", "default", "network.lua"), encoding="utf-8-sig") as handle:
        text = handle.read()
    text = set_lua_values(text, {"SQL_HOST": "127.0.0.1", "SQL_PORT": int(port), "SQL_LOGIN": DB_USER,
                                 "SQL_PASSWORD": db_password, "SQL_DATABASE": DB_NAME})
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return "Wrote settings/network.lua."


def write_boot(ashita_dir, login, password):
    """config/boot/xiforever.ini from Ashita's private-server example: xiloader, this PC, the new account."""
    boot_dir = os.path.join(ashita_dir, "config", "boot")
    target = os.path.join(boot_dir, BOOT_NAME)
    if os.path.exists(target):
        return f"{BOOT_NAME} already exists - left as it is."
    with open(os.path.join(boot_dir, "example-privateserver.ini"), encoding="utf-8-sig") as handle:
        text = handle.read()
    lines = {"name": "XI: Forever Offline", "file": ".\\\\bootloader\\\\xiloader.exe",
             "command": f"--server 127.0.0.1 --user {login} --pass {password}", "script": SCRIPT_NAME}
    for key, value in lines.items():
        text, count = re.subn(r"(?m)^(" + key + r"\s*=\s*).*$", lambda m: m.group(1) + value, text, count=1)
        if count == 0:
            raise RuntimeError(f"Ashita's example boot file has no '{key}' line.")
    with open(target, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(text)
    return f"Wrote config/boot/{BOOT_NAME}."


def write_script(ashita_dir, interface, addons=(), plugins=()):
    """scripts/xiforever.txt: Ashita's default script plus the chosen interface and add-ons."""
    scripts = os.path.join(ashita_dir, "scripts")
    target = os.path.join(scripts, SCRIPT_NAME)
    if os.path.exists(target):
        return f"{SCRIPT_NAME} already exists - left as it is."
    try:
        with open(os.path.join(scripts, "default.txt"), encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except OSError:
        lines = ["/load thirdparty", "/load addons", "/load screenshot"]
    lines = ["# Managed by the XI: Forever Offline launcher (Addons tab)."] + lines
    loads = [f"/load {p}" for p in plugins] + [f"/addon load {a}" for a in addons]
    if interface == "xiui":
        loads.append("/addon load xiui")
    elif interface == "xiuiplus":
        loads.append("/load XIUIplus")
    present = {line.strip().lower() for line in lines}
    lines += [line for line in loads if line.lower() not in present]
    with open(target, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return f"Wrote scripts/{SCRIPT_NAME}."


def write_config(kit, values):
    """config.json from config.example.json with this install's values. Never replaces an existing one."""
    target = os.path.join(kit, "config.json")
    if os.path.exists(target):
        raise RuntimeError("config.json already exists.")
    with open(os.path.join(kit, "config.example.json"), encoding="utf-8-sig") as handle:
        cfg = json.load(handle)
    cfg.update(values)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cfg, handle, indent=2)
    os.replace(tmp, target)
    return cfg


# ----- the kit's own addons -----
OWN_ADDONS = ("Gambits", "followme", "servermenu", "squadpanel")
STOCK_ADDONS = ("distance", "fps", "move", "timestamp", "tparty", "checker", "drawdistance", "allmaps")
STOCK_PLUGINS = ("minimap",)
START_ADDONS = ("Gambits", "servermenu", "crystalboy")          # loaded at startup on a new install


def install_own_addons(kit, ashita_dir):
    """Copies the kit's addons (addons-src, crystalboy) into Ashita and makes Crystal Boy's folders."""
    addons = os.path.join(ashita_dir, "addons")
    for name in OWN_ADDONS:
        src = os.path.join(kit, "addons-src", name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(addons, name), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.before-*", "*.bak"))
    src = os.path.join(kit, "crystalboy")
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(addons, "crystalboy"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.before-*", "*.bak", "rewards_default.lua"))
        cfg = os.path.join(ashita_dir, "config", "addons", "crystalboy")
        for folder in ("roms", "system", "saves", "states", "claims", "snaps"):
            os.makedirs(os.path.join(cfg, folder), exist_ok=True)
        rewards = os.path.join(cfg, "rewards.lua")
        if not os.path.exists(rewards) and os.path.exists(os.path.join(src, "rewards_default.lua")):
            shutil.copy2(os.path.join(src, "rewards_default.lua"), rewards)


# ----- the whole setup -----
def run_setup(kit, choices, tp, log=print, fetch=None, run=subprocess.run, popen=subprocess.Popen):
    """choices: ffxi_dir, ashita_dir, server_dir, mariadb_dir, world, population, interface, extras (list of
    thirdparty ids), login, password. Every step can be run again: what is already there is kept."""
    import launcher_core as core
    fetch = fetch or tp._get
    items = {item["id"]: item for item in tp.load_manifest(kit)}
    ashita, server, mdb = choices["ashita_dir"], choices["server_dir"], choices["mariadb_dir"]

    log("1/9 Checking Final Fantasy XI...")
    if not valid_ffxi(choices.get("ffxi_dir")):
        raise RuntimeError("That folder is not FINAL FANTASY XI (FFXiMain.dll is missing). Install the game first.")

    log("2/9 The game server...")
    if not valid_server(server):
        try:
            tp.install(items["server"], kit, ashita, fetch=fetch, log=log, server=server)
        except Exception as problem:
            raise RuntimeError(f"The server files could not be downloaded ({problem}). Check the internet connection, "
                               "or choose a folder with a built server.")
    if not tp.status(items["vcredist"], kit, ashita)[0]:
        tp.install(items["vcredist"], kit, ashita, fetch=fetch, log=log, run=run)
    log("   Ashita and xiloader...")
    for iid in ("ashita", "xiloader"):
        if not tp.status(items[iid], kit, ashita)[0]:
            tp.install(items[iid], kit, ashita, fetch=fetch, log=log)
    log("3/9 Add-ons...")
    wanted = [choices["interface"]] if choices.get("interface") in ("xiui", "xiuiplus") else []
    for iid in wanted + list(choices.get("extras", [])):
        item = items.get(iid)
        if item and item["source"]["type"] not in ("page", "installer") and not tp.status(item, kit, ashita)[0]:
            try:
                tp.install(item, kit, ashita, fetch=fetch, log=log)
            except Exception as problem:             # an optional add-on never stops the setup
                log(f"{item['name']} was not installed ({problem}); get it later on the Downloads tab.")
    install_own_addons(kit, ashita)
    if choices.get("era_dats", True):                 # Phoenix's era game files, with a backup of the originals
        try:
            if not tp.status(items["eradats"], kit, ashita)[0]:
                tp.install(items["eradats"], kit, ashita, fetch=fetch, log=log)
            for line in install_era_dats(kit, choices["ffxi_dir"], log=log):
                log(line)
        except Exception as problem:
            log(f"The Era-DATs were not installed ({problem}); do it later on the Downloads tab.")
    if choices.get("world") == "living_ai":           # the AI: Ollama, then the model (about 8 GB) - never stops the setup
        try:
            if not tp.find_ollama():
                tp.install(items["ollama"], kit, ashita, fetch=fetch, log=log, run=run)
            if not tp.status(items["aimodel"], kit, ashita)[0]:
                log("Getting the AI model (about 8 GB, this takes a while)...")
                tp.install(items["aimodel"], kit, ashita, fetch=fetch, log=log)
        except Exception as problem:
            log(f"The AI is not ready ({problem}). Finish it later on the launcher's Downloads tab (Ollama, then the AI model).")

    log("4/9 Database program (MariaDB)...")
    if not os.path.isfile(mariadb_exe(mdb, "mariadbd")):
        found = resolve_mariadb(fetch)
        log(f"Downloading MariaDB {found['version']}...")
        folder = os.path.join(kit, "downloads", "mariadb")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, found["name"])
        data = fetch(found["url"], timeout=1800)
        if found.get("sha256"):
            import hashlib
            if hashlib.sha256(data).hexdigest() != found["sha256"].lower():
                raise RuntimeError("The MariaDB download does not match its published checksum.")
        with open(path, "wb") as handle:
            handle.write(data)
        unpack_single_folder(path, mdb)
    secrets_file = os.path.join(mdb, "xiforever-db.json")       # the database passwords of this install (git-ignored)
    if os.path.exists(secrets_file):
        with open(secrets_file, encoding="utf-8") as handle:
            keys = json.load(handle)
    else:
        keys = {"root": new_password(), "xi": new_password(), "port": free_port()}
        with open(secrets_file, "w", encoding="utf-8") as handle:
            json.dump(keys, handle)
    log(init_mariadb(mdb, keys["root"], keys["port"], run=run))
    proc = start_mariadb(mdb, keys["port"], popen=popen)
    try:
        log("5/9 Database and tables (a few minutes)...")
        create_database(mdb, keys["port"], keys["root"], keys["xi"], run=run)
        tables = sql(mdb, keys["port"], DB_USER, keys["xi"], "SHOW TABLES LIKE 'accounts'", database=DB_NAME, run=run).strip()
        if not tables:
            import_sql(mdb, keys["port"], keys["xi"], import_order(server), log=log, run=run)
        else:
            log("The tables are already there.")
        log("6/9 Your game account...")
        log(create_account(mdb, keys["port"], keys["xi"], choices["login"], choices["password"], run=run))
    finally:
        stop_mariadb(mdb, keys["port"], keys["root"], run=run)
        if proc is not None:
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()

    log("7/9 Server settings...")
    log(write_network_settings(server, keys["port"], keys["xi"]))
    log("8/9 Ashita boot file and script...")
    log(write_boot(ashita, choices["login"], choices["password"]))
    addons = list(STOCK_ADDONS) + list(START_ADDONS) + [a for a in ("mobdb", "chains") if a in choices.get("extras", [])]
    plugins = list(STOCK_PLUGINS) + (["Nameplate"] if "nameplate" in choices.get("extras", []) else [])
    log(write_script(ashita, choices.get("interface"), addons, plugins))

    log("9/9 Your settings...")
    rates = core.apply_world(dict(core.RATE_DEFAULTS), choices["world"], choices["population"])
    if not os.path.exists(core.rates_path(kit)):
        core.save_rates(kit, rates)
    cfg = write_config(kit, {
        "server_dir": server, "ffxi_client_dir": choices["ffxi_dir"], "ashita_dir": ashita, "ashita_boot": BOOT_NAME,
        "db_name": DB_NAME, "db_user": DB_USER, "db_pass": keys["xi"], "db_port": keys["port"],
        "game_user": choices["login"], "game_pass": choices["password"],
        "mariadb_dir": mdb, "mariadb_service": "", "world": choices["world"]})
    log("Setup finished.")
    return cfg


# ----- used by the launcher on every Play (portable installs only) -----
def portable_keys(cfg):
    with open(os.path.join(cfg["mariadb_dir"], "xiforever-db.json"), encoding="utf-8") as handle:
        return json.load(handle)


def start_portable(cfg, popen=subprocess.Popen):
    """Starts the kit's MariaDB if it is not running yet. Returns the process this call started, or None."""
    return start_mariadb(cfg["mariadb_dir"], int(cfg.get("db_port", 3306)), popen=popen)


def stop_portable(cfg, run=subprocess.run):
    try:
        stop_mariadb(cfg["mariadb_dir"], int(cfg.get("db_port", 3306)), portable_keys(cfg)["root"], run=run)
    except (OSError, ValueError, KeyError):
        pass


# ----- Phoenix's Era-DATs (the same steps and backup layout as install-era-dats.ps1 / restore-original-dats.ps1) -----
def install_era_dats(kit, ffxi_dir, era_dir=None, log=print):
    """Copies Era-DATs\\ROM..ROM4 into the game folder. Every file it replaces is saved in <kit>\\dat-backup first and the
    new ones are listed in dat-backup\\new-files.txt, so restore-original-dats.ps1 can undo it."""
    era_dir = era_dir or os.path.join(kit, "Era-DATs")
    backup = os.path.join(kit, "dat-backup")
    if not os.path.isdir(os.path.join(ffxi_dir, "ROM")):
        raise RuntimeError("That is not the FFXI game folder (no ROM folder).")
    if os.path.isdir(backup):
        return ["The Era-DATs are already installed (dat-backup exists). Run restore-original-dats.ps1 to undo them."]
    files = []
    for rom in ("ROM", "ROM2", "ROM3", "ROM4"):
        for root, _dirs, names in os.walk(os.path.join(era_dir, rom)):
            files += [os.path.relpath(os.path.join(root, n), era_dir) for n in names]
    if not files:
        raise RuntimeError("The Era-DATs are not downloaded yet.")
    new = []
    for index, rel in enumerate(files, 1):
        dest = os.path.join(ffxi_dir, rel)
        if os.path.exists(dest):
            os.makedirs(os.path.dirname(os.path.join(backup, rel)), exist_ok=True)
            shutil.copy2(dest, os.path.join(backup, rel))
        else:
            new.append(rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(os.path.join(era_dir, rel), dest)
        if index % 500 == 0:
            log(f"Era-DATs: {index}/{len(files)}")
    os.makedirs(backup, exist_ok=True)
    with open(os.path.join(backup, "new-files.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(new) + ("\n" if new else ""))
    return [f"Era-DATs installed: {len(files)} files ({len(files) - len(new)} originals saved in dat-backup)."]
