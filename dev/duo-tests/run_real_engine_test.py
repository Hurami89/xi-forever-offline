#!/usr/bin/env python3
"""Runs the real gambit engine next to the follow addon in a stand-in game and checks what he does in a fight.
The engine is built here from the file bundled in addons-src, with each patch applied exactly as the patch tools apply it."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, KIT)
import patch_gambits_solo as first
import patch_gambits_status as second
original = first.read(os.path.join(KIT, "addons-src", "TitanGambits", "TitanGambits.lua"))
assert first.sha(original) == first.ORIGINAL_SHA, "the bundled engine is not the version the patch tools know"
v1 = first.apply_patches(original)
assert first.sha(v1) == first.PATCHED_SHA
v2 = second.apply_patches(v1)
assert first.sha(v2) == second.NEW_SHA
scratch = tempfile.mkdtemp()
paths = []
for name, text in (("engine_v1.lua", v1), ("engine_v2.lua", v2)):
    path = os.path.join(scratch, name); first.write(path, text); paths.append(path)
follow = os.path.join(KIT, "addons-src", "followme", "followme.lua")
sys.exit(subprocess.call(["texlua", os.path.join(HERE, "test_real_engine.lua"), follow] + paths))
