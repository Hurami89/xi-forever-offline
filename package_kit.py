"""Makes the player download: xi-forever-offline-<version>-win64.zip (+ SHA256SUMS.txt) in dist\\kit\\.

    python package_kit.py v0.1.1            (build the exe first: .\\build_release.ps1)
    python package_kit.py v0.1.1 --list     only shows what would go in

Inside is one folder, "XI Forever Offline", with every file git tracks in this kit (the launcher's scripts, assets,
addons, data, tests) and XI Forever Offline.exe. A player unzips it anywhere and runs the exe; the first-run setup
does the rest. Never inside: anything git does not track (config.json, rates.json, your squad mates, backups, logs, ROMs,
downloads, dist\\ and build\\).
"""
import argparse
import hashlib
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = "XI Forever Offline.exe"
TOP = "XI Forever Offline/"


def tracked():
    out = subprocess.run(["git", "-C", HERE, "ls-files", "-z"], capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    if out.returncode != 0:
        raise RuntimeError("git ls-files: " + out.stderr.strip())
    return [f for f in out.stdout.split("\0") if f]


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version")
    parser.add_argument("--out", default=os.path.join(HERE, "dist", "kit"))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    files = [f for f in tracked() if os.path.isfile(os.path.join(HERE, *f.split("/")))]
    exe = os.path.join(HERE, EXE)
    if not os.path.isfile(exe):
        raise SystemExit(f"{EXE} is missing: run .\\build_release.ps1 first.")
    changed = subprocess.run(["git", "-C", HERE, "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                             text=True, env=dict(os.environ, GIT_OPTIONAL_LOCKS="0")).stdout.splitlines()
    if changed:
        print(f"WARNING: {len(changed)} tracked file(s) are not committed; they are packaged as they are on disk.")
    size = sum(os.path.getsize(os.path.join(HERE, *f.split("/"))) for f in files) + os.path.getsize(exe)
    print(f"{len(files)} kit files + {EXE}, {size / 1e6:.0f} MB before compression.")
    if args.list:
        return 0
    commit = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    os.makedirs(args.out, exist_ok=True)
    name = f"xi-forever-offline-{args.version}-win64.zip"
    target = os.path.join(args.out, name)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for rel in files:
            archive.write(os.path.join(HERE, *rel.split("/")), TOP + rel)
        archive.write(exe, TOP + EXE)
        archive.writestr(TOP + "VERSION.txt", f"XI: Forever Offline {args.version}\ncommit {commit}\n")
    digest = hashlib.sha256()
    with open(target, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    with open(os.path.join(args.out, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{digest.hexdigest()}  {name}\n")
    print(f"Wrote {target} ({os.path.getsize(target) / 1e6:.0f} MB) and SHA256SUMS.txt.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
