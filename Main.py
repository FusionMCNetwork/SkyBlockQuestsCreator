import random
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk, messagebox


# =========================
# YAML minimal dumper
# =========================
def _yaml_needs_quotes(s: str) -> bool:
    if s == "":
        return True
    specials = [":", "{", "}", "[", "]", "#", "&", "*", "!", "|", ">", "%", "@", "`"]
    if any(ch in s for ch in specials):
        return True
    if s[0].isspace() or s[-1].isspace():
        return True
    if s.lower() in {"true", "false", "null", "~"}:
        return True
    return False


def _yaml_quote(s: str) -> str:
    # Usiamo doppi apici, escapando i doppi apici interni
    return '"' + s.replace('"', '\\"') + '"'


def yaml_dump(data, indent: int = 0) -> str:
    sp = "  " * indent

    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}{k}:")
                lines.append(yaml_dump(v, indent + 1))
            else:
                lines.append(f"{sp}{k}: {yaml_dump(v, 0).lstrip()}")
        return "\n".join(lines)

    if isinstance(data, list):
        if not data:
            return f"{sp}[]"
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{sp}-")
                lines.append(yaml_dump(item, indent + 1))
            else:
                lines.append(f"{sp}- {yaml_dump(item, 0).lstrip()}")
        return "\n".join(lines)

    if isinstance(data, bool):
        return f"{sp}{'true' if data else 'false'}"
    if isinstance(data, int):
        return f"{sp}{data}"
    if data is None:
        return f"{sp}null"
    if isinstance(data, str):
        return f"{sp}{_yaml_quote(data) if _yaml_needs_quotes(data) else data}"

    # fallback
    return f"{sp}{_yaml_quote(str(data))}"


# =========================
# Task definitions (schema)
# =========================
TASK_DEFS = {
    "blockbreak": {
        "required": {"amount": ("int", None)},
        "optional": {
            "block": ("str", ""),                  # mutually exclusive with blocks
            "blocks": ("list[str]", []),           # mutually exclusive with block
            "reverse-if-placed": ("bool", False),
            "allow-silk-touch": ("bool", True),
            "allow-negative-progress": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [("block", "blocks")],
    },
    "blockplace": {
        "required": {"amount": ("int", None)},
        "optional": {
            "block": ("str", ""),
            "blocks": ("list[str]", []),
            "reverse-if-broken": ("bool", False),
            "allow-negative-progress": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [("block", "blocks")],
    },
    "neobrewing": {
        "required": {"amount": ("int", None)},
        "optional": {
            "ingredient": ("str", ""),
            "exact-match": ("bool", True),
            "required-effects": ("list[str]", []),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [],
    },
    "consume": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),
            "exact-match": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [],
    },
    "crafting": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),
            "exact-match": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [],
    },
    "farming": {
        "required": {"amount": ("int", None)},
        "optional": {
            "block": ("str", ""),
            "blocks": ("list[str]", []),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [("block", "blocks")],
    },
    "inventory": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),                  # nel testo dici obbligatorio item/items; qui permetto item o items
            "items": ("list[str]", []),
            "exact-match": ("bool", True),
            "remove-items-when-complete": ("bool", False),
            "allow-partial-completion": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [("item", "items")],
    },
    "mobkilling": {
        "required": {"amount": ("int", None)},
        "optional": {
            "mob": ("str", ""),
            "mobs": ("list[str]", []),
            "name": ("str", ""),
            "names": ("list[str]", []),
            "hostile": ("str", ""),               # lasciamo stringa vuota oppure "true"/"false" a tua scelta
            "item": ("str", ""),
            "exact-match": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [("mob", "mobs"), ("name", "names")],
    },
    "smelting": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),
            "exact-match": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [],
    },
    "smithing": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),
            "exact-match": ("bool", True),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [],
    },
}

TASK_TYPES = list(TASK_DEFS.keys())


