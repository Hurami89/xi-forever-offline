"""XI: Forever Offline Setup: the one file a new player downloads (2026-11-27, Hurami: "when you download the installer
there's a ton of files in the folder with it, it can be a little intimidating for some players, any chance the install
file can be a 1 click file?").

One window: where to put the game (C:\\XIForeverOffline unless you pick another folder), Install. It downloads the newest
full release (the same XI-Forever-Offline.zip the website links), checks it against the release's SHA256SUMS.txt, unpacks
it, puts "XI Forever Offline" on the desktop and in the Start menu, and opens the launcher, which does the rest of the
setup as before. The launcher then keeps itself up to date, so this file is only needed once.

Built into "XI Forever Offline Setup.exe" by build_installer.ps1 (PyInstaller, one file, no Python needed).
Test without a window:  python installer/xifo_setup.py --quiet <folder>   (no shortcuts, does not open the launcher)
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile

REPO = "Hurami89/xi-forever-offline"
ZIP_URL = f"https://github.com/{REPO}/releases/latest/download/XI-Forever-Offline.zip"
SUMS_URL = f"https://github.com/{REPO}/releases/latest/download/SHA256SUMS.txt"
DEFAULT_DIR = r"C:\XIForeverOffline"
EXE_NAME = "XI Forever Offline.exe"
TOP = "XI Forever Offline"          # the one folder at the top of the zip
NEED_BYTES = 800 * 1024 * 1024      # the download, the unpacked kit, and room to spare
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
LOG = os.path.join(tempfile.gettempdir(), "xifo-setup.log")


def log(text):
    try:
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except OSError:
        pass


def ssl_context():
    """Windows' certificates plus Mozilla's (certifi, bundled), as the launcher does: a fresh PC may not have GitHub's root yet."""
    import ssl
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except Exception:
        pass
    return context


def folder_problem(folder):
    """Why this folder can't be used, or None."""
    full = os.path.abspath(folder)
    low = os.path.normcase(full).lower()
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "SystemRoot"):
        root = os.environ.get(env)
        root = os.path.normcase(os.path.abspath(root)).lower() if root else None
        if root and (low == root or low.startswith(root.rstrip(os.sep) + os.sep)):
            return ("Windows protects this folder, so the game could not save anything there. "
                    "Pick a folder of your own, for example " + DEFAULT_DIR + ".")
    if os.path.isdir(full) and os.listdir(full) and not os.path.isfile(os.path.join(full, EXE_NAME)):
        return "This folder already has other files in it. Pick an empty or new folder (for example " + DEFAULT_DIR + ")."
    probe = full
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        free = shutil.disk_usage(probe).free
        if free < NEED_BYTES:
            return f"Not enough free space on that drive: {free / 1e9:.1f} GB free, about {NEED_BYTES / 1e9:.1f} GB needed."
    except OSError:
        return "That drive or folder can't be reached."
    return None


