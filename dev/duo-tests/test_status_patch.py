import os, sys, json, shutil, tempfile, hashlib
KIT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs/ffxi-local"
sys.path.insert(0, KIT)
import patch_gambits_solo as first, patch_gambits_status as second
orig = open(os.path.join(KIT, "addons-src", "TitanGambits", "TitanGambits.lua"), encoding="utf-8", newline="").read()
assert first.sha(orig) == first.ORIGINAL_SHA, "the bundled engine is not the one the tools know"
def world(content):
    root = tempfile.mkdtemp(); kit = os.path.join(root, "kit"); ash = os.path.join(root, "ash"); os.makedirs(kit)
    os.makedirs(os.path.join(ash, "addons", "TitanGambits"))
    open(os.path.join(ash, "addons", "TitanGambits", "TitanGambits.lua"), "w", encoding="utf-8", newline="").write(content)
    return {"ashita_dir": ash}, kit
def current(cfg): return first.read(first.addon_path(cfg))
# both tools keep their backups next to themselves (HERE); point the module at a scratch folder
tmp = tempfile.mkdtemp(); first.HERE = tmp; second.HERE = tmp
v1 = first.apply_patches(orig); assert first.sha(v1) == first.PATCHED_SHA
# 1. the file as it is on your machine
cfg, _ = world(v1)
assert second.status(cfg)[0] == "base"
assert second.apply(cfg) == 0
assert first.sha(current(cfg)) == second.NEW_SHA and first.lua_blocks(current(cfg))
assert "S.statusSnapshots[target.id]" in current(cfg) and current(cfg).count("function E.request_status_snapshot") == 1
assert os.path.exists(second.backup_path()) and first.read(second.backup_path()) == v1
assert second.status(cfg)[0] == "patched" and second.apply(cfg) == 0 and first.sha(current(cfg)) == second.NEW_SHA     # again: nothing to do
# 2. undo gives back exactly the file before
assert second.undo(cfg) == 0 and current(cfg) == v1 and second.status(cfg)[0] == "base"
assert second.undo(cfg) == 0 and current(cfg) == v1                                                                  # undo when not applied: nothing
# 3. the original, unpatched engine: refuses, says what to do first
cfg, _ = world(orig); assert second.status(cfg)[0] == "original" and second.apply(cfg) == 2 and current(cfg) == orig
# 4. a file it does not know: untouched
cfg, _ = world(v1 + "\n-- somebody edited this\n"); before = current(cfg)
assert second.status(cfg)[0] == "unknown" and second.apply(cfg) == 1 and current(cfg) == before
# 5. not installed
root = tempfile.mkdtemp(); cfg = {"ashita_dir": root}; assert second.status(cfg)[0] == "missing" and second.apply(cfg) == 1
# 6. the same chain from the original with both tools reaches the new checksum
cfg, _ = world(orig); first.apply(cfg); assert second.apply(cfg) == 0 and first.sha(current(cfg)) == second.NEW_SHA
# 7. if the text it expects is gone, it changes nothing
cfg, _ = world(v1.replace("local now=E.now();\n    if S.statusRequest", "local now=E.now()\n    if S.statusRequest", 1))
try: second.apply_patches(current(cfg)); assert False
except RuntimeError as e: assert "changed nothing" in str(e)
print("status patch tool OK")
