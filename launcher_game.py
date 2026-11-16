"""The game files for XI: Forever Offline.

Three ways to get them (first-run setup asks):
  copy      the player has FINAL FANTASY XI: copy PlayOnline and FFXI into the kit's own Game folder, so their own
            install (retail, other servers, HD packs) is never changed. Era-DATs then go into the copy only.
  existing  use the installed game as it is (how every install worked before this file).
  official  no FFXI on this PC: download Square Enix's own full installer from Square Enix and run it.

xiloader finds the game through Windows' registry (32-bit view): PlayOnline's InstallFolder values (0001 = FFXI,
1000 = the PlayOnline viewer) and two COM registrations, polcore (one class per language) and FFXi.dll. When a copy
is used and those point at another install, Play runs this file elevated ("hold"): it points them at the copy, waits
until every game window is closed and puts the old values back. The old values are kept in game-switch.json until
then, so a crash or power cut is undone the next time the launcher starts ("recover").
"""
import json
import ntpath
import os
import shutil
import subprocess
import sys
import time
import urllib.request

LANG_KEY = {"JP": "PlayOnline", "US": "PlayOnlineUS", "EU": "PlayOnlineEU"}
POLCORE_CLSID = {"JP": "{07974581-0DF6-4EF0-BD05-604B3ADA9BE9}", "US": "{3501F5DD-7894-42DF-866A-A2B6527D8049}",
                 "EU": "{E5966FB3-C97B-42EB-84BF-37F95EE54A9F}"}
POLCORE_DLL = {"JP": "polcore.dll", "US": "polcore.dll", "EU": "polcoreeu.dll"}
FFXI_CLSID = "{989D790D-6236-11D4-80E9-00105A81E890}"
FFXI_DLL = "FFXi.dll"
# Square Enix's own full installer (FFXI, PlayOnline and every expansion), straight from Square Enix: part1.exe
# unpacks itself and part2.rar, part3.rar... (5 parts, about 7.2 GB, in 2026) into FFXIFullSetup_US, then
# FFXISetup.exe in there installs the game. Parts are fetched until Square Enix has no next one.
OFFICIAL_BASE = {"US": "https://gdl.square-enix.com/ffxi/download/us/FFXIFullSetup_US"}
OFFICIAL_MIN_PARTS = 5
OFFICIAL_MAX_PARTS = 12
STATE_FILE = "game-switch.json"
HKLM = "HKLM"


def game_paths(root):
    """Where a copy lives: <root>\\SquareEnix\\PlayOnlineViewer and <root>\\SquareEnix\\FINAL FANTASY XI."""
    base = os.path.join(root, "SquareEnix")
    return {"viewer": os.path.join(base, "PlayOnlineViewer"), "ffxi": os.path.join(base, "FINAL FANTASY XI")}


# ----- the registry (32-bit view, as xiloader reads it) -----
class WinRegistry:
    """get/set/delete one value under HKLM in the 32-bit view. name "" is a key's default value."""

    def __init__(self):
        import winreg
        self.w = winreg

    def get(self, path, name):
        w = self.w
        try:
            with w.OpenKey(w.HKEY_LOCAL_MACHINE, path, 0, w.KEY_READ | w.KEY_WOW64_32KEY) as key:
                return w.QueryValueEx(key, name)[0]
        except OSError:
            return None

    def set(self, path, name, value):
        w = self.w
        with w.CreateKeyEx(w.HKEY_LOCAL_MACHINE, path, 0, w.KEY_WRITE | w.KEY_WOW64_32KEY) as key:
            w.SetValueEx(key, name, 0, w.REG_SZ, value)

    def delete(self, path, name):
        w = self.w
        try:
            with w.OpenKey(w.HKEY_LOCAL_MACHINE, path, 0, w.KEY_WRITE | w.KEY_WOW64_32KEY) as key:
                w.DeleteValue(key, name)
        except OSError:
            pass


def registry():
    return WinRegistry()


