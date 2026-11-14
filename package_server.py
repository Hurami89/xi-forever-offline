"""Makes the prebuilt server package for players: xi-forever-offline-server-<version>-win64.zip + SHA256SUMS.txt.

Run on the dev PC after building the server (Rebuild server.bat):
    python package_server.py v0.1.0              writes dist\\ in this kit folder
    python package_server.py v0.1.0 --list       only shows what would go in, and the size

What goes in: the five server programs and the DLLs they load, settings\\default, and the files git tracks in scripts,
sql, modules, data, res and ximeshes (read from disk), plus the navmeshes submodule. What never goes in: anything git
does not track (backups, logs, crash dumps, settings\\network.lua and the other settings written on this PC, the
launcher's generated configs), the login/profile .cert and .key files (the server makes its own on first start), the
debug libzmq-d_64.dll, .pdb files and the build folder. Upload both files to a GitHub release of
xi-forever-offline-server; the launcher's first-run setup downloads the zip from there and checks it against SHA256SUMS.txt.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAMS = ["xi_connect.exe", "xi_world.exe", "xi_search.exe", "xi_profile.exe", "xi_map.exe"]
DLLS = ["libcrypto-3-x64.dll", "libluajit_64.dll", "libmariadb64.dll", "libssl-3-x64.dll", "libzmq_64.dll"]
TRACKED = ["scripts", "sql", "modules", "data", "res", "ximeshes"]
ROOT_FILES = ["LICENSE", "README.md"]
NEVER = (".before-", ".bak", ".retired", ".pdb", ".cert", ".key")


def git(server, *args):
    out = subprocess.run(["git", "-C", server] + list(args), capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    if out.returncode != 0:
        raise RuntimeError("git " + " ".join(args) + ": " + out.stderr.strip())
    return out.stdout


def walk(server, folder):
    """Every file in a submodule folder, without its git files or backups."""
    out = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(names):
            if name.startswith(".git") or any(mark in name for mark in NEVER):
                continue
            path = os.path.join(root, name)
            out.append((path, os.path.relpath(path, server).replace("\\", "/")))
    return out


def file_list(server):
    """[(path on disk, path in the zip)] and a list of warnings."""
    files, warnings = [], []
    for name in PROGRAMS + DLLS + ROOT_FILES:
        path = os.path.join(server, name)
        if os.path.isfile(path):
            files.append((path, name))
        elif name in PROGRAMS + DLLS:
            raise RuntimeError(f"{name} is missing: build the server first.")
    default = os.path.join(server, "settings", "default")
    for name in sorted(os.listdir(default)):
        if name.endswith(".lua"):
            files.append((os.path.join(default, name), "settings/default/" + name))
    tracked = git(server, "ls-files", "-z", "--", *TRACKED).split("\0")
    for rel in sorted(r for r in tracked if r):
        if any(mark in rel for mark in NEVER):
            continue
        path = os.path.join(server, *rel.split("/"))
        if os.path.isfile(path):
            files.append((path, rel))
        elif os.path.isdir(path):                      # a submodule (ximeshes, modules/phoenix_ac): everything in it
            files += walk(server, path)
        else:
            warnings.append("tracked but missing on disk: " + rel)
    files += walk(server, os.path.join(server, "navmeshes"))
    changed = [line for line in git(server, "status", "--porcelain", "--untracked-files=no", "--", *TRACKED).splitlines()]
    if changed:
        warnings.append(f"{len(changed)} tracked file(s) have changes that are not committed; they are packaged as they are "
                        "on disk (commit them so the release matches the repo): " + ", ".join(c[3:] for c in changed[:5]))
    return files, warnings


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the release tag, for example v0.1.0")
    parser.add_argument("--server", help="the server folder (default: server_dir in config.json)")
    parser.add_argument("--out", default=os.path.join(HERE, "dist"))
    parser.add_argument("--list", action="store_true", help="only show what would be packaged")
    args = parser.parse_args(argv)
    server = args.server
    if not server:
        with open(os.path.join(HERE, "config.json"), encoding="utf-8-sig") as handle:
            server = json.load(handle)["server_dir"]
    files, warnings = file_list(server)
    size = sum(os.path.getsize(p) for p, _ in files)
    for warning in warnings:
        print("WARNING:", warning)
    top = {}
    for _path, rel in files:
        key = rel.split("/")[0] if "/" in rel else "(top level)"
        top[key] = top.get(key, 0) + 1
    print(f"{len(files)} files, {size / 1e6:.0f} MB before compression: " + ", ".join(f"{k} {v}" for k, v in sorted(top.items())))
    if args.list:
        return 0
    commit = git(server, "rev-parse", "HEAD").strip()
    os.makedirs(args.out, exist_ok=True)
    name = f"xi-forever-offline-server-{args.version}-win64.zip"
    target = os.path.join(args.out, name)
    folder = f"xi-forever-offline-server-{args.version}/"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for index, (path, rel) in enumerate(files, 1):
            archive.write(path, folder + rel)
            if index % 2000 == 0:
                print(f"  {index}/{len(files)}")
        archive.writestr(folder + "VERSION.txt", f"XI: Forever Offline server {args.version}\ncommit {commit}\n")
    digest = hashlib.sha256()
    with open(target, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    with open(os.path.join(args.out, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{digest.hexdigest()}  {name}\n")
    print(f"Wrote {target} ({os.path.getsize(target) / 1e6:.0f} MB) and SHA256SUMS.txt (server commit {commit[:10]}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
