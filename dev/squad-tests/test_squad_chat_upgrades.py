"""Stand-in checks for the squad chat upgrades: fight awareness, daily moods, the bot world, remembering bots.
Run: python3 test_squad_chat_upgrades.py <folder with squad_chat.py>"""
import importlib.util, json, random, shutil, sys, tempfile, time
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else ".") / "squad_chat.py"
work = Path(tempfile.mkdtemp())
shutil.copy(src, work / "squad_chat.py")
for d in ("mates", "memory", "logs", "lore", "archive"):
    (work / d).mkdir()
(work / "lore" / "ffxi_era.md").write_text("Vana'diel, 75 era.", encoding="utf-8")
for name, job in (("Momo", "RDM"), ("Kasumi", "WHM"), ("Gio", "WAR")):
    (work / "mates" / f"{name}.json").write_text(json.dumps({"name": name, "slug": name.lower(), "race": "Hume", "job": job,
        "level": 20, "chat_examples": [f"{name} line {i}" for i in range(30)]}), encoding="utf-8")
spec = importlib.util.spec_from_file_location("squad_chat", work / "squad_chat.py")
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
sc.CONFIG = sc.load_config(); sc.CONFIG["stub"] = True
sc.LORE = sc.load_lore(); sc.PROFILES = sc.load_profiles()
sc.time.sleep = lambda s: None
prompts = []
real_call = sc.call_ollama
def spy(messages, *a, **k):
    prompts.append(messages)
    return real_call(messages, *a, **k)
sc.call_ollama = spy

passes = fails = 0
def check(name, cond, detail=""):
    global passes, fails
    if cond: passes += 1; print("ok  ", name)
    else: fails += 1; print("FAIL", name, "--", detail)

def out_lines():
    return [l for l in sc.OUT_FILE.read_text(encoding="utf-8").splitlines() if l] if sc.OUT_FILE.exists() else []

def journal(name):
    return sc.load_memory(name).get("journal", [])

sc.handle_line("CTX\tValkurm Dunes\t20\t1\tMomo,Kasumi,Gio")

# 1. moods
m1 = sc.mood_for("Momo", "2026-11-07"); m2 = sc.mood_for("Momo", "2026-11-07")
check("a mate's mood is the same all day", m1 == m2)
days = {sc.mood_for("Momo", f"2026-11-{d:02d}")[0] for d in range(1, 29)}
check("... and changes from day to day", len(days) >= 5, days)
check("mates differ on the same day (not all one mood)", len({sc.mood_for(n, "2026-11-07")[0] for n in ("Momo", "Kasumi", "Gio", "Kyo", "Aldo", "Bree")}) >= 2)
sys_prompt = sc.system_prompt(sc.PROFILES["Momo"], sc.load_memory("Momo"))
check("the mood is in the prompt", "Your mood today:" in sys_prompt and sc.mood_for("Momo")[0] in sys_prompt)
sc.CONFIG["mood"]["enabled"] = False
check("mood can be turned off", "Your mood today:" not in sc.system_prompt(sc.PROFILES["Momo"], sc.load_memory("Momo")))
sc.CONFIG["mood"]["enabled"] = True

# 2. fight awareness
sc.handle_line("FIGHT\tGoblin Mugger\t60\t80\t-1\tMomo:90:20,Kasumi:100:70,Gio:40:-1")
p = sc.system_prompt(sc.PROFILES["Momo"], sc.load_memory("Momo"))
check("the fight is in the prompt (monster and its health)", "fighting Goblin Mugger" in p and "60% health" in p, p[-600:])
check("... its own state as 'You are'", "You are at 90% HP and 20% MP" in p)
check("... the others' state", "Gio is at 40% HP" in p and "Kasumi is at 100% HP and 70% MP" in p)
check("... Hurami's HP", "Hurami is at 80% HP" in p)
sc.CONTEXT["fight_at"] = time.time() - 60
check("an old fight (no update for 15 s) is not in the prompt", "fighting Goblin" not in sc.system_prompt(sc.PROFILES["Momo"], sc.load_memory("Momo")))
sc.handle_line("FIGHT\t\t-1\t-1\t-1\t")
check("fight over: nothing in the prompt", "fighting" not in sc.system_prompt(sc.PROFILES["Momo"], sc.load_memory("Momo")))

