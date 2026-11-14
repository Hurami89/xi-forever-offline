"""FFXI Solo Launcher - one window: Play button, server status, squad, rates, graphics, Ashita addon/plugin toggles."""
import ctypes, os, queue, random, subprocess, sys, threading, time, traceback
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import launcher_core as core

try:
    import launcher_squad as sq
except Exception:  # the Squad tab just won't appear
    sq = None

try:
    import launcher_rules as lr
except Exception:  # the rules editor just won't be offered
    lr = None

LOGS = os.path.join(HERE, "logs")
BG, PANEL, PANEL2, FG, DIM = "#0a1118", "#101c28", "#162634", "#e9f1f5", "#8aa0ad"
BORDER, GOLD = "#1d3445", "#e6be64"
GREEN, RED, GREY, ACCENT = "#3ecf6e", "#e5534b", "#44525d", "#35c4e0"
ASSETS = os.path.join(HERE, "assets")
VERSION = "1.1"


GALLERY_W, GALLERY_H, PICTURE_SECONDS = 920, 368, 6
LIST_HINT_MAIN = "Tick what you want loaded in your main game window. Changes apply the next time you press PLAY."
LIST_HINT_SECOND = "Tick what you want loaded in the second window (dualbox). Changes apply the next time you click DUALBOX."


def load_gallery():
    """The pictures shown while the game loads: every png/gif/jpg in assets\\taru. With Pillow installed any picture is fitted to the
    frame; without it only png/gif files that are already 920x368 are used."""
    folder = os.path.join(ASSETS, "taru")
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith((".png", ".gif", ".jpg", ".jpeg")))
    except OSError:
        return []
    try:
        from PIL import Image, ImageTk
    except ImportError:
        Image = ImageTk = None
    pictures = []
    for name in names:
        path = os.path.join(folder, name)
        try:
            if Image is not None:
                img = Image.open(path).convert("RGB")
                scale = max(GALLERY_W / img.width, GALLERY_H / img.height)
                img = img.resize((max(GALLERY_W, round(img.width * scale)), max(GALLERY_H, round(img.height * scale))), Image.LANCZOS)
                left, top = (img.width - GALLERY_W) // 2, (img.height - GALLERY_H) // 2
                pictures.append(ImageTk.PhotoImage(img.crop((left, top, left + GALLERY_W, top + GALLERY_H))))
            elif name.lower().endswith((".png", ".gif")):
                photo = tk.PhotoImage(file=path)
                if photo.width() == GALLERY_W and photo.height() == GALLERY_H:
                    pictures.append(photo)
        except Exception:
            continue
    return pictures


def button_variants(kind):
    """The names of the button pictures in assets\\buttons\\<kind>: every <name>.png, with optional <name>_hover.png and <name>_off.png."""
    folder = os.path.join(ASSETS, "buttons", kind)
    try:
        return sorted(n[:-4] for n in os.listdir(folder) if n.lower().endswith(".png") and not n.lower().endswith(("_hover.png", "_off.png")))
    except OSError:
        return []


def load_button_images(kind, name):
    base = os.path.join(ASSETS, "buttons", kind, name)

    def get(suffix, fallback=None):
        path = base + suffix + ".png"
        if os.path.exists(path):
            try:
                return tk.PhotoImage(file=path)
            except tk.TclError:
                return fallback
        return fallback

    normal = get("")
    return {"normal": normal, "hover": get("_hover", normal), "off": get("_off", normal)}


def choose_button_sets():
    """One random picture for PLAY, STOP and DUALBOX from the folders, so every launch looks different. When there are at least three
    pictures of each, the three buttons show three different ones. A kind with no pictures is left out (the old single picture is used)."""
    names = {kind: button_variants(kind) for kind in ("play", "stop", "dual")}
    present = {kind: values for kind, values in names.items() if values}
    if not present:
        return {}
    shortest = min(len(values) for values in present.values())
    chosen = {}
    if len(present) == 3 and shortest >= 3:
        for kind, index in zip(present, random.sample(range(shortest), 3)):
            chosen[kind] = present[kind][index]
    else:
        for kind, values in present.items():
            chosen[kind] = random.choice(values)
    return {kind: load_button_images(kind, name) for kind, name in chosen.items()}


def load_image(name, shrink=1):
    """A picture from the assets folder, or None if it is missing (the launcher still works without the art)."""
    try:
        img = tk.PhotoImage(file=os.path.join(ASSETS, name))
        return img.subsample(shrink) if shrink > 1 else img
    except Exception:
        return None


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate_and_exit():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', HERE, 1)
    sys.exit(0)


class Cancelled(Exception):
    pass


class CheckList(tk.Frame):
    """Scrollable list of checkboxes. Ticking one adds/removes its load line immediately."""

    def __init__(self, parent, kind, scripts):
        super().__init__(parent, bg=BG)
        self.kind, self.scripts, self.message = kind, scripts, ""
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.reload()

    def use(self, scripts, message=""):
        """Show another window's list (or nothing, with a message saying why)."""
        self.scripts, self.message = scripts, message
        self.reload()

    def reload(self):
        for w in self.inner.winfo_children():
            w.destroy()
        if self.scripts is None:
            tk.Label(self.inner, text=self.message or "Nothing to show.", bg=BG, fg=DIM, wraplength=480, justify="left").pack(anchor="w", padx=8, pady=8)
            return
        ashita = self.scripts.ashita
        names = core.list_addons(ashita) if self.kind == "addon" else core.list_plugins(ashita)
        try:
            on = self.scripts.enabled(self.kind)
        except Exception:
            on = set()
        if not names:
            tk.Label(self.inner, text="Nothing found. Copy addon folders into the addons folder, then press Refresh.",
                     bg=BG, fg=DIM, wraplength=480, justify="left").pack(anchor="w", padx=8, pady=8)
        for n in names:
            var = tk.BooleanVar(value=n.lower() in on)
            tk.Checkbutton(self.inner, text=n, variable=var, command=lambda n=n, v=var: self.toggle(n, v),
                           bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                           anchor="w", font=("Segoe UI", 10)).pack(fill="x", padx=8, pady=1)

    def toggle(self, name, var):
        try:
            self.scripts.set(self.kind, name, var.get())
        except Exception as e:
            messagebox.showerror("Could not save", str(e))


class ItemPicker(tk.Toplevel):
    """Pick one piece of equipment for a slot."""

    def __init__(self, parent, conn, slot, slot_label, job, level, charid, require_unlock, on_pick):
        super().__init__(parent)
        self.conn, self.slot, self.job, self.level = conn, slot, job, level
        self.charid, self.require_unlock, self.on_pick = charid, require_unlock, on_pick
        self.rows = []
        self.title(f"Choose {slot_label} item")
        self.configure(bg=BG)
        self.geometry("440x520")
        self.transient(parent.winfo_toplevel())

        self.search = tk.StringVar()
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(top, text="Search:", bg=BG, fg=FG).pack(side="left")
        entry = tk.Entry(top, textvariable=self.search, bg=PANEL, fg=FG, insertbackground=FG, relief="flat")
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.focus_set()
        self.search.trace_add("write", lambda *a: self.refresh())

        self.only_usable = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Only items this job can wear at this level", variable=self.only_usable, command=self.refresh,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG).pack(anchor="w", padx=10)
        self.show_locked = tk.BooleanVar(value=False)
        if require_unlock:
            tk.Checkbutton(self, text="Show locked items too (not yet given to your squad)", variable=self.show_locked, command=self.refresh,
                           bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG).pack(anchor="w", padx=10)

        self.info = tk.Label(self, text="", bg=BG, fg=DIM, wraplength=400, justify="left")
        self.info.pack(anchor="w", padx=10, pady=4)
        self.listbox = tk.Listbox(self, bg=PANEL, fg=FG, selectbackground=ACCENT, relief="flat", exportselection=False, font=("Segoe UI", 10))
        self.listbox.pack(fill="both", expand=True, padx=10, pady=4)
        self.listbox.bind("<Double-Button-1>", lambda e: self.choose())

        bar = tk.Frame(self, bg=BG)
        bar.pack(pady=8)
        tk.Button(bar, text="Equip", command=self.choose, bg=ACCENT, fg="white", relief="flat", padx=16).pack(side="left", padx=4)
        tk.Button(bar, text="Cancel", command=self.destroy, bg=PANEL, fg=FG, relief="flat", padx=16).pack(side="left", padx=4)
        self.refresh()

    def refresh(self):
        usable = self.only_usable.get()
        locked_only = self.require_unlock and not self.show_locked.get()
        try:
            self.rows = sq.search_items(self.conn, self.slot, self.job if usable else 0, self.level if usable else 0,
                                        self.search.get(), charid=self.charid, require_unlock=locked_only)
        except Exception as e:
            self.rows = []
            self.info.configure(text=f"Search failed: {e}")
            return
        self.listbox.delete(0, "end")
        for _id, name, lv in self.rows:
            self.listbox.insert("end", f"{sq.pretty(name)}   (Lv {lv})")
        if locked_only and not self.rows and not self.search.get():
            self.info.configure(text="No unlocked items for this slot yet. In game, use  !squad give <item>  to add items to your squad's collection.")
        else:
            self.info.configure(text=f"{len(self.rows)} item(s)" + (" (showing the first 300)" if len(self.rows) >= 300 else ""))

    def choose(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.on_pick(self.rows[sel[0]][0])
        self.destroy()


class RuleDialog(tk.Toplevel):
    """Add or change one squad rule. Calls on_ok(rule) with a rule that has passed the checks."""

    def __init__(self, parent, names, rule=None, on_ok=None):
        super().__init__(parent)
        self.title("Rule")
        self.configure(bg=BG)
        self.transient(parent)
        self.resizable(False, False)
        self.names, self.on_ok, self.original = names, on_ok, rule
        rule = rule or {"on": True, "target": "PARTY", "cond": ["ALWAYS", 0], "action": ["family", "CURE"]}
        body = tk.Frame(self, bg=BG)
        body.pack(padx=14, pady=12)
        self.on_var = tk.BooleanVar(value=rule.get("on", True))
        tk.Checkbutton(body, text="This rule is on", variable=self.on_var, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.target_labels = [lr.TARGET_LABELS[t] for t in lr.TARGETS]
        self.target_box = self.combo(body, 1, "For", self.target_labels, readonly=True, width=26)
        self.target_box.set(lr.TARGET_LABELS.get(rule.get("target"), lr.TARGET_LABELS["PARTY"]))
        self.cond1 = self.condition(body, 2, "When", rule.get("cond"), False)
        self.cond2 = self.condition(body, 3, "And", rule.get("cond2"), True)
        self.kind_box = self.combo(body, 4, "Do", list(lr.ACTIONS), readonly=True, width=26)
        self.kind_box.set(rule["action"][0] if rule.get("action") else "family")
        self.kind_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_action())
        self.kind_text = tk.Label(body, text="", bg=BG, fg=DIM)
        self.kind_text.grid(row=4, column=2, sticky="w", padx=6)
        self.name_box = self.combo(body, 5, "Name", [], readonly=False, width=26)
        if rule.get("action") and len(rule["action"]) == 2:
            self.name_box.set(rule["action"][1])
        self.refresh_action()
        tk.Label(body, text="Retry (seconds)", bg=BG, fg=FG).grid(row=6, column=0, sticky="w", pady=3)
        self.retry_var = tk.StringVar(value=str(rule.get("retry", "")))
        tk.Entry(body, textvariable=self.retry_var, width=8, bg=PANEL, fg=FG, insertbackground=FG, relief="flat").grid(row=6, column=1, sticky="w")
        tk.Label(body, text="the least time before it may repeat on the same enemy", bg=BG, fg=DIM).grid(row=6, column=2, sticky="w", padx=6)
        tk.Label(body, text="Least level", bg=BG, fg=FG).grid(row=7, column=0, sticky="w", pady=3)
        self.level_var = tk.StringVar(value=str(rule.get("level", "")))
        tk.Entry(body, textvariable=self.level_var, width=8, bg=PANEL, fg=FG, insertbackground=FG, relief="flat").grid(row=7, column=1, sticky="w")
        tk.Label(body, text="job abilities only: the level the mate needs for it", bg=BG, fg=DIM).grid(row=7, column=2, sticky="w", padx=6)
        bar = tk.Frame(self, bg=BG)
        bar.pack(pady=(0, 12))
        tk.Button(bar, text="OK", command=self.ok, bg=ACCENT, fg="white", relief="flat", padx=18).pack(side="left", padx=4)
        tk.Button(bar, text="Cancel", command=self.destroy, bg=PANEL, fg=FG, relief="flat", padx=14).pack(side="left", padx=4)

    def combo(self, parent, row, label, values, readonly, width):
        tk.Label(parent, text=label, bg=BG, fg=FG).grid(row=row, column=0, sticky="w", pady=3)
        box = ttk.Combobox(parent, values=values, state="readonly" if readonly else "normal", width=width)
        box.grid(row=row, column=1, sticky="w")
        return box

    def condition(self, parent, row, label, cond, allow_none):
        names = (["(none)"] if allow_none else []) + list(lr.CONDITIONS)
        name_box = self.combo(parent, row, label, names, readonly=True, width=26)
        arg_box = ttk.Combobox(parent, values=[], width=20)
        arg_box.grid(row=row, column=2, sticky="w", padx=6)
        name, text = lr.condition_to_fields(cond) if cond else ("(none)" if allow_none else "ALWAYS", "")
        name_box.set(name)
        parts = {"name": name_box, "arg": arg_box}
        name_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_condition(parts))
        self.refresh_condition(parts, text)
        return parts

    def refresh_condition(self, parts, text=None):
        name = parts["name"].get()
        kind = lr.CONDITIONS.get(name, (None, None))[1]
        parts["arg"].configure(values=self.names.get(kind, []) if kind in ("effect", "flag", "ecosystem") else [],
                               state="normal" if kind else "disabled")
        parts["arg"].set(text if (text is not None and kind) else "")

    def refresh_action(self):
        kind = self.kind_box.get()
        self.kind_text.configure(text=lr.ACTIONS.get(kind, ""))
        named = kind in ("family", "spell", "ja")
        self.name_box.configure(values=self.names.get(kind, []) if named else [], state="normal" if named else "disabled")
        if not named:
            self.name_box.set("")

    def ok(self):
        label = self.target_box.get()
        target = lr.TARGETS[self.target_labels.index(label)] if label in self.target_labels else None
        fields = {"cond": (self.cond1["name"].get(), self.cond1["arg"].get()), "cond2": (self.cond2["name"].get(), self.cond2["arg"].get())}
        rule, problems = lr.build_rule(self.on_var.get(), target, fields["cond"][0], fields["cond"][1], fields["cond2"][0], fields["cond2"][1],
                                       self.kind_box.get(), self.name_box.get(), self.retry_var.get(), self.level_var.get())
        if problems:
            messagebox.showerror("Rule", "\n".join(problems), parent=self)
            return
        rule = lr.keep_original_conditions(self.original, rule, fields)
        self.destroy()
        if self.on_ok:
            self.on_ok(rule)


