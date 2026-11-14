"""One-off: make the ambient crowd/bot chat stop saying things that cannot be true.

  * healer shouts promise spells the speaker does not have (a WHM 14 shouting Cure III / Raise)
  * a pair line asserted a level up that never happened ("gz on the level!")
  * one bot said three unrelated things in a few seconds (no per-speaker cooldown)
  * support jobs included advanced jobs at levels where they are not unlocked yet (THF 18/NIN 9)
  * the Ollama pool held invented words and non-FFXI nouns ("healing materia", "gmfg", "merijin")

Run from the server folder:  python C:\\FFXISOLO\\chat_cleanup.py
Every touched file is copied to <file>.before-chatclean first.
"""
import io
import json
import os
import re
import shutil
import sys

SERVER = r"C:\ffxi-local\server"
os.chdir(SERVER)


def patch(path, pairs, label):
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    backup = path + ".before-chatclean"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    for old, new in pairs:
        if text.count(old) != 1:
            sys.exit("%s: expected exactly one match, got %d for %r" % (label, text.count(old), old[:80]))
        text = text.replace(old, new)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("patched %s" % label)


# ---------------------------------------------------------------- 1. data file
patch("modules/custom/lua/crowds_chat_data.lua", [
    ("c.shout.lfp_heal = { 'WHM{lvl} LFP, have Raise', 'LFP WHM {lvl}/BLM, Cure III', 'RDM{lvl} LFP, Refresh', 'LFP BRD{lvl}, Ballad + Minuets' }",
     "-- Each line carries the level where the spell it promises is actually castable (a WHM 14 has neither Cure III\n"
     "-- nor Raise): crowds_chat.lua only offers the lines the speaker can cast.\n"
     "c.shout.lfp_heal = {\n"
     "    { 'WHM{lvl} LFP, can raise', 25 },\n"
     "    { 'LFP WHM {lvl}/BLM, Cure III', 21 },\n"
     "    { 'RDM{lvl} LFP, Refresh', 41 },\n"
     "    { 'LFP BRD{lvl}, Ballad + Minuets', 45 },\n"
     "}"),
    ("    { 'did you get your AF?', 'still farming the coffer' }, { 'ready?', 'one sec, buying drinks' }, { 'gz on the level!', 'ty :)' },",
     "    { 'did you get your AF?', 'still farming the coffer' }, { 'ready?', 'one sec, buying drinks' },"),
], "crowds_chat_data.lua")

# ---------------------------------------------------------------- 2. chat logic
patch("modules/custom/lua/crowds_chat.lua", [
    ("local GREET_AGAIN    = 15 * 60",
     "local GREET_AGAIN    = 15 * 60\n"
     "local SPEAK_GAP      = 90    -- seconds: one bot does not speak twice in a row (they used to monologue)"),

    ("    local sub = who.sub or pick(T.subs[job]) or 'WAR'\n    who.sub = sub",
     "    local sub = who.sub or pick(T.subs[job]) or 'WAR'\n"
     "    if lvl < 45 and not BASE[sub] then\n"
     "        -- an advanced job cannot be this bot's support job this early (a player that low has not unlocked it)\n"
     "        sub = pick({ 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF' })\n"
     "    end\n"
     "\n"
     "    who.sub = sub"),

    ("        local own = {}\n"
     "        for _, line in ipairs(T.shout.lfp_heal) do\n"
     "            if line:find(who.job or '?', 1, true) then\n"
     "                own[#own + 1] = line\n"
     "            end\n"
     "        end",
     "        local own = {}\n"
     "        for _, entry in ipairs(T.shout.lfp_heal) do\n"
     "            local line, need = entry, 0\n"
     "            if type(entry) == 'table' then\n"
     "                line, need = entry[1], entry[2] or 0\n"
     "            end\n"
     "\n"
     "            if lvl >= need and line:find(who.job or '?', 1, true) then\n"
     "                own[#own + 1] = line\n"
     "            end\n"
     "        end"),

    ("    local function who(e)\n"
     "        return { name = e:getName(), job = JOBS[e:getMainJob()] or 'WAR', lvl = e:getMainLvl(), level = e:getMainLvl(),\n"
     "                 ls = xi.bots and xi.bots.lsName and xi.bots.lsName(e) or nil }\n"
     "    end",
     "    local function who(e)\n"
     "        return { name = e:getName(), job = JOBS[e:getMainJob()] or 'WAR', lvl = e:getMainLvl(), level = e:getMainLvl(),\n"
     "                 ls = xi.bots and xi.bots.lsName and xi.bots.lsName(e) or nil }\n"
     "    end\n"
     "\n"
     "    -- one bot does not speak again right away (a single bot used to say three unrelated things in a few seconds)\n"
     "    z.said = z.said or {}\n"
     "    local function onCooldown(name)\n"
     "        return z.said[name] ~= nil and now - z.said[name] < SPEAK_GAP\n"
     "    end\n"
     "\n"
     "    local function spoke(name)\n"
     "        z.said[name] = now\n"
     "    end"),

    ("        local e = pick(speakers)\n        for _ = 1, 3 do",
     "        local free = {}\n"
     "        for _, speaker in ipairs(speakers) do\n"
     "            if not onCooldown(speaker:getName()) then\n"
     "                free[#free + 1] = speaker\n"
     "            end\n"
     "        end\n"
     "\n"
     "        if #free == 0 then\n"
     "            return\n"
     "        end\n"
     "\n"
     "        local e = pick(free)\n"
     "        for _ = 1, 3 do"),

    ("            if line and line ~= '' and recentCheck(z, line) then\n"
     "                speak(e, 1, line)\n"
     "                return\n"
     "            end",
     "            if line and line ~= '' and recentCheck(z, line) then\n"
     "                speak(e, 1, line)\n"
     "                spoke(e:getName())\n"
     "                return\n"
     "            end"),

    ("            if nearAPlayer(players, pos.x, pos.z, SAY_RANGE) then\n"
     "                near[#near + 1] = e\n"
     "            end",
     "            if not onCooldown(e:getName()) and nearAPlayer(players, pos.x, pos.z, SAY_RANGE) then\n"
     "                near[#near + 1] = e\n"
     "            end"),

    ("        if partner then\n"
     "            local l1, l2 = pairLines(who(a), who(partner), zoneId)\n"
     "            speak(a, 0, l1)\n"
     "            a:timer(rnd(3000, 6000), function()\n"
     "                if partner:isAlive() then\n"
     "                    speak(partner, 0, l2)\n"
     "                end\n"
     "            end)\n"
     "        else\n"
     "            speak(a, 0, sayLine(who(a), zoneId, prof.outpost))\n"
     "        end",
     "        if partner then\n"
     "            local l1, l2 = pairLines(who(a), who(partner), zoneId)\n"
     "            if not recentCheck(z, l1) then\n"
     "                return\n"
     "            end\n"
     "\n"
     "            speak(a, 0, l1)\n"
     "            spoke(a:getName())\n"
     "            a:timer(rnd(3000, 6000), function()\n"
     "                if partner:isAlive() then\n"
     "                    speak(partner, 0, l2)\n"
     "                    spoke(partner:getName())\n"
     "                end\n"
     "            end)\n"
     "        else\n"
     "            local line = sayLine(who(a), zoneId, prof.outpost)\n"
     "            if recentCheck(z, line) then\n"
     "                speak(a, 0, line)\n"
     "                spoke(a:getName())\n"
     "            end\n"
     "        end"),
], "crowds_chat.lua")

