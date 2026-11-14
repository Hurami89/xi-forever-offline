"""Give each FFXI character its own XIUI profile.

XIUI saves the active profile when the addon unloads. With both game windows on the
same "Default" profile, whichever window closes last overwrites the other window's
layout. That is why settings can look reset on the next login.

This makes Hurami and Kurami separate profiles, copying the current Default profile
as the starting point. Existing profiles and character files are backed up first.

    python dev/setup_xiui_profiles.py            # set it up
    python dev/setup_xiui_profiles.py --check    # only report what would change
"""
import re
import shutil
import sys
from pathlib import Path

XIUI = Path(r"C:\Ashita-v4beta-main\config\addons\xiui")
BACKUP = Path(r"C:\FFXISOLO\backups\xiui-profiles-2026-10-29")
CHARS = {
    "Hurami_6": "Hurami",
    "Kurami_8": "Kurami",
}
DEFAULT = XIUI / "profiles" / "Default.lua"
PROFILE_LIST = XIUI / "profiles" / "profilelist.lua"


def say(text=""):
    print(text, flush=True)


def backup(path):
    if not path.exists():
        return
    target = BACKUP / path.relative_to(XIUI)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def profile_list_text() -> str:
    names = ["Default"] + list(CHARS.values())
    lines = ["local settings = {};", 'settings["names"] = {};']
    for i, name in enumerate(names, 1):
        lines.append(f'settings["names"][{i}] = "{name}";')
    lines.append('settings["order"] = {};')
    for i, name in enumerate(names, 1):
        lines.append(f'settings["order"][{i}] = "{name}";')
    lines.extend(['settings["version"] = "1.8.4";', "return settings;"])
    return "\n".join(lines) + "\n"


def set_current_profile(path: Path, name: str) -> bool:
    text = path.read_text(encoding="utf-8-sig")
    new, count = re.subn(r'(settings\["currentProfile"\]\s*=\s*)"[^"]*";', rf'\1"{name}";', text, count=1)
    if count == 0:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main(check_only: bool) -> int:
    if not DEFAULT.exists():
        say(f"I could not find {DEFAULT}. Is XIUI installed for Ashita?")
        return 1
    changes = []
    for char_dir, profile in CHARS.items():
        settings = XIUI / char_dir / "settings.lua"
        if not settings.exists():
            say(f"Missing {settings}; skipping {char_dir}.")
            continue
        current = re.search(r'settings\["currentProfile"\]\s*=\s*"([^"]*)"', settings.read_text(encoding="utf-8-sig"))
        if not current or current.group(1) != profile:
            changes.append((char_dir, profile, settings))
        target = XIUI / "profiles" / f"{profile}.lua"
        if not target.exists():
            changes.append((f"create {profile}.lua", profile, target))

    if not changes:
        say("Already set up: Hurami and Kurami each have their own XIUI profile.")
        return 0

    for label, _profile, path in changes:
        say(f"Will set {label}: {path}")

    if check_only:
        return 0

    BACKUP.mkdir(parents=True, exist_ok=True)
    backup(DEFAULT)
    backup(PROFILE_LIST)
    for char_dir in CHARS:
        backup(XIUI / char_dir / "settings.lua")

    for char_dir, profile, settings in changes:
        target = XIUI / "profiles" / f"{profile}.lua"
        if not target.exists():
            shutil.copy2(DEFAULT, target)
            say(f"Created {target.name} from the current Default profile.")
        if settings.parent.name in CHARS and set_current_profile(settings, profile):
            say(f"{settings.parent.name}: currentProfile -> {profile}")

    PROFILE_LIST.write_text(profile_list_text(), encoding="utf-8")
    say(f"Updated {PROFILE_LIST}.")
    say("Restart the game. Hurami and Kurami will now save their own XIUI layouts.")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv[1:]))