before = len(out_lines()); prompts.clear()
sc.CONFIG["fight"]["lowmp_chance"] = 1.0
sc.handle_line("ACT\tlowmp\tMomo\tGoblin Mugger")
lines = out_lines()[before:]
check("low MP: that mate calls it out", len(lines) == 1 and lines[0].startswith("SAY\tMomo\t"), lines)
check("... the model is told it is low on MP", prompts and "low on MP" in prompts[-1][-1]["content"])

before = len(out_lines())
sc.CONFIG["fight"]["hurt_chance"] = 1.0
sc.handle_line("ACT\thurt\tHurami\tGoblin Mugger")
lines = out_lines()[before:]
check("Hurami badly hurt: the healer (WHM/RDM) answers", len(lines) == 1 and (lines[0].startswith("SAY\tKasumi") or lines[0].startswith("SAY\tMomo")), lines)

before = len(out_lines())
sc.CONFIG["fight"]["ws_chance"] = 1.0
sc.LAST_FIGHT_LINE = 0
sc.handle_line("ACT\tws\tHurami\tGoblin Mugger\t412")
lines = out_lines()[before:]
check("a weapon skill gets a reaction", len(lines) == 1, lines)
check("... with the damage", "412 damage" in prompts[-1][-1]["content"])
before = len(out_lines())
sc.handle_line("ACT\tws\tHurami\tGoblin Mugger\t300")
check("... but not two in a row (12 s gap)", len(out_lines()) == before)
sc.CONFIG["fight"]["won_chance"] = 0.0
sc.LAST_FIGHT_LINE = 0
before = len(out_lines())
sc.handle_line("ACT\twon\tHurami\tGoblin Mugger")
check("chance 0: no line", len(out_lines()) == before)
sc.handle_line("CHAT_STATE\t0")
sc.CONFIG["fight"]["won_chance"] = 1.0
before = len(out_lines())
sc.handle_line("ACT\twon\tHurami\tGoblin Mugger")
check("chat off: fights stay quiet", len(out_lines()) == before)
sc.handle_line("CHAT_STATE\t1")
check("fight callouts are not written into the journal", not any("low on MP" in j or "weapon skill" in j for j in journal("Momo")))

# 3. the bot world
sc.handle_line("WORLD\tHumef (WAR 22),Aldric (WHM 19)\tTaliah (BLM 30)\tCrimsonWolves\t")
p = sc.system_prompt(sc.PROFILES["Gio"], sc.load_memory("Gio"))
check("nearby bot players are in the prompt", "Other adventurers nearby: Humef (WAR 22), Aldric (WHM 19)" in p)
check("... Hurami's friends online and linkshell", "friends who are online: Taliah (BLM 30)" in p and "linkshell: CrimsonWolves" in p)

# 4. bots joining / leaving, remembered
before = len(out_lines())
sc.CONFIG["world"]["botjoin_chance"] = 1.0
sc.handle_line("BOTJOIN\tHumef\tWAR\t22\tValkurm Dunes")
check("a bot joining goes into every mate's journal", all(any("Humef, a level 22 WAR, joined the party in Valkurm Dunes." == j for j in journal(n)) for n in ("Momo", "Kasumi", "Gio")), journal("Gio"))
check("... and a mate greets it", len(out_lines()) == before + 1)
sc.CONFIG["world"]["botleave_chance"] = 0.0
sc.handle_line("BOTLEAVE\tHumef\t12\tValkurm Dunes")
check("a bot leaving: the fights together are remembered", any("Humef left the party in Valkurm Dunes after 12 fights together." == j for j in journal("Kasumi")), journal("Kasumi")[-2:])

# 5. a bot speaking in the party
before = len(out_lines())
sc.CONFIG["world"]["botsay_chance"] = 0.0
sc.handle_line("BOTSAY\tHumef\thow many more do we need?")
check("a bot's line is not always answered (chance)", len(out_lines()) == before)
sc.handle_line("BOTSAY\tHumef\tgio you ok?")
lines = out_lines()[before:]
check("... but a mate it names answers", len(lines) == 1 and lines[0].startswith("SAY\tGio"), lines)
check("... and it is remembered as Humef's line", any(r.get("who") == "Humef" for r in sc.load_memory("Gio")["recent"]))

print(f"\n{passes} passed, {fails} failed")
shutil.rmtree(work, ignore_errors=True)
sys.exit(1 if fails else 0)
