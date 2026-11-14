"""Squad mate personalities for the launcher's Squad tab > Personality page (no GUI code here, so it can be tested).

A personality is the sheet squad chat (squad-chat/squad_chat.py) uses when a mate talks: who they are, how they
sound, what they want. One file per mate: squad-chat/mates/<name>.json. The sheets are each player's own; they are
not part of the kit's repo. A sheet can be written here by hand, started from one of the examples in
squad-chat/examples/, or written by squad chat itself with the local AI (Living world + AI chat).
"""
import json
import os
import re
import shutil

RACES = {1: ("Hume", "male", "he/him"), 2: ("Hume", "female", "she/her"),
         3: ("Elvaan", "male", "he/him"), 4: ("Elvaan", "female", "she/her"),
         5: ("Tarutaru", "male", "he/him"), 6: ("Tarutaru", "female", "she/her"),
         7: ("Mithra", "female", "she/her"), 8: ("Galka", "Galka (conventionally male)", "he/him")}
NATIONS = ["San d'Oria", "Bastok", "Windurst"]
TEXT_FIELDS = ("personality", "voice", "quirk", "goal", "fear", "appearance", "origin")
LIST_FIELDS = ("hooks", "chat_examples")
# What an example gives a mate: everything about who they are, nothing about what they are (name, race, job, level).
EXAMPLE_FIELDS = TEXT_FIELDS + LIST_FIELDS + ("backstory", "talkativeness")
TALK_MIN, TALK_MAX = 0.2, 3.0


def slug(name):
    """The file name squad chat uses for a mate (same rule as squad_chat.slug)."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_") or "mate"


def chat_dir(kit):
    return os.path.join(kit, "squad-chat")


def sheet_path(kit, name):
    return os.path.join(chat_dir(kit), "mates", slug(name) + ".json")


def load_sheet(kit, name):
    """The mate's sheet, or None if squad chat has none for them yet."""
    try:
        with open(sheet_path(kit, name), encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def new_sheet(name, race_id, job, level, nation="San d'Oria"):
    """An empty sheet with the facts the game already knows about the mate."""
    sheet = {"name": name, "slug": slug(name), "backstory": "", "hooks": [], "relationships": {}, "chat_examples": [],
             "talkativeness": 1.0}
    for field in TEXT_FIELDS:
        sheet[field] = ""
    return update_facts(sheet, name, race_id, job, level, nation)


def update_facts(sheet, name, race_id, job, level, nation=None):
    """Name, race, job and level always come from the game (the Look & jobs page), not from the sheet."""
    race_id = int(race_id or 1)
    base, sex, pronouns = RACES.get(race_id, RACES[1])
    sheet.update({"name": name, "slug": slug(name), "race": base, "race_id": race_id, "sex": sex, "pronouns": pronouns,
                  "job": str(job).upper(), "level": int(level or 1)})
    if nation:
        sheet["nation"] = nation
    sheet.setdefault("nation", "San d'Oria")
    return sheet


def clean_text(value, limit=600):
    return " ".join(str(value or "").split())[:limit]


def clean_lines(lines, limit=6, width=200):
    out = []
    for line in lines or []:
        text = clean_text(line, width)
        if text:
            out.append(text)
    return out[:limit]


def clamp_talk(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 1.0
    return round(max(TALK_MIN, min(TALK_MAX, value)), 2)


def problems(sheet):
    """What stops a sheet from being useful; an empty list means it is fine to save."""
    found = []
    if not clean_text(sheet.get("personality")):
        found.append("Write at least a line of personality: squad chat leans on it the most.")
    if len(str(sheet.get("backstory", "")).strip()) > 4000:
        found.append("The backstory is very long (over 4000 characters); squad chat reads all of it every line.")
    return found


def save_sheet(kit, sheet):
    """Writes the sheet for squad chat, keeping the previous one as <name>.json.bak (as squad chat does)."""
    sheet = dict(sheet)
    for field in TEXT_FIELDS:
        sheet[field] = clean_text(sheet.get(field))
    for field in LIST_FIELDS:
        sheet[field] = clean_lines(sheet.get(field))
    sheet["backstory"] = str(sheet.get("backstory", "")).strip()
    sheet["talkativeness"] = clamp_talk(sheet.get("talkativeness", 1.0))
    sheet.pop("_mtime", None)
    path = sheet_path(kit, sheet["name"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        shutil.copy2(path, path[:-5] + ".json.bak")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(sheet, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return sheet


def examples(kit):
    """The example personalities shipped in squad-chat/examples/, as (title, sheet) sorted by title."""
    folder = os.path.join(chat_dir(kit), "examples")
    found = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return found
    for file_name in names:
        if not file_name.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, file_name), encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("title"):
            found.append((str(data["title"]), data))
    return sorted(found, key=lambda item: item[0].lower())


def apply_example(sheet, example):
    """Gives the mate the example's personality; {name} in its text becomes the mate's name."""
    sheet = dict(sheet)
    name = sheet.get("name", "")

    def fill(value):
        return str(value).replace("{name}", name)
    for field in EXAMPLE_FIELDS:
        if field not in example:
            continue
        value = example[field]
        if isinstance(value, list):
            sheet[field] = [fill(item) for item in value]
        elif isinstance(value, str):
            sheet[field] = fill(value)
        else:
            sheet[field] = value
    sheet["relationships"] = {}      # an example knows nobody in this squad
    return sheet


def request_ai_sheet(kit, name, race_id, job, level, nation="San d'Oria"):
    """Asks squad chat to write (or rewrite) the mate's sheet with the local AI. The request waits in
    squad-chat/in.txt until squad chat runs (it starts with the servers when AI chat is on). A rewrite keeps the
    old sheet as <name>.json.bak."""
    folder = chat_dir(kit)
    os.makedirs(folder, exist_ok=True)

    def field(value):
        return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
    if load_sheet(kit, name) is not None:
        line = "LORE\t" + field(name)
    else:
        line = "\t".join(["NEWMATE", field(name), str(int(race_id or 1)), field(job).upper(), str(int(level or 1)), field(nation)])
    with open(os.path.join(folder, "in.txt"), "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    return line


def request_rename(kit, old, new):
    """After the launcher renames a mate: squad chat moves their sheet and memory to the new name (the next time it
    runs, or right away if it is running). Nothing happens if the mate has no sheet."""
    if old == new or load_sheet(kit, old) is None:
        return None
    folder = chat_dir(kit)
    line = "RENAME\t" + str(old).strip() + "\t" + str(new).strip()
    with open(os.path.join(folder, "in.txt"), "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    return line