def entries(lang, viewer, ffxi, reg):
    """[(path, name, value wanted for this copy)] for the four values xiloader and the game read."""
    folder = rf"SOFTWARE\{LANG_KEY[lang]}\InstallFolder"
    polcore = rf"SOFTWARE\Classes\CLSID\{POLCORE_CLSID[lang]}\InprocServer32"
    game = rf"SOFTWARE\Classes\CLSID\{FFXI_CLSID}\InprocServer32"
    # keep the file names the installed registration uses (polcore.dll / FFXi.dll), only the folder moves
    polcore_name = ntpath.basename(reg.get(polcore, "") or "") or POLCORE_DLL[lang]
    game_name = ntpath.basename(reg.get(game, "") or "") or FFXI_DLL
    return [(folder, "0001", ffxi), (folder, "1000", viewer),
            (polcore, "", ntpath.join(viewer, polcore_name)), (game, "", ntpath.join(ffxi, game_name))]


def _same(a, b):
    return a is not None and b is not None and os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def needs_switch(cfg, reg):
    """True when the game copy is used and Windows points PlayOnline at another install."""
    if not cfg.get("game_copy"):
        return False
    lang = cfg.get("pol_lang", "US")
    return any(not _same(reg.get(p, n), v) for p, n, v in entries(lang, cfg["pol_dir"], cfg["ffxi_client_dir"], reg))


def _restore(originals, reg):
    for path, name, value in originals:
        if value is None:
            reg.delete(path, name)
        else:
            reg.set(path, name, value)


def _write_state(state_path, state):
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=1)
    os.replace(tmp, state_path)


def hold(state_path, reg, is_running, sleep=time.sleep, start_wait=180, poll=2):
    """Elevated: point the registry at the copy, wait until the game has started and every game window is closed,
    then put the old values back. The old values are saved first, so recover() can undo a crash."""
    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    want = entries(state["lang"], state["viewer"], state["ffxi"], reg)
    state["originals"] = [(p, n, reg.get(p, n)) for p, n, _v in want]
    _write_state(state_path, state)
    try:
        for path, name, value in want:
            reg.set(path, name, value)
        state["applied"] = True
        _write_state(state_path, state)
        waited = 0
        while not is_running() and waited < start_wait:     # the launcher starts the game right after "applied"
            sleep(poll)
            waited += poll
        while is_running():
            sleep(poll)
    finally:
        _restore(state["originals"], reg)
        os.remove(state_path)


def recover(state_path, reg):
    """Puts back what a hold() that never finished (crash, power cut) had changed. True when something was undone."""
    if not os.path.exists(state_path):
        return False
    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    if state.get("originals"):
        _restore(state["originals"], reg)
    os.remove(state_path)
    return bool(state.get("originals"))


def pending_recovery(kit):
    """True when an earlier switch was left in place (its helper never got to put the old values back)."""
    return os.path.exists(os.path.join(kit, STATE_FILE))


def start_switch(kit, cfg, run_elevated, reg=None, is_running=None, sleep=time.sleep, timeout=60):
    """Before Play: when the copy is used and the registry points elsewhere, starts the elevated helper and waits until
    it has switched. Returns False when nothing needed switching. Raises when Windows' permission was refused."""
    reg = reg or registry()
    if not needs_switch(cfg, reg):
        return False
    state_path = os.path.join(kit, STATE_FILE)
    if os.path.exists(state_path):
        if is_running is not None and is_running():
            return True          # a game window is open: the helper from that Play still holds the switch
        run_elevated(["recover", state_path])           # left over from a crash: undo it first
        for _ in range(timeout):
            if not os.path.exists(state_path):
                break
            sleep(1)
    _write_state(state_path, {"lang": cfg.get("pol_lang", "US"), "viewer": cfg["pol_dir"], "ffxi": cfg["ffxi_client_dir"]})
    run_elevated(["hold", state_path])
    for _ in range(timeout * 2):
        try:
            with open(state_path, encoding="utf-8") as handle:
                if json.load(handle).get("applied"):
                    return True
        except (OSError, ValueError):
            pass
        sleep(0.5)
    try:
        os.remove(state_path)
    except OSError:
        pass
    raise RuntimeError("PlayOnline could not be pointed at XI: Forever Offline's copy of the game: Windows' permission "
                       "prompt was refused or never answered. Press PLAY again and choose Yes, or the game would start "
                       "your other FINAL FANTASY XI install.")


