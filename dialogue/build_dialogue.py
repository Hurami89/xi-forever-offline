"""XI: Forever Offline - build the bots' written dialogue from the dialogue packs.

  dialogue/packs/<name>/dialogue.json   a pack exactly as it came (never edited here)
  dialogue/voice/<name>/*.txt           our voice layer for it: what each line is used for, a casual version,
                                        and which lines are left out (and why). See voice/README.txt.

Writes:
  dialogue/dialogue_lines.json                              for the AI helpers (personalities, example lines)
  <server>/modules/custom/lua/bots_dialogue_data.lua        for the game (bots_dialogue.lua reads it)

  python build_dialogue.py                      check everything, write both files (server found like the launcher)
  python build_dialogue.py --check              check only, write nothing
  python build_dialogue.py --server C:\\ffxi-local\\server

Exits 1 on any error, and then writes nothing. A pack that adds lines later only needs its voice files updated: every
template of the pack must have exactly one voice record, so nothing new slips in unchecked.
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)

TAGS = {
    "ls", "say", "party", "pair",
    "r.greet", "r.bye", "r.thanks", "r.yw", "r.yes", "r.no", "r.maybe", "r.unsure", "r.agree", "r.alt", "r.congrats",
    "r.sympathy", "r.encourage", "r.help", "r.newbie", "r.question", "r.calm", "r.where", "r.doing", "r.job", "r.misc",
    "r.laugh", "r.back",
    "e.login", "e.logout", "e.wb", "e.wb_long", "e.join", "e.lfp", "e.lfm", "e.levelup", "e.levelup_react", "e.death",
    "e.death_react", "e.raised", "e.win", "e.win_react", "e.wipe", "e.party_end", "e.gear", "e.gear_react", "e.craft",
    "e.rankup", "e.rankup_react", "e.quest", "e.jobchange", "e.loot_react", "e.bcnm_start",
}
CONDS = {"@town", "@field", "@hunt", "@craft", "@mage", "@morning", "@night", "@busy", "@endgame", "@exp", "@leader",
         "@rival", "@gossip", "@party", "@quiet", "@lowlevel"}
SLOTS = {"camp", "here", "job", "lvl", "sub", "member", "player", "doing"}
FILL_MAX = {"camp": "Sea Serpent Grotto", "here": "Southern San d'Oria", "job": "PUP", "lvl": "75", "sub": "NIN",
            "member": "Abcdefghijklmno", "player": "Abcdefghijklmno", "doing": "hanging around town in Lower Jeuno"}
EMOTES = {"wave", "nod", "stretch", "sit", "salute"}
# squad mates (a pack's "squad" section, voice file squad.txt)
SQUAD_TAGS = {"s.recruit", "s.ack_pull", "s.ack_follow", "s.ack_hold", "s.battle", "s.lowhp", "s.lowmp", "s.after", "s.reply",
              "s.down", "s.wipe", "s.idle_town", "s.idle_field", "s.banter", "s.bond", "s.jobchange", "s.jobchange_whm",
              "s.bench", "s.reunion", "s.race", "s.gender", "s.scene_first", "s.scene_lowhp", "s.scene_wipe", "s.scene_rest",
              "s.scene_return"}
SQUAD_SLOTS = {"name"}
ERA_DENY = re.compile(r"\b(trusts?(?! me)|abyssea|adoulin|wings of the goddess|wotg|seekers|level 99|lvl 99|job points?|"
                      r"unity|geomancer|rune fencer|ambuscade|omen|reives?|guild points?|dancer|scholar|campaign)\b", re.I)
JOBS_RE = r"\b(WAR|MNK|WHM|BLM|RDM|THF|PLD|DRK|BST|BRD|RNG|SAM|NIN|DRG|SMN|BLU|COR|PUP)\b"

# How each personality types: polite = the pack's own wording, casual = our casual line, terse = casual, lower case,
# no full stop. Personalities a pack adds later default to casual.
POLITE = {"veteran_mentor", "patient_healer", "reserved_knight", "curious_scholar", "retired_adventurer",
          "linkshell_leader", "old_friend", "gentle_beastmaster", "cautious_scout", "map_reader", "dedicated_crafter",
          "wandering_storyteller", "cautious_adventurer", "helpful_regular", "endgame_planner", "party_leader", "npc_town"}
TERSE = {"quiet_regular", "restless_thief", "night_owl"}
LEADERS = {"linkshell_leader", "party_leader", "endgame_planner"}
RIVALS = {"friendly_rival", "proud_monk", "lucky_hunter"}
# pack scene lines that belong to the player (the newcomer, the one returning), dropped from the scene, by position
SCENE_SKIP = {"living_world": {"S02": [3], "S11": [1], "S22": [5], "S31": [3], "S32": [1]}}


class Build:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def check_text(self, text, where):
        if not text:
            self.err(f"{where}: empty text")
            return
        if any(ord(c) > 126 or ord(c) < 32 for c in text):
            self.err(f"{where}: non-ASCII text: {text}")
        for slot in re.findall(r"{(\w+)}", text):
            if slot not in SLOTS:
                self.err(f"{where}: unknown slot {{{slot}}} in: {text}")
        filled = re.sub(r"{(\w+)}", lambda m: FILL_MAX.get(m.group(1), "x"), text)
        if len(filled) > 110:
            (self.err if len(filled) > 120 else self.warn)(f"{where}: {len(filled)} chars once filled: {text}")
        if ERA_DENY.search(text):
            self.err(f"{where}: out-of-era word in: {text}")
        if "*" in text or "|" in text:
            self.err(f"{where}: '*' or '|' in: {text}")

    def parse_tags(self, tagstr, where):
        tags, conds = [], []
        for t in tagstr.split(","):
            t = t.strip()
            if t.startswith("@"):
                if t in CONDS:
                    conds.append(t[1:])
                else:
                    self.err(f"{where}: unknown condition {t}")
            elif t in TAGS:
                tags.append(t)
            else:
                self.err(f"{where}: unknown tag {t}")
        return tags, conds


def sentences(t):
    return re.split(r"(?<=[.!?])\s+", t.strip())


def templates(pack):
    """The pack's distinct lines: stock endings stripped, zone and job names made into {zone}/{job}. Numbered in pack
    order; the voice files refer to these numbers."""
    entries = pack["entries"]
    tails = collections.Counter(sentences(x["text"])[-1] for x in entries if len(sentences(x["text"])) > 1)
    stock = {t for t, n in tails.items() if n >= 4}
    zones = sorted({x["context"]["zone"] for x in entries if x["context"].get("zone")}, key=len, reverse=True)
    zones += ["Port Windurst", "Windurst Waters", "Bastok Markets", "Port Bastok", "Southern San d'Oria",
              "Northern San d'Oria", "Lower Jeuno", "Upper Jeuno"]

    def norm(t):
        for z in zones:
            t = t.replace(z, "{zone}")
        return re.sub(JOBS_RE, "{job}", t)

    groups = collections.OrderedDict()
    for x in entries:
        s = sentences(x["text"])
        stem = " ".join(s[:-1]) if len(s) > 1 and s[-1] in stock else x["text"].strip()
        key = (x["category"], norm(stem))
        g = groups.setdefault(key, {"cat": x["category"], "orig": norm(stem), "ids": []})
        g["ids"].append(x["id"])
    return {i + 1: g for i, g in enumerate(groups.values())}


def read_voice(b, vdir, name):
    voice, new_lines, scene_recs = {}, [], []
    files = sorted(f for f in os.listdir(vdir) if f.endswith(".txt") and f not in ("scenes.txt", "README.txt", "squad.txt"))
    for part in files:
        for ln, raw in enumerate(open(os.path.join(vdir, part), encoding="utf-8"), 1):
            raw = raw.rstrip("\n")
            if not raw.strip() or raw.startswith("#"):
                continue
            f = raw.split("|")
            where = f"{name}/{part}:{ln}"
            if f[0].startswith("+"):
                new_lines.append((f[0][1:], f[1:], where))
                continue
            try:
                n = int(f[0])
            except ValueError:
                b.err(f"{where}: bad record: {raw}")
                continue
            if n in voice:
                b.err(f"{where}: template {n:03d} has two records")
            voice[n] = (f[1:], where)
    path = os.path.join(vdir, "scenes.txt")
    if os.path.exists(path):
        for ln, raw in enumerate(open(path, encoding="utf-8"), 1):
            raw = raw.rstrip("\n")
            if raw.strip() and not raw.startswith("#"):
                scene_recs.append((raw.split("|"), f"{name}/scenes.txt:{ln}"))
    return voice, new_lines, scene_recs


def build_pack(b, name, pack, vdir):
    nums = templates(pack)
    voice, new_lines, scene_recs = read_voice(b, vdir, name)
    for n, g in nums.items():
        if n not in voice:
            b.err(f"{name}: template {n:03d} ({g['orig'][:60]}) has no voice record")
    for n, (_, where) in voice.items():
        if n not in nums:
            b.err(f"{where}: template {n:03d} is not in the pack")

    lines, dropped, npc, emotes = [], [], [], []
    for n, g in nums.items():
        if n not in voice:
            continue
        f, where = voice[n]
        kind = f[0]
        if kind == "x":
            dropped.append({"pack": name, "num": n, "cat": g["cat"], "ids": g["ids"], "text": g["orig"],
                            "why": f[1] if len(f) > 1 else ""})
            continue
        if kind == "npc":
            if "{" in g["orig"]:
                b.err(f"{where}: NPC line with a slot: {g['orig']}")
            b.check_text(g["orig"], where)
            npc.append({"id": g["ids"][0], "src": g["ids"], "cat": g["cat"], "text": g["orig"]})
            continue
        if kind.startswith("emote:"):
            em = kind.split(":", 1)[1]
            if em not in EMOTES:
                b.err(f"{where}: unknown emote {em}")
            emotes.append({"id": g["ids"][0], "src": g["ids"], "emote": em})
            continue
        tags, conds = b.parse_tags(kind, where)
        casual = f[1] if len(f) > 1 else ""
        extra = f[2] if len(f) > 2 and f[2] else None
        rec = {"id": g["ids"][0], "src": g["ids"], "cat": g["cat"], "tags": tags, "conds": conds, "casual": casual}
        b.check_text(casual, where)
        if "pair" in tags:
            if not extra or not extra.startswith(">"):
                b.err(f"{where}: a pair needs a '>answer' field")
            else:
                rec["answer"] = extra[1:]
                b.check_text(rec["answer"], where)
            rec["polite"] = g["orig"]
        else:
            rec["polite"] = extra or g["orig"]
            if not extra and "{zone}" in g["orig"]:
                b.err(f"{where}: the pack line names a zone but has no polite override: {g['orig']}")
            if not extra and "{job}" in g["orig"] and "{job}" not in casual:
                b.err(f"{where}: the pack line has {{job}} but the casual line does not: {g['orig']}")
        b.check_text(rec["polite"], where)
        if set(re.findall(r"{(\w+)}", rec["polite"])) != set(re.findall(r"{(\w+)}", casual)):
            b.err(f"{where}: polite and casual lines need the same slots: {rec['polite']} / {casual}")
        if not tags:
            b.err(f"{where}: no usable tag")
        lines.append(rec)

    for lid, f, where in new_lines:
        tags, conds = b.parse_tags(f[0], where)
        casual = f[1] if len(f) > 1 else ""
        polite = f[2] if len(f) > 2 and f[2] else casual if not casual[:1].isalpha() or casual.lower().startswith("o/") \
            else (casual[:1].upper() + casual[1:])
        b.check_text(casual, where)
        b.check_text(polite, where)
        if set(re.findall(r"{(\w+)}", polite)) != set(re.findall(r"{(\w+)}", casual)):
            b.err(f"{where}: polite and casual lines need the same slots")
        lines.append({"id": "fo_" + lid, "src": [], "cat": "forever_offline", "tags": tags, "conds": conds,
                      "casual": casual, "polite": polite})

    orig = {f"S{i:02d}": s for i, s in enumerate(pack.get("scenarios", []), 1)}
    scenes, scenes_dropped, cur = [], [], None
    for f, where in scene_recs:
        if f[0].startswith("S"):
            sid = f[0]
            if sid not in orig:
                b.err(f"{where}: unknown scene {sid}")
                cur = None
                continue
            o = orig[sid]
            if f[1] == "x":
                scenes_dropped.append({"pack": name, "sid": sid, "id": o["id"], "trigger": o["trigger"],
                                       "why": f[2] if len(f) > 2 else ""})
                cur = None
                continue
            tags, conds = b.parse_tags(f[1], where)
            cur = {"sid": sid, "id": o["id"], "trigger": o["trigger"], "tags": tags, "conds": conds,
                   "cooldown": o["cooldown_minutes"], "lines": []}
            scenes.append(cur)
        elif cur is None:
            b.err(f"{where}: a scene line outside a scene")
        else:
            b.check_text(f[1], where)
            cur["lines"].append({"role": int(f[0]), "casual": f[1], "polite": f[2] if len(f) > 2 and f[2] else None})
    for sc in scenes:
        skip = SCENE_SKIP.get(name, {}).get(sc["sid"], [])
        origs = [l for i, l in enumerate(orig[sc["sid"]]["lines"], 1) if i not in skip]
        if len(origs) != len(sc["lines"]):
            b.err(f"{name} scene {sc['sid']}: {len(sc['lines'])} lines, the pack has {len(origs)} after skips")
            continue
        for mine, ol in zip(sc["lines"], origs):
            mine["polite"] = mine["polite"] or ol["text"]
            b.check_text(mine["polite"], f"{name} scene {sc['sid']}")
        roles = sorted({l["role"] for l in sc["lines"]})
        if roles != list(range(1, len(roles) + 1)):
            b.err(f"{name} scene {sc['sid']}: roles must be 1..n")
        sc["roles"] = len(roles)
    seen = {s["sid"] for s in scenes} | {s["sid"] for s in scenes_dropped}
    for sid in orig:
        if sid not in seen:
            b.err(f"{name}: scene {sid} has no record")

    squad = build_squad(b, name, pack, vdir)

    personas = []
    for p in pack.get("personalities", []):
        reg = "polite" if p["id"] in POLITE else "terse" if p["id"] in TERSE else "casual"
        personas.append({"id": p["id"], "name": p["name"], "voice": p.get("voice", ""), "habits": p.get("habits", []),
                         "avoid": p.get("avoid", []), "register": reg, "leader": p["id"] in LEADERS,
                         "rival": p["id"] in RIVALS})
    return {"lines": lines, "scenes": scenes, "npc": npc, "emotes": emotes, "dropped": dropped,
            "scenes_dropped": scenes_dropped, "personas": personas, "squad": squad}


def build_squad(b, name, pack, vdir):
    """A pack's squad section: lines and scenes for the squad mates, each with its use (squad.txt) or why it is out."""
    sq = pack.get("squad")
    out = {"lines": [], "scenes": [], "dropped": [], "scenes_dropped": []}
    if not sq:
        return out
    path = os.path.join(vdir, "squad.txt")
    if not os.path.exists(path):
        b.err(f"{name}: the pack has squad lines but voice/{name}/squad.txt is missing")
        return out
    recs = {}
    for ln, raw in enumerate(open(path, encoding="utf-8"), 1):
        raw = raw.rstrip("\n")
        if not raw.strip() or raw.startswith("#"):
            continue
        f = raw.split("|")
        if f[0] in recs:
            b.err(f"{name}/squad.txt:{ln}: {f[0]} has two records")
        recs[f[0]] = (f[1:], f"{name}/squad.txt:{ln}")

    def tags_of(tagstr, where):
        tags = [t.strip() for t in tagstr.split(",")]
        for t in tags:
            if t not in SQUAD_TAGS:
                b.err(f"{where}: unknown squad tag {t}")
        return tags

    def check(text, where):
        b.check_text(re.sub(r"{name}", "Abcdefghijklmno", text), where)
        for slot in re.findall(r"{(\w+)}", text):
            if slot not in SQUAD_SLOTS:
                b.err(f"{where}: squad lines may only use {{name}}: {text}")

    for i, e in enumerate(sq.get("entries", []), 1):
        key = f"Q{i:02d}"
        if key not in recs:
            b.err(f"{name}: squad line {key} ({e['text'][:50]}) has no record in squad.txt")
            continue
        f, where = recs.pop(key)
        if f[0] == "x":
            out["dropped"].append({"pack": name, "key": key, "id": e["id"], "text": e["text"], "why": f[1] if len(f) > 1 else ""})
            continue
        text = f[1] if len(f) > 1 and f[1] else e["text"]
        check(text, where)
        any_ = lambda v: [x for x in (v or ["any"]) if x != "any"]
        out["lines"].append({"id": e["id"], "tags": tags_of(f[0], where), "roles": any_(e.get("roles")),
                             "races": any_(e.get("races")), "genders": any_(e.get("genders")),
                             "fam": any_(e.get("familiarity")), "text": text, "pack_text": e["text"]})
    for i, sc in enumerate(sq.get("scenarios", []), 1):
        key = f"QS{i}"
        if key not in recs:
            b.err(f"{name}: squad scene {key} ({sc['id']}) has no record in squad.txt")
            continue
        f, where = recs.pop(key)
        if f[0] == "x":
            out["scenes_dropped"].append({"pack": name, "key": key, "id": sc["id"], "trigger": sc.get("trigger"),
                                          "why": f[1] if len(f) > 1 else ""})
            continue
        for l in sc["lines"]:
            check(l["text"], f"{where} ({sc['id']})")
        out["scenes"].append({"id": sc["id"], "tags": tags_of(f[0], where), "cooldown": sc.get("cooldown_minutes", 60),
                              "roles": sorted({l["role"] for l in sc["lines"]}),
                              "lines": [{"role": l["role"], "text": l["text"]} for l in sc["lines"]]})
    for key, (_, where) in recs.items():
        b.err(f"{where}: {key} is not in the pack's squad section")
    return out