class RulesEditor(tk.Toplevel):
    """Edit what each job does: the rules a squad mate follows, starting from the built-in ones. Saved to squad_rules_user.json, and written
    for the server as modules/custom/lua/squad_rules_data.lua (read when the servers start)."""

    COLUMNS = (("on", "On", 42), ("target", "For", 130), ("when", "When", 230), ("and", "And", 170), ("do", "Do", 190), ("retry", "Retry s", 56), ("level", "Level", 48))

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.title("Squad job rules")
        self.configure(bg=BG)
        self.geometry("1000x600")
        self.transient(parent)
        defaults = lr.load_json(os.path.join(HERE, "squad-data", "squad_rules_default.json"))
        if not defaults:
            messagebox.showerror("Squad job rules", "I could not find squad-data\\squad_rules_default.json.\n\nInstall the squad behavior update first.")
            self.after(0, self.destroy)
            return
        self.names = lr.known_names(defaults)
        user_path = os.path.join(HERE, "squad-data", "squad_rules_user.json")
        lua_path = os.path.join(cfg["server_dir"], "modules", "custom", "lua", "squad_rules_data.lua")
        self.state = lr.EditorState(lr.RuleSet(defaults, lr.load_json(user_path)), user_path, lua_path)
        self.build()
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def build(self):
        style = ttk.Style(self)
        style.configure("Rules.Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=24, borderwidth=0)
        style.map("Rules.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        style.configure("Rules.Treeview.Heading", background=PANEL2, foreground=FG, relief="flat")
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(top, text="Job", bg=BG, fg=FG).pack(side="left")
        self.job_box = ttk.Combobox(top, values=lr.JOB_ORDER, state="readonly", width=6)
        self.job_box.set(self.state.job)
        self.job_box.pack(side="left", padx=6)
        self.job_box.bind("<<ComboboxSelected>>", lambda e: self.pick())
        self.part_var = tk.StringVar(value=self.state.part)
        for part in lr.PARTS:
            tk.Radiobutton(top, text=lr.PART_LABELS[part], value=part, variable=self.part_var, command=self.pick, bg=BG, fg=FG, selectcolor=PANEL,
                           activebackground=BG, activeforeground=FG).pack(side="left", padx=(8, 0))
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_check = tk.Checkbutton(top, text="Use my rules for this job", variable=self.enabled_var, command=self.toggle_enabled, bg=BG, fg=FG,
                                            selectcolor=PANEL, activebackground=BG, activeforeground=FG)
        self.enabled_check.pack(side="left", padx=(20, 0))
        self.status = tk.Label(self, text="", bg=BG, fg=DIM, anchor="w")
        self.status.pack(fill="x", padx=14)

        middle = tk.Frame(self, bg=BG)
        middle.pack(fill="both", expand=True, padx=12, pady=6)
        self.tree = ttk.Treeview(middle, columns=[c[0] for c in self.COLUMNS], show="headings", style="Rules.Treeview", selectmode="browse")
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w", stretch=key in ("when", "do"))
        scroll = ttk.Scrollbar(middle, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit_rule())

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=12, pady=4)
        for text, command in (("Add rule", self.add_rule), ("Edit", self.edit_rule), ("Delete", self.delete_rule), ("Move up", lambda: self.move(-1)),
                              ("Move down", lambda: self.move(1)), ("Turn on / off", self.toggle_rule)):
            tk.Button(bar, text=text, command=command, bg=PANEL, fg=FG, relief="flat", padx=10, pady=3).pack(side="left", padx=(0, 6))
        tk.Button(bar, text="Reset this list", command=self.reset_list, bg=PANEL, fg=FG, relief="flat", padx=10, pady=3).pack(side="right", padx=(6, 0))
        tk.Button(bar, text="Reset this job", command=self.reset_job, bg=PANEL, fg=FG, relief="flat", padx=10, pady=3).pack(side="right")

        tk.Label(self, text=("Rules are read top to bottom. A role or mode (Behavior page) still applies on top of them. How a mate stands and moves is not part of "
                             "the rules. Names the server does not know are skipped and logged, so a typo never stops a mate from appearing."),
                 bg=BG, fg=DIM, wraplength=950, justify="left").pack(anchor="w", padx=14, pady=(2, 0))
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=12, pady=8)
        tk.Button(bottom, text="Save", command=self.save, bg=ACCENT, fg="white", relief="flat", padx=22, pady=4).pack(side="left")
        tk.Button(bottom, text="Close", command=self.close, bg=PANEL, fg=FG, relief="flat", padx=16, pady=4).pack(side="left", padx=8)
        self.msg = tk.Label(bottom, text="", bg=BG, fg=DIM, wraplength=760, justify="left")
        self.msg.pack(side="left", padx=10)

    def say(self, text):
        self.msg.configure(text=text)

    def pick(self):
        self.state.pick(self.job_box.get(), self.part_var.get())
        self.refresh()

    def refresh(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self.state.rows()):
            self.tree.insert("", "end", iid=str(i), values=[row[key] for key, _title, _w in self.COLUMNS])
        job = self.state.job
        self.enabled_var.set(self.state.rs.enabled(job))
        self.enabled_check.configure(state="normal" if self.state.rs.is_custom(job) else "disabled")
        self.status.configure(text=f"{job} - {lr.PART_LABELS[self.state.part]}: {self.state.status()}")
        if select is not None and 0 <= select < len(self.state.rules):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))

    def selected(self):
        chosen = self.tree.selection()
        return int(chosen[0]) if chosen else None

    def need_selection(self):
        index = self.selected()
        if index is None:
            self.say("Pick a rule in the list first.")
        return index

    def add_rule(self):
        index = self.selected()
        at = None if index is None else index + 1
        RuleDialog(self, self.names, None, lambda rule: (self.state.add(rule, at), self.refresh(select=len(self.state.rules) - 1 if at is None else at)))

    def edit_rule(self):
        index = self.need_selection()
        if index is not None:
            RuleDialog(self, self.names, self.state.rules[index], lambda rule: (self.state.update(index, rule), self.refresh(select=index)))

    def delete_rule(self):
        index = self.need_selection()
        if index is not None and messagebox.askyesno("Delete rule", "Delete this rule?", parent=self):
            self.state.delete(index)
            self.refresh(select=min(index, len(self.state.rules) - 1))

    def move(self, delta):
        index = self.need_selection()
        if index is not None:
            self.refresh(select=self.state.move(index, delta))

    def toggle_rule(self):
        index = self.need_selection()
        if index is not None:
            self.state.toggle(index)
            self.refresh(select=index)

    def toggle_enabled(self):
        self.state.set_enabled(bool(self.enabled_var.get()))
        self.refresh()

    def reset_list(self):
        if messagebox.askyesno("Reset", "Put this list back to the built-in rules?", parent=self):
            self.state.reset_list()
            self.refresh()

    def reset_job(self):
        if messagebox.askyesno("Reset", f"Put every list of {self.state.job} back to the built-in rules?", parent=self):
            self.state.reset_job()
            self.refresh()

    def save(self):
        try:
            self.say(self.state.save())
        except ValueError as problem:
            messagebox.showerror("Squad job rules", str(problem), parent=self)
        except OSError as problem:
            messagebox.showerror("Squad job rules", f"Could not write the files: {problem}", parent=self)

    def close(self):
        if self.state.dirty:
            answer = messagebox.askyesnocancel("Squad job rules", "Save your changes before closing?", parent=self)
            if answer is None:
                return
            if answer:
                self.save()
                if self.state.dirty:
                    return
        self.destroy()


