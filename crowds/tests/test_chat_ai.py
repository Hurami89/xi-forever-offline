"""Checks crowd_chat_ai.py against a stand-in Ollama (a tiny local web server). Usage: python test_chat_ai.py"""
import http.server
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cca", os.path.join(HERE, "crowd_chat_ai.py"))
cca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cca)
fails = 0


def check(name, cond, detail=""):
    global fails
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)))
    fails += 0 if cond else 1


REPLIES = {
    "pairs": {"lines": [{"a": "you ready?", "b": "one sec, buying food"}, {"a": "abyssea tonight?", "b": "sure"},
                        {"a": "lfp?", "b": "ya"}, ["where is the AH", "upstairs"], {"a": "x" * 120, "b": "too long"}]},
    "default": {"lines": ["brb food", "so laggy lol", "anyone know where the guild is?", "lets do Abyssea", "need trusts",
                          "level 99 soon", "Hurami is cool", "café time", "x" * 100, "{name} hi", "Sure, here are 12 lines:",
                          "TP burn at Valkurm?", "ty for the cure", "anyone selling Echo Drops?", "brb food"]},
}
asked = []


class Fake(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = body["messages"][-1]["content"]
        asked.append(body)
        kind = "pairs" if "two-line" in user else "default"
        out = json.dumps({"message": {"content": json.dumps(REPLIES[kind])}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
cfg = {"model": "test", "ollama_url": "http://127.0.0.1:%d" % srv.server_port}

server = tempfile.mkdtemp()
os.makedirs(os.path.join(server, "modules", "custom", "lua"))
pool = cca.load_pool(server)
for _ in range(12):
    cca.one_round(cfg, server, pool)
check("asks the model with the era rules and JSON format", asked and asked[0]["format"] == "json" and "75 era" in asked[0]["messages"][0]["content"])
check("one request at a time, small", all(a["options"]["num_predict"] <= 800 for a in asked))
allsay = pool["say"] + pool["outpost"] + pool["react"] + pool["shout"]
check("good lines kept", "brb food" in pool["say"] and "TP burn at Valkurm?" in allsay)
bad = [l for l in allsay if any(w in l.lower() for w in ("abyssea", "trusts", "99", "hurami", "caf", "{", "sure,"))] + [l for l in allsay if len(l) > 90]
check("out-of-era, non-ASCII, too long, names and chatter-about-the-task dropped", not bad, bad)
check("no duplicates", len(set(pool["say"])) == len(pool["say"]))
check("pairs kept as two lines, bad pair dropped", ["you ready?", "one sec, buying food"] in pool["pairs"] and
      all("abyssea" not in (a + b).lower() for a, b in pool["pairs"]) and ["where is the AH", "upstairs"] in pool["pairs"])
lua = os.path.join(server, "modules", "custom", "lua", "crowds_chat_ai.lua")
check("pool written for the server", os.path.exists(lua) and not os.path.exists(lua + ".tmp"))
# the Lua file loads (texlua) and has the categories
probe = os.path.join(server, "probe.lua")
with open(probe, "w") as f:
    f.write("local t = dofile(arg[1]); print(#t.say, #t.pairs, #t.outpost, #t.react, #t.shout, t.pairs[1] and t.pairs[1][2])")
try:
    out = subprocess.run(["texlua", probe, lua], capture_output=True, text=True).stdout.split()
    check("the Lua pool file loads: " + " ".join(out), len(out) >= 5 and int(out[0]) > 0)
except FileNotFoundError:
    print("skip texlua not found")
# reload keeps the pool
again = cca.load_pool(server)
check("pool survives a restart (json)", again["say"] == pool["say"])
# full pool: swaps only a few lines
for k in cca.TARGET:
    pool[k] = (pool[k] * 200)[:cca.TARGET[k]] if pool[k] else (["x%d" % i for i in range(cca.TARGET[k])] if k != "pairs" else [["a%d" % i, "b"] for i in range(cca.TARGET[k])])
before = {k: list(v) for k, v in pool.items()}
full = cca.one_round(cfg, server, pool)
changed = sum(1 for k in pool for a, b in zip(before[k], pool[k]) if a != b) + sum(abs(len(before[k]) - len(pool[k])) for k in pool)
check("when full: reports full, never grows, swaps at most a few", full and all(len(pool[k]) <= cca.TARGET[k] for k in pool), changed)
# squad chat busy -> skipped
kit = tempfile.mkdtemp()
os.makedirs(os.path.join(kit, "squad-chat"))
open(os.path.join(kit, "squad-chat", "in.txt"), "w").write("x")
cca.KIT = kit
check("squad chat active in the last minute -> waits", cca.squad_busy())
old = time.time() - 600
os.utime(os.path.join(kit, "squad-chat", "in.txt"), (old, old))
check("squad chat quiet -> goes ahead", not cca.squad_busy())
# Ollama down -> the run loop survives (one round raises URLError, caught in main)
srv.shutdown()
r = subprocess.run([sys.executable, os.path.join(HERE, "crowd_chat_ai.py"), "--once", "--server", server], capture_output=True, text=True,
                   timeout=60, env=dict(os.environ))
check("Ollama not running: says so and exits cleanly with --once", r.returncode == 0, r.stdout + r.stderr)
r = subprocess.run([sys.executable, os.path.join(HERE, "crowd_chat_ai.py"), "--status", "--server", server], capture_output=True, text=True)
check("--status shows the pool", "say" in r.stdout and "/160" in r.stdout, r.stdout)
print("\n" + ("all passed" if fails == 0 else "%d FAILED" % fails))
sys.exit(1 if fails else 0)
