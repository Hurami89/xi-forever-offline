"""Forever Gloves (item 23869): beta testers' hands, made from the Fisherman's Gloves (14070), which stay exactly as
they were. Its own item and its own look, like the Forever Beta Shirt, the Forever Patch and the Forever Track Pants.

What it changes in the FINAL FANTASY XI folder (originals kept once in backups\\forever-gloves):
  * Look: hands model 517 (the hands of the free set whose head the patch and whose legs the track pants use; no item
    uses them) gets the Fisherman's Gloves' model (hands model 102) with a new texture in the Forever Beta Shirt's
    colours: the leather turns royal purple, light trim and metal turn gold, the darkest parts turn black. Skin is
    left as it is. Built from the player's own game files; no Square Enix art is stored in the kit.
  * Item: the empty armor slot 23869 in ROM\\286\\73.DAT gets name, description, the Fisherman's Gloves icon
    recoloured, and a use: one charge that never runs out, 8 seconds after equipping, 10 minutes between uses.
The server side is modules\\custom\\lua\\forever_gloves.lua + modules\\custom\\sql\\forever_gloves.sql.
Stats: DEF:1, Fishing skill +1. Use: Teleport to the Fishermen's Guild in Port Windurst.

    python forever_gloves.py status | apply | restore | preview | server   (server: the item's rows into the running database)
    preview writes logs\\forever-gloves\\<race>_<texture>_before.png and _after.png (changes nothing).
(2026-11-27, v2: recoloured by colour, with three crystals placed from the texture; where they land on the hand is not
checked in game yet.)
"""
import argparse, json, os, shutil, struct, sys

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import forever_beta_shirt as fbs                     # shared: game files, DXT3 encoder, item record helpers

VERSION = 3                       # bump when the design changes, so installs rebuild (2: crystals, no skin guess, 3: FOXI)
ITEM_ID, TEMPLATE_ID, TEMPLATE_NAMES = 23869, 14070, ("Fisherman's Gloves", "Fsh. Gloves")
SLOT = 2                          # head 0, body 1, hands 2, legs 3, feet 4
NEW_MODEL = 517                   # a free hands model (the patch uses this set's head, the track pants its legs)
SRC_FILES = {"HumeM": "ROM/125/95", "HumeF": "ROM/126/10", "ElvaanM": "ROM/126/54", "ElvaanF": "ROM/126/99",
             "Tarutaru": "ROM/127/15", "Mithra": "ROM/127/59", "Galka": "ROM/127/103"}   # Fisherman's Gloves (hands model 102), from AltanaViewer's lists
TEMPLATE_FILE, TEMPLATE_FIRST = "ROM/118/109.DAT", 10240   # the English armor file (holds 14070)
ITEM_FILE, ITEM_FIRST, RS = "ROM/286/73.DAT", 23040, 0x1400
RACES = fbs.RACES
BACKUP = os.path.join(KIT, "backups", "forever-gloves")
STATE = os.path.join(BACKUP, "state.json")

ITEM = {
    "name": "Forever Gloves", "log": "pair of Forever Gloves", "plural": "pairs of Forever Gloves",
    "desc": "DEF:1 Fishing skill +1\nEnchantment: Teleport (Windurst Fishermen's Guild)",
    "flags": 0xFC40,              # as the others: CanUse + CanEquip, NoAuction, NoSale, NoDelivery, Ex, Rare
    "targets": 1, "charges": 1, "cast": 8, "delay": 8, "recast": 600,     # as the Forever Track Pants
}


def model_files(g):
    """Our hands model 517's file for each race (models 320-575: dev\\model-ids\\ft.py)."""
    t = fbs.file_table(g)
    return {race: t[70927 + r * 1536 + SLOT * 256 + NEW_MODEL] for r, race in enumerate(RACES)}


def shared_with(g, path):
    """How many model numbers use this game file (a placeholder file is shared by many; ours must not be)."""
    return sum(1 for p in fbs.file_table(g).values() if p == path)


def keep_original(g, rel):
    bk = os.path.join(BACKUP, *rel.split("/")) + ("" if rel.endswith(".DAT") else ".DAT")
    if not os.path.exists(bk):
        os.makedirs(os.path.dirname(bk), exist_ok=True)
        shutil.copy2(fbs.gpath(g, rel), bk)
    return bk


