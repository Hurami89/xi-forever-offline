"""Give the Home Point crystals their retail teleport window back.

  python restore_retail_homepoints.py            put the retail Home Point events back (close the game first)
  python restore_retail_homepoints.py --status   show which zones have the era or the retail Home Point events
  python restore_retail_homepoints.py --undo     put the era versions back

Why: the era DAT pack (install-era-dats.ps1) replaced the event files of the cities and outposts. In those files
it patched the Home Point crystals (11 bytes each) so their window only offers "set home point". Everything else in
the era files is kept as it is. This tool copies ONLY the Home Point entries from the original game files (the
backups the era installer saved in dat-backup) back into the era files.

- Event files are a count, a table of entry sizes, then one entry per NPC (starting with the NPC's id).
- Home Point NPC ids come from the server's zone data (display_name "Home Point ...").
- An entry is replaced only when the original has the same size, so nothing else in the file moves.
- Each file is copied once to backups\\homepoint-events\\ before the first change (for --undo).
Run again after reinstalling the era DAT pack.
"""
import argparse, glob, json, os, re, shutil, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, "backups", "homepoint-events")


def config():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8-sig") as f:
        return json.load(f)


def homepoint_ids(server_dir):
    ids = set()
    for path in glob.glob(os.path.join(server_dir, "data", "zones", "*", "npcs.yaml")):
        current = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^  (\d+):\s*$", line)
                if m:
                    current = int(m.group(1))
                    continue
                m = re.match(r"^    display_name:\s*(.*)", line)
                if m and current is not None and m.group(1).strip().strip("'\"").startswith("Home Point"):
                    ids.add(current)
    return ids


def entries(data):
    """List of (start, size) of every entry, or None if this is not an event file."""
    if len(data) < 8:
        return None
    count = struct.unpack_from("<I", data, 0)[0]
    if count == 0 or count > 5000 or 4 + 4 * count > len(data):
        return None
    sizes = struct.unpack_from("<%dI" % count, data, 4)
    if 4 + 4 * count + sum(sizes) != len(data):
        return None
    out, off = [], 4 + 4 * count
    for s in sizes:
        out.append((off, s))
        off += s
    return out


def entry_id(data, start, size):
    return struct.unpack_from("<I", data, start)[0] if size >= 4 else None


def plan(game_dir, era_backup_dir, hp_ids):
    """For every event file the era pack replaced: (relative path, [(start, retail bytes)], skipped, already)."""
    result = []
    for root, _dirs, files in os.walk(era_backup_dir):
        for name in files:
            if not name.upper().endswith(".DAT"):
                continue
            rel = os.path.relpath(os.path.join(root, name), era_backup_dir)
            game_file = os.path.join(game_dir, rel)
            if not os.path.isfile(game_file):
                continue
            with open(os.path.join(era_backup_dir, rel), "rb") as f:
                retail = f.read()
            with open(game_file, "rb") as f:
                current = f.read()
            er, ec = entries(retail), entries(current)
            if er is None or ec is None:
                continue
            retail_by_id = {}
            for start, size in er:
                eid = entry_id(retail, start, size)
                if eid in hp_ids:
                    retail_by_id[eid] = retail[start:start + size]
            if not retail_by_id:
                continue
            changes, skipped, already = [], [], 0
            for start, size in ec:
                eid = entry_id(current, start, size)
                if eid not in retail_by_id:
                    continue
                want = retail_by_id[eid]
                if current[start:start + size] == want:
                    already += 1
                elif len(want) != size:
                    skipped.append(eid)
                else:
                    changes.append((start, want))
            result.append((rel, changes, skipped, already))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Retail Home Point teleport window")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--client", help="game folder (default: config.json ffxi_client_dir)")
    ap.add_argument("--server", help="server folder (default: config.json server_dir)")
    ap.add_argument("--era-backup", help="the era installer's backup of the original files (default: <kit>\\dat-backup)")
    a = ap.parse_args(argv)
    cfg = config()
    game = a.client or cfg["ffxi_client_dir"]
    server = a.server or cfg["server_dir"]
    era_backup = a.era_backup or os.path.join(HERE, "dat-backup")

    if a.undo:
        n = 0
        for root, _dirs, files in os.walk(BACKUP):
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), BACKUP)
                shutil.copy2(os.path.join(root, name), os.path.join(game, rel))
                n += 1
        print("Put back %d era event file(s). Restart the game." % n)
        return 0

    if not os.path.isdir(era_backup):
        print("No era backup folder at %s: the era DAT pack does not seem to be installed, so the Home Points should already be retail." % era_backup)
        return 1
    hp_ids = homepoint_ids(server)
    if not hp_ids:
        print("No Home Points found in %s\\data\\zones - is server_dir right?" % server)
        return 1

    work = plan(game, era_backup, hp_ids)
    if a.status:
        for rel, changes, skipped, already in sorted(work):
            state = "retail" if not changes and not skipped else "ERA (%d to restore)" % len(changes)
            print("  %-16s %s%s" % (rel, state, ("  skipped (size differs): %s" % skipped) if skipped else ""))
        return 0

    total, files = 0, 0
    for rel, changes, skipped, already in sorted(work):
        if not changes:
            continue
        path = os.path.join(game, rel)
        keep = os.path.join(BACKUP, rel)
        if not os.path.exists(keep):
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            shutil.copy2(path, keep)
        with open(path, "rb") as f:
            data = bytearray(f.read())
        for start, want in changes:
            data[start:start + len(want)] = want
        tmp = path + ".hp-tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        with open(path, "rb") as f:
            check = f.read()
        if any(check[s:s + len(w)] != w for s, w in changes):
            print("Read-back check failed for %s - run with --undo." % rel)
            return 1
        print("  %-16s %d Home Point(s) restored%s" % (rel, len(changes), ("; skipped %s" % skipped) if skipped else ""))
        total += len(changes)
        files += 1
    print("Done: %d Home Point(s) in %d file(s). Start the game: the crystals now show the retail teleport window." % (total, files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
