"""Install the Crystal Boy addon (Game Boy emulator window) into Ashita 4.

  python install_crystalboy.py              install or update
  python install_crystalboy.py --core FILE  use a core DLL you downloaded yourself
  python install_crystalboy.py --status     show what is installed
  python install_crystalboy.py --uninstall  remove the addon (saves and ROMs are kept)

Your ROMs go in  <Ashita>\\config\\addons\\crystalboy\\roms
"""
import argparse, io, json, os, shutil, struct, sys, tempfile, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "crystalboy")
KIT = r"C:\FFXISOLO"
CORE_URL = "https://buildbot.libretro.com/nightly/windows/x86/latest/{}_libretro.dll.zip"
CORES = ["gambatte", "sameboy", "gearboy"]
NEEDED = ["retro_init", "retro_run", "retro_load_game", "retro_api_version", "retro_serialize",
          "retro_unserialize", "retro_serialize_size", "retro_get_memory_data", "retro_get_memory_size"]
AUTOLOAD = "/addon load crystalboy"


def ashita_dir():
    cfg = os.path.join(KIT, "config.json")
    try:
        with open(cfg, encoding="utf-8") as f:
            d = json.load(f).get("ashita_dir")
        if d:
            return d
    except (OSError, ValueError):
        pass
    return r"C:\Ashita-v4beta-main"


def boot_script(ashita):
    """The addon script used by the main window (phoenixsolo.txt)."""
    name = "phoenixsolo"
    try:
        with open(os.path.join(KIT, "config.json"), encoding="utf-8") as f:
            boot = json.load(f).get("ashita_boot", "phoenixsolo.ini")
        name = os.path.splitext(os.path.basename(boot))[0]
    except (OSError, ValueError):
        pass
    return os.path.join(ashita, "scripts", name + ".txt")