# ------------------------------------------------------------------ texture
from PIL import Image, ImageChops


def masks(img):
    H, S, V = img.convert("RGB").convert("HSV").split()
    m = lambda ch, lo, hi: ch.point(lambda v: 255 if lo <= v <= hi else 0)
    mul = lambda *ms: ms[0] if len(ms) == 1 else ImageChops.multiply(ms[0], mul(*ms[1:]))
    # (v2, 2026-11-27) the gloves' texture has no bare skin: its pale tan patch (the palm) is leather too. Guessing skin by
    # colour left a tan smear on the Hume gloves, so nothing is kept back any more.
    skin = Image.new("L", img.size, 0)
    light = mul(m(S, 0, 70), m(V, 150, 255))                       # pale trim, stitching, metal -> gold
    dark = m(V, 0, 45)                                             # the darkest parts -> black
    rest = Image.new("L", img.size, 255)
    for mk in (skin, light, dark):
        rest = ImageChops.subtract(rest, mk)
    return H, S, V, skin, light, dark, rest


def recolor(img):
    """Leather -> royal purple, pale trim and metal -> gold, the darkest parts -> black-purple; skin stays."""
    a = img.getchannel("A")
    H, S, V, skin, light, dark, rest = masks(img)
    c = lambda v: Image.new("L", img.size, v)
    H2 = Image.composite(c(196), H, rest); S2 = Image.composite(c(150), S, rest)
    V2 = Image.composite(V.point(lambda v: min(255, int(v * 1.25 + 20))), V, rest)
    H2 = Image.composite(c(32), H2, light); S2 = Image.composite(c(150), S2, light)
    V2 = Image.composite(V.point(lambda v: min(255, int(v * 1.05 + 10))), V2, light)
    H2 = Image.composite(c(200), H2, dark); S2 = Image.composite(c(90), S2, dark)
    V2 = Image.composite(V.point(lambda v: int(v * 0.8 + 8)), V2, dark)
    out = Image.merge("HSV", (H2, S2, V2)).convert("RGB"); out.putalpha(a)
    return out


# (v2, 2026-11-27, the user: "add some crystals in there like the other shirts") Glowing crystals like the shirt's
# and the patch's, as fractions of the texture (every race's has the same layout; Tarutaru's is half the size): two on
# the back of the hand, either side of the stitched seam, and a small one in place of the wrist band's buckle.
CRYSTALS = [(0.17, 0.27, 1.0),          # back of the hand, left of the seam
            (0.50, 0.27, 1.0),          # back of the hand, right of the seam
            (0.345, 0.62, 0.7)]         # the wrist band's buckle
BUCKLE = {"Tarutaru": (0.56, 0.625), "Galka": (0.47, 0.575)}   # where those two races' buckle sits instead

# (v3, 2026-11-27, the user: "add the letters FOXI on the gloves somewhere") FOXI in gold with a dark edge, the Forever
# Patch's lettering, on the wrist band beside the buckle: (x0, y0, x1, y1) as fractions of the texture. The band is the
# lighter strip at about 0.56-0.65 down (Tarutaru's 0.62-0.71). Both hands most likely share these pixels, so one
# hand may show the word backwards, as the shirt's side text does (not checked in game).
FOXI = {"default": (0.04, 0.565, 0.31, 0.645), "Galka": (0.06, 0.565, 0.42, 0.645), "Tarutaru": (0.14, 0.625, 0.50, 0.705)}


def design(img, race):
    out = recolor(img)
    import forever_patch as fp
    w0, h0 = img.size
    for k, (fx, fy, size) in enumerate(CRYSTALS):
        if k == 2 and race in BUCKLE:
            fx, fy = BUCKLE[race]
        w = max(6, int(w0 * 0.075 * size)); h = max(9, int(w * 1.45))
        fp.put(out, fp.glow(fp.crystal_sprite(w, h), 2, 0.8), w0 * fx, h0 * fy)
    x0, y0, x1, y1 = FOXI.get(race, FOXI["default"])
    out = fp.strap_text(out, img, [("FOXI", (int(w0 * x0), int(h0 * y0), int(w0 * x1), int(h0 * y1)))])
    a = img.getchannel("A"); out = out.convert("RGB"); out.putalpha(a)
    return out