# =========================
# Data model
# =========================
@dataclass
class Task:
    name: str
    type: str
    params: dict = field(default_factory=dict)
    label: str = ""  # usata per la generazione placeholders (opzionale)


@dataclass
class Quest:
    quest_id: str
    sort_order: int
    category: str

    tasks: dict = field(default_factory=dict)  # name -> Task

    display_name: str = ""
    display_type: str = ""
    lore_normal: list = field(default_factory=list)
    lore_started: list = field(default_factory=list)

    rewards: list = field(default_factory=list)

    repeatable: bool = False
    cooldown_enabled: bool = True
    cooldown_time: int = 1440
    requires: list = field(default_factory=list)


# =========================
# Small UI helpers
# =========================
class ListEditor(tk.Frame):
    def __init__(self, master, title: str, initial=None):
        super().__init__(master)
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text=title).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))

        self.listbox = tk.Listbox(self, height=6)
        self.listbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self.rowconfigure(1, weight=1)

        btns = ttk.Frame(self)
        btns.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=4)

        ttk.Button(btns, text="Aggiungi", command=self._add).grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Button(btns, text="Modifica", command=self._edit).grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(btns, text="Rimuovi", command=self._remove).grid(row=2, column=0, sticky="ew", pady=2)

        if initial:
            for x in initial:
                self.listbox.insert(tk.END, x)

    def _ask_text(self, title: str, initial: str = "") -> str | None:
        win = tk.Toplevel(self)
        win.title(title)
        win.resizable(False, False)
        win.grab_set()

        ttk.Label(win, text=title).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        var = tk.StringVar(value=initial)
        ent = ttk.Entry(win, textvariable=var, width=60)
        ent.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        ent.focus_set()

        btns = ttk.Frame(win)
        btns.grid(row=2, column=0, sticky="e", padx=10, pady=10)

        result = {"value": None}

        def ok():
            result["value"] = var.get()
            win.destroy()

        def cancel():
            win.destroy()

        ttk.Button(btns, text="OK", command=ok).grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="Annulla", command=cancel).grid(row=0, column=1, padx=5)

        win.wait_window()
        return result["value"]

    def _add(self):
        s = self._ask_text("Nuova riga", "")
        if s is None:
            return
        self.listbox.insert(tk.END, s)

    def _edit(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        old = self.listbox.get(idx)
        s = self._ask_text("Modifica riga", old)
        if s is None:
            return
        self.listbox.delete(idx)
        self.listbox.insert(idx, s)

    def _remove(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.listbox.delete(sel[0])

    def get_list(self) -> list[str]:
        return list(self.listbox.get(0, tk.END))

    def set_list(self, values: list[str]):
        self.listbox.delete(0, tk.END)
        for x in values:
            self.listbox.insert(tk.END, x)


class MultiLineTextDialog:
    @staticmethod
    def ask_list(master, title: str, initial: list[str]) -> list[str] | None:
        win = tk.Toplevel(master)
        win.title(title)
        win.geometry("520x360")
        win.grab_set()

        ttk.Label(win, text="Inserisci 1 valore per riga:").pack(anchor="w", padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True, padx=10, pady=6)
        txt.insert("1.0", "\n".join(initial or []))

        btns = ttk.Frame(win)
        btns.pack(anchor="e", padx=10, pady=10)

        result = {"value": None}

        def ok():
            content = txt.get("1.0", "end").splitlines()
            # pulizia: rimuovo solo le righe finali vuote
            while content and content[-1] == "":
                content.pop()
            result["value"] = content
            win.destroy()

        def cancel():
            win.destroy()

        ttk.Button(btns, text="OK", command=ok).pack(side="left", padx=5)
        ttk.Button(btns, text="Annulla", command=cancel).pack(side="left", padx=5)

        win.wait_window()
        return result["value"]


# =========================
# Task dialogs
# =========================
class TaskNameTypeDialog:
    def __init__(self, master, existing_names: set[str]):
        self.master = master
        self.existing_names = existing_names
        self.result = None

        self.win = tk.Toplevel(master)
        self.win.title("Nuova Task")
        self.win.resizable(False, False)
        self.win.grab_set()

        ttk.Label(self.win, text="Nome task (univoco nella quest):").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.name_var = tk.StringVar()
        ttk.Entry(self.win, textvariable=self.name_var, width=40).grid(row=1, column=0, sticky="ew", padx=10, pady=4)

        ttk.Label(self.win, text="Categoria/Tipo task:").grid(row=2, column=0, sticky="w", padx=10, pady=(10, 4))
        self.type_var = tk.StringVar(value=TASK_TYPES[0])
        ttk.Combobox(self.win, textvariable=self.type_var, values=TASK_TYPES, state="readonly", width=37).grid(
            row=3, column=0, sticky="ew", padx=10, pady=4
        )

        btns = ttk.Frame(self.win)
        btns.grid(row=4, column=0, sticky="e", padx=10, pady=10)

        ttk.Button(btns, text="Conferma", command=self._ok).grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="Annulla", command=self._cancel).grid(row=0, column=1, padx=5)

        self.win.bind("<Return>", lambda e: self._ok())
        self.win.bind("<Escape>", lambda e: self._cancel())

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Errore", "Il nome della task non può essere vuoto.", parent=self.win)
            return
        if name in self.existing_names:
            messagebox.showerror("Errore", f"Esiste già una task chiamata '{name}' in questa quest.", parent=self.win)
            return
        self.result = (name, self.type_var.get())
        self.win.destroy()

    def _cancel(self):
        self.win.destroy()

    def show(self):
        self.win.wait_window()
        return self.result


class TaskConfigDialog:
    def __init__(self, master, task_type: str, initial_params: dict, initial_label: str):
        self.master = master
        self.task_type = task_type
        self.result = None

        self.win = tk.Toplevel(master)
        self.win.title(f"Config Task: {task_type}")
        self.win.geometry("560x520")
        self.win.grab_set()

        container = ttk.Frame(self.win)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(container, text="Label (opzionale, usata nei placeholders):").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.label_var = tk.StringVar(value=initial_label or "")
        ttk.Entry(container, textvariable=self.label_var).grid(row=1, column=0, sticky="ew", pady=(0, 10))
        container.columnconfigure(0, weight=1)

        self.fields = {}  # key -> (type, widget/var)

        schema = TASK_DEFS[task_type]
        all_fields = [("required", schema["required"]), ("optional", schema["optional"])]

        row = 2
        for section_name, fields in all_fields:
            ttk.Label(container, text=section_name.upper()).grid(row=row, column=0, sticky="w", pady=(6, 2))
            row += 1

            for key, (ftype, default) in fields.items():
                ttk.Label(container, text=key).grid(row=row, column=0, sticky="w")
                row += 1

                init_value = initial_params.get(key, default)

                if ftype == "int":
                    var = tk.StringVar(value=str(init_value if init_value is not None else random.randint(1, 64)))
                    ent = ttk.Entry(container, textvariable=var)
                    ent.grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "bool":
                    var = tk.BooleanVar(value=bool(init_value))
                    chk = ttk.Checkbutton(container, variable=var, text="true/false")
                    chk.grid(row=row, column=0, sticky="w", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "str":
                    var = tk.StringVar(value=str(init_value) if init_value is not None else "")
                    ent = ttk.Entry(container, textvariable=var)
                    ent.grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "list[str]":
                    btn = ttk.Button(
                        container,
                        text="Modifica lista...",
                        command=lambda k=key: self._edit_list(k),
                    )
                    btn.grid(row=row, column=0, sticky="w", pady=(0, 8))
                    self.fields[key] = (ftype, list(init_value or []))

                else:
                    var = tk.StringVar(value=str(init_value))
                    ent = ttk.Entry(container, textvariable=var)
                    ent.grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                row += 1

        hint = "Nota: per i campi mutuamente esclusivi (es. block/blocks) lasciane uno vuoto."
        ttk.Label(container, text=hint).grid(row=row, column=0, sticky="w", pady=(8, 0))
        row += 1

        btns = ttk.Frame(container)
        btns.grid(row=row, column=0, sticky="e", pady=10)
        ttk.Button(btns, text="Conferma", command=self._ok).grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="Annulla", command=self._cancel).grid(row=0, column=1, padx=5)

    def _edit_list(self, key: str):
        ftype, current = self.fields[key]
        edited = MultiLineTextDialog.ask_list(self.win, f"Modifica lista: {key}", current)
        if edited is None:
            return
        self.fields[key] = (ftype, edited)

    def _ok(self):
        schema = TASK_DEFS[self.task_type]

        params = {}
        # required: sempre presenti
        for key, (ftype, _default) in schema["required"].items():
            params[key] = self._read_field(key, ftype, required=True)

        # optional: includo solo se "significativo"
        for key, (ftype, default) in schema["optional"].items():
            val = self._read_field(key, ftype, required=False)
            if ftype == "str":
                if val != "":
                    params[key] = val
            elif ftype == "list[str]":
                if val:
                    params[key] = val
            elif ftype == "bool":
                # per coerenza con i template includo sempre i bool se l'utente li ha toccati? Qui: includo sempre.
                params[key] = val
            elif ftype == "int":
                params[key] = val
            else:
                if val is not None:
                    params[key] = val

        # mutex validation (es: block XOR blocks)
        for a, b in schema.get("mutex_groups", []):
            a_present = a in params and ((isinstance(params[a], str) and params[a] != "") or (isinstance(params[a], list) and len(params[a]) > 0))
            b_present = b in params and ((isinstance(params[b], str) and params[b] != "") or (isinstance(params[b], list) and len(params[b]) > 0))
            if a_present and b_present:
                messagebox.showerror("Errore", f"I campi '{a}' e '{b}' non possono essere entrambi valorizzati.", parent=self.win)
                return

        label = self.label_var.get().strip()
        self.result = (params, label)
        self.win.destroy()

    def _read_field(self, key: str, ftype: str, required: bool):
        _t, holder = self.fields[key]
        if ftype == "int":
            s = holder.get().strip()
            try:
                v = int(s)
            except ValueError:
                messagebox.showerror("Errore", f"'{key}' deve essere un numero intero.", parent=self.win)
                raise
            return v
        if ftype == "bool":
            return bool(holder.get())
        if ftype == "str":
            return holder.get()
        if ftype == "list[str]":
            return list(holder)
        return holder.get()

    def _cancel(self):
        self.win.destroy()

    def show(self):
        self.win.wait_window()
        return self.result


# =========================
# Quest tab
# =========================
class QuestTab(ttk.Frame):
    def __init__(self, master, quest: Quest, placeholder_cfg_getter):
        super().__init__(master)
        self.quest = quest
        self.placeholder_cfg_getter = placeholder_cfg_getter

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas)

        self.body.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._build()

    def _build(self):
        # ===== Tasks
        tasks_box = ttk.LabelFrame(self.body, text="Tasks")
        tasks_box.pack(fill="x", padx=10, pady=10)

        cols = ("name", "type")
        self.tasks_tree = ttk.Treeview(tasks_box, columns=cols, show="headings", height=6)
        self.tasks_tree.heading("name", text="Nome")
        self.tasks_tree.heading("type", text="Tipo")
        self.tasks_tree.column("name", width=200)
        self.tasks_tree.column("type", width=160)
        self.tasks_tree.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        tasks_box.columnconfigure(0, weight=1)

        btns = ttk.Frame(tasks_box)
        btns.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

        ttk.Button(btns, text="Aggiungi", command=self._add_task).grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Button(btns, text="Modifica", command=self._edit_task).grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(btns, text="Rimuovi", command=self._remove_task).grid(row=2, column=0, sticky="ew", pady=2)

        self._refresh_tasks_tree()

        # ===== Display
        display_box = ttk.LabelFrame(self.body, text="Display")
        display_box.pack(fill="x", padx=10, pady=10)

        ttk.Label(display_box, text="name").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.display_name_var = tk.StringVar(value=self.quest.display_name)
        ttk.Entry(display_box, textvariable=self.display_name_var).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        ttk.Label(display_box, text="type (materiale Minecraft)").grid(row=0, column=1, sticky="w", padx=8, pady=(8, 2))
        self.display_type_var = tk.StringVar(value=self.quest.display_type)
        ttk.Entry(display_box, textvariable=self.display_type_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))

        display_box.columnconfigure(0, weight=1)
        display_box.columnconfigure(1, weight=1)

        lore_frame = ttk.Frame(display_box)
        lore_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        lore_frame.columnconfigure(0, weight=1)
        lore_frame.columnconfigure(1, weight=1)

        self.lore_normal_editor = ListEditor(lore_frame, "lore-normal", self.quest.lore_normal)
        self.lore_normal_editor.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.lore_started_editor = ListEditor(lore_frame, "lore-started", self.quest.lore_started)
        self.lore_started_editor.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ===== Rewards
        rewards_box = ttk.LabelFrame(self.body, text="Rewards (comandi Minecraft)")
        rewards_box.pack(fill="x", padx=10, pady=10)
        self.rewards_editor = ListEditor(rewards_box, "Lista rewards", self.quest.rewards)
        self.rewards_editor.pack(fill="both", expand=True)

        # ===== Placeholders preview / config hint
        ph_box = ttk.LabelFrame(self.body, text="Placeholders (generati automaticamente)")
        ph_box.pack(fill="x", padx=10, pady=10)

        self.ph_preview = tk.Text(ph_box, height=7, wrap="none")
        self.ph_preview.pack(fill="x", padx=8, pady=8)
        self.ph_preview.configure(state="disabled")

        ttk.Button(ph_box, text="Aggiorna anteprima placeholders", command=self._update_placeholders_preview).pack(
            anchor="e", padx=8, pady=(0, 8)
        )
        self._update_placeholders_preview()

        # ===== Options
        opt_box = ttk.LabelFrame(self.body, text="Options")
        opt_box.pack(fill="x", padx=10, pady=10)
        opt_box.columnconfigure(1, weight=1)

        ttk.Label(opt_box, text="category").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.category_var = tk.StringVar(value=self.quest.category)
        ent_cat = ttk.Entry(opt_box, textvariable=self.category_var, state="disabled")
        ent_cat.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 2))

        ttk.Label(opt_box, text="sort-order").grid(row=1, column=0, sticky="w", padx=8, pady=2)
        self.sort_order_var = tk.IntVar(value=self.quest.sort_order)
        ttk.Spinbox(opt_box, from_=1, to=999999, textvariable=self.sort_order_var, width=10).grid(
            row=1, column=1, sticky="w", padx=8, pady=2
        )

        self.repeatable_var = tk.BooleanVar(value=self.quest.repeatable)
        ttk.Checkbutton(opt_box, text="repeatable", variable=self.repeatable_var).grid(
            row=2, column=1, sticky="w", padx=8, pady=2
        )

        cooldown_frame = ttk.Frame(opt_box)
        cooldown_frame.grid(row=3, column=1, sticky="w", padx=8, pady=2)

        self.cooldown_enabled_var = tk.BooleanVar(value=self.quest.cooldown_enabled)
        ttk.Checkbutton(cooldown_frame, text="cooldown.enabled", variable=self.cooldown_enabled_var).grid(row=0, column=0, padx=(0, 10))

        ttk.Label(cooldown_frame, text="cooldown.time (minuti)").grid(row=0, column=1, padx=(0, 6))
        self.cooldown_time_var = tk.IntVar(value=self.quest.cooldown_time)
        ttk.Spinbox(cooldown_frame, from_=0, to=10_000_000, textvariable=self.cooldown_time_var, width=10).grid(row=0, column=2)

        self.requires_editor = ListEditor(opt_box, "requires (quest richieste)", self.quest.requires)
        self.requires_editor.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)

    def _refresh_tasks_tree(self):
        for i in self.tasks_tree.get_children():
            self.tasks_tree.delete(i)
        for name, task in self.quest.tasks.items():
            self.tasks_tree.insert("", tk.END, values=(name, task.type))

    def _selected_task_name(self) -> str | None:
        sel = self.tasks_tree.selection()
        if not sel:
            return None
        values = self.tasks_tree.item(sel[0], "values")
        return values[0] if values else None

    def _default_params_for(self, task_type: str) -> dict:
        schema = TASK_DEFS[task_type]
        params = {}
        # required
        for key, (ftype, _default) in schema["required"].items():
            if ftype == "int":
                params[key] = random.randint(1, 64)
            else:
                params[key] = ""
        # optional defaults
        for key, (ftype, default) in schema["optional"].items():
            if ftype == "list[str]":
                params[key] = []
            else:
                params[key] = default
        return params

    def _add_task(self):
        d1 = TaskNameTypeDialog(self, existing_names=set(self.quest.tasks.keys()))
        res = d1.show()
        if not res:
            return
        name, task_type = res

        initial_params = self._default_params_for(task_type)
        d2 = TaskConfigDialog(self, task_type, initial_params=initial_params, initial_label=name.capitalize())
        res2 = d2.show()
        if not res2:
            return
        params, label = res2

        self.quest.tasks[name] = Task(name=name, type=task_type, params=params, label=label)
        self._refresh_tasks_tree()
        self._update_placeholders_preview()

    def _edit_task(self):
        name = self._selected_task_name()
        if not name:
            return
        task = self.quest.tasks[name]
        d = TaskConfigDialog(self, task.type, initial_params=dict(task.params), initial_label=task.label or "")
        res = d.show()
        if not res:
            return
        params, label = res
        task.params = params
        task.label = label
        self._refresh_tasks_tree()
        self._update_placeholders_preview()

    def _remove_task(self):
        name = self._selected_task_name()
        if not name:
            return
        if messagebox.askyesno("Conferma", f"Rimuovere la task '{name}'?", parent=self):
            self.quest.tasks.pop(name, None)
            self._refresh_tasks_tree()
            self._update_placeholders_preview()

    def _update_placeholders_preview(self):
        placeholders, progress_placeholders = self.generate_placeholders()

        lines = ["placeholders:"]
        for k, v in placeholders.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("progress-placeholders:")
        for k, v in progress_placeholders.items():
            lines.append(f"  {k}: {v}")

        self.ph_preview.configure(state="normal")
        self.ph_preview.delete("1.0", "end")
        self.ph_preview.insert("1.0", "\n".join(lines))
        self.ph_preview.configure(state="disabled")

    def generate_placeholders(self) -> tuple[dict, dict]:
        cfg = self.placeholder_cfg_getter()
        # cfg keys:
        #   placeholders_key_fmt, placeholders_value_fmt, progress_value_fmt
        placeholders = {}
        progress = {}

        for tname, task in self.quest.tasks.items():
            label = (task.label or tname).strip() or tname

            key = cfg["placeholders_key_fmt"].format(task=tname, label=label)
            val = cfg["placeholders_value_fmt"].format(
                task=tname,
                label=label,
                progress=f"{{{tname}:progress}}",
                goal=f"{{{tname}:goal}}",
            )
            placeholders[key] = val

            pval = cfg["progress_value_fmt"].format(
                task=tname,
                label=label,
                progress=f"{{{tname}:progress}}",
                goal=f"{{{tname}:goal}}",
            )
            progress[tname] = pval

        return placeholders, progress

    def apply_ui_to_model(self):
        self.quest.display_name = self.display_name_var.get()
        self.quest.display_type = self.display_type_var.get()
        self.quest.lore_normal = self.lore_normal_editor.get_list()
        self.quest.lore_started = self.lore_started_editor.get_list()
        self.quest.rewards = self.rewards_editor.get_list()

        self.quest.sort_order = int(self.sort_order_var.get())
        self.quest.repeatable = bool(self.repeatable_var.get())
        self.quest.cooldown_enabled = bool(self.cooldown_enabled_var.get())
        self.quest.cooldown_time = int(self.cooldown_time_var.get())
        self.quest.requires = self.requires_editor.get_list()


