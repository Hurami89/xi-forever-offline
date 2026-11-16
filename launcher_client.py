"""Game-file changes XI: Forever Offline makes to the player's FINAL FANTASY XI folder, after the era game files.

  1. Home Point teleport window: the era files only offer "Set home point"; the retail Home Point entries are put
     back (restore_retail_homepoints.py; needs the era installer's backup in <kit>\\dat-backup).
  2. Crystal Boy items: the Crystal Boy and the four Recollections (ROM\\118\\107.DAT), the four Memory key items
     (ROM\\175\\35.DAT) and the Anniversary Ring made stackable (ROM\\118\\109.DAT) (install_crystalboy_items.py).
  3. Chariot Band: its description (+75%, 720 min, 4000), 3 charges and a 15-hour recast (client-patches\\chariot_band.json).

Every step checks first and only writes what is missing, so this runs at the end of first-run setup and again on
every PLAY of a player install (an update or a reinstalled era pack is caught the next time). A step that cannot be
done (a folder Windows won't let the launcher write, a file that is not the expected one) is reported and skipped;
it never stops the game from starting. Originals are kept in <kit>\\backups.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _kit_module(kit, name):
    if kit not in sys.path:
        sys.path.insert(0, kit)
    return __import__(name)


# ----- 1. Home Points -----
def homepoints(kit, game, server, log=print):
    rrh = _kit_module(kit, "restore_retail_homepoints")
    era_backup = os.path.join(kit, "dat-backup")
    if not os.path.isdir(era_backup):
        return "Home Points: the era game files are not installed, so they are already retail."
    hp_ids = rrh.homepoint_ids(server)
    if not hp_ids:
        return "Home Points: no Home Points found in the server's zone data; skipped."
    total = files = 0
    for rel, changes, _skipped, _already in sorted(rrh.plan(game, era_backup, hp_ids)):
        if not changes:
            continue
        path = os.path.join(game, rel)
        keep = os.path.join(rrh.BACKUP, rel)
        if not os.path.exists(keep):
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            with open(path, "rb") as src, open(keep, "wb") as dst:
                dst.write(src.read())
        with open(path, "rb") as handle:
            data = bytearray(handle.read())
        for start, want in changes:
            data[start:start + len(want)] = want
        tmp = path + ".hp-tmp"
        with open(tmp, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
        total += len(changes)
        files += 1
    if not total:
        return None
    return f"Home Points: the teleport window is back on {total} crystal(s) in {files} file(s)."


# ----- 2. Crystal Boy items -----
def crystalboy(kit, game, log=print):
    icb = _kit_module(kit, "install_crystalboy_items")
    done = []
    path = os.path.join(game, icb.DAT_REL)
    rs = icb.record_size(path)
    with open(path, "rb") as handle:
        data = handle.read()
    if any(icb.item_name(icb.read_record(data, rs, it["id"])) != it["name"] for it in icb.ITEMS):
        icb.dat_install(game)
        done.append("items")
    with open(os.path.join(game, icb.KI_REL), "rb") as handle:
        index, body = icb.ki_entries(handle.read())
    def ki_name(kid):
        j = index.get(kid)
        return None if j is None else icb.ki_parse(body[j * icb.KI_ENTRY:(j + 1) * icb.KI_ENTRY])[4]
    if any(ki_name(k["id"]) != k["name"] for k in icb.KEY_ITEMS):
        icb.ki_install(game)
        done.append("key items")
    ring = icb.ring_install(game)
    if "already" not in ring:
        done.append("Anniversary Ring")
    return ("Crystal Boy: game files updated (" + ", ".join(done) + ").") if done else None


# ----- 3. Chariot Band -----
def chariot_band(kit, game, log=print):
    with open(os.path.join(kit, "client-patches", "chariot_band.json"), encoding="utf-8") as handle:
        patch = json.load(handle)
    path = os.path.join(game, *patch["file"].split("/"))
    if os.path.getsize(path) != patch["size"]:
        return "Chariot Band: the game's armor file is not the expected one; its description was left as it is."
    with open(path, "rb") as handle:
        data = bytearray(handle.read())
    if all(data[at] == new for at, _old, new in patch["bytes"]):
        return None
    if not all(data[at] == old for at, old, _new in patch["bytes"]):
        return "Chariot Band: the game's armor file is not the expected one; its description was left as it is."
    keep = os.path.join(kit, "backups", "chariot-band-dat", "109.DAT.original")
    if not os.path.exists(keep):
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        with open(keep, "wb") as handle:
            handle.write(data)
    for at, _old, new in patch["bytes"]:
        data[at] = new
    tmp = path + ".cb-tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)
    return "Chariot Band: its description now matches this server (+75%, 3 charges, 15 hours)."


def apply_all(kit, game, server, log=print):
    """Runs the three steps; returns the messages. Never raises."""
    messages = []
    for name, step in (("Home Points", lambda: homepoints(kit, game, server, log)),
                       ("Crystal Boy", lambda: crystalboy(kit, game, log)),
                       ("Chariot Band", lambda: chariot_band(kit, game, log))):
        try:
            message = step()
        except PermissionError:
            message = (f"{name}: Windows did not let the launcher change the game files in {game}. "
                       "Run the launcher as administrator once (right-click > Run as administrator).")
        except Exception as problem:            # a game file that is not what we expect: leave it alone
            message = f"{name}: skipped ({problem})."
        if message:
            messages.append(message)
            log(message)
    return messages