def download(url, path, progress=None, opener=None):
    """Downloads url to path. progress(done, total) as it goes. Returns the file's SHA-256."""
    opener = opener or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "XIFO-Setup"}),
                                                         timeout=60, context=ssl_context()))
    digest = hashlib.sha256()
    with opener(url) as response, open(path, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return digest.hexdigest()


def published_sums(text):
    """The SHA-256 values in a SHA256SUMS.txt (lines "<hash>  <file name>")."""
    out = set()
    for line in (text or "").splitlines():
        parts = line.split()
        if parts and len(parts[0]) == 64 and all(c in "0123456789abcdefABCDEF" for c in parts[0]):
            out.add(parts[0].lower())
    return out


def unpack(zip_path, folder, progress=None):
    """Unpacks the kit's zip into folder, without its top folder. Never writes outside folder."""
    target = os.path.abspath(folder)
    with zipfile.ZipFile(zip_path) as z:
        names = z.infolist()
        for i, info in enumerate(names):
            name = info.filename.replace("\\", "/")
            if name.startswith(TOP + "/"):
                name = name[len(TOP) + 1:]
            if not name:
                continue
            dest = os.path.abspath(os.path.join(target, *name.split("/")))
            if dest != target and not dest.startswith(target + os.sep):
                raise RuntimeError("the download has a file that points outside the game folder: " + info.filename)
            if name.endswith("/"):
                os.makedirs(dest, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
            if progress and i % 25 == 0:
                progress(i + 1, len(names))
    if not os.path.isfile(os.path.join(target, EXE_NAME)):
        raise RuntimeError("the download did not hold " + EXE_NAME)


def shortcut(link, target, folder):
    """A Windows shortcut (.lnk) through PowerShell's WScript.Shell."""
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:XIFO_LINK); $s.TargetPath = $env:XIFO_TARGET; "
              "$s.WorkingDirectory = $env:XIFO_DIR; $s.IconLocation = $env:XIFO_TARGET + ',0'; $s.Save()")
    env = dict(os.environ, XIFO_LINK=link, XIFO_TARGET=target, XIFO_DIR=folder)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], env=env,
                   capture_output=True, creationflags=NO_WINDOW, timeout=60)


def make_shortcuts(folder):
    exe = os.path.join(folder, EXE_NAME)
    made = []
    places = [os.path.join(os.path.expanduser("~"), "Desktop")]
    appdata = os.environ.get("APPDATA")
    if appdata:
        places.append(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    for place in places:
        try:
            if os.path.isdir(place):
                link = os.path.join(place, "XI Forever Offline.lnk")
                shortcut(link, exe, folder)
                if os.path.isfile(link):
                    made.append(link)
        except Exception as e:                  # a shortcut is a convenience: the game is installed anyway
            log(f"shortcut in {place}: {e}")
    return made


def install(folder, status, progress, sums_text=None, opener=None):
    """The whole install. status(text) and progress(fraction 0..1) report it. Returns the folder."""
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, "_setup_download.zip")
    try:
        status("Downloading XI: Forever Offline (about 180 MB)...")
        got = download(ZIP_URL, tmp, lambda done, total: progress(0.8 * done / total if total else 0,
                       f"Downloading... {done / 1e6:.0f}" + (f" of {total / 1e6:.0f} MB" if total else " MB")), opener=opener)
        status("Checking the download...")
        if sums_text is None:
            try:
                fetch = opener or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "XIFO-Setup"}),
                                                                    timeout=60, context=ssl_context()))
                with fetch(SUMS_URL) as response:
                    sums_text = response.read().decode("utf-8", "replace")
            except Exception as e:
                log(f"SHA256SUMS.txt: {e}")
                sums_text = ""
        sums = published_sums(sums_text)
        if sums and got.lower() not in sums:
            raise RuntimeError("the download does not match the release's checksum (it may have been cut short). Try again.")
        with zipfile.ZipFile(tmp) as z:
            bad = z.testzip()
            if bad:
                raise RuntimeError(f"the download is damaged ({bad}). Try again.")
        status("Unpacking...")
        unpack(tmp, folder, lambda i, n: progress(0.8 + 0.2 * i / max(1, n), f"Unpacking... {i} of {n} files"))
        progress(1.0, "Installed.")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return folder


def open_launcher(folder):
    subprocess.Popen([os.path.join(folder, EXE_NAME)], cwd=folder, close_fds=True)