def pe_check(data):
    """Return (ok, message). ok only for a 32-bit Windows DLL exporting the libretro functions."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        return False, "not a Windows program file"
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return False, "not a Windows program file"
    machine, nsec = struct.unpack_from("<HH", data, pe + 4)
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    if machine != 0x14C:
        return False, "this core is 64-bit (machine %04X); the game needs a 32-bit core" % machine
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x10B:
        return False, "unexpected file layout"
    exp_rva = struct.unpack_from("<I", data, opt + 96)[0]
    secs = []
    for i in range(nsec):
        s = opt + opt_size + i * 40
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, s + 8)
        secs.append((va, max(vsize, rsize), raw))

    def off(rva):
        for va, size, raw in secs:
            if va <= rva < va + size:
                return rva - va + raw
        raise ValueError("bad address")

    try:
        e = off(exp_rva)
        nnames, _, names = struct.unpack_from("<III", data, e + 24)
        found = set()
        for i in range(nnames):
            p = off(struct.unpack_from("<I", data, off(names) + i * 4)[0])
            found.add(data[p:data.index(b"\0", p)].decode("ascii", "replace"))
    except (ValueError, struct.error):
        return False, "could not read the list of functions"
    missing = [n for n in NEEDED if n not in found]
    if missing:
        return False, "not a usable libretro core (missing %s)" % ", ".join(missing)
    return True, "32-bit libretro core"


def download_core(dest_dir):
    for name in CORES:
        url = CORE_URL.format(name)
        print("  Trying %s ..." % url)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                blob = r.read()
            z = zipfile.ZipFile(io.BytesIO(blob))
            dll = next(n for n in z.namelist() if n.lower().endswith(".dll"))
            data = z.read(dll)
        except Exception as ex:  # network, 404, bad zip
            print("    not available (%s)" % ex)
            continue
        ok, why = pe_check(data)
        if not ok:
            print("    skipped: " + why)
            continue
        path = os.path.join(dest_dir, os.path.basename(dll))
        with open(path, "wb") as f:
            f.write(data)
        print("    OK: %s (%d KB)" % (os.path.basename(path), len(data) // 1024))
        return path
    return None


def installed_core(cores):
    if not os.path.isdir(cores):
        return None
    for n in sorted(os.listdir(cores)):
        if n.lower().endswith("_libretro.dll"):
            p = os.path.join(cores, n)
            with open(p, "rb") as f:
                if pe_check(f.read())[0]:
                    return p
    return None


def set_autoload(script, on):
    if not os.path.isfile(script):
        print("  Addon script not found (%s): load it by hand with /addon load crystalboy" % script)
        return
    with open(script, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    has = any(l.strip().lower() == AUTOLOAD for l in lines)
    if on and not has:
        shutil.copy2(script, script + ".before-crystalboy")
        with open(script, "a", encoding="utf-8") as f:
            if lines and lines[-1] != "":
                f.write("\n")
            f.write(AUTOLOAD + "\n")
        print("  Added '%s' to %s" % (AUTOLOAD, os.path.basename(script)))
    elif not on and has:
        shutil.copy2(script, script + ".before-crystalboy-removal")
        with open(script, "w", encoding="utf-8") as f:
            f.write("\n".join(l for l in lines if l.strip().lower() != AUTOLOAD) + "\n")
        print("  Removed the autoload line from %s" % os.path.basename(script))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Install Crystal Boy")
    ap.add_argument("--ashita", help="Ashita folder (default: from config.json)")
    ap.add_argument("--core", help="a libretro core .dll (or its .zip) you downloaded")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--no-autoload", action="store_true", help="do not add the addon to the startup script")
    a = ap.parse_args(argv)

    ashita = a.ashita or ashita_dir()
    target = os.path.join(ashita, "addons", "crystalboy")
    cores = os.path.join(target, "cores")
    cfg = os.path.join(ashita, "config", "addons", "crystalboy")
    script = boot_script(ashita)

    if not os.path.isdir(ashita):
        print("Ashita folder not found: %s" % ashita)
        return 1

    if a.status:
        print("Addon folder : %s (%s)" % (target, "installed" if os.path.isfile(os.path.join(target, "crystalboy.lua")) else "not installed"))
        c = installed_core(cores)
        print("Core         : %s" % (c or "none"))
        roms = os.path.join(cfg, "roms")
        n = len([x for x in os.listdir(roms) if x.lower().endswith((".gb", ".gbc"))]) if os.path.isdir(roms) else 0
        print("ROMs         : %d in %s" % (n, roms))
        return 0

    if a.uninstall:
        set_autoload(script, False)
        if os.path.isdir(target):
            shutil.rmtree(target)
            print("  Removed %s" % target)
        print("Done. Your ROMs, saves and states are still in %s" % cfg)
        return 0

    if not os.path.isfile(os.path.join(SRC, "crystalboy.lua")):
        print("The crystalboy folder is missing next to this script. Unzip the whole kit first.")
        return 1

    print("1. Addon files")
    os.makedirs(cores, exist_ok=True)
    for root, _dirs, files in os.walk(SRC):
        rel = os.path.relpath(root, SRC)
        dest = os.path.join(target, rel) if rel != "." else target
        os.makedirs(dest, exist_ok=True)
        for fn in files:
            if fn == "rewards_default.lua":
                continue
            shutil.copy2(os.path.join(root, fn), os.path.join(dest, fn))
    print("  Copied to %s" % target)

    print("2. Emulator core")
    if a.core:
        data = open(a.core, "rb").read()
        name = os.path.basename(a.core)
        if a.core.lower().endswith(".zip"):
            z = zipfile.ZipFile(a.core)
            name = next(n for n in z.namelist() if n.lower().endswith(".dll"))
            data = z.read(name)
            name = os.path.basename(name)
        ok, why = pe_check(data)
        if not ok:
            print("  That file cannot be used: " + why)
            return 1
        if not name.lower().endswith("_libretro.dll"):
            name = os.path.splitext(name)[0] + "_libretro.dll"
        with open(os.path.join(cores, name), "wb") as f:
            f.write(data)
        print("  Installed %s (%s)" % (name, why))
    else:
        have = installed_core(cores)
        if have:
            print("  Already installed: %s" % os.path.basename(have))
        elif not download_core(cores):
            print("  Could not download a core. Get the 32-bit (x86) gambatte_libretro.dll.zip from")
            print("  https://buildbot.libretro.com/nightly/windows/x86/latest/ and run:")
            print('  python install_crystalboy.py --core "%USERPROFILE%\\Downloads\\gambatte_libretro.dll.zip"')

    print("3. Folders and settings")
    for d in ("roms", "system", "saves", "states", "claims", "snaps"):
        os.makedirs(os.path.join(cfg, d), exist_ok=True)
    rw = os.path.join(cfg, "rewards.lua")
    if not os.path.exists(rw):
        shutil.copy2(os.path.join(SRC, "rewards_default.lua"), rw)
        print("  Wrote %s" % rw)
    print("  ROM folder: %s" % os.path.join(cfg, "roms"))

    print("4. Startup")
    if not a.no_autoload:
        set_autoload(script, True)

    print("\nDone. Put your .gb/.gbc files in the ROM folder, start the game, then type /cb")
    print("(If the game is already running: /addon load crystalboy)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
