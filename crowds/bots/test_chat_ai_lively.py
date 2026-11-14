"""Stand-in checks for the livelier bot chat (bots_chat_ai.py) and the model choice (crowd_chat_ai.py), with a fake Ollama.

  python3 test_chat_ai_lively.py [folder with bots_chat_ai.py]   (crowd_chat_ai.py is one folder up)
"""
import http.server
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading

HERE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
passes = fails = 0


def check(name, cond, detail=""):
    global passes, fails
    if cond:
        passes += 1
        print("ok  ", name)
    else:
        fails += 1
        print("FAIL", name, "--", detail)


SEEN = []           # request bodies
REPLY = {"text": "lol yeah"}
MODELS = ["mistral-nemo:latest"]


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"name": m} for m in MODELS]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n))
        SEEN.append(req)
        last = req["messages"][-1]["content"]
        if "Answer with JSON only" in last:
            content = json.dumps({"player": "a night shift nurse who plays after work", "style": "lowercase, lots of lol"})
        elif "what do you now know and think about" in last:
            content = "Hurami is a friendly whm who helped me at dunes, i like them"
        else:
            content = REPLY["text"]
        body = json.dumps({"message": {"content": content}}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)


srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}"

work = tempfile.mkdtemp()
spec = importlib.util.spec_from_file_location("bots_chat_ai", os.path.join(HERE, "bots_chat_ai.py"))
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)
ai.MEMORY = os.path.join(work, "mem")
ai.log = lambda m: None
cfg = {"model": "gemma4:12b", "ollama_url": URL}

info = {"job": "WHM", "level": 22, "doing": "hunting in Valkurm Dunes", "recent": "hit level 22 on WHM | wiped in a BCNM 20 at Ghelsba Outpost",
        "gossip": "Aldric started a social linkshell called CozyMoogles | Taliah made nation rank 4", "lsMates": "Aldric, Humef",
        "lastParty": "Kerowyn, Bo"}

# 1. the prompt carries its own story, the people it knows, server talk; a thinking model answers straight away
lines = ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "hey whats up", "info": info})
req = SEEN[-1]
system = req["messages"][0]["content"]
check("a reply comes back", lines == ["lol yeah"], lines)
check("its recent days are in the prompt", "wiped in a BCNM 20 at Ghelsba Outpost" in system and "hit level 22" in system)
check("server talk is in it (other players)", "CozyMoogles" in system and "Taliah made nation rank 4" in system)
check("people it knows (linkshell mates, last party)", "Aldric, Humef" in system and "Kerowyn, Bo" in system)
check("not like an assistant: varied length, opinions, asking back", "not like a helpful assistant" in system and "ask them something back" in system)
check("gemma4: think is off (no reasoning in chat)", req.get("think") is False, req.get("think"))
check("gemma4: its sampling (temperature 1.0, top_k 64)", req["options"].get("temperature") == 1.0 and req["options"].get("top_k") == 64, req["options"])
check("more room to talk (110 tokens, 4096 context)", req["options"]["num_predict"] == 110 and req["options"]["num_ctx"] == 4096)
mem = ai.load_memory("Mira")
check("the diary is kept in its memory file", len(mem.get("diary", [])) == 2, mem.get("diary"))
ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "nice", "info": info})
check("... without repeats", len(ai.load_memory("Mira").get("diary", [])) == 2)

cfg2 = {"model": "mistral-nemo:latest", "ollama_url": URL}
ai.answer_lines(cfg2, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "ok", "info": {"job": "WHM", "level": 22}})
check("an older model gets no think field", "think" not in SEEN[-1])

# 2. two lines, thinking blocks, stage directions
REPLY["text"] = "<think>they asked about dunes</think>oh man dunes was crazy today, we pulled two goblins at once and the whm ran oom. anyway you still need a party? we have room"
lines = ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "how was dunes", "info": info})
check("a long thought goes out as two lines", len(lines) == 2 and all(len(l) <= ai.MAX_CHARS for l in lines), lines)
check("no thinking text in chat", all("think" not in l and "they asked" not in l for l in lines))
REPLY["text"] = "*waves* hey hey"
check("no *actions*", ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "o/", "info": info}) == ["hey hey"])
REPLY["text"] = "i am an ai language model"
check("out of era / AI talk is refused (the bot answers on its own in game)", ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "?", "info": info}) == [])

# 3. after a few exchanges it sums up what it knows about you, and uses it
REPLY["text"] = "haha sure"
for i in range(7):
    ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": f"line {i}", "info": info})
mem = ai.load_memory("Mira")
check("it remembers you in a sentence", "friendly whm" in mem.get("about", {}).get("Hurami", ""), mem.get("about"))
ai.answer_lines(cfg, {"bot": "Mira", "to": "Hurami", "kind": "tell", "text": "back", "info": info})
check("... and the next chat knows it", "friendly whm" in SEEN[-1]["messages"][0]["content"])

# 4. serve writes two lines with the same id
lua = os.path.join(work, "server", "modules", "custom", "lua")
os.makedirs(lua)
REPLY["text"] = "first part of a long answer that goes on and on about the auction house prices being crazy lately. second bit here ok"
import time
with open(os.path.join(lua, "bots_chat_state.json"), "w") as f:
    json.dump({"offset": 0}, f)
with open(os.path.join(lua, "bots_chat_in.txt"), "w") as f:
    f.write(json.dumps({"id": 42, "t": time.time(), "bot": "Mira", "to": "Hurami", "kind": "tell", "text": "ah prices?", "info": info}) + "\n")
ai.serve(cfg, os.path.join(work, "server"))
out = open(os.path.join(lua, "bots_chat_out.txt")).read().splitlines()
check("serve: two lines, both with the request id", len(out) == 2 and all(l.startswith("42\t") for l in out), out)

# 5. the model: the new one when it is pulled, else the old one
sys.path.insert(0, os.path.dirname(HERE))
spec2 = importlib.util.spec_from_file_location("crowd_chat_ai", os.path.join(os.path.dirname(HERE), "crowd_chat_ai.py"))
cc = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(cc)
check("not pulled yet: it keeps using the old model", cc.pick_model("gemma4:12b", "mistral-nemo:latest", URL) == "mistral-nemo:latest")
MODELS.append("gemma4:12b")
cc._installed["at"] = 0
check("pulled: the new one", cc.pick_model("gemma4:12b", "mistral-nemo:latest", URL) == "gemma4:12b")
check("Ollama not answering: the configured one (no crash)", cc.pick_model("gemma4:12b", "mistral-nemo:latest", "http://127.0.0.1:1") in ("gemma4:12b", "mistral-nemo:latest"))
check("think off only for thinking models", cc.model_extra("gemma4:12b") == {"think": False} and cc.model_extra("mistral-nemo:latest") == {})

srv.shutdown()
shutil.rmtree(work, ignore_errors=True)
print(f"\n{passes} passed, {fails} failed")
sys.exit(1 if fails else 0)
