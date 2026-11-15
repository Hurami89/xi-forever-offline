"""Downloads other people's add-ons and tools from their official releases (thirdparty.json). No GUI code.

Nothing here is rehosted: every file comes from the author's own release page, and the version that was installed is
written to thirdparty-installed.json in the kit folder. Files a download would replace are copied first to
backups\\thirdparty\\<id>-<time>\\, and folders listed in an item's "keep" (your settings) are never overwritten.
"""
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import time
import urllib.request
import zipfile

USER_AGENT = "XI-Forever-Offline-launcher"
API = "https://api.github.com/repos/"


def load_manifest(kit):
    with open(os.path.join(kit, "thirdparty.json"), encoding="utf-8-sig") as handle:
        return json.load(handle)["items"]


def state_path(kit):
    return os.path.join(kit, "thirdparty-installed.json")


def load_state(kit):
    try:
        with open(state_path(kit), encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(kit, state):
    with open(state_path(kit), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)


def target_root(item, kit, ashita, server=None):
    into = item.get("into", "ashita")
    return ashita if into == "ashita" else server if into == "server" else kit


def find_ollama():
    """ollama.exe from PATH or where its installer puts it, or None."""
    found = shutil.which("ollama")
    for guess in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
                  os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe")):
        if not found and os.path.isfile(guess):
            found = guess
    return found


def ollama_models(run=None):
    """The model names Ollama has pulled ([] when Ollama is missing or not running)."""
    import subprocess
    exe = find_ollama()
    if not exe:
        return []
    try:
        out = (run or subprocess.run)([exe, "list"], capture_output=True, text=True, timeout=20, creationflags=0x08000000)
    except Exception:
        return []
    return [line.split()[0] for line in (out.stdout or "").splitlines()[1:] if line.strip()]


def status(item, kit, ashita, state=None, server=None):
    """(installed, version text) from what this launcher recorded, else from the item's check file."""
    if item["source"]["type"] == "ollama_model":
        model = item["source"]["model"]
        have = any(name == model or name == model + ":latest" for name in ollama_models())
        return have, model if have else ""
    if item.get("check_system"):             # something Windows itself keeps (the Visual C++ runtime)
        present = os.path.exists(os.path.expandvars(item["check_system"]))
        return present, "installed" if present else ""
    state = load_state(kit) if state is None else state
    record = state.get(item["id"])
    root = target_root(item, kit, ashita, server)
    present = bool(item.get("check")) and bool(root) and os.path.exists(os.path.join(root, item["check"]))
    if record and (present or not item.get("check")):
        return True, record.get("version", "")
    if present:
        version = ""
        if item["check"].endswith(".lua"):
            try:
                with open(os.path.join(root, item["check"]), encoding="utf-8", errors="replace") as handle:
                    found = re.search(r"addon\.version\s*=\s*['\"]([^'\"]+)", handle.read(20000))
                version = found.group(1) if found else ""
            except OSError:
                pass
        return True, version or "installed"
    return False, ""


# ----- finding the download -----
def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def resolve(item, fetch=_get):
    """What to download: {"version", "url", "name", "sha256" (or None)}. Raises ValueError for a page-only item."""
    source = item["source"]
    kind = source["type"]
    if kind == "github_release":
        tag = source.get("tag", "latest")
        if tag == "latest" and source.get("prereleases"):
            # GitHub's releases/latest skips pre-releases: take the newest published one, test builds included
            releases = [r for r in json.loads(fetch(API + source["repo"] + "/releases?per_page=20")) if not r.get("draft")]
            if not releases:
                raise RuntimeError(f"{item['name']}: no release published yet.")
            release = releases[0]
        else:
            path = "releases/latest" if tag == "latest" else "releases/tags/" + tag
            release = json.loads(fetch(API + source["repo"] + "/" + path))
        assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        names = [n for n in assets if re.search(source["asset"], n)]
        if not names:
            raise RuntimeError(f"{item['name']}: no file matching {source['asset']} in release {release.get('tag_name')}")
        name = sorted(names)[0]
        digest = None
        if source.get("sha256sums"):
            sums = fetch(assets[source["sha256sums"]]).decode("utf-8", "replace")
            for line in sums.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[-1].lstrip("*") == name:
                    digest = parts[0].lower()
            if not digest:
                raise RuntimeError(f"{item['name']}: {name} is not listed in {source['sha256sums']}")
        return {"version": release.get("tag_name", tag), "url": assets[name], "name": name, "sha256": digest}
    if kind == "github_archive":
        ref = source["ref"]
        url = f"https://github.com/{source['repo']}/archive/{ref}.zip"
        return {"version": ref, "url": url, "name": source["repo"].split("/")[-1] + "-" + ref + ".zip", "sha256": None}
    if kind == "ollama_model":
        return {"version": source["model"], "url": "", "name": source["model"], "sha256": None}
    if kind in ("url", "installer"):
        return {"version": time.strftime("%Y-%m-%d"), "url": source["url"], "name": source["url"].rsplit("/", 1)[-1], "sha256": None}
    raise ValueError(f"{item['name']} is downloaded from its page by hand: {source.get('url', item.get('homepage'))}")


def download(item, kit, found, fetch=_get):
    """Downloads into downloads\\<id>\\ and checks the SHA-256 when the release lists one. Returns the file path."""
    folder = os.path.join(kit, "downloads", item["id"])
    os.makedirs(folder, exist_ok=True)
    data = fetch(found["url"], timeout=600)
    actual = hashlib.sha256(data).hexdigest()
    if found.get("sha256") and actual != found["sha256"]:
        raise RuntimeError(f"{item['name']}: the download does not match its published checksum - not installed.")
    path = os.path.join(folder, found["name"])
    with open(path, "wb") as handle:
        handle.write(data)
    found["sha256_actual"] = actual
    return path


# ----- putting the files in place -----
def plan(item, names):
    """Where each file in the download goes: [(name in the download, relative destination)]."""
    out = []
    for name in names:
        if name.endswith("/"):
            continue
        for source, dest in item.get("files", []):
            if source.startswith("*/"):              # "*/x/" = x/ inside the download's single top folder
                head, _, rest = name.partition("/")
                pattern = source[2:]
                if not rest:
                    continue
                if pattern == "":
                    out.append((name, dest + rest))
                    break
                if rest.startswith(pattern):
                    out.append((name, dest + rest[len(pattern):]))
                    break
            elif source.endswith("/"):
                if name.startswith(source):
                    out.append((name, dest + name[len(source):]))
                    break
            elif fnmatch.fnmatch(name, source) or name == source:
                out.append((name, dest))
                break
    for _name, dest in out:
        parts = dest.replace("\\", "/").split("/")
        if dest.startswith(("/", "\\")) or ":" in dest or ".." in parts:
            raise RuntimeError(f"{item['name']}: refusing to write outside its folder ({dest})")
    return out


def pull_model(model, log=print, popen=None):
    """ollama pull <model>, starting Ollama first when it is not running. Reports progress about every 20 seconds."""
    import subprocess
    exe = find_ollama()
    if not exe:
        raise RuntimeError("Ollama is not installed yet (install it first).")
    if not ollama_models() and subprocess.run([exe, "list"], capture_output=True, creationflags=0x08000000).returncode != 0:
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        time.sleep(5)
    proc = (popen or subprocess.Popen)([exe, "pull", model], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       creationflags=0x08000000)
    last, buffer = 0.0, b""
    while True:
        chunk = proc.stdout.read(256)
        if not chunk:
            break
        buffer = (buffer + chunk)[-400:]
        if time.time() - last > 20:
            text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", buffer.decode("utf-8", "replace")).replace("\r", "\n")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines:
                log(f"AI model {model}: {lines[-1][:90]}")
            last = time.time()
    if proc.wait() != 0:
        raise RuntimeError(f"ollama pull {model} failed (code {proc.returncode}).")
    log(f"AI model {model} is ready.")


def install(item, kit, ashita, fetch=_get, log=print, server=None, run=None):
    """Downloads and installs one item. Returns the version installed."""
    if item["source"]["type"] == "ollama_model":
        pull_model(item["source"]["model"], log=log)
        return item["source"]["model"]
    root = target_root(item, kit, ashita, server)
    if not root:
        raise RuntimeError("Set the " + ("server" if item.get("into") == "server" else "Ashita") + " folder first.")
    found = resolve(item, fetch)
    log(f"{item['name']}: downloading {found['name']} ({found['version']})...")
    path = download(item, kit, found, fetch)
    if item["source"]["type"] == "installer":
        log(f"{item['name']}: starting its installer.")
        if item["source"].get("wait"):             # quiet installers (Visual C++): wait until done
            import subprocess
            result = (run or subprocess.run)([path] + list(item["source"].get("args", [])))
            if result.returncode not in (0, 1638, 3010):    # 1638 = a newer one is installed, 3010 = done, restart later
                raise RuntimeError(f"{item['name']}: the installer stopped with code {result.returncode}.")
        else:
            os.startfile(path)                     # Windows: the installer asks the player itself
    else:
        if zipfile.is_zipfile(path):
            archive = zipfile.ZipFile(path)
            names = archive.namelist()
            read = archive.read
        else:
            names = [found["name"]]
            read = lambda _name: open(path, "rb").read()
        moves = plan(item, names)
        if not moves:
            raise RuntimeError(f"{item['name']}: nothing in {found['name']} matched where it should go.")
        keep = tuple(item.get("keep", []))
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(kit, "backups", "thirdparty", f"{item['id']}-{stamp}")
        written = kept = 0
        for name, rel in moves:
            dest = os.path.join(root, rel)
            if os.path.exists(dest):
                if rel.startswith(keep) and keep:
                    kept += 1
                    continue
                os.makedirs(os.path.dirname(os.path.join(backup, rel)), exist_ok=True)
                shutil.copy2(dest, os.path.join(backup, rel))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as handle:
                handle.write(read(name))
            written += 1
        log(f"{item['name']}: {written} file(s) installed" + (f", {kept} of your own kept" if kept else "")
            + (f"; replaced files saved in {backup}" if os.path.isdir(backup) else "") + ".")
    state = load_state(kit)
    state[item["id"]] = {"version": found["version"], "file": found["name"], "sha256": found.get("sha256_actual"),
                         "from": found["url"], "at": time.strftime("%Y-%m-%d %H:%M")}
    _save_state(kit, state)
    return found["version"]


def latest_version(item, fetch=_get):
    """The newest release tag for a GitHub release item (to offer an update), or None."""
    source = item["source"]
    if source["type"] != "github_release":
        return None
    try:
        if source.get("prereleases"):
            releases = [r for r in json.loads(fetch(API + source["repo"] + "/releases?per_page=20")) if not r.get("draft")]
            return releases[0]["tag_name"] if releases else None
        return json.loads(fetch(API + source["repo"] + "/releases/latest")).get("tag_name")
    except Exception:
        return None


def credits_lines(kit):
    """One line per item for the About box and CREDITS: name, author, license, home page."""
    return [f"{i['name']} - {i['author']} - {i['license']} - {i['homepage']}" for i in load_manifest(kit)]


# ----- our edits to an add-on the player installs by hand (Journal's era filter) -----
def apply_patch(kit, ashita, folder, dry_run=False):
    """Applies addons-src\\<folder>\\patch.json to Ashita. Every 'find' must appear exactly once (or its 'replace' must
    already be there: applied before), else nothing is changed. Changed files are backed up as <file>.before-era first.
    Returns a list of messages."""
    base = os.path.join(kit, "addons-src", folder)
    with open(os.path.join(base, "patch.json"), encoding="utf-8") as handle:
        patch = json.load(handle)
    texts, todo = {}, []
    for rel, find, replace in patch["edits"]:
        path = os.path.join(ashita, *rel.split("/"))
        if rel not in texts:
            if not os.path.exists(path):
                raise RuntimeError(f"{rel} is not there: install the add-on first.")
            with open(path, encoding="utf-8", newline="") as handle:
                texts[rel] = handle.read()
        text = texts[rel]
        crlf = "\r\n" in text
        f, r = (find.replace("\n", "\r\n"), replace.replace("\n", "\r\n")) if crlf else (find, replace)
        if text.count(f) == 1:
            todo.append((rel, f, r))
        elif text.count(r) == 1:
            continue                                   # already applied
        else:
            raise RuntimeError(f"{rel} is not the version these edits were made for ({patch.get('made_for')}): nothing was changed.")
    if dry_run:
        return [f"{len(todo)} change(s) to make"]
    messages = []
    for rel, f, r in todo:
        texts[rel] = texts[rel].replace(f, r, 1)
    for rel in sorted({t[0] for t in todo}):
        path = os.path.join(ashita, *rel.split("/"))
        if not os.path.exists(path + ".before-era"):
            shutil.copy2(path, path + ".before-era")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(texts[rel])
        messages.append(f"Edited {rel}.")
    for src, dest in patch.get("copy", []):
        target = os.path.join(ashita, *dest.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.exists(target):
            shutil.copy2(os.path.join(base, src), target)
            messages.append(f"Added {dest}.")
    return messages or ["The edits were already there."]