# ---------------------------------------------------------------- 3. the generator
patch(r"C:\FFXISOLO\crowds\crowd_chat_ai.py", [
    ('NAME_LIKE = re.compile(r"\\b(Hurami|Kurami)\\b")',
     'NAME_LIKE = re.compile(r"\\b(Hurami|Kurami)\\b")\n'
     '# Words the model invents that no era player would type, or things that are not in this game at all.\n'
     '# Keeping them out here means a pruned pool cannot quietly refill with the same nonsense.\n'
     'JUNK = re.compile(\n'
     '    r"\\b(materia|colosseum|merijin|meracid|mpg|gmfg|gmba|w1n|tahat|kuholz|mtg|sps|vdh|kz|jn|ahu|mnd|t1|samson|"\n'
     '    r"kageno|quetzalcoatl|obsidian)\\b|si\'jhin|\\bnashmau port\\b|\\brabao flight\\b|\\bxp share\\b|\\btp pots?\\b|"\n'
     '    r"\\bmerit book\\b|\\bblue pots\\b|\\bmoo shop\\b|\\bWT\\b|/rune\\b", re.I)'),

    ('    if "{" in text or "}" in text or "\\\\" in text or ERA_DENY.search(text) or NAME_LIKE.search(text):',
     '    if ("{" in text or "}" in text or "\\\\" in text or ERA_DENY.search(text) or NAME_LIKE.search(text)\n'
     '            or JUNK.search(text)):'),
], "crowd_chat_ai.py")

# ---------------------------------------------------------------- 4. prune the live pool
LUA = "modules/custom/lua/crowds_chat_ai.lua"
JSN = "modules/custom/lua/crowds_chat_ai.json"