def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def lua_list(items):
    return "{ " + ", ".join(lua_str(i) for i in items) + " }" if items else "{}"


def write_lua(out, path, stamp):
    rows = ["-- XI: Forever Offline: the bots' written dialogue. GENERATED by C:\\FFXISOLO\\dialogue\\build_dialogue.py",
            "-- from the dialogue packs and our voice layer. Do not edit: change the voice files and build again.",
            f"-- {stamp}", "return {", "    personas = {"]
    for p in out["personas"]:
        rows.append(f"        {{ id = {lua_str(p['id'])}, reg = {lua_str(p['register'])}, leader = {str(p['leader']).lower()}, "
                    f"rival = {str(p['rival']).lower()} }},")
    rows.append("    },")
    rows.append("    lines = {")
    for l in out["lines"]:
        extra = f", an = {lua_str(l['answer'])}" if l.get("answer") else ""
        rows.append(f"        {{ id = {lua_str(l['id'])}, t = {lua_list(l['tags'])}, c = {lua_list(l['conds'])}, "
                    f"ca = {lua_str(l['casual'])}, po = {lua_str(l['polite'])}{extra} }},")
    rows.append("    },")
    rows.append("    scenes = {")
    for s in out["scenes"]:
        ls = ", ".join(f"{{ {l['role']}, {lua_str(l['casual'])}, {lua_str(l['polite'])} }}" for l in s["lines"])
        rows.append(f"        {{ id = {lua_str(s['id'])}, t = {lua_list(s['tags'])}, c = {lua_list(s['conds'])}, "
                    f"cd = {int(s['cooldown'])}, roles = {s['roles']}, l = {{ {ls} }} }},")
    rows.append("    },")
    rows.append("    npc = {")
    for n in out["npc"]:
        rows.append(f"        {{ id = {lua_str(n['id'])}, cat = {lua_str(n['cat'])}, text = {lua_str(n['text'])} }},")
    rows.append("    },")
    rows.append("    emotes = {")
    for e in out["emotes"]:
        rows.append(f"        {{ id = {lua_str(e['id'])}, emote = {lua_str(e['emote'])} }},")
    rows.append("    },")
    rows.append("    squad = {")
    rows.append("        lines = {")
    for l in out["squad"]["lines"]:
        rows.append(f"            {{ id = {lua_str(l['id'])}, t = {lua_list(l['tags'])}, roles = {lua_list(l['roles'])}, "
                    f"races = {lua_list(l['races'])}, genders = {lua_list(l['genders'])}, fam = {lua_list(l['fam'])}, "
                    f"text = {lua_str(l['text'])} }},")
    rows.append("        },")
    rows.append("        scenes = {")
    for sc in out["squad"]["scenes"]:
        ls = ", ".join(f"{{ {lua_str(l['role'])}, {lua_str(l['text'])} }}" for l in sc["lines"])
        rows.append(f"            {{ id = {lua_str(sc['id'])}, t = {lua_list(sc['tags'])}, cd = {int(sc['cooldown'])}, "
                    f"roles = {lua_list(sc['roles'])}, l = {{ {ls} }} }},")
    rows.append("        },")
    rows.append("    },")
    rows.append("}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(rows) + "\n")
    os.replace(tmp, path)


def server_dir():
    try:
        sys.path.insert(0, KIT)
        import launcher_core  # noqa
        return launcher_core.server_dir() if hasattr(launcher_core, "server_dir") else r"C:\ffxi-local\server"
    except Exception:
        return r"C:\ffxi-local\server"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check only, write nothing")
    ap.add_argument("--server", help="server folder (default: the launcher's)")
    ap.add_argument("--packs", default=os.path.join(HERE, "packs"))
    ap.add_argument("--voice", default=os.path.join(HERE, "voice"))
    ap.add_argument("--out", default=os.path.join(HERE, "dialogue_lines.json"))
    args = ap.parse_args()

    b = Build()
    merged = {"lines": [], "scenes": [], "npc": [], "emotes": [], "dropped": [], "scenes_dropped": [], "personas": [],
              "squad": {"lines": [], "scenes": [], "dropped": [], "scenes_dropped": []}}
    packs = []
    for name in sorted(os.listdir(args.packs)):
        pfile = os.path.join(args.packs, name, "dialogue.json")
        if not os.path.isfile(pfile):
            continue
        vdir = os.path.join(args.voice, name)
        if not os.path.isdir(vdir):
            b.err(f"pack {name} has no voice folder voice/{name}: nothing of it is used until it has one")
            continue
        pack = json.load(open(pfile, encoding="utf-8"))
        part = build_pack(b, name, pack, vdir)
        packs.append({"name": name, "version": pack.get("project_version") or pack.get("policy", {}).get("version", "?")})
        for k in merged:
            if k == "personas":
                have = {p["id"] for p in merged["personas"]}
                merged["personas"] += [p for p in part["personas"] if p["id"] not in have]
            elif k == "squad":
                for sk in merged["squad"]:
                    merged["squad"][sk] += part["squad"][sk]
            else:
                merged[k] += part[k]
    ids = collections.Counter(l["id"] for l in merged["lines"])
    for i, c in ids.items():
        if c > 1:
            b.err(f"line id {i} is used {c} times")
    texts = collections.Counter(l["casual"].lower() for l in merged["lines"])
    for t, c in texts.items():
        if c > 1:
            b.warn(f"casual line used {c} times: {t}")
    if not packs:
        b.err("no packs found in " + args.packs)

    for w in b.warnings:
        print("warning:", w)
    for e in b.errors:
        print("ERROR:", e)
    tagc = collections.Counter(t for l in merged["lines"] for t in l["tags"])
    summary = (f"{len(merged['lines'])} lines ({sum(1 for l in merged['lines'] if l['src'])} from packs, "
               f"{sum(1 for l in merged['lines'] if not l['src'])} ours), {len(merged['scenes'])} scenes, "
               f"{len(merged['npc'])} NPC lines, {len(merged['emotes'])} emotes, {len(merged['personas'])} personalities; "
               f"left out: {len(merged['dropped'])} templates ({sum(len(d['ids']) for d in merged['dropped'])} pack entries), "
               f"{len(merged['scenes_dropped'])} scenes; squad: {len(merged['squad']['lines'])} lines, "
               f"{len(merged['squad']['scenes'])} scenes (left out {len(merged['squad']['dropped'])} lines, "
               f"{len(merged['squad']['scenes_dropped'])} scenes)")
    if b.errors:
        print(f"FAILED: {len(b.errors)} error(s). Nothing written.")
        return 1
    print("OK: " + summary)
    print("by use: " + ", ".join(f"{k} {v}" for k, v in sorted(tagc.items())))
    if args.check:
        return 0

    stamp = "packs: " + ", ".join(f"{p['name']} {p['version']}" for p in packs) + "; " + summary
    out = dict(merged, format="xi-forever-offline-dialogue/1", packs=packs)
    with open(args.out + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=True)
    os.replace(args.out + ".tmp", args.out)
    print("wrote " + args.out)
    server = args.server or server_dir()
    lua_dir = os.path.join(server, "modules", "custom", "lua")
    if not os.path.isdir(lua_dir):
        print("server folder not found (" + lua_dir + "): bots_dialogue_data.lua not written")
        return 1
    write_lua(out, os.path.join(lua_dir, "bots_dialogue_data.lua"), stamp)
    print("wrote " + os.path.join(lua_dir, "bots_dialogue_data.lua"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
