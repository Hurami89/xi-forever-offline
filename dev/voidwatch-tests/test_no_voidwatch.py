import os, sys, json, shutil, tempfile, subprocess, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", ".."))
SAMPLE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "zones")
sys.path.insert(0, KIT)
import make_no_voidwatch as mv
def out(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a)
    return r, buf.getvalue()
def server(init="custom/lua/era_exp.lua\r\n# custom/lua/claim_shield.lua\r\n", zones=SAMPLE):
    root = tempfile.mkdtemp(); sv = os.path.join(root, "server"); os.makedirs(os.path.join(sv, "modules", "custom", "lua")); os.makedirs(os.path.join(sv, "data"))
    shutil.copytree(zones, os.path.join(sv, "data", "zones"))
    open(os.path.join(sv, "modules", "init.txt"), "w", newline="").write(init)
    return {"server_dir": sv}, sv
rd = lambda p: open(p, newline="").read()
# 1. the real zone data: every Voidwatch NPC, grouped by the zone its id belongs to
found = mv.find_voidwatch_npcs(SAMPLE)
total = sum(len(v) for v in found.values()); names = {}
for v in found.values():
    for _, n in v: names[n] = names.get(n, 0) + 1
assert total == 38 and names == {"Planar Rift": 18, "Riftworn Pyxis": 18, "Atmacite Refiner": 1, "Voidwatch Officer": 1}, (total, names)
assert 127 in found and 17297502 in [i for i, _ in found[127]] and all(((i >> 12) & 0x1FF) == z for z, v in found.items() for i, _ in v)
assert set(found) >= {105, 111, 118, 127}
# 2. build: module written, registered, summary
cfg, sv = server(); r, text = out(mv.build, cfg); assert r == 0 and "Found 38 Voidwatch NPCs" in text and "Planar Rift" in text, text
mod = rd(os.path.join(sv, "modules", "custom", "lua", "no_voidwatch.lua")); init = rd(os.path.join(sv, "modules", "init.txt"))
assert "[127] = {" in mod and "17297502" in mod and "xi.player.onGameIn" in mod and mod.startswith(mv.MARKER) and "xi.status.INVISIBLE" in mod
assert init == "custom/lua/era_exp.lua\r\n# custom/lua/claim_shield.lua\r\ncustom/lua/no_voidwatch.lua\r\n", repr(init)         # appended with the file's own line endings, nothing else changed
assert os.path.exists(os.path.join(sv, "modules", "init.txt.before-no-voidwatch")) and rd(os.path.join(sv, "modules", "init.txt.before-no-voidwatch")) == "custom/lua/era_exp.lua\r\n# custom/lua/claim_shield.lua\r\n"
# 3. again: nothing doubled
r, text = out(mv.build, cfg); assert "already switched on" in text and rd(os.path.join(sv, "modules", "init.txt")).count("no_voidwatch") == 1
# 4. status, undo, status
r, text = out(mv.status, cfg); assert text.startswith("On. It hides 38 Voidwatch NPCs in"), text
r, text = out(mv.undo, cfg); assert "Removed from modules/init.txt" in text and "Module file deleted" in text
assert rd(os.path.join(sv, "modules", "init.txt")) == "custom/lua/era_exp.lua\r\n# custom/lua/claim_shield.lua\r\n" and not os.path.exists(os.path.join(sv, "modules", "custom", "lua", "no_voidwatch.lua"))
r, text = out(mv.status, cfg); assert text.startswith("Off: it is not in modules/init.txt"), text
r, text = out(mv.undo, cfg); assert "was not in modules/init.txt" in text and "no module file" in text            # undo twice: harmless
# 5. it was in init.txt but commented out: switched back on, not added twice
cfg, sv = server(init="custom/lua/era_exp.lua\n# custom/lua/no_voidwatch.lua\n"); out(mv.build, cfg)
assert rd(os.path.join(sv, "modules", "init.txt")) == "custom/lua/era_exp.lua\ncustom/lua/no_voidwatch.lua\n"
# 6. init.txt with no final newline
cfg, sv = server(init="custom/lua/era_exp.lua"); out(mv.build, cfg); assert rd(os.path.join(sv, "modules", "init.txt")) == "custom/lua/era_exp.lua\ncustom/lua/no_voidwatch.lua\n"
# 7. a server with no Voidwatch NPCs at all: says so, writes nothing
empty = tempfile.mkdtemp(); os.makedirs(os.path.join(empty, "a_zone")); open(os.path.join(empty, "a_zone", "npcs.yaml"), "w").write("  17297502:\n    script: Foo\n    display_name: Foo\n    content: abyssea\n")
cfg, sv = server(zones=empty); r, text = out(mv.build, cfg); assert "nothing to hide" in text and not os.path.exists(os.path.join(sv, "modules", "custom", "lua", "no_voidwatch.lua"))
# 8. a different tag with the word in it, quotes around the tag, and a block order change
odd = tempfile.mkdtemp(); os.makedirs(os.path.join(odd, "z1")); open(os.path.join(odd, "z1", "npcs.yaml"), "w").write(
 "  17297500:\n    content: 'voidwatch'\n    script: Planar_Rift\n    display_name: \"Planar Rift\"\n\n  17297501:\n    script: X\n    content: voidwatch_extra\n    display_name: Nope\n\n  17297502:\n    script: Y\n    display_name: Plain\n")
f = mv.find_voidwatch_npcs(odd); assert f == {127: [(17297500, "Planar Rift")]}, f
# 9. a missing zone folder is a clear message, not a crash
try: mv.build({"server_dir": tempfile.mkdtemp()}); assert False
except RuntimeError as e: assert "zone data" in str(e)
# 10. the generated Lua file is real Lua and the module does what it says
cfg, sv = server(); out(mv.build, cfg); mod_path = os.path.join(sv, "modules", "custom", "lua", "no_voidwatch.lua")
r = subprocess.run(["texluac", "-p", mod_path], capture_output=True, text=True); assert r.returncode == 0, r.stderr
print("generator OK; module written to", mod_path)
r = subprocess.run(["texlua", os.path.join(HERE, "test_module.lua"), mod_path], capture_output=True, text=True); print(r.stdout.strip().splitlines()[-1]); assert r.returncode == 0, r.stdout