DROP = {s.lower() for s in [
    "wheres that nm for my exp?", "who knows wheres the afk?", "ty for the gil, np", "ty for gz, np",
    "need 1 mp restore tonite", "gonna hit the merijin", "any1 got a pull?", "inc is too high, need a break",
    "anyone know wheres the mt?", "need a meracid for my blm", "wtb cheap sps, hmu", "gg no rez on that pull :(",
    "wtf who pulled that lizard?", "exp share or im out, k?", "need some tp pots, brb",
    "inc pull? don't wanna waste mp", "anyone got a spare merit book?", "when's the next rabao flight?",
    "wonder if they have fresh fish at the whm guild?", "who's got the best deal on healing materia?",
    "wish they'd fix these broken links in jeuno", "just spent ages waiting for mtg, no party yet :(",
    "who wants to hit up the colosseum later?", "need 500 gil for a nashmau port, anyone?",
    "brb, gonna afk at the tavern for a bit", "ggs @ moo shop?", "exp @ nashmau?",
    "anyone got exp advice for nashmau?", "got a nice pull in kuholz, join us?",
    "got lucky at nashmau, +1 to my sam gear!", "need a /rune in whitegate, where's the shop?",
    "can't find the gm shop in tav, anyone?", "someone pull that npc pls, lost again", "just lost a tp, grr",
    "inc afk, back soon", "need 2 mnd for my nm run", "who knows where tahat's at?", "need a whm stat boost",
    "looking 4 brd, gz if u can play", "just pulled 2k in merits, yes!", "brb need tp potions",
    "gotta check out the new gear :3", "wts fischers t1?", "w1n w1n w1n", "need mpg in windurst?",
    "inc mpg pls?", "got mpg?", "need to farm kz", "exp in jn?", "need brd in ahu?", "need smn pet?",
    "gmfg windurstians", "gmba all!", "where's samson?", "who knows where rabao npc?",
    "any1 know where kageno?", "hey folks, ever seen a quetzalcoatl?",
    "got any idea where i can farm some obsidian?", "where tf is zilart?", "going to vdh who's in?",
    "crafters here for wt?", "need a weaver for some gear pls",
]}

JUNK_RE = re.compile(
    r"\b(materia|colosseum|merijin|meracid|mpg|gmfg|gmba|w1n|tahat|kuholz|mtg|sps|vdh|kz|jn|ahu|mnd|t1|samson|"
    r"kageno|quetzalcoatl|obsidian)\b|si'jhin|\bnashmau port\b|\brabao flight\b|\bxp share\b|\btp pots?\b|"
    r"\bmerit book\b|\bblue pots\b|\bmoo shop\b|\bWT\b|/rune\b", re.I)
LAG_RE = re.compile(r"\blag", re.I)
STR_RE = re.compile(r"'((?:\\.|[^'])*)'")
LAG_KEEP = 3          # the pool had a dozen near-identical lag complaints


def bad(text, budget):
    if text.lower() in DROP or JUNK_RE.search(text):
        return True
    if LAG_RE.search(text):
        return budget[0] <= 0
    return False


if os.path.exists(LUA):
    backup = LUA + ".before-chatclean"
    if not os.path.exists(backup):
        shutil.copy2(LUA, backup)
    budget, kept, dropped = [LAG_KEEP], [], 0
    for line in io.open(LUA, encoding="utf-8").read().split("\n"):
        stripped = line.strip()
        if stripped.startswith("'") or stripped.startswith("{ '"):
            parts = [m.group(1).replace("\\'", "'") for m in STR_RE.finditer(line)]
            if any(bad(p, budget) for p in parts):
                dropped += 1
                continue
            if any(LAG_RE.search(p) for p in parts):
                budget[0] -= 1
        kept.append(line)
    io.open(LUA, "w", encoding="utf-8", newline="\n").write("\n".join(kept))
    left = sum(1 for l in kept if l.strip().startswith("'") or l.strip().startswith("{ '"))
    print("crowds_chat_ai.lua: dropped %d entries, %d left" % (dropped, left))

if os.path.exists(JSN):
    try:
        pool = json.load(io.open(JSN, encoding="utf-8"))
    except (OSError, ValueError):
        pool = None
    if isinstance(pool, dict):
        backup = JSN + ".before-chatclean"
        if not os.path.exists(backup):
            shutil.copy2(JSN, backup)
        budget = [LAG_KEEP]
        before = sum(len(v) for v in pool.values() if isinstance(v, list))
        for key, items in list(pool.items()):
            if not isinstance(items, list):
                continue
            keep = []
            for item in items:
                parts = item if isinstance(item, list) else [item]
                if any(bad(str(p), budget) for p in parts):
                    continue
                if any(LAG_RE.search(str(p)) for p in parts):
                    budget[0] -= 1
                keep.append(item)
            pool[key] = keep
        tmp = JSN + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(pool, f, indent=1, ensure_ascii=False)
        os.replace(tmp, JSN)
        print("crowds_chat_ai.json: %d -> %d entries" % (before, sum(len(v) for v in pool.values() if isinstance(v, list))))
        for key in pool:
            if isinstance(pool[key], list):
                print("   %-8s %d" % (key, len(pool[key])))

# ---------------------------------------------------------------- 5. syntax
for exe in ("luac", "luajit", "lua"):
    found = shutil.which(exe)
    if not found:
        continue
    flag = "-p" if exe == "luac" else ("-bl" if exe == "luajit" else "-e")
    files = " ".join('"modules/custom/lua/%s"' % f for f in
                     ("crowds_chat.lua", "crowds_chat_data.lua", "crowds_chat_ai.lua"))
    rc = os.system('"%s" %s %s' % (found, flag, files)) if exe == "luac" else os.system('"%s" %s' % (found, files))
    print("%s syntax check rc=%s" % (exe, rc))
    break
else:
    print("no lua interpreter on PATH: syntax checked by inspection only")