# =========================
# Main app
# =========================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SkyBlock Quests Creator")
        self.geometry("980x720")

        self.quests: list[Quest] = []
        self.quest_tabs: list[QuestTab] = []

        self._build_setup_ui()

    def _build_setup_ui(self):
        self.setup_frame = ttk.Frame(self)
        self.setup_frame.pack(fill="both", expand=True, padx=14, pady=14)

        box = ttk.LabelFrame(self.setup_frame, text="Impostazioni iniziali")
        box.pack(fill="x", pady=10)

        ttk.Label(box, text="1) Numero quest da creare (range)").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.count_var = tk.IntVar(value=3)
        ttk.Spinbox(box, from_=1, to=200, textvariable=self.count_var, width=10).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 4))

        ttk.Label(box, text="2) Nome categoria (ID) es: mining").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.category_var = tk.StringVar(value="mining")
        ttk.Entry(box, textvariable=self.category_var).grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(box, text="3) Nome visualizzato ai player (display) es: Miniera").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.category_display_var = tk.StringVar(value="Miniera")
        ttk.Entry(box, textvariable=self.category_display_var).grid(row=2, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(box, text="4) Ultimo sort-order esistente (<=0 per iniziare da 1)").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        self.last_sort_var = tk.IntVar(value=0)
        ttk.Spinbox(box, from_=-999999, to=999999, textvariable=self.last_sort_var, width=10).grid(row=3, column=1, sticky="w", padx=10, pady=4)

        box.columnconfigure(1, weight=1)

        # Placeholder format settings
        ph = ttk.LabelFrame(self.setup_frame, text="Formato placeholders (automatici)")
        ph.pack(fill="x", pady=10)

        ttk.Label(ph, text="placeholders: chiave (es: progress-{task})").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.ph_key_fmt_var = tk.StringVar(value="progress-{task}")
        ttk.Entry(ph, textvariable=self.ph_key_fmt_var).grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 4))

        ttk.Label(ph, text="placeholders: valore (usa {label} {progress} {goal})").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.ph_val_fmt_var = tk.StringVar(value="&7{label} &f{progress}&8/&f{goal}")
        ttk.Entry(ph, textvariable=self.ph_val_fmt_var).grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(ph, text="progress-placeholders: valore (usa {label} {progress} {goal})").grid(row=2, column=0, sticky="w", padx=10, pady=(4, 10))
        self.ph_prog_val_fmt_var = tk.StringVar(value="&7{label} &f{progress}&8/&f{goal}")
        ttk.Entry(ph, textvariable=self.ph_prog_val_fmt_var).grid(row=2, column=1, sticky="ew", padx=10, pady=(4, 10))

        ph.columnconfigure(1, weight=1)

        btns = ttk.Frame(self.setup_frame)
        btns.pack(fill="x", pady=10)
        ttk.Button(btns, text="Conferma", command=self._confirm_setup).pack(side="right", padx=5)
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side="right", padx=5)

    def _placeholder_cfg(self) -> dict:
        return {
            "placeholders_key_fmt": self.ph_key_fmt_var.get().strip() or "progress-{task}",
            "placeholders_value_fmt": self.ph_val_fmt_var.get().strip() or "&7{label} &f{progress}&8/&f{goal}",
            "progress_value_fmt": self.ph_prog_val_fmt_var.get().strip() or "&7{label} &f{progress}&8/&f{goal}",
        }

    def _confirm_setup(self):
        count = int(self.count_var.get())
        category = self.category_var.get().strip()
        category_display = self.category_display_var.get().strip()
        last_sort = int(self.last_sort_var.get())

        if not category:
            messagebox.showerror("Errore", "La categoria non può essere vuota.", parent=self)
            return
        if count <= 0:
            messagebox.showerror("Errore", "Il range deve essere >= 1.", parent=self)
            return

        # Crea quest
        self.quests.clear()
        base = 0 if last_sort <= 0 else last_sort

        for i in range(1, count + 1):
            sort_order = base + i if base > 0 else i
            quest_id = f"{category}{sort_order}"

            q = Quest(
                quest_id=quest_id,
                sort_order=sort_order,
                category=category,
                display_name=f"&e{category_display} {sort_order}",
                display_type="STONE",
                lore_normal=[
                    "&6Obiettivo:",
                    "&8 - &7Configura le task qui sotto",
                    "",
                    "&c&l ✘ &7Non iniziata.",
                ],
                lore_started=[
                    "",
                ],
                rewards=[],
                repeatable=False,
                cooldown_enabled=True,
                cooldown_time=1440,
                requires=[],
            )

            # Regola requires automatica (catena)
            if sort_order > 1 and (last_sort > 0 or i > 1):
                prev_id = f"{category}{sort_order - 1}"
                q.requires = [prev_id]

            self.quests.append(q)

        # Passa a UI notebook
        self.setup_frame.destroy()
        self._build_editor_ui()

    def _build_editor_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="Schede quest: configura tutto e poi premi 'Salva' per generare i file .yml").pack(anchor="w")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.quest_tabs.clear()
        for q in self.quests:
            tab = QuestTab(self.nb, q, placeholder_cfg_getter=self._placeholder_cfg)
            self.nb.add(tab, text=q.quest_id)
            self.quest_tabs.append(tab)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(bottom, text="Salva", command=self._save_all).pack(side="right")

    def _save_all(self):
        # sincronizza UI -> model
        for tab in self.quest_tabs:
            tab.apply_ui_to_model()

        # salva
        try:
            for q in self.quests:
                self._save_quest_yaml(q)
        except Exception as e:
            messagebox.showerror("Errore", f"Salvataggio fallito: {e}", parent=self)
            return

        messagebox.showinfo("OK", "File YAML salvati correttamente nella cartella 'quests/'.", parent=self)

    def _save_quest_yaml(self, q: Quest):
        # Sezione tasks nel formato del plugin:
        # tasks:
        #   stone:
        #     type: "blockbreak"
        #     amount: 64
        #     block: STONE
        tasks_out = {}
        for tname, task in q.tasks.items():
            tdict = {"type": task.type}
            tdict.update(task.params)
            tasks_out[tname] = tdict

        # placeholders auto
        # NB: per coerenza con i template metto anche "placeholders" + "progress-placeholders"
        tab = next((t for t in self.quest_tabs if t.quest is q), None)
        placeholders, progress_placeholders = tab.generate_placeholders() if tab else ({}, {})

        out = {
            "tasks": tasks_out,
            "display": {
                "name": q.display_name,
                "lore-normal": q.lore_normal,
                "lore-started": q.lore_started,
                "type": q.display_type,
            },
            "rewards": q.rewards,
            "placeholders": placeholders,
            "progress-placeholders": progress_placeholders,
            "options": {
                "category": q.category,
                "repeatable": q.repeatable,
                "requires": q.requires if q.requires else None,  # se vuota la tolgo dopo
                "cooldown": {
                    "enabled": q.cooldown_enabled,
                    "time": q.cooldown_time,
                },
                "sort-order": q.sort_order,
            },
        }

        # pulizia: rimuovo requires se None (per non mettere "requires: null")
        if out["options"].get("requires") is None:
            out["options"].pop("requires", None)

        # crea cartelle e scrive file
        base_dir = Path("quests") / q.category
        base_dir.mkdir(parents=True, exist_ok=True)

        file_path = base_dir / f"{q.quest_id}.yml"
        content = yaml_dump(out) + "\n"
        file_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    App().mainloop()