def textures(d):
    """Every DXT3 texture in a model file: [(offset of the pixels, width, height, name)]."""
    out, o = [], 0
    while o + 16 <= len(d):
        v = struct.unpack_from("<I", d, o + 4)[0]; kind = v & 0x7F; size = ((v >> 7) & 0x7FFFF) * 16
        if kind == 0x20 and d[o + 73:o + 77][::-1] == b"DXT3":
            w, h = struct.unpack_from("<ii", d, o + 37)
            out.append((o + 85, w, abs(h), bytes(d[o:o + 4]).decode("latin-1")))
        if size <= 0:
            break
        o += size
    if not out:
        raise RuntimeError("no DXT3 texture in the Fisherman's Gloves model")
    return out


def build_model(src, race):
    d = bytearray(src)
    before, after = [], []
    for off, w, h, name in textures(src):
        n = w * h
        img = Image.frombytes("RGBA", (w, h), bytes(src[off:off + n]), "bcn", (2,))
        new = design(img, race)
        enc = fbs.dxt3_encode(new)
        if len(enc) != n:
            raise RuntimeError("texture encoder size mismatch (%d of %d bytes)" % (len(enc), n))
        fbs.check_encoding(enc, new)
        d[off:off + n] = enc
        before.append((name, img)); after.append((name, new))
    return bytes(d), before, after


# ------------------------------------------------------------------ item record
def icon_recolor(block):
    block = bytearray(block)
    pal_at = 4 + 1 + 16 + 40
    pal = block[pal_at:pal_at + 1024]
    px = Image.new("RGBA", (256, 1))
    px.putdata([(pal[i * 4 + 2], pal[i * 4 + 1], pal[i * 4], 255) for i in range(256)])
    raw = recolor(px).convert("RGB").tobytes()
    for i, (r, g, b) in enumerate(zip(raw[0::3], raw[1::3], raw[2::3])):
        if i == 0:
            continue
        block[pal_at + i * 4:pal_at + i * 4 + 3] = bytes((b, g, r))
    return bytes(block)


def build_record(template):
    rec = bytearray(template)
    if struct.unpack_from("<I", rec, 0)[0] != TEMPLATE_ID or fbs.strings(rec)[0] not in TEMPLATE_NAMES:
        raise RuntimeError("the Fisherman's Gloves record is not where expected")
    struct.pack_into("<I", rec, 0x00, ITEM_ID)
    struct.pack_into("<I", rec, 0x04, ITEM["flags"])
    struct.pack_into("<H", rec, 0x0E, ITEM["targets"])
    rec[0x20] = ITEM["charges"]; rec[0x21] = ITEM["cast"]
    struct.pack_into("<H", rec, 0x22, ITEM["delay"]); struct.pack_into("<I", rec, 0x24, ITEM["recast"])
    entries = [(0, ITEM["name"]), (1, 0), (0, ITEM["log"]), (0, ITEM["plural"]), (0, ITEM["desc"])]
    table = bytearray(); heads = []; base = 4 + 8 * len(entries)
    for kind, value in entries:
        heads.append((base + len(table), kind))
        if kind == 1:
            table += struct.pack("<I", value)
        else:
            text = value.encode("latin-1") + b"\0"; text += b"\0" * (-len(text) % 4)
            table += struct.pack("<I", 1) + b"\0" * 24 + text
    blob = struct.pack("<I", len(entries)) + b"".join(struct.pack("<II", o, k) for o, k in heads) + table
    if 0x30 + len(blob) > 0x280:
        raise ValueError("texts too long")
    rec[0x30:0x280] = b"\0" * (0x280 - 0x30)
    rec[0x30:0x30 + len(blob)] = blob
    size = struct.unpack_from("<I", rec, 0x280)[0]
    if size != 0x839 or rec[0x284:0x28D] != b"\x91armor   ":
        raise RuntimeError("the icon is not where expected")
    icon = bytearray(icon_recolor(rec[0x280:0x280 + 4 + size])); icon[13:21] = ("%05d   " % ITEM_ID).encode("ascii")
    rec[0x280:0x280 + len(icon)] = icon
    return bytes(rec)