def detect_lang(ffxi_dir, reg=None):
    """US, EU or JP: the PlayOnline entry whose FFXI folder is this one (US when none matches)."""
    try:
        reg = reg or registry()
    except ImportError:
        return "US"
    for lang, key in (("US", "PlayOnlineUS"), ("EU", "PlayOnlineEU"), ("JP", "PlayOnline")):
        if _same(reg.get(rf"SOFTWARE\{key}\InstallFolder", "0001"), ffxi_dir):
            return lang
    return "US"


# ----- making a copy -----
def find_viewer(ffxi_dir, lang="US", reg=None):
    """The PlayOnline viewer folder that belongs with this FFXI folder."""
    try:
        reg = reg or registry()
        viewer = reg.get(rf"SOFTWARE\{LANG_KEY[lang]}\InstallFolder", "1000")
        if viewer and os.path.isdir(viewer):
            return viewer
    except ImportError:
        pass
    sibling = os.path.join(os.path.dirname(os.path.normpath(ffxi_dir)), "PlayOnlineViewer")
    return sibling if os.path.isdir(sibling) else None


def folder_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def copy_install(ffxi_dir, viewer_dir, dest_root, log=print, free=None):
    """Copies PlayOnline and FFXI into dest_root (see game_paths). Files already copied (same size) are skipped, so
    it can be run again after a stop. Returns the new paths."""
    paths = game_paths(dest_root)
    jobs = [(viewer_dir, paths["viewer"]), (ffxi_dir, paths["ffxi"])]
    todo = []
    for src, dst in jobs:
        for root, _dirs, files in os.walk(src):
            for name in files:
                s = os.path.join(root, name)
                d = os.path.join(dst, os.path.relpath(s, src))
                size = os.path.getsize(s)
                if not (os.path.exists(d) and os.path.getsize(d) == size):
                    todo.append((s, d, size))
    need = sum(size for _s, _d, size in todo)
    os.makedirs(dest_root, exist_ok=True)
    have = free if free is not None else shutil.disk_usage(dest_root).free
    if need > have - 512 * 1024 * 1024:
        raise RuntimeError(f"Not enough free space for the game copy: it needs {need / 2**30:.1f} GB and "
                           f"{have / 2**30:.1f} GB is free on that drive.")
    log(f"   Copying {len(todo)} game files ({need / 2**30:.1f} GB) into {dest_root}...")
    done, step = 0, max(need // 20, 1)
    mark = step
    for s, d, size in todo:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        done += size
        if done >= mark:
            log(f"   {done * 100 // max(need, 1)}%")
            mark += step
    return paths


# ----- Square Enix's official installer -----
def download_to(url, path, log=print, context=None, chunk=1 << 20):
    """Streams a big file to disk; a stopped download carries on from where it was (<name>.part)."""
    if os.path.exists(path):
        return path
    part = path + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    request = urllib.request.Request(url, headers={"User-Agent": "XI-Forever-Offline"})
    if have:
        request.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(request, timeout=60, context=context) as response:
        if have and response.status != 206:      # the server started over: so do we
            have = 0
        total = have + int(response.headers.get("Content-Length") or 0)
        mark = 0
        with open(part, "ab" if have else "wb") as handle:
            done = have
            while True:
                data = response.read(chunk)
                if not data:
                    break
                handle.write(data)
                done += len(data)
                if total and done * 10 // total > mark:
                    mark = done * 10 // total
                    log(f"   {os.path.basename(path)}: {done * 100 // total}% of {total / 2**30:.1f} GB")
    os.replace(part, path)
    return path


def official_folder(kit):
    return os.path.join(kit, "downloads", "ffxi-installer")


def download_official(kit, log=print, lang="US", context=None, download=None):
    """Every part of Square Enix's installer into downloads\\ffxi-installer (parts already there are kept)."""
    import urllib.error
    download = download or download_to
    folder = official_folder(kit)
    os.makedirs(folder, exist_ok=True)
    files = []
    for number in range(1, OFFICIAL_MAX_PARTS + 1):
        name = f"{OFFICIAL_BASE[lang].rsplit('/', 1)[-1]}.part{number}." + ("exe" if number == 1 else "rar")
        url = f"{OFFICIAL_BASE[lang]}.part{number}." + ("exe" if number == 1 else "rar")
        log(f"   Downloading {name} from Square Enix...")
        try:
            files.append(download(url, os.path.join(folder, name), log=log, context=context))
        except urllib.error.HTTPError as problem:
            if problem.code == 404 and number > OFFICIAL_MIN_PARTS:
                log(f"   That was the last part ({number - 1} in all).")
                break
            raise
    return files


def find_setup(kit):
    """FFXISetup.exe inside what part1.exe unpacked, or None."""
    for root, _dirs, names in os.walk(official_folder(kit)):
        for name in names:
            if name.lower() == "ffxisetup.exe":
                return os.path.join(root, name)
    return None


def run_official_installer(kit, files, log=print, popen=subprocess.Popen):
    """Unpacks the parts (part1.exe: press Extract and keep its folder) unless that was done, then runs FFXISetup.exe
    (tick PlayOnline, FINAL FANTASY XI and the expansions, then Install) and waits for it."""
    setup = find_setup(kit)
    if setup is None:
        log("   Square Enix's unpacker is opening: press Extract and keep the folder it suggests.")
        popen([files[0]], cwd=os.path.dirname(files[0])).wait()
        setup = find_setup(kit)
        if setup is None:
            raise RuntimeError("Square Enix's files were not unpacked into " + official_folder(kit) + ". Press Install again "
                               "and let the unpacker extract into the folder it suggests.")
    log("   Square Enix's setup is opening: tick every box (PlayOnline, FINAL FANTASY XI and the expansions), press "
        "Install and follow it to the end.")
    proc = popen([setup], cwd=os.path.dirname(setup))
    proc.wait()
    return proc.returncode


# ----- the first update of a fresh install (PlayOnline's free "Check Files"; no Square Enix account needed) -----
VTABLE = "VTABLE.DAT"
VTABLE_BACKUP = "VTABLE.DAT.before-update"


def viewer_dir(cfg, reg=None):
    """The PlayOnline viewer folder of this install (the copy's own, or the one that goes with the FFXI folder)."""
    if cfg.get("pol_dir") and os.path.isdir(cfg["pol_dir"]):
        return cfg["pol_dir"]
    ffxi = cfg.get("ffxi_client_dir", "")
    lang = cfg.get("pol_lang") or detect_lang(ffxi, reg)
    return find_viewer(ffxi, lang, reg)


def pol_exe(cfg, reg=None):
    viewer = viewer_dir(cfg, reg)
    for name in ("pol.exe", "polboot.exe"):
        if viewer and os.path.isfile(os.path.join(viewer, name)):
            return os.path.join(viewer, name)
    return None


def open_playonline(cfg, start=None, reg=None):
    """Starts PlayOnline the way Windows would (so it can ask for administrator rights for its own update)."""
    exe = pol_exe(cfg, reg)
    if not exe:
        raise RuntimeError("PlayOnline (pol.exe) wasn't found next to your game. Start 'PlayOnline Viewer' from the "
                           "Start menu instead.")
    (start or os.startfile)(exe)
    return exe


def force_version_check(ffxi_dir):
    """When Check Files says there is nothing to update (it happens without a retail account), moving VTABLE.DAT
    aside makes it look again. finish_version_check puts it back if PlayOnline didn't rebuild it."""
    table, backup = os.path.join(ffxi_dir, VTABLE), os.path.join(ffxi_dir, VTABLE_BACKUP)
    if not os.path.exists(table):
        return os.path.exists(backup)          # already moved
    if os.path.exists(backup):
        os.remove(backup)
    os.replace(table, backup)
    return True


def finish_version_check(ffxi_dir):
    """'updated' (PlayOnline rebuilt VTABLE.DAT: our copy is dropped), 'restored' (it didn't: ours put back),
    or 'unchanged' (the trick was never used)."""
    table, backup = os.path.join(ffxi_dir, VTABLE), os.path.join(ffxi_dir, VTABLE_BACKUP)
    if not os.path.exists(backup):
        return "unchanged"
    if os.path.exists(table):
        os.remove(backup)
        return "updated"
    os.replace(backup, table)
    return "restored"


def main(argv):
    """XI Forever Offline.exe --run launcher_game.py hold|recover <state file>   (run elevated by the launcher)"""
    if len(argv) != 2 or argv[0] not in ("hold", "recover"):
        print(main.__doc__)
        return 2
    reg = registry()
    if argv[0] == "recover":
        recover(argv[1], reg)
        return 0
    import launcher_core as core
    hold(argv[1], reg, lambda: core.is_running("xiloader"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