class SquadTab(tk.Frame):
    """Create squad mates, set their look, jobs, job levels and gear. Changes are saved to the database right away
    and apply the next time a mate is called in game."""

    def __init__(self, parent, cfg):
        super().__init__(parent, bg=BG)
        self.cfg = cfg
        self.conn = None
        self.chars, self.mates, self.mate = [], [], None
        self.require_unlock = bool(cfg.get("squad_require_unlock", True))
        self.level_vars, self.gear_vars, self.level_spins = {}, {}, {}
        self.unlocked, self.choices = set(), []
        self.is_running = lambda: False          # the launcher sets this: True while the servers are up
        self.build()
        self.after(300, self.load_characters)

    # ----- layout -----
    def build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(top, text="Character:", bg=BG, fg=FG).pack(side="left")
        self.char_var = tk.StringVar()
        self.char_box = ttk.Combobox(top, textvariable=self.char_var, state="readonly", width=22)
        self.char_box.pack(side="left", padx=6)
        self.char_box.bind("<<ComboboxSelected>>", lambda e: self.load_squad())
        tk.Button(top, text="Refresh", command=self.load_characters, bg=PANEL, fg=FG, relief="flat", padx=8).pack(side="left")
        self.msg = tk.Label(self, text="", bg=BG, fg=DIM, wraplength=520, justify="left")
        self.msg.pack(anchor="w", padx=10)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="y")
        self.listbox = tk.Listbox(left, height=8, width=26, bg=PANEL, fg=FG, selectbackground=ACCENT, relief="flat",
                                  exportselection=False, font=("Segoe UI", 10))
        self.listbox.pack()
        self.listbox.bind("<<ListboxSelect>>", lambda e: self.on_select())
        bar = tk.Frame(left, bg=BG)
        bar.pack(pady=6)
        tk.Button(bar, text="New", command=self.new_mate, bg=ACCENT, fg="white", relief="flat", padx=12).pack(side="left", padx=3)
        tk.Button(bar, text="Delete", command=self.delete_mate, bg=PANEL, fg=FG, relief="flat", padx=12).pack(side="left", padx=3)

        pages = ttk.Notebook(body)
        pages.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.build_look_page(pages)
        self.build_levels_page(pages)
        self.build_gear_page(pages)
        self.build_behavior_page(pages)

    def row(self, parent, label):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=10, pady=3)
        tk.Label(f, text=label, bg=BG, fg=FG, width=11, anchor="w").pack(side="left")
        return f

    def build_look_page(self, pages):
        page = tk.Frame(pages, bg=BG)
        pages.add(page, text=" Look & jobs ")
        self.name_var = tk.StringVar()
        f = self.row(page, "Name")
        tk.Entry(f, textvariable=self.name_var, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", width=18).pack(side="left")
        tk.Button(f, text="Rename", command=self.apply_name, bg=PANEL, fg=FG, relief="flat", padx=8).pack(side="left", padx=6)

        f = self.row(page, "Race")
        self.race_box = ttk.Combobox(f, values=sq.RACES, state="readonly", width=18)
        self.race_box.pack(side="left")
        f = self.row(page, "Face")
        self.face_box = ttk.Combobox(f, values=[str(i) for i in range(1, 17)], state="readonly", width=6)
        self.face_box.pack(side="left")
        tk.Button(f, text="Apply look", command=self.apply_look, bg=PANEL, fg=FG, relief="flat", padx=8).pack(side="left", padx=6)

        f = self.row(page, "Main job")
        self.mjob_box = ttk.Combobox(f, values=sq.JOBS, state="readonly", width=8)
        self.mjob_box.pack(side="left")
        f = self.row(page, "Sub job")
        self.sjob_box = ttk.Combobox(f, values=["None"] + sq.JOBS, state="readonly", width=8)
        self.sjob_box.pack(side="left")
        tk.Button(f, text="Apply jobs", command=self.apply_jobs, bg=PANEL, fg=FG, relief="flat", padx=8).pack(side="left", padx=6)

        self.summary = tk.Label(page, text="", bg=BG, fg=FG, justify="left", wraplength=360)
        self.summary.pack(anchor="w", padx=10, pady=10)
        tk.Label(page, text="Sub jobs unlock at main level 18. The sub level is half the main level, but never higher\n"
                            "than the sub job's own level. Changes apply next time you call the mate in game.",
                 bg=BG, fg=DIM, justify="left", wraplength=360).pack(anchor="w", padx=10)

    def build_levels_page(self, pages):
        page = tk.Frame(pages, bg=BG)
        pages.add(page, text=" Job levels ")
        grid = tk.Frame(page, bg=BG)
        grid.pack(padx=10, pady=8, anchor="w")
        for i, job in enumerate(sq.JOBS):
            col, r = (i // 8) * 3, i % 8
            tk.Label(grid, text=job, bg=BG, fg=FG, width=5, anchor="w").grid(row=r, column=col, pady=2)
            var = tk.IntVar(value=1)
            self.level_vars[i + 1] = var
            spin = tk.Spinbox(grid, from_=1, to=sq.MAX_LEVEL, width=4, textvariable=var, bg=PANEL, fg=FG, relief="flat")
            spin.grid(row=r, column=col + 1, padx=4)
            self.level_spins[i + 1] = spin
            exp = tk.Label(grid, text="", bg=BG, fg=DIM, width=10, anchor="w")
            exp.grid(row=r, column=col + 2)
            self.level_vars[("exp", i + 1)] = exp
        tk.Button(page, text="Save levels", command=self.apply_levels, bg=ACCENT, fg="white", relief="flat", padx=14).pack(pady=8)
        tk.Label(page, text="Each job levels on its own in game. Exp is shown next to each level.",
                 bg=BG, fg=DIM).pack(anchor="w", padx=10)

    def build_gear_page(self, pages):
        page = tk.Frame(pages, bg=BG)
        pages.add(page, text=" Gear ")
        self.gear_title = tk.Label(page, text="", bg=BG, fg=FG, font=("Segoe UI", 10, "bold"))
        self.gear_title.pack(anchor="w", padx=10, pady=(8, 2))
        grid = tk.Frame(page, bg=BG)
        grid.pack(padx=10, anchor="w")
        for r, (slot, label) in enumerate(sq.EQUIP_SLOTS):
            tk.Label(grid, text=label, bg=BG, fg=DIM, width=7, anchor="w").grid(row=r, column=0, pady=1)
            var = tk.StringVar(value="-")
            self.gear_vars[slot] = var
            tk.Label(grid, textvariable=var, bg=BG, fg=FG, width=26, anchor="w").grid(row=r, column=1)
            tk.Button(grid, text="Change", command=lambda s=slot, l=label: self.pick_item(s, l), bg=PANEL, fg=FG, relief="flat", padx=6).grid(row=r, column=2, padx=2)
            tk.Button(grid, text="Clear", command=lambda s=slot: self.clear_item(s), bg=PANEL, fg=FG, relief="flat", padx=6).grid(row=r, column=3)
        tk.Label(page, text="Gear is saved per job. Items must fit the slot, the job and the mate's level.",
                 bg=BG, fg=DIM).pack(anchor="w", padx=10, pady=4)

    # ----- data -----
    def build_behavior_page(self, pages):
        page = tk.Frame(pages, bg=BG)
        pages.add(page, text=" Behavior ")
        self.beh_title = tk.Label(page, text="", bg=BG, fg=FG, font=("Segoe UI", 10, "bold"))
        self.beh_title.pack(anchor="w", padx=10, pady=(10, 4))
        f = self.row(page, "Role")
        self.role_box = ttk.Combobox(f, values=sq.ROLES, state="readonly", width=12)
        self.role_box.pack(side="left")
        f = self.row(page, "Mode")
        self.mode_box = ttk.Combobox(f, values=sq.MODES, state="readonly", width=12)
        self.mode_box.pack(side="left")
        tk.Button(f, text="Apply", command=self.apply_behavior, bg=PANEL, fg=FG, relief="flat", padx=14).pack(side="left", padx=10)
        tk.Label(page, text=("tank: Provoke, Flash, own buffs; heals only the badly hurt.\n"
                             "damage: attacks and nukes; heals only the badly hurt.\n"
                             "healer: cures, status removal and party buffs; no nukes.\n"
                             "support: buffs, weakening spells and cures; no nukes.\n"
                             "auto: what the job normally does.\n\n"
                             "aggressive: heals earlier and holds nothing back.\n"
                             "conserve: heals later and keeps 40% mana in reserve."),
                 bg=BG, fg=DIM, justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        tk.Label(page, text="Applies the next time you call the mate. Change it with the game closed here, or in the game (the Squad panel, /sq).",
                 bg=BG, fg=DIM, wraplength=470, justify="left").pack(anchor="w", padx=10)
        tk.Button(page, text="Edit job rules...", command=self.open_rules, bg=ACCENT, fg="white", relief="flat", padx=14, pady=4).pack(anchor="w", padx=10, pady=12)

    def show_behavior(self):
        m = self.mate
        if m is None or lr is None:
            return
        try:
            role, mode = sq.get_behavior(self.conn, self.charid(), m["id"])
        except Exception as problem:
            self.beh_title.configure(text=f"{m['name']}: role and mode (could not be read: {problem})")
            return
        self.role_box.set(role)
        self.mode_box.set(mode)
        self.beh_title.configure(text=f"{m['name']}: role and mode")

    def apply_behavior(self):
        def go():
            m = self.mate
            if m is None:
                return
            if self.is_running():
                messagebox.showinfo("Squad", "The servers are running, and they keep a character's variables in memory, so a change made here "
                                             "could be lost.\n\nClose the game first, or use the Squad panel in the game (/sq).")
                return
            sq.set_behavior(self.conn, self.charid(), m["id"], self.role_box.get(), self.mode_box.get())
            self.say(f"Saved: {m['name']} is now {self.role_box.get()} / {self.mode_box.get()}. It applies the next time you call them.")
        self.guard(go)

    def open_rules(self):
        if lr is None:
            messagebox.showerror("Squad", "The rules editor (launcher_rules.py) is missing. Unpack the squad behavior update again.")
            return
        RulesEditor(self, self.cfg)

    def say(self, text):
        self.msg.configure(text=text)

    def guard(self, fn):
        """Run a database action; show a message instead of crashing on errors."""
        try:
            return fn()
        except Exception as e:
            self.say(f"Error: {e}")
            messagebox.showerror("Squad", str(e))
            return None

    def load_characters(self):
        def go():
            if self.conn is None:
                self.conn = sq.connect(self.cfg)
            self.chars = sq.list_characters(self.conn)
            self.char_box.configure(values=[f"{n} (#{i})" for i, n in self.chars])
            if self.chars:
                if self.char_box.current() < 0:
                    self.char_box.current(0)
                self.load_squad()
            else:
                self.say("No characters found. Log in to the game once to create one.")
        self.guard(go)

    def charid(self):
        i = self.char_box.current()
        return self.chars[i][0] if 0 <= i < len(self.chars) else None

    def load_squad(self, select_id=None):
        def go():
            charid = self.charid()
            if charid is None:
                return
            self.mates = sq.get_squad(self.conn, charid)
            self.unlocked = sq.unlocked_jobs(self.conn, charid)
            self.listbox.delete(0, "end")
            for m in self.mates:
                self.listbox.insert("end", sq.describe(m))
            index = 0
            for i, m in enumerate(self.mates):
                if m["id"] == select_id:
                    index = i
            if self.mates:
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(index)
                self.on_select()
            else:
                self.mate = None
                self.say("No squad mates yet. Press New to create one.")
        self.guard(go)

    def on_select(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self.mates):
            return
        self.mate = self.mates[sel[0]]
        m = self.mate
        self.name_var.set(m["name"])
        self.race_box.current((m["race"] or 1) - 1)  # a mate with no race chosen is a Hume male
        self.face_box.current(min(m["face"], 15))
        # Only offer jobs this character has unlocked (plus whatever the mate already has set)
        self.choices = sorted((self.unlocked | {m["mjob"], m["sjob"]}) - {0})
        names = [sq.JOBS[j - 1] for j in self.choices]
        self.mjob_box.configure(values=names)
        self.sjob_box.configure(values=["None"] + names)
        self.mjob_box.current(self.choices.index(m["mjob"]))
        self.sjob_box.current(0 if m["sjob"] == 0 else self.choices.index(m["sjob"]) + 1)
        main, sub, sub_level = sq.effective_levels(m)
        text = f"{sq.JOBS[m['mjob'] - 1]} {main}"
        if sub:
            text += f"  /  {sq.JOBS[sub - 1]} {sub_level}"
        self.summary.configure(text=text)
        for job in range(1, 16):
            level, exp = m["jobs"].get(job, (1, 0))
            locked = job not in self.unlocked and job not in m["jobs"]
            self.level_vars[job].set(level)
            self.level_spins[job].configure(state="disabled" if locked else "normal")
            self.level_vars[("exp", job)].configure(text="locked" if locked else (f"{exp} exp" if exp else ""))
        self.refresh_gear()
        self.show_behavior()
        self.say(f"Editing {m['name']}. Changes apply the next time you call them in game.")

    def refresh_gear(self):
        m = self.mate
        job = m["mjob"]
        self.gear_title.configure(text=f"{m['name']} - gear for {sq.JOBS[job - 1]}")
        worn = m["equip"].get(job, {})
        for slot, var in self.gear_vars.items():
            item = worn.get(slot)
            var.set(sq.pretty(item[1]) if item and item[1] else (f"item #{item[0]}" if item else "-"))

    def reload(self):
        self.load_squad(self.mate["id"] if self.mate else None)

    # ----- actions -----
    def new_mate(self):
        def go():
            charid = self.charid()
            if charid is None:
                raise ValueError("Pick a character first.")
            name = simpledialog.askstring("New squad mate", "Name (3-15 letters):", parent=self)
            if name is None:
                return
            if not (name.isalpha() and 3 <= len(name) <= 15):
                raise ValueError("The name must be 3-15 letters, no spaces or numbers.")
            new_id = sq.create_mate(self.conn, charid, name, 1, 1)
            self.load_squad(new_id)
            self.say(f"Created {name} as a level 1 WAR. Change the job, levels and gear on the right.")
        self.guard(go)

    def delete_mate(self):
        if self.mate is None:
            return
        if not messagebox.askyesno("Delete", f"Delete {self.mate['name']} and all of their levels and gear?"):
            return
        self.guard(lambda: (sq.delete_mate(self.conn, self.mate["id"]), self.load_squad()))

    def apply_name(self):
        def go():
            name = self.name_var.get().strip()
            if not (name.isalpha() and 3 <= len(name) <= 15):
                raise ValueError("The name must be 3-15 letters, no spaces or numbers.")
            sq.rename_mate(self.conn, self.mate["id"], name)
            self.reload()
        if self.mate:
            self.guard(go)

    def apply_look(self):
        if self.mate:
            self.guard(lambda: (sq.set_look(self.conn, self.mate["id"], self.race_box.current() + 1, self.face_box.current()), self.reload()))

    def apply_jobs(self):
        if self.mate:
            si = self.sjob_box.current()
            mjob = self.choices[self.mjob_box.current()]
            sjob = 0 if si <= 0 else self.choices[si - 1]
            self.guard(lambda: (sq.set_jobs(self.conn, self.charid(), self.mate["id"], mjob, sjob), self.reload()))

    def apply_levels(self):
        def go():
            for job in range(1, 16):
                if job not in self.unlocked and job not in self.mate["jobs"]:
                    continue
                level = int(self.level_vars[job].get())
                old = self.mate["jobs"].get(job, (1, 0))
                if level != old[0]:
                    sq.set_job_level(self.conn, self.mate["id"], job, level, 0)
            self.reload()
        if self.mate:
            self.guard(go)

    def pick_item(self, slot, label):
        if self.mate is None:
            return
        m = self.mate
        main, _sub, _sl = sq.effective_levels(m)

        def chosen(item_id):
            self.guard(lambda: (sq.set_equip(self.conn, m["id"], m["mjob"], slot, item_id), self.reload()))

        ItemPicker(self, self.conn, slot, label, m["mjob"], main, self.charid(), self.require_unlock, chosen)

    def clear_item(self, slot):
        if self.mate:
            self.guard(lambda: (sq.set_equip(self.conn, self.mate["id"], self.mate["mjob"], slot, 0), self.reload()))


class ImageButton(tk.Canvas):
    """A button drawn from pictures: normal, hover and off. Falls back to plain text if the pictures are missing."""

    def __init__(self, parent, images, command, fallback_text):
        normal = images.get("normal")
        width, height = (normal.width(), normal.height()) if normal else (200, 48)
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2")
        self.imgs, self.command, self.state, self.hover, self.fallback_text = images, command, "normal", False, fallback_text
        if normal:
            self.item = self.create_image(0, 0, anchor="nw", image=normal)
        else:
            self.item = self.create_text(width // 2, height // 2, text=fallback_text, fill=FG, font=("Segoe UI", 12, "bold"))
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    def _set_hover(self, value):
        self.hover = value
        self._show()

    def _show(self):
        key = "off" if self.state == "disabled" else ("hover" if self.hover else "normal")
        img = self.imgs.get(key) or self.imgs.get("normal")
        if img:
            self.itemconfigure(self.item, image=img)
        else:
            self.itemconfigure(self.item, fill=DIM if self.state == "disabled" else (ACCENT if self.hover else FG))
        tk.Canvas.configure(self, cursor="arrow" if self.state == "disabled" else "hand2")

    def _click(self, _event):
        if self.state != "disabled" and self.command:
            self.command()

    def configure(self, cnf=None, **kw):
        if "state" in kw:
            self.state = kw.pop("state")
            self._show()
        if cnf or kw:
            return tk.Canvas.configure(self, cnf, **kw)

    config = configure


class RatesTab(tk.Frame):
    """Experience, drop, gil and skill-up rates, the level cap and a few switches. Read when PLAY is pressed."""

    def __init__(self, parent, rates):
        super().__init__(parent, bg=BG)
        self.vars, self.rates = {}, rates
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(top, text="Preset:", bg=BG, fg=FG).pack(side="left")
        self.preset = ttk.Combobox(top, values=list(core.RATE_PRESETS), state="readonly", width=22)
        self.preset.pack(side="left", padx=6)
        tk.Button(top, text="Fill in preset", command=self.fill_preset, bg=PANEL, fg=FG, relief="flat", padx=8).pack(side="left")
        tk.Label(self, text="Changes apply the next time you press PLAY. 1 = normal game speed.", bg=BG, fg=DIM,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10)

        box = tk.Frame(self, bg=BG)
        box.pack(fill="both", expand=True, padx=6, pady=4)
        canvas = tk.Canvas(box, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        for i, field in enumerate(core.RATE_FIELDS):
            tk.Label(inner, text=field[3], bg=BG, fg=FG, anchor="w", width=38).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            var = tk.StringVar(value=str(rates.get(field[0], field[4])))
            ttk.Spinbox(inner, from_=field[5], to=field[6], increment=1 if field[7] == "int" else 0.25,
                        textvariable=var, width=8).grid(row=i, column=1, padx=6, pady=2)
            self.vars[field[0]] = var
        n = len(core.RATE_FIELDS)
        self.all_crafts = tk.BooleanVar(value=rates.get("all_crafts", True))
        tk.Checkbutton(inner, text="Every craft can reach 100 (off = only one, like the retail rule)", variable=self.all_crafts, bg=BG, fg=FG,
                       selectcolor=PANEL, activebackground=BG, activeforeground=FG).grid(row=n, column=0, columnspan=2, sticky="w", padx=6, pady=(10, 2))
        self.ah_sim = tk.BooleanVar(value=rates.get("ah_sim", False))
        tk.Checkbutton(inner, text="Auction house simulator (stocks the auction house, buys what you list)", variable=self.ah_sim, bg=BG, fg=FG,
                       selectcolor=PANEL, activebackground=BG, activeforeground=FG).grid(row=n + 1, column=0, columnspan=2, sticky="w", padx=6, pady=2)
        self.era_exp = tk.BooleanVar(value=rates.get("era_exp", False))
        tk.Checkbutton(inner, text="Aht Urhgan-era experience tables (kill exp and per-monster cap). Keep 'Experience from monsters' at 1.0 with this on.",
                       variable=self.era_exp, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       wraplength=520, justify="left").grid(row=n + 2, column=0, columnspan=2, sticky="w", padx=6, pady=2)
        self.conquest_sim = tk.BooleanVar(value=rates.get("conquest_sim", False))
        tk.Checkbutton(inner, text="Conquest simulator: the other nations and the beastmen act while you are away, so regions can change hands",
                       variable=self.conquest_sim, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       wraplength=520, justify="left").grid(row=n + 3, column=0, columnspan=2, sticky="w", padx=6, pady=2)
        self.claim_shield = tk.BooleanVar(value=rates.get("claim_shield", False))
        tk.Checkbutton(inner, text="NM claim shield: a short no-claim window after some NMs spawn. Only matters with other players, so leave it off for solo.",
                       variable=self.claim_shield, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       wraplength=520, justify="left").grid(row=n + 4, column=0, columnspan=2, sticky="w", padx=6, pady=2)

    def fill_preset(self):
        name = self.preset.get()
        if not name:
            return
        values = core.apply_preset(self.collect(), name)
        for fid, var in self.vars.items():
            var.set(str(values.get(fid)))
        self.era_exp.set(bool(values.get("era_exp", False)))

    def collect(self):
        rates = dict(core.RATE_DEFAULTS)
        for field in core.RATE_FIELDS:
            rates[field[0]] = core.clean_rate(field, self.vars[field[0]].get())
        rates["all_crafts"] = bool(self.all_crafts.get())
        rates["ah_sim"] = bool(self.ah_sim.get())
        rates["era_exp"] = bool(self.era_exp.get())
        rates["conquest_sim"] = bool(self.conquest_sim.get())
        rates["claim_shield"] = bool(self.claim_shield.get())
        return rates


class GraphicsTab(tk.Frame):
    """Display settings, written into the Ashita boot file's [ffxi.registry] section when PLAY is pressed."""

    def __init__(self, parent, values, ini_path):
        super().__init__(parent, bg=BG)
        self.ini_path = ini_path
        self.v = {gid: tk.StringVar(value=str(values[gid])) for gid in core.GRAPHICS_KEYS}
        self.window = tk.StringVar(value=core.WINDOW_MODES[values["window_mode"]])
        self.textures = tk.StringVar(value=core.TEXTURE_LEVELS[values["textures"]])
        self.fonts = tk.StringVar(value=core.FONT_LEVELS[values["fonts"]])
        self.bump = tk.BooleanVar(value=bool(values["bump"]))
        self.stab = tk.BooleanVar(value=bool(values["stab"]))
        self.bg_sound = tk.BooleanVar(value=bool(values["bg_sound"]))
        self.warning = tk.StringVar(value="")

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 2))
        tk.Label(top, text="Preset:", bg=BG, fg=FG).pack(side="left")
        self.preset = ttk.Combobox(top, values=list(core.GRAPHICS_PRESETS), state="readonly", width=24)
        self.preset.pack(side="left", padx=6)
        tk.Button(top, text="Fill in preset", command=self.fill_preset, bg=PANEL, fg=FG, relief="flat", padx=8).pack(side="left")
        tk.Label(self, text="Applied when you press PLAY. Presets only change quality, not your screen size.", bg=BG, fg=DIM,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10)

        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="x", padx=10, pady=6)
        row = 0

        def label(text, r):
            tk.Label(grid, text=text, bg=BG, fg=FG, anchor="w", width=26).grid(row=r, column=0, sticky="w", pady=3)

        def pair(text, kw, kh, r):
            label(text, r)
            for col, k in ((1, kw), (2, kh)):
                lo, hi = core.GRAPHICS_KEYS[k][2], core.GRAPHICS_KEYS[k][3]
                ttk.Spinbox(grid, from_=lo, to=hi, increment=64, textvariable=self.v[k], width=7).grid(row=r, column=col, padx=4)

        label("Window", row)
        ttk.Combobox(grid, values=list(core.WINDOW_MODES.values()), textvariable=self.window, state="readonly", width=18).grid(row=row, column=1, columnspan=2, sticky="w", padx=4)
        row += 1
        pair("Screen resolution", "screen_w", "screen_h", row); row += 1
        pair("Menu resolution", "menu_w", "menu_h", row)
        tk.Button(grid, text="Match screen", command=self.match_menu, bg=PANEL, fg=FG, relief="flat", padx=6).grid(row=row, column=3, padx=6)
        row += 1
        pair("3D (background) resolution", "bg_w", "bg_h", row); row += 1
        label("Mip mapping (0 = off, 6 = most)", row)
        ttk.Spinbox(grid, from_=0, to=6, increment=1, textvariable=self.v["mip"], width=7).grid(row=row, column=1, padx=4); row += 1
        label("Textures", row)
        ttk.Combobox(grid, values=list(core.TEXTURE_LEVELS.values()), textvariable=self.textures, state="readonly", width=22).grid(row=row, column=1, columnspan=3, sticky="w", padx=4); row += 1
        label("Fonts", row)
        ttk.Combobox(grid, values=list(core.FONT_LEVELS.values()), textvariable=self.fonts, state="readonly", width=22).grid(row=row, column=1, columnspan=3, sticky="w", padx=4); row += 1
        for text, var in (("Bump mapping", self.bump), ("Graphics stabilization", self.stab), ("Keep playing sound when the window is in the background", self.bg_sound)):
            tk.Checkbutton(grid, text=text, variable=var, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                           activeforeground=FG).grid(row=row, column=0, columnspan=4, sticky="w", pady=1)
            row += 1

        tk.Label(self, textvariable=self.warning, bg=BG, fg="#e0a030", wraplength=480, justify="left").pack(anchor="w", padx=10, pady=(2, 0))
        bar = tk.Frame(self, bg=BG)
        bar.pack(anchor="w", padx=10, pady=6)
        tk.Button(bar, text="Check", command=self.check, bg=PANEL, fg=FG, relief="flat", padx=10).pack(side="left", padx=(0, 6))
        tk.Button(bar, text="Restore original settings", command=self.restore, bg=PANEL, fg=FG, relief="flat", padx=10).pack(side="left")
        tk.Label(self, text="Not listed yet: Map Compression, Maintain Aspect Ratio, 3D LCD Mode and Environment. "
                            "I have not confirmed which values control those, so they are left alone.",
                 bg=BG, fg=DIM, wraplength=480, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(4, 0))
        self.check()

    def _reverse(self, table, text):
        return next((k for k, v in table.items() if v == text), None)

    def collect(self):
        values = {gid: var.get() for gid, var in self.v.items()}
        values["window_mode"] = self._reverse(core.WINDOW_MODES, self.window.get())
        values["textures"] = self._reverse(core.TEXTURE_LEVELS, self.textures.get())
        values["fonts"] = self._reverse(core.FONT_LEVELS, self.fonts.get())
        values["bump"], values["stab"], values["bg_sound"] = int(bool(self.bump.get())), int(bool(self.stab.get())), int(bool(self.bg_sound.get()))
        return core.clean_graphics({k: v for k, v in values.items() if v is not None})

    def show(self, values):
        for gid, var in self.v.items():
            var.set(str(values[gid]))
        self.window.set(core.WINDOW_MODES[values["window_mode"]])
        self.textures.set(core.TEXTURE_LEVELS[values["textures"]])
        self.fonts.set(core.FONT_LEVELS[values["fonts"]])
        self.bump.set(bool(values["bump"]))
        self.stab.set(bool(values["stab"]))
        self.bg_sound.set(bool(values["bg_sound"]))
        self.check()

    def fill_preset(self):
        name = self.preset.get()
        if name:
            values = self.collect()
            values.update(core.GRAPHICS_PRESETS[name])
            self.show(core.clean_graphics(values))

    def match_menu(self):
        self.v["menu_w"].set(self.v["screen_w"].get())
        self.v["menu_h"].set(self.v["screen_h"].get())
        self.check()

    def check(self):
        self.warning.set(core.aspect_warning(self.collect()))

    def restore(self):
        if core.restore_graphics(self.ini_path):
            self.show(core.read_boot_graphics(self.ini_path))
            messagebox.showinfo("Restored", "The boot file is back to how it was before the launcher first changed the display settings.")
        else:
            messagebox.showinfo("Nothing to restore", "The launcher has not changed the display settings yet.")


class GfxModTab(tk.Frame):
    """dgVoodoo + ReShade: install them next to pol.exe, switch them on and off, take them out again."""

    def __init__(self, parent, here, cfg):
        super().__init__(parent, bg=BG)
        self.here = here
        self.state = core.gfx_load(here)
        recommended = core.gfx_find_target(cfg.get("gfxmod_target", ""), cfg.get("ashita_dir", ""))
        nothing_installed = not self.state["installed"]["files"]
        if not self.state["target"] or not os.path.isdir(self.state["target"]) or (nothing_installed and recommended):
            self.state["target"] = recommended   # until something is installed the recommended folder always wins
        if not self.state["dgvoodoo"] and not self.state["reshade"]:
            self.state["dgvoodoo"], self.state["reshade"] = core.gfx_guess_sources()
        self.dg_var = tk.StringVar(value=self.state["dgvoodoo"])
        self.rs_var = tk.StringVar(value=self.state["reshade"])
        self.target_var = tk.StringVar(value=self.state["target"])
        self.status = tk.StringVar(value="")

        tk.Label(self, text="Sharper, nicer-looking graphics with dgVoodoo and ReShade.", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(self, text="Point this at the files you already use (for example from your Horizon setup). The launcher copies them next to the "
                            "game, keeps a backup of anything of yours it would replace, and can switch them off or remove them again.",
                 bg=BG, fg=DIM, wraplength=860, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=14)

        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="x", padx=14, pady=(10, 4))
        self._row(grid, 0, "dgVoodoo folder", self.dg_var, "Has D3D8.dll and dgVoodoo.conf (the official download works too).")
        self._row(grid, 1, "ReShade folder", self.rs_var, "Has dxgi.dll, ReShade.ini and your preset, and ideally a reshade-shaders folder.")
        self._row(grid, 2, "Loader folder", self.target_var, "Where the files go: the folder with xiloader.exe (Ashita's bootloader). Found automatically.")

        tk.Label(self, textvariable=self.status, bg=BG, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(8, 0))
        self.api = tk.StringVar(value="")
        tk.Label(self, textvariable=self.api, bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=(0, 2))
        bar = tk.Frame(self, bg=BG)
        bar.pack(anchor="w", padx=14, pady=4)
        for text, command in (("Install / update", self.install), ("Turn ON", lambda: self.toggle(True)), ("Turn OFF", lambda: self.toggle(False)),
                              ("Reset settings", self.reset), ("Uninstall", self.uninstall), ("Add shaders...", self.add_shaders), ("Check shaders", self.check_shaders), ("Fix search paths", self.fix_paths), ("dgVoodoo settings", self.open_cpl), ("Open folder", self.open_target)):
            tk.Button(bar, text=text, command=command, bg=PANEL2, fg=FG, relief="flat", padx=12, pady=4,
                      activebackground=BORDER, activeforeground=FG).pack(side="left", padx=(0, 6))

        self.log = tk.Text(self, height=9, bg=PANEL, fg=DIM, relief="flat", font=("Consolas", 9), state="disabled", bd=0, highlightthickness=0)
        self.log.pack(fill="both", expand=True, padx=14, pady=(8, 6))
        tk.Label(self, text="Close the game before installing, switching or removing (Windows locks the files while it runs). "
                            "Install / update keeps your current ReShade and dgVoodoo settings; Reset settings replaces them with the source files. "
                            "If another launcher (such as the Horizon launcher) also manages these files, use only one launcher at a time.",
                 bg=BG, fg=DIM, wraplength=860, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 10))
        self.refresh()

    def _row(self, grid, row, label, var, hint):
        tk.Label(grid, text=label, bg=BG, fg=FG, anchor="w", width=20).grid(row=row * 2, column=0, sticky="w", pady=(4, 0))
        tk.Entry(grid, textvariable=var, bg=PANEL2, fg=FG, insertbackground=FG, relief="flat", width=70).grid(row=row * 2, column=1, padx=6, pady=(4, 0))
        tk.Button(grid, text="Browse...", command=lambda: self.browse(var), bg=PANEL2, fg=FG, relief="flat", padx=8,
                  activebackground=BORDER, activeforeground=FG).grid(row=row * 2, column=2)
        tk.Label(grid, text=hint, bg=BG, fg=DIM, font=("Segoe UI", 8), anchor="w").grid(row=row * 2 + 1, column=1, sticky="w", padx=6)

    def browse(self, var):
        chosen = filedialog.askdirectory(initialdir=var.get() or os.path.expanduser("~"))
        if chosen:
            var.set(os.path.normpath(chosen))

    def read_fields(self):
        self.state["dgvoodoo"], self.state["reshade"], self.state["target"] = self.dg_var.get().strip(), self.rs_var.get().strip(), self.target_var.get().strip()

    def refresh(self):
        self.status.set("Status: " + core.gfx_status(self.state))
        installed = core.gfx_read_output_api(self.state["target"]) if self.state["installed"]["files"] else ""
        chosen = installed or core.gfx_read_output_api(self.dg_var.get().strip()) or core.gfx_read_output_api(os.path.join(self.dg_var.get().strip(), ""))
        self.api.set(f"dgVoodoo draws using: {chosen}   (change it in 'dgVoodoo settings')" if chosen
                     else "dgVoodoo draws using: not shown here - open 'dgVoodoo settings' to see or change it")

    def say(self, lines):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(lines))
        self.log.configure(state="disabled")

    def run(self, action):
        self.read_fields()
        try:
            notes = action()
        except PermissionError:
            messagebox.showwarning("Close the game first", "Windows would not let the launcher change a file. Close the game (and anything using it) and try again.")
            self.refresh()
            return
        except Exception as e:
            messagebox.showerror("That did not work", str(e))
            self.refresh()
            return
        try:
            core.gfx_save(self.here, self.state)
        except OSError:
            pass
        self.say(notes or ["Done."])
        self.refresh()

    def install(self):
        self.run(lambda: core.gfx_install(self.here, self.state))

    def reset(self):
        self.run(lambda: core.gfx_install(self.here, self.state, reset_settings=True))

    def toggle(self, enabled):
        word = "ON" if enabled else "OFF"

        def action():
            if not self.state["installed"]["files"]:
                return ["Nothing is installed yet - press Install / update first."]
            n = core.gfx_set_enabled(self.state, enabled)
            if n:
                return [f"Turned {word} ({n} file(s) switched). Start the game to see it."]
            return [f"It is already {word}."]
        self.run(action)

    def uninstall(self):
        if messagebox.askyesno("Uninstall", "Remove the dgVoodoo and ReShade files the launcher added, and put your own files back?"):
            self.run(lambda: core.gfx_uninstall(self.here, self.state))

    def add_shaders(self):
        chosen = filedialog.askdirectory(title="Choose a folder of shaders (a reshade-shaders folder, or any folder with .fx files)", initialdir=os.path.expanduser("~"))
        if chosen:
            self.run(lambda: core.gfx_add_shaders(self.state, os.path.normpath(chosen)) + ["Press 'Check shaders' to see if ReShade can find everything now."])

    def check_shaders(self):
        target = self.target_var.get().strip()
        result = core.gfx_check_shaders(target)
        if result is None:
            self.say(["There is no ReShade.ini in the loader folder yet. Install first."])
            return
        found, total, missing, fx = result
        lines = [f"ReShade looks in {total} shader folder(s): {found} exist, {len(missing)} missing. Shader files found: {fx}."]
        if missing:
            lines.append("Missing: " + ", ".join(missing))
            lines.append("")
            lines.append("To get them: close the game, run the ReShade installer (ReShade_Setup_6.8.0.exe), choose xiloader.exe in the loader folder,")
            lines.append("pick 'Direct3D 10/11/12', then tick the effect packages and press Install. Then press Check shaders again.")
        elif fx == 0:
            lines.append("The folders exist but hold no shader files.")
        else:
            lines.append("All of ReShade's shader folders are there.")
        hidden = core.gfx_unsearched_shader_folders(target)
        if hidden:
            lines.append("")
            lines.append("These folders exist but ReShade is NOT told to look in them, so their effects do not show up: "
                         + ", ".join(f"{name} ({count} files)" for name, count in hidden))
            lines.append("Press 'Fix search paths' to add them.")
        self.say(lines)

    def fix_paths(self):
        def action():
            added = core.gfx_fix_search_paths(self.target_var.get().strip())
            if not added:
                return ["ReShade already searches every shader folder that exists."]
            return ["Added to ReShade.ini: " + ", ".join(added), "Start the game (or press Reload in ReShade) to see the new effects."]
        self.run(action)

    def open_cpl(self):
        cpl = os.path.join(self.target_var.get().strip(), "dgVoodooCpl.exe")
        if os.path.isfile(cpl):
            os.startfile(cpl)
        else:
            messagebox.showinfo("dgVoodoo settings", "Install it first (that copies dgVoodoo's settings window next to the game), then press this again.")

    def open_target(self):
        target = self.target_var.get().strip()
        if target and os.path.isdir(target):
            os.startfile(target)