def record(data, item_id, first):
    i = item_id - first
    if i < 0 or (i + 1) * RS > len(data):
        raise RuntimeError("item %d is not in that file" % item_id)
    return bytearray(fbs.rot_dec(data[i * RS:(i + 1) * RS]))


# ------------------------------------------------------------------ apply / status / restore
def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(st):
    os.makedirs(BACKUP, exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(STATE + ".tmp", STATE)


def item_ok(g):
    try:
        return fbs.strings(record(fbs.read(fbs.gpath(g, ITEM_FILE)), ITEM_ID, ITEM_FIRST))[0] == ITEM["name"]
    except (ValueError, struct.error, RuntimeError):
        return False


def _apply_look(g, st, rebuild, log):
    done = []
    new_files = model_files(g)
    for race in RACES:
        if shared_with(g, new_files[race]) != 1:
            raise RuntimeError("hands model %d's file for %s is shared with other models; not changed" % (NEW_MODEL, race))
        sp, np_ = fbs.gpath(g, SRC_FILES[race]), fbs.gpath(g, new_files[race])
        if rebuild or fbs.sha(fbs.read(np_)) != st.get("models", {}).get(race):
            src = fbs.read(sp)
            keep_original(g, new_files[race])
            data, _, _ = build_model(src, race)
            fbs.write(np_, data)
            st.setdefault("models", {})[race] = fbs.sha(data); st.setdefault("source", {})[race] = fbs.sha(src)
            done.append(race)
    return done


def apply(g, log=print, force=False):
    """Writes only what is missing. Returns a message, or None when everything was already in place."""
    st = load_state(); done = []; problem = None
    rebuild = force or st.get("version") != VERSION
    try:
        done += _apply_look(g, st, rebuild, log)
    except PermissionError:
        raise
    except Exception as e:                   # the item still gets its name; the look is tried again at the next PLAY
        problem = e; st["version"] = None
    save_state(st)
    if rebuild or not item_ok(g):
        path = fbs.gpath(g, ITEM_FILE)
        keep_original(g, ITEM_FILE)
        data = bytearray(fbs.read(path))
        cur = record(data, ITEM_ID, ITEM_FIRST)
        if fbs.strings(cur)[0] not in (".", ITEM["name"]):
            raise RuntimeError("item slot %d is used by '%s'" % (ITEM_ID, fbs.strings(cur)[0]))
        rec = build_record(record(fbs.read(fbs.gpath(g, TEMPLATE_FILE)), TEMPLATE_ID, TEMPLATE_FIRST))
        i = ITEM_ID - ITEM_FIRST
        data[i * RS:(i + 1) * RS] = fbs.rot_enc(rec)
        try:
            fbs.write(path, bytes(data))
        except PermissionError:
            raise RuntimeError("the item file is in use: close FINAL FANTASY XI and run this again")
        if not item_ok(g):
            raise RuntimeError("read-back check of the item failed")
        done.append("item")
    if problem is None:
        st["version"] = VERSION
    save_state(st)
    if problem is not None:
        return "Forever Gloves: item %s; their look was skipped (%s)." % ("updated" if "item" in done else "in place", problem)
    if not done:
        return None
    return "Forever Gloves: game files updated (%s)." % ", ".join(done)


def status(g):
    st = load_state(); out = []
    try:
        rec = record(fbs.read(fbs.gpath(g, TEMPLATE_FILE)), TEMPLATE_ID, TEMPLATE_FIRST)
        out.append("template %d: %s" % (TEMPLATE_ID, fbs.strings(rec)[0]))
    except Exception as e:
        out.append("template %d: NOT FOUND (%s)" % (TEMPLATE_ID, e))
    try:
        name = fbs.strings(record(fbs.read(fbs.gpath(g, ITEM_FILE)), ITEM_ID, ITEM_FIRST))[0]
        out.append("item slot %d: '%s' (%s)" % (ITEM_ID, name, "ours" if item_ok(g) else "free" if name == "." else "USED BY ANOTHER ITEM"))
    except Exception as e:
        out.append("item slot %d: unreadable (%s)" % (ITEM_ID, e))
    for race, p in model_files(g).items():
        cur = fbs.sha(fbs.read(fbs.gpath(g, p)))
        n = shared_with(g, p)
        out.append("%-9s gloves %-12s -> ours %-14s %s%s" % (race, SRC_FILES[race], p,
                   "ours" if cur == st.get("models", {}).get(race) else "not written yet",
                   "" if n == 1 else "  (SHARED by %d models!)" % n))
    return out


def restore(g):
    """Puts back the model files. The item file is shared with the other Forever gifts, so only our record is blanked."""
    out = []
    for rel in model_files(g).values():
        bk = os.path.join(BACKUP, *rel.split("/")) + ".DAT"
        if os.path.exists(bk):
            shutil.copy2(bk, fbs.gpath(g, rel)); out.append("restored " + rel)
    bk = os.path.join(BACKUP, *ITEM_FILE.split("/"))
    if os.path.exists(bk):
        orig = fbs.read(bk); path = fbs.gpath(g, ITEM_FILE); data = bytearray(fbs.read(path))
        i = ITEM_ID - ITEM_FIRST
        data[i * RS:(i + 1) * RS] = orig[i * RS:(i + 1) * RS]
        fbs.write(path, bytes(data)); out.append("item %d blanked" % ITEM_ID)
    if os.path.exists(STATE):
        os.replace(STATE, STATE + ".restored")
    return out


def server_db(log=print):
    """Puts the item's rows (modules/custom/sql/forever_gloves.sql) into the running database now, like dbtool would."""
    with open(os.path.join(KIT, "config.json"), encoding="utf-8-sig") as f:
        cfg = json.load(f)
    sql_path = os.path.join(cfg["server_dir"], "modules", "custom", "sql", "forever_gloves.sql")
    with open(sql_path, encoding="utf-8") as f:
        body = "\n".join(l for l in f.read().splitlines() if not l.strip().startswith("--"))
    import mariadb
    conn = mariadb.connect(host=cfg.get("db_host", "127.0.0.1"), port=int(cfg.get("db_port", 3306)),
                           user=cfg["db_user"], password=cfg["db_pass"], database=cfg["db_name"])
    cur = conn.cursor()
    for stmt in [x.strip() for x in body.split(";") if x.strip()]:
        cur.execute(stmt)
    conn.commit()
    cur.execute("SELECT b.name, e.MId, u.reuseDelay FROM item_basic b JOIN item_equipment e ON e.itemId = b.itemid "
                "JOIN item_usable u ON u.itemid = b.itemid WHERE b.itemid = ?", (ITEM_ID,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("the rows are not in the database after writing")
    return "Database: %s, model %d, %d s between uses." % row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "apply", "restore", "preview", "server"])
    ap.add_argument("--game"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "server":
        print(server_db()); return
    g = fbs.game_dir(a.game)
    if a.cmd == "status":
        print("\n".join(status(g)))
    elif a.cmd in ("apply", "restore"):
        print((apply(g, force=a.force) or "Forever Gloves: already in place.") if a.cmd == "apply" else ("\n".join(restore(g)) or "nothing to restore"))
        try:
            import launcher_setup
            launcher_setup.record_era_state(KIT, g)
        except Exception as problem:
            print("(could not record the era files' state: %s)" % problem)
    else:
        out = os.path.join(KIT, "logs", "forever-gloves"); os.makedirs(out, exist_ok=True)
        for race, p in SRC_FILES.items():
            _, before, after = build_model(fbs.read(fbs.gpath(g, p)), race)
            for (name, b), (_, a_) in zip(before, after):
                tag = "".join(ch if ch.isalnum() else "_" for ch in name)
                b.save(os.path.join(out, "%s_%s_before.png" % (race, tag))); a_.save(os.path.join(out, "%s_%s_after.png" % (race, tag)))
            print("preview", race, [(n, im.size) for n, im in before])


if __name__ == "__main__":
    main()