# ----------------------------------------------------------------------------------------------------- the window
def window():
    import tkinter as tk
    from tkinter import filedialog, ttk

    NAVY, GOLD, TEXT, DIM = "#0f173e", "#e8c463", "#f2ecd8", "#a9b0cc"
    root = tk.Tk()
    root.title("XI: Forever Offline Setup")
    root.configure(bg=NAVY)
    root.resizable(False, False)
    here = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    try:
        root.iconbitmap(os.path.join(here, "icon.ico"))
    except Exception:
        pass
    try:
        from PIL import Image, ImageTk
        img = Image.open(os.path.join(here, "icon.png")).resize((96, 96), Image.LANCZOS)
        root._logo = ImageTk.PhotoImage(img)
        tk.Label(root, image=root._logo, bg=NAVY).pack(pady=(18, 6))
    except Exception:
        pass

    tk.Label(root, text="XI: Forever Offline", font=("Georgia", 18, "bold"), fg=GOLD, bg=NAVY).pack()
    tk.Label(root, text="Your own offline Vana'diel. This puts the game on your PC and opens its launcher.",
             font=("Segoe UI", 10), fg=TEXT, bg=NAVY, wraplength=430).pack(padx=24, pady=(4, 14))

    row = tk.Frame(root, bg=NAVY)
    row.pack(padx=24, fill="x")
    tk.Label(row, text="Install to:", font=("Segoe UI", 10), fg=TEXT, bg=NAVY).pack(side="left")
    folder = tk.StringVar(value=DEFAULT_DIR)
    entry = tk.Entry(row, textvariable=folder, width=34, font=("Segoe UI", 10))
    entry.pack(side="left", padx=6)

    def browse():
        picked = filedialog.askdirectory(initialdir=os.path.dirname(folder.get()) or "C:\\")
        if picked:
            folder.set(os.path.join(os.path.normpath(picked), "XIForeverOffline")
                       if os.path.isdir(picked) and os.listdir(picked) else os.path.normpath(picked))
    tk.Button(row, text="Browse...", command=browse).pack(side="left")

    status = tk.Label(root, text="", font=("Segoe UI", 9), fg=DIM, bg=NAVY, wraplength=430, justify="left")
    status.pack(padx=24, pady=(12, 4), anchor="w")
    bar = ttk.Progressbar(root, length=430, maximum=1000)
    bar.pack(padx=24)
    go = tk.Button(root, text="Install", font=("Segoe UI", 11, "bold"), width=16, bg=GOLD, fg=NAVY, activebackground=GOLD)
    go.pack(pady=18)

    def say(text, color=DIM):
        root.after(0, lambda: status.configure(text=text, fg=color))

    def step(fraction, text=None):
        root.after(0, lambda: (bar.configure(value=int(fraction * 1000)), text and status.configure(text=text, fg=DIM)))

    def finished(path, error=None):
        if error:
            go.configure(state="normal", text="Try again")
            entry.configure(state="normal")
            say("Setup could not finish: " + error + f"\n(Details: {LOG})", "#ff9a8a")
            return
        made = make_shortcuts(path)
        say("Installed in " + path + (". A shortcut is on your desktop." if made else ".") + " Opening the launcher...", GOLD)
        try:
            open_launcher(path)
        except Exception as e:
            say("Installed in " + path + ", but the launcher did not open (" + str(e) + "). Open " + EXE_NAME + " there.", "#ff9a8a")
            return
        root.after(2500, root.destroy)

    def start():
        path = os.path.abspath(folder.get().strip() or DEFAULT_DIR)
        if os.path.isfile(os.path.join(path, EXE_NAME)):
            # already installed: the launcher updates itself, so just make the shortcuts again and open it
            finished(path)
            return
        problem = folder_problem(path)
        if problem:
            say(problem, "#ff9a8a")
            return
        go.configure(state="disabled", text="Installing...")
        entry.configure(state="disabled")

        def work():
            try:
                install(path, say, step)
                root.after(0, lambda: finished(path))
            except Exception as e:
                log(f"install to {path}: {e!r}")
                root.after(0, lambda: finished(path, str(e)))
        threading.Thread(target=work, daemon=True).start()

    go.configure(command=start)
    root.mainloop()


def main(argv):
    if len(argv) >= 3 and argv[1] == "--quiet":
        print(install(argv[2], print, lambda f, t=None: None))
        return 0
    window()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