class UpdatesTab(tk.Frame):
    """The Settings page: a GM account for testing, and updates from Phoenix. setup_gm.py and server_update.py do the work; this page shows what they say."""

    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.busy = False
        self.lines = queue.Queue()
        self.gm_buttons = []
        gm = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        gm.pack(fill="x", padx=14, pady=(14, 6))
        tk.Label(gm, text="GM account for testing", bg=PANEL, fg=FG, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(gm, text=("A separate account whose characters are GMs, so your real character is never touched. Set it up once, then press Start GM game. "
                           "The first time, create a character in the lobby: it is a GM from its first login. GM commands can change your world, "
                           "so back up the database first."),
                 bg=PANEL, fg=DIM, wraplength=880, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 8))
        gm_bar = tk.Frame(gm, bg=PANEL)
        gm_bar.pack(anchor="w", padx=12, pady=(0, 12))
        for text, command in (("Set up GM account", lambda: self.run_script("setup_gm.py", ["setup"])), ("Start GM game", app.start_gm),
                              ("GM commands", lambda: self.run_script("setup_gm.py", ["commands"])), ("Make a character GM...", self.promote),
                              ("Back up database now", lambda: self.run_script("setup_gm.py", ["backup"]))):
            button = tk.Button(gm_bar, text=text, command=command, bg=PANEL2, fg=FG, relief="flat", padx=12, pady=5, activebackground=BORDER, activeforeground=FG)
            button.pack(side="left", padx=(0, 8))
            self.gm_buttons.append(button)
        tk.Label(self, text="Keep your server up to date with Phoenix", bg=BG, fg=FG, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(8, 2))
        tk.Label(self, text=("Check shows what is new and changes nothing. Update saves your database, then merges the new version in, applies database "
                             "changes and rebuilds the server. If anything clashes with our own changes it is cancelled and nothing changes. "
                             "Close the game before updating. Undo goes back to the version from before the last update."),
                 bg=BG, fg=DIM, wraplength=900, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=(0, 8))
        bar = tk.Frame(self, bg=BG)
        bar.pack(anchor="w", padx=14)
        self.buttons = []
        for text, command in (("Check for updates", self.check), ("Update now", self.update), ("Undo last update", self.undo),
                              ("Open backups folder", lambda: app.open_dir(os.path.join(HERE, "backups")))):
            button = tk.Button(bar, text=text, command=command, bg=PANEL, fg=FG, relief="flat", padx=14, pady=6, activebackground=PANEL2, activeforeground=FG)
            button.pack(side="left", padx=(0, 8))
            self.buttons.append(button)
        box = tk.Frame(self, bg=BG)
        box.pack(fill="both", expand=True, padx=14, pady=10)
        self.output = tk.Text(box, bg=PANEL, fg=FG, font=("Consolas", 9), state="disabled", relief="flat", wrap="word", bd=0, highlightthickness=0)
        scroll = ttk.Scrollbar(box, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.output.pack(side="left", fill="both", expand=True)
        self.write("Press 'Check for updates' to see whether Phoenix has released anything new. The GM buttons above print their results here too.")
        self.after(200, self.pump)

    def write(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def check(self):
        self.start(["check"])

    def update(self):
        if self.app.running:
            messagebox.showwarning("Close the game first", "The servers are running. Close the game (it stops the servers), then update.")
            return
        if messagebox.askyesno("Update", "Update the server to Phoenix's newest version?\n\nYour database is saved first. If anything clashes with our changes "
                                         "the update is cancelled and nothing changes. A rebuild can take up to half an hour."):
            self.start(["update"])

    def undo(self):
        if self.app.running:
            messagebox.showwarning("Close the game first", "The servers are running. Close the game (it stops the servers), then undo.")
            return
        answer = messagebox.askyesnocancel("Undo the last update",
                                           "Go back to the version from before the last update?\n\n"
                                           "Yes: also put the saved database back (anything you did in the game since then is lost).\n"
                                           "No: go back to the old code only and keep the database as it is.\n"
                                           "Cancel: do nothing.")
        if answer is None:
            return
        self.start(["undo"] + (["--restore-db"] if answer else []))

    def promote(self):
        name = simpledialog.askstring("Make a character a GM", "Character name (log that character out first):", parent=self)
        if name and name.strip():
            self.run_script("setup_gm.py", ["promote", name.strip(), "5"])

    def start(self, args):
        self.run_script("server_update.py", args)

    def run_script(self, script_name, args):
        if self.busy:
            return
        script = os.path.join(HERE, script_name)
        if not os.path.exists(script):
            self.write(f"{script_name} is missing from the launcher folder. Unpack the update zip again.")
            return
        self.busy = True
        for button in self.buttons[:3] + self.gm_buttons:
            button.configure(state="disabled")
        self.write("")
        self.write("---- " + script_name.replace(".py", "") + " " + " ".join(args) + " ----")
        threading.Thread(target=self.work, args=(script, args), daemon=True).start()

    def work(self, script, args):
        try:
            proc = subprocess.Popen([sys.executable, "-u", script] + args, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", creationflags=core.NO_WINDOW)
            for line in proc.stdout:
                self.lines.put(("line", line.rstrip()))
            self.lines.put(("done", proc.wait()))
        except Exception as problem:
            self.lines.put(("line", f"Could not run the update tool: {problem}"))
            self.lines.put(("done", 1))

    def pump(self):
        try:
            while True:
                kind, value = self.lines.get_nowait()
                if kind == "line":
                    self.write(value)
                else:
                    self.busy = False
                    for button in self.buttons[:3] + self.gm_buttons:
                        button.configure(state="normal")
        except queue.Empty:
            pass
        self.after(200, self.pump)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FFXI Solo Launcher")
        self.geometry("980x790")
        self.minsize(900, 760)
        self.configure(bg=BG)
        self._images = []   # keep pictures alive (Tk forgets a picture nobody holds on to)
        icon = load_image("logo_icon.png") or load_image("logo.png")
        if icon:
            self._images.append(icon)
            try:
                self.iconphoto(True, icon)
            except Exception:
                pass
        self.cfg = core.load_config(os.path.join(HERE, "config.json"))
        self.q = queue.Queue()
        self.procs, self.logfiles = {}, []
        self.running, self.stop_requested = False, False
        self.scripts = None
        self.ashita = self.cfg.get("ashita_dir")
        self.rates = core.load_rates(HERE)
        self.boot_ini = os.path.join(self.ashita, "config", "boot", self.cfg.get("ashita_boot", "phoenixsolo.ini")) if self.ashita else None
        has_ini = bool(self.boot_ini) and os.path.exists(self.boot_ini)
        self.graphics = core.load_graphics(HERE, self.boot_ini if has_ini else None)
        self.build_ui()
        self.after(200, self.pump)
        self.after(1000, self.lights)
        self.after(PICTURE_SECONDS * 1000, self.next_picture)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----- UI -----
    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        # the page switcher is our own top bar, so the notebook's own tabs are hidden
        style.layout("Tabless.TNotebook.Tab", [])
        style.layout("Tabless.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        style.configure("Tabless.TNotebook", background=BG, borderwidth=0)
        style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=FG, arrowcolor=ACCENT,
                        bordercolor=BORDER, lightcolor=PANEL2, darkcolor=PANEL2, selectbackground=PANEL2, selectforeground=FG)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", FG)],
                  selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", FG)])
        style.configure("TSpinbox", fieldbackground=PANEL2, background=PANEL2, foreground=FG, arrowcolor=ACCENT,
                        bordercolor=BORDER, lightcolor=PANEL2, darkcolor=PANEL2)
        style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=BG, arrowcolor=DIM, bordercolor=BG,
                        lightcolor=BORDER, darkcolor=BORDER)
        style.configure("Solo.Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT, bordercolor=BORDER,
                        lightcolor=ACCENT, darkcolor=ACCENT, thickness=8)
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", BG)

        # top bar: logo, name, page buttons (filled in by build_nav once every page exists)
        self.nav = tk.Frame(self, bg=BG)
        self.nav.pack(fill="x", padx=20, pady=(12, 0))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(8, 0))

        # bottom status bar (packed before the pages so it always keeps its room)
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(side="bottom", fill="x")
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")
        inner = tk.Frame(bar, bg=PANEL)
        inner.pack(fill="x", padx=20, pady=7)
        self.summary_dot = tk.Label(inner, text="\u25cf", bg=PANEL, fg=GREY, font=("Segoe UI", 11))
        self.summary_dot.pack(side="left")
        self.summary = tk.StringVar(value="Servers offline")
        tk.Label(inner, textvariable=self.summary, bg=PANEL, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 18))
        tk.Label(inner, text="Offline single-player  \u00b7  Level 75 era", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Label(inner, text=f"Launcher v{VERSION}", bg=PANEL, fg=DIM, font=("Segoe UI", 9)).pack(side="right")

        tabs = ttk.Notebook(self, style="Tabless.TNotebook")
        tabs.pack(fill="both", expand=True, padx=10, pady=(4, 6))
        self.tabs = tabs

        play = tk.Frame(tabs, bg=BG)
        tabs.add(play, text="  Play  ")
        # the big area shows the banner, the Taru Taru pictures while the game loads and runs, or (Show details) the servers and log
        self.stage = tk.Frame(play, bg=PANEL, width=GALLERY_W + 2, height=GALLERY_H + 2, highlightbackground=BORDER, highlightthickness=1)
        self.stage.pack(pady=(8, 0))
        self.stage.pack_propagate(False)
        banner = load_image("banner.png")
        self.banner_label = tk.Label(self.stage, bg=PANEL, bd=0)
        if banner:
            self._images.append(banner)
            self.banner_label.configure(image=banner)
        else:
            self.banner_label.configure(text="FFXI SOLO", fg=FG, font=("Georgia", 30, "bold"))
        self.pictures = load_gallery()
        self._images.extend(self.pictures)
        self.picture_index = 0
        self.showing_details = False
        self.picture_label = tk.Label(self.stage, bg=PANEL, bd=0, cursor="hand2")
        if self.pictures:
            self.picture_label.configure(image=self.pictures[0])
            self.picture_label.bind("<Button-1>", lambda e: self.next_picture(manual=True))

        self.details = tk.Frame(self.stage, bg=PANEL)
        tk.Label(self.details, text="GAME SERVERS", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        row = tk.Frame(self.details, bg=PANEL)
        row.pack(anchor="w", padx=8, pady=(2, 6))
        self.dots = {}
        for n in core.SERVERS:
            f = tk.Frame(row, bg=PANEL)
            f.pack(side="left", padx=9)
            d = tk.Label(f, text="\u25cf", bg=PANEL, fg=GREY, font=("Segoe UI", 16))
            d.pack()
            tk.Label(f, text=n[3:], bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack()
            self.dots[n] = d
        tk.Label(self.details, text="ACTIVITY", bg=PANEL, fg=DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(4, 2))
        self.log = tk.Text(self.details, height=12, bg=PANEL, fg=DIM, relief="flat", font=("Consolas", 9), state="disabled", bd=0, highlightthickness=0)
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.banner_label.pack(fill="both", expand=True)

        # under it: what is happening and the loading bar on the left, the two buttons on the right
        controls = tk.Frame(play, bg=BG)
        controls.pack(fill="x", padx=22, pady=(8, 4))
        right = tk.Frame(controls, bg=BG)
        right.pack(side="right")
        left = tk.Frame(controls, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.status = tk.StringVar(value="Ready when you are.")
        tk.Label(left, textvariable=self.status, bg=BG, fg=FG, font=("Segoe UI", 11), wraplength=300, justify="left", anchor="w").pack(fill="x", pady=(18, 6))
        self.progress = ttk.Progressbar(left, mode="indeterminate", style="Solo.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 8))
        links = tk.Frame(left, bg=BG)
        links.pack(anchor="w")
        self.details_link = tk.Label(links, text="Show details", bg=BG, fg=ACCENT, cursor="hand2", font=("Segoe UI", 9, "underline"))
        self.details_link.pack(side="left")
        self.details_link.bind("<Button-1>", lambda e: self.toggle_details())
        opener = tk.Label(links, text="Open logs folder", bg=BG, fg=DIM, cursor="hand2", font=("Segoe UI", 9, "underline"))
        opener.pack(side="left", padx=(16, 0))
        opener.bind("<Button-1>", lambda e: self.open_dir(LOGS))

        # PLAY, STOP and DUALBOX: banner buttons, a different race each time the launcher opens (pictures in assets\buttons\play, stop, dual)
        chosen = choose_button_sets()
        old_pictures = {"play": ("btn_play.png", "btn_play_hover.png", "btn_play_off.png"),
                        "stop": ("btn_stop.png", "btn_stop_hover.png", "btn_stop_off.png"),
                        "dual": ("btn_dual.png", "btn_dual_hover.png", "btn_dual.png")}
        sets = {}
        for kind, names in old_pictures.items():
            sets[kind] = chosen.get(kind) or {"normal": load_image(names[0]), "hover": load_image(names[1]), "off": load_image(names[2])}
            self._images.extend(i for i in sets[kind].values() if i)
        self.play_btn = ImageButton(right, sets["play"], self.start, "PLAY NOW")
        self.play_btn.pack(pady=(0, 3))
        self.stop_btn = ImageButton(right, sets["stop"], self.stop, "STOP")
        self.stop_btn.pack(pady=(0, 3))
        self.stop_btn.configure(state="disabled")
        # a second character in a second game window (set up once with setup_dualbox.py)
        self.dual_btn = ImageButton(right, sets["dual"], self.start_second, "DUALBOX")
        self.dual_btn.pack()

        # Squad tab
        self.squad_tab = None
        if sq is not None and "db_user" in self.cfg and "db_name" in self.cfg:
            try:
                import mariadb  # noqa: F401  (comes with the server's Python requirements)
                self.squad_tab = SquadTab(tabs, self.cfg)
                self.squad_tab.is_running = lambda: self.running
                tabs.add(self.squad_tab, text="  Squad  ")
            except ImportError:
                self.add_note(tabs, "Squad", "The Squad tab needs the Python 'mariadb' package.\nRun:  python -m pip install mariadb")
        else:
            self.add_note(tabs, "Squad", "The Squad tab needs db_user, db_pass and db_name in config.json.")

        # Rates tab
        self.rates_tab = RatesTab(tabs, self.rates)
        tabs.add(self.rates_tab, text="  Rates  ")

        # Graphics tab (needs the Ashita boot file)
        self.graphics_tab = None
        if self.boot_ini and os.path.exists(self.boot_ini):
            self.graphics_tab = GraphicsTab(tabs, self.graphics, self.boot_ini)
            tabs.add(self.graphics_tab, text="  Graphics  ")
        else:
            self.add_note(tabs, "Graphics", "The Graphics tab needs ashita_dir and ashita_boot in config.json to point at your Ashita boot file.")

        # Shaders tab: dgVoodoo + ReShade
        self.gfx_tab = GfxModTab(tabs, HERE, self.cfg)
        tabs.add(self.gfx_tab, text="  Shaders  ")

        # Updates tab: new Phoenix versions
        self.updates_tab = UpdatesTab(tabs, self)
        tabs.add(self.updates_tab, text="  Settings  ")

        # Addons / Plugins tabs
        self.lists = []
        if self.ashita and os.path.isdir(self.ashita):
            try:
                self.scripts = core.ScriptManager(self.ashita, self.cfg.get("ashita_boot", "phoenixsolo.ini"))
                self.scripts.prepare()
            except Exception as e:
                self.scripts = None
                self.add_note(tabs, "Addons", f"Could not set up addon control:\n{e}")
        else:
            self.add_note(tabs, "Addons", "Set ashita_dir in config.json to manage addons here.")
        if self.scripts:
            self.list_target = tk.StringVar(value="main")
            self.hints = []
            self.second_scripts = None
            for kind, title, folder in (("addon", "  Addons  ", "addons"), ("plugin", "  Plugins  ", "plugins")):
                page = tk.Frame(tabs, bg=BG)
                tabs.add(page, text=title)
                hint = tk.Label(page, text=LIST_HINT_MAIN, bg=BG, fg=DIM, font=("Segoe UI", 9))
                hint.pack(anchor="w", padx=10, pady=(10, 4))
                self.hints.append(hint)
                picker = tk.Frame(page, bg=BG)
                picker.pack(anchor="w", padx=10, pady=(0, 4))
                tk.Label(picker, text="List for:", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side="left")
                for value, text in (("main", "Main window"), ("second", "Second window (dualbox)")):
                    tk.Radiobutton(picker, text=text, value=value, variable=self.list_target, command=self.switch_list_target,
                                   bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                                   font=("Segoe UI", 10)).pack(side="left", padx=(10, 0))
                lst = CheckList(page, kind, self.scripts)
                lst.pack(fill="both", expand=True, padx=6)
                self.lists.append(lst)
                bar = tk.Frame(page, bg=BG)
                bar.pack(pady=8)
                tk.Button(bar, text="Refresh", command=lst.reload, bg=PANEL, fg=FG, relief="flat", padx=10).pack(side="left", padx=4)
                tk.Button(bar, text=f"Open {folder} folder", relief="flat", bg=PANEL, fg=FG, padx=10,
                          command=lambda f=folder: self.open_dir(os.path.join(self.ashita, f))).pack(side="left", padx=4)
        self.build_nav()

    def second_manager(self):
        """The second window's addon/plugin list: (manager, "") or (None, why it is not available)."""
        if getattr(self, "second_scripts", None) is not None:
            return self.second_scripts, ""
        boot2 = self.cfg.get("ashita_boot2")
        path = os.path.join(self.ashita, "config", "boot", boot2) if (self.ashita and boot2) else ""
        if not path or not os.path.exists(path):
            return None, "The second window is not set up yet. In PowerShell, in C:\\FFXISOLO, run:   python setup_dualbox.py setup"
        try:
            manager = core.ScriptManager(self.ashita, boot2, script_name="dualbox.txt")
            manager.prepare()
        except Exception as e:
            return None, f"Could not read the second window's script: {e}"
        self.second_scripts = manager
        return manager, ""

    def switch_list_target(self):
        second = self.list_target.get() == "second"
        manager, why = self.second_manager() if second else (self.scripts, "")
        for lst in self.lists:
            lst.use(manager, why)
        for hint in self.hints:
            hint.configure(text=LIST_HINT_SECOND if second else LIST_HINT_MAIN)

    def build_nav(self):
        wordmark = load_image("logo_nav.png")
        if wordmark:
            self._images.append(wordmark)
            tk.Label(self.nav, image=wordmark, bg=BG, bd=0).pack(side="left", padx=(0, 28))
        else:
            logo = load_image("logo.png", 2)
            if logo:
                self._images.append(logo)
                tk.Label(self.nav, image=logo, bg=BG, bd=0).pack(side="left")
            tk.Label(self.nav, text="FFXI SOLO", bg=BG, fg=FG, font=("Georgia", 17, "bold")).pack(side="left", padx=(8, 26))
        self.nav_items = []
        for index, tab_id in enumerate(self.tabs.tabs()):
            name = self.tabs.tab(tab_id, "text").strip().upper()
            holder = tk.Frame(self.nav, bg=BG, cursor="hand2")
            holder.pack(side="left", padx=2)
            label = tk.Label(holder, text=name, bg=BG, fg=DIM, font=("Segoe UI", 10, "bold"), padx=10, pady=6, cursor="hand2")
            label.pack()
            underline = tk.Frame(holder, bg=BG, height=2)
            underline.pack(fill="x", padx=10)
            for widget in (holder, label):
                widget.bind("<Button-1>", lambda e, i=index: self.select_tab(i))
            self.nav_items.append((label, underline))
        self.select_tab(0)

    def select_tab(self, index):
        self.tabs.select(index)
        for i, (label, underline) in enumerate(self.nav_items):
            label.configure(fg=ACCENT if i == index else DIM)
            underline.configure(bg=ACCENT if i == index else BG)

    def add_note(self, tabs, title, text):
        page = tk.Frame(tabs, bg=BG)
        tabs.add(page, text=f"  {title}  ")
        tk.Label(page, text=text, bg=BG, fg=DIM, wraplength=480, justify="left").pack(padx=14, pady=20, anchor="w")

    def open_dir(self, path):
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    # ----- the big area on the Play page -----
    def refresh_stage(self):
        for widget in (self.banner_label, self.picture_label, self.details):
            widget.pack_forget()
        if self.showing_details:
            self.details.pack(fill="both", expand=True)
        elif self.running and self.pictures:
            self.picture_label.pack(fill="both", expand=True)
        else:
            self.banner_label.pack(fill="both", expand=True)
        self.details_link.configure(text="Show banner" if self.showing_details else "Show details")

    def next_picture(self, manual=False):
        if len(self.pictures) > 1 and self.running and not self.showing_details:
            self.picture_index = (self.picture_index + 1) % len(self.pictures)
            self.picture_label.configure(image=self.pictures[self.picture_index])
        if not manual:
            self.after(PICTURE_SECONDS * 1000, self.next_picture)

    def toggle_details(self):
        self.showing_details = not self.showing_details
        self.refresh_stage()

    # ----- messages from the worker thread -----
    def say(self, msg):
        self.q.put(("log", msg))

    def say_status(self, msg):
        """Changes the status line only, without adding a line to the details log (for something that updates every second)."""
        self.q.put(("status", msg))

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "status":
                    self.status.set(val)
                elif kind == "log":
                    self.status.set(val)
                    self.log.configure(state="normal")
                    self.log.insert("end", time.strftime("%H:%M:%S  ") + val + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "error":
                    messagebox.showerror("Launcher", val)
                elif kind == "done":
                    self.progress.stop()
                    self.play_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.refresh_stage()
        except queue.Empty:
            pass
        self.after(200, self.pump)

    def lights(self):
        up = 0
        for n, d in self.dots.items():
            p = self.procs.get(n)
            if p is None:
                d.configure(fg=GREY)
            else:
                alive = p.poll() is None
                up += alive
                d.configure(fg=GREEN if alive else RED)
        if up == len(self.dots):
            self.summary.set("Servers online")
            self.summary_dot.configure(fg=GREEN)
        elif up:
            self.summary.set(f"{up} of {len(self.dots)} servers running")
            self.summary_dot.configure(fg="#e0a030")
        else:
            self.summary.set("Servers offline")
            self.summary_dot.configure(fg=GREY)
        self.after(1000, self.lights)

    # ----- buttons -----
    def start(self):
        if self.running:
            return
        self.rates = self.rates_tab.collect()
        try:
            core.save_rates(HERE, self.rates)
        except OSError:
            pass
        if self.graphics_tab is not None:
            self.graphics = self.graphics_tab.collect()
            try:
                core.save_graphics(HERE, self.graphics)
            except OSError:
                pass
        self.running, self.stop_requested = True, False
        self.play_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.start(14)
        self.refresh_stage()
        threading.Thread(target=self.worker, daemon=True).start()

    def stop(self):
        self.stop_requested = True
        self.say("Stopping...")

    def on_close(self):
        if self.running and not messagebox.askyesno("Quit", "The servers are running. Stop them and quit?"):
            return
        self.stop_requested = True
        self.cleanup()
        self.destroy()

    # ----- the actual launch sequence (runs in a background thread) -----
    def check(self):
        if self.stop_requested:
            raise Cancelled()

    def worker(self):
        try:
            self.launch()
        except Cancelled:
            self.say("Stopped.")
        except Exception as e:
            self.q.put(("error", str(e)))
            self.say("Failed - see the message.")
        finally:
            self.cleanup()
            self.running = False
            self.q.put(("done", None))

    def launch(self):
        cfg = self.cfg
        self.say("Cleaning up old processes...")
        for n in core.SERVERS + ["xiloader"]:
            core.kill(n)
        time.sleep(2)
        self.check()

        svc = cfg.get("mariadb_service", "MariaDB")
        if not core.ensure_service(svc):
            raise RuntimeError(f"The database service '{svc}' was not found or would not start.")

        self.say("Applying your rates...")
        try:
            for note in core.apply_rates(cfg["server_dir"], self.rates):
                self.say(note)
        except Exception as e:
            self.say(f"Could not apply the rates ({e}) - starting with the server's normal settings.")

        self.conquest_ticked = self.run_conquest("tick")      # catch the world up on the time you were away (servers are not running yet)

        self.procs.clear()
        for n in core.SERVERS:
            self.check()
            self.say(f"Starting {n}...")
            p, f = core.start_server(cfg, n, LOGS)
            self.procs[n] = p
            self.logfiles.append(f)
            time.sleep(3)

        self.wait_for_map()
        time.sleep(2)
        self.check()

        self.start_ah_sim()
        if self.ashita:
            self.launch_ashita()
        else:
            self.launch_plain()

    def wait_for_map(self):
        """Waits for the map server to say it is ready, showing the seconds so far. It waits as long as the map log keeps growing (the first
        start can take a minute or two) and only gives up if the log has not moved for 90 seconds, or after 10 minutes."""
        cfg = self.cfg
        self.say("Loading the world (this can take a minute or two)...")
        minwait, start = cfg.get("map_wait_seconds", 25), time.time()
        offset, grew = 0, time.time()
        last_size = core.log_size(LOGS, "xi_map")
        while time.time() - start < cfg.get("map_max_wait_seconds", 600):
            self.check()
            for n, p in self.procs.items():
                if p.poll() is not None:
                    raise RuntimeError(f"{n} stopped unexpectedly.\n\nLast lines of its log:\n"
                                       + core.tail(os.path.join(LOGS, n + ".log")))
            ready, offset = core.map_ready_from(LOGS, offset)
            if ready:
                break
            size = core.log_size(LOGS, "xi_map")
            if size != last_size:
                last_size, grew = size, time.time()
            if time.time() - start > minwait and size == 0:
                break  # log not readable; fall back to the fixed wait
            if time.time() - grew > 90:
                break  # the log has stopped moving: carry on instead of waiting for ever
            self.say_status(f"Loading the world... {int(time.time() - start)} seconds so far")
            time.sleep(1)
        seconds = int(time.time() - start)
        self.say(f"The world is ready ({seconds} seconds).")
        return seconds

    def launch_ashita(self):
        cfg = self.cfg
        cli = os.path.join(self.ashita, "Ashita-cli.exe")
        if not os.path.exists(cli):
            raise RuntimeError(f"Missing {cli}")
        if core.sync_loader(cfg):
            self.say("Updated the loader inside Ashita.")
        if self.graphics_tab is not None:
            try:
                core.apply_graphics(self.boot_ini, self.graphics)
                self.say("Applied your graphics settings.")
            except Exception as e:
                self.say(f"Could not apply the graphics settings ({e}) - starting with the boot file as it is.")
        self.say("Starting the game through Ashita...")
        alog = open(os.path.join(LOGS, "ashita.log"), "wb")
        self.logfiles.append(alog)
        boot = getattr(self, "launch_boot", None) or cfg.get("ashita_boot", "phoenixsolo.ini")      # the GM game starts with its own boot file
        self.launch_boot = None
        subprocess.Popen([cli, boot], cwd=self.ashita, stdout=alog,
                         stderr=subprocess.STDOUT, creationflags=core.NO_WINDOW)
        for _ in range(60):
            self.check()
            if core.is_running("xiloader"):
                break
            time.sleep(1)
        else:
            raise RuntimeError("The game loader never started.\n\nAshita said:\n"
                               + core.tail(os.path.join(LOGS, "ashita.log")))
        self.say("Game is running. Closing it will stop the servers.")
        while core.is_running("xiloader"):
            self.check()
            time.sleep(2)
        self.say("Game closed.")

    def launch_plain(self):
        cfg = self.cfg
        loader = None
        for root, _d, files in os.walk(cfg["xiloader_dir"]):
            if "xiloader.exe" in files:
                loader = os.path.join(root, "xiloader.exe")
                break
        if not loader:
            raise RuntimeError("xiloader.exe not found - did setup finish?")
        self.say("Starting the game...")
        p = subprocess.Popen([loader, "--server", "127.0.0.1", "--user", cfg["game_user"], "--pass", cfg["game_pass"]],
                             cwd=cfg["ffxi_client_dir"])
        while p.poll() is None:
            self.check()
            time.sleep(2)
        self.say("Game closed.")

    def start_second(self):
        """Opens a second game window (a second character on a second account) next to the first. The servers stay up until every window is closed."""
        if not self.running or not core.is_running("xiloader"):
            messagebox.showinfo("Second character", "Press PLAY first. The second character joins the servers that are already running.")
            return
        boot2 = self.cfg.get("ashita_boot2")
        path = os.path.join(self.ashita, "config", "boot", boot2) if (self.ashita and boot2) else ""
        if not path or not os.path.exists(path):
            messagebox.showinfo("Second character", "The second character is not set up yet.\n\nOpen PowerShell, go to C:\\FFXISOLO and run:\n\n    python setup_dualbox.py setup\n\nThen try again.")
            return
        if core.count_running("xiloader") >= 2:
            messagebox.showinfo("Second character", "A second game window is already open.")
            return
        self.launch_extra(boot2, "ashita2.log")
        self.say("Starting the second character... (the first time it shows character creation)")

    def launch_extra(self, boot, log_name):
        """Opens one more game window with the given boot file, next to the one already running."""
        cli = os.path.join(self.ashita, "Ashita-cli.exe")
        log = open(os.path.join(LOGS, log_name), "wb")
        self.logfiles.append(log)
        subprocess.Popen([cli, boot], cwd=self.ashita, stdout=log, stderr=subprocess.STDOUT, creationflags=core.NO_WINDOW)

    def start_gm(self):
        """Opens the game as the GM account (set up on the Settings page). With the servers off it starts them too, like PLAY."""
        boot = self.cfg.get("ashita_boot_gm")
        path = os.path.join(self.ashita, "config", "boot", boot) if (self.ashita and boot) else ""
        if not path or not os.path.exists(path):
            messagebox.showinfo("GM game", "The GM account is not set up yet.\n\nOn the Settings page press 'Set up GM account' first.")
            return
        if self.running and core.is_running("xiloader"):
            self.launch_extra(boot, "ashita-gm.log")
            self.say("Starting the GM game next to your other window...")
            return
        if self.running:
            return
        self.launch_boot = boot
        self.select_tab(0)          # shows the Play page and highlights it in the top bar
        self.start()

    def run_conquest(self, mode):
        # The conquest simulator (conquest_sim.py) edits the conquest table. "tick" runs before the servers start, "stamp" after they stop.
        script = os.path.join(HERE, "conquest_sim.py")
        if not self.rates.get("conquest_sim", False) or not os.path.exists(script):
            return False
        try:
            done = subprocess.run([sys.executable, script, mode], cwd=HERE, capture_output=True, text=True, timeout=90,
                                  creationflags=core.NO_WINDOW)
            if done.returncode != 0:
                lines = (done.stderr or done.stdout or "").strip().splitlines()
                self.say("The conquest simulator had a problem: " + (lines[-1] if lines else "unknown") + " - continuing without it.")
                return False
            lines = (done.stdout or "").strip().splitlines()
            if mode == "tick" and lines:
                self.say(lines[-1])
            return True
        except Exception as e:
            self.say(f"The conquest simulator did not run: {e}")
            return False

    def start_ah_sim(self):
        # The auction house simulator (ah_sim.py) stocks the auction house and buys what you list. Switched on the Rates tab.
        script = os.path.join(HERE, "ah_sim.py")
        if not self.rates.get("ah_sim", self.cfg.get("ah_sim", False)) or not os.path.exists(script):
            return
        try:
            log = open(os.path.join(LOGS, "ah_sim.log"), "wb")
            self.logfiles.append(log)
            self.ah_proc = subprocess.Popen([sys.executable, script, "run"], cwd=HERE, stdout=log, stderr=subprocess.STDOUT,
                                            creationflags=core.NO_WINDOW)
            self.say("Auction house simulator started.")
        except Exception as e:
            self.say(f"Auction house simulator did not start: {e}")

    def cleanup(self):
        ah = getattr(self, "ah_proc", None)
        if ah is not None:
            try:
                if ah.poll() is None:
                    ah.terminate()
            except Exception:
                pass
            self.ah_proc = None
        for p in self.procs.values():
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        for n in core.SERVERS:
            core.kill(n)
        if self.stop_requested:
            core.kill("xiloader")
        if getattr(self, "conquest_ticked", False):
            self.run_conquest("stamp")                         # the session is over: note the time so the tally is not repeated
            self.conquest_ticked = False
        for f in self.logfiles:
            try:
                f.close()
            except Exception:
                pass
        self.logfiles.clear()
        self.procs.clear()
        self.say("Servers stopped.")


def main():
    if os.name == "nt" and not is_admin():
        elevate_and_exit()
    try:
        App().mainloop()
    except Exception:
        os.makedirs(LOGS, exist_ok=True)
        err = traceback.format_exc()
        with open(os.path.join(LOGS, "launcher-error.log"), "w") as f:
            f.write(err)
        try:
            messagebox.showerror("Launcher crashed", err[-1500:])
        except Exception:
            pass


if __name__ == "__main__":
    main()
