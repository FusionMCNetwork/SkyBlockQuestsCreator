import random
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk, messagebox


# =========================
# Helpers
# =========================
def int_to_roman(n: int) -> str:
    """Converte un intero positivo in numeri romani (formato latino)."""
    if n <= 0:
        return str(n)
    pairs = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    for value, sym in pairs:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


# =========================
# YAML minimal dumper (senza PyYAML)
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

    return f"{sp}{_yaml_quote(str(data))}"


# =========================
# Task definitions (schema)
# =========================
TASK_DEFS = {
    "blockbreak": {
        "required": {"amount": ("int", None)},
        "optional": {
            "block": ("str", ""),
            "blocks": ("list[str]", []),
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
            "item": ("str", ""),
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
            "hostile": ("str", ""),  # vuoto oppure "true"/"false"
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
    "enchanting": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),
            "enchantment": ("list[str]", []),
            # min-level: opzionale, default null -> se vuoto NON va scritto nel yaml e NON randomizzato
            "min-level": ("opt_int", None),
            "worlds": ("list[str]", []),
        },
        "mutex_groups": [],
    },
    # === NUOVA TASK: interact ===
    "interact": {
        "required": {"amount": ("int", None)},
        "optional": {
            "item": ("str", ""),
            "exact-match": ("bool", True),

            "block": ("str", ""),
            "blocks": ("list[str]", []),

            "action": ("str", ""),
            "actions": ("list[str]", []),

            "use-interacted-block-result": ("str", ""),
            "use-interacted-block-results": ("list[str]", []),

            "use-item-in-hand-result": ("str", ""),
            "use-item-in-hand-results": ("list[str]", []),

            "worlds": ("list[str]", []),
        },
        "mutex_groups": [
            ("block", "blocks"),
            ("action", "actions"),
            ("use-interacted-block-result", "use-interacted-block-results"),
            ("use-item-in-hand-result", "use-item-in-hand-results"),
        ],
    },
}

TASK_TYPES = list(TASK_DEFS.keys())

# task-type -> task-title (titoli “belli” per i player)
TASK_TYPE_TITLES = {
    "blockbreak": "Scava",
    "blockplace": "Piazza",
    "neobrewing": "Crafta",
    "consume": "Consuma",
    "crafting": "Crafta",
    "farming": "Coltiva",
    "inventory": "Ottieni",
    "mobkilling": "Uccidi",
    "smelting": "Cuoci",
    "smithing": "Forgia",
    "enchanting": "Incanta",
    "interact": "Interagisci",
}


# =========================
# Data model
# =========================
@dataclass
class Task:
    name: str
    type: str
    params: dict = field(default_factory=dict)
    label: str = ""  # usata per lore-started + placeholders (titolo obiettivo)


@dataclass
class Quest:
    quest_id: str
    sort_order: int
    category: str
    category_display: str

    tasks: dict = field(default_factory=dict)  # name -> Task

    display_name: str = ""
    display_type: str = "STONE"

    lore_normal: list = field(default_factory=list)
    lore_started: list = field(default_factory=list)

    rewards: list = field(default_factory=list)  # comandi minecraft

    repeatable: bool = False
    cooldown_enabled: bool = True
    cooldown_time: int = 1440
    requires: list = field(default_factory=list)

    # placeholders modificabili
    placeholders_override: dict = field(default_factory=dict)  # key -> value
    progress_placeholders_override: dict = field(default_factory=dict)  # taskName -> value

    # premi mostrati nel lore (sezione "Premi:") - NON sono comandi
    lore_reward_lines: list = field(default_factory=list)

    # lore: permetti modifica manuale senza farsi sovrascrivere dall'auto
    lore_normal_manual: bool = False
    lore_started_manual: bool = False

    # display auto in numeri romani
    display_auto: bool = True


# =========================
# UI helpers
# =========================
class ListEditor(tk.Frame):
    """Editor listbox con Aggiungi/Modifica/Rimuovi (usato per rewards comandi, requires, ecc.)."""

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

        def save():
            result["value"] = var.get()
            win.destroy()

        def cancel():
            win.destroy()

        ttk.Button(btns, text="Salva", command=save).grid(row=0, column=0, padx=5)
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
    """Dialog per list[str] (una riga = un valore) con tasto SALVA."""

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

        def save():
            content = txt.get("1.0", "end").splitlines()
            while content and content[-1] == "":
                content.pop()
            result["value"] = content
            win.destroy()

        def cancel():
            win.destroy()

        ttk.Button(btns, text="Salva", command=save).pack(side="left", padx=5)
        ttk.Button(btns, text="Annulla", command=cancel).pack(side="left", padx=5)

        win.wait_window()
        return result["value"]


class DictTextDialog:
    """
    Editor per dict YAML-like: 1 riga = "chiave: valore"
    (split sul primo ':', il resto è valore). Ha tasto SALVA.
    """

    @staticmethod
    def ask_dict(master, title: str, initial_dict: dict) -> dict | None:
        win = tk.Toplevel(master)
        win.title(title)
        win.geometry("700x420")
        win.grab_set()

        ttk.Label(
            win,
            text="Formato: una riga per entry, es: chiave: valore (split sul primo ':').\n"
                 "Suggerimento: puoi aggiungere entry custom.",
        ).pack(anchor="w", padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True, padx=10, pady=6)

        lines = []
        for k, v in (initial_dict or {}).items():
            lines.append(f"{k}: {v}")
        txt.insert("1.0", "\n".join(lines))

        btns = ttk.Frame(win)
        btns.pack(anchor="e", padx=10, pady=10)

        result = {"value": None}

        def save():
            raw_lines = txt.get("1.0", "end").splitlines()
            out = {}
            for ln in raw_lines:
                if not ln.strip():
                    continue
                if ":" not in ln:
                    messagebox.showerror("Errore", f"Riga non valida (manca ':'): {ln}", parent=win)
                    return
                k, v = ln.split(":", 1)
                k = k.strip()
                v = v.lstrip()
                if not k:
                    messagebox.showerror("Errore", f"Chiave vuota nella riga: {ln}", parent=win)
                    return
                out[k] = v
            result["value"] = out
            win.destroy()

        def cancel():
            win.destroy()

        ttk.Button(btns, text="Salva", command=save).pack(side="left", padx=5)
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
        self.win.geometry("560x560")
        self.win.grab_set()

        container = ttk.Frame(self.win)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.columnconfigure(0, weight=1)

        ttk.Label(container, text="Label (Nome obiettivo per lore-started / placeholders):").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.label_var = tk.StringVar(value=initial_label or "")
        ttk.Entry(container, textvariable=self.label_var).grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.fields = {}  # key -> (ftype, holder)

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
                    ttk.Entry(container, textvariable=var).grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "opt_int":
                    var = tk.StringVar(value="" if init_value is None else str(init_value))
                    ttk.Entry(container, textvariable=var).grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "bool":
                    var = tk.BooleanVar(value=bool(init_value))
                    ttk.Checkbutton(container, variable=var, text="true/false").grid(row=row, column=0, sticky="w", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "str":
                    var = tk.StringVar(value=str(init_value) if init_value is not None else "")
                    ttk.Entry(container, textvariable=var).grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                elif ftype == "list[str]":
                    ttk.Button(container, text="Modifica lista...", command=lambda k=key: self._edit_list(k)).grid(
                        row=row, column=0, sticky="w", pady=(0, 8)
                    )
                    self.fields[key] = (ftype, list(init_value or []))

                else:
                    var = tk.StringVar(value=str(init_value))
                    ttk.Entry(container, textvariable=var).grid(row=row, column=0, sticky="ew", pady=(0, 8))
                    self.fields[key] = (ftype, var)

                row += 1

        ttk.Label(container, text="Nota: per campi mutuamente esclusivi (es. block/blocks) valorizzane solo uno.").grid(
            row=row, column=0, sticky="w", pady=(8, 0)
        )
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

    def _read_field(self, key: str, ftype: str):
        _t, holder = self.fields[key]
        if ftype == "int":
            s = holder.get().strip()
            try:
                return int(s)
            except ValueError:
                messagebox.showerror("Errore", f"'{key}' deve essere un numero intero.", parent=self.win)
                raise

        if ftype == "opt_int":
            s = holder.get().strip()
            if s == "":
                return None
            try:
                return int(s)
            except ValueError:
                messagebox.showerror("Errore", f"'{key}' deve essere un numero intero oppure vuoto.", parent=self.win)
                raise

        if ftype == "bool":
            return bool(holder.get())
        if ftype == "str":
            return holder.get()
        if ftype == "list[str]":
            return list(holder)
        return holder.get()

    def _ok(self):
        schema = TASK_DEFS[self.task_type]

        params = {}
        for key, (ftype, _default) in schema["required"].items():
            params[key] = self._read_field(key, ftype)

        for key, (ftype, _default) in schema["optional"].items():
            val = self._read_field(key, ftype)

            if ftype == "str":
                if val != "":
                    params[key] = val
            elif ftype == "list[str]":
                if val:
                    params[key] = val
            elif ftype == "opt_int":
                if val is not None:
                    params[key] = val
            elif ftype == "bool":
                params[key] = val
            elif ftype == "int":
                params[key] = val
            else:
                if val is not None:
                    params[key] = val

        for a, b in schema.get("mutex_groups", []):
            a_present = a in params and (
                (isinstance(params[a], str) and params[a] != "")
                or (isinstance(params[a], list) and len(params[a]) > 0)
            )
            b_present = b in params and (
                (isinstance(params[b], str) and params[b] != "")
                or (isinstance(params[b], list) and len(params[b]) > 0)
            )
            if a_present and b_present:
                messagebox.showerror("Errore", f"I campi '{a}' e '{b}' non possono essere entrambi valorizzati.", parent=self.win)
                return

        label = self.label_var.get().strip()
        self.result = (params, label)
        self.win.destroy()

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

        self.body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._build()

    def _task_category_title(self, task_type: str) -> str:
        return TASK_TYPE_TITLES.get(task_type, task_type)

    def _set_text_view(self, widget: tk.Text, content: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _rebuild_lore(self):
        # Se l'utente ha messo manuale, non sovrascrivo quella sezione
        grouped: dict[str, list[tuple[str, str]]] = {}
        for tname, task in self.quest.tasks.items():
            cat = self._task_category_title(task.type)
            grouped.setdefault(cat, [])
            title = (task.label or tname).strip() or tname
            grouped[cat].append((tname, title))

        if not self.quest.lore_normal_manual:
            lore_normal: list[str] = []
            for cat in sorted(grouped.keys()):
                lore_normal.append(f"&6{cat}:")
                for _tname, title in grouped[cat]:
                    lore_normal.append(f"&8- &7{title}")

            lore_normal.append("")
            lore_normal.append("&6Premi:")
            for line in (self.quest.lore_reward_lines or []):
                lore_normal.append(f"&8- &7{line}")
            lore_normal.append("")
            lore_normal.append("&c&l ✘ &7Non iniziata.")

            self.quest.lore_normal = lore_normal

        if not self.quest.lore_started_manual:
            lore_started: list[str] = [""]
            for tname, task in self.quest.tasks.items():
                title = (task.label or tname).strip() or tname
                lore_started.append(f"&6{title}: &7{{{tname}:progress}}/{{{tname}:goal}}")

            self.quest.lore_started = lore_started

        self._set_text_view(self.lore_normal_view, "\n".join(self.quest.lore_normal))
        self._set_text_view(self.lore_started_view, "\n".join(self.quest.lore_started))

    def _edit_lore_rewards(self):
        edited = MultiLineTextDialog.ask_list(self, "Modifica premi (lore)", list(self.quest.lore_reward_lines or []))
        if edited is None:
            return
        self.quest.lore_reward_lines = edited
        # aggiornare la lore-normal solo se non è manuale
        self._rebuild_lore()

    def _edit_lore_normal(self):
        edited = MultiLineTextDialog.ask_list(self, "Modifica lore-normal", list(self.quest.lore_normal or []))
        if edited is None:
            return
        self.quest.lore_normal = edited
        self.quest.lore_normal_manual = True
        self._rebuild_lore()

    def _edit_lore_started(self):
        edited = MultiLineTextDialog.ask_list(self, "Modifica lore-started", list(self.quest.lore_started or []))
        if edited is None:
            return
        self.quest.lore_started = edited
        self.quest.lore_started_manual = True
        self._rebuild_lore()

    def _reset_lore_auto(self):
        if not messagebox.askyesno("Conferma", "Vuoi ripristinare le lore automatiche (sovrascrive le modifiche manuali)?", parent=self):
            return
        self.quest.lore_normal_manual = False
        self.quest.lore_started_manual = False
        self._rebuild_lore()

    def _default_display_name(self) -> str:
        roman = int_to_roman(int(self.sort_order_var.get()))
        return f"&e{self.quest.category_display} {roman}"

    def _on_sort_order_change(self, *_):
        if self.display_auto_var.get():
            self.display_name_var.set(self._default_display_name())

    def _on_display_auto_toggle(self):
        if self.display_auto_var.get():
            self.display_name_var.set(self._default_display_name())

    def _build(self):
        # ===== Tasks
        tasks_box = ttk.LabelFrame(self.body, text="Tasks")
        tasks_box.pack(fill="x", padx=10, pady=10)

        cols = ("name", "type")
        self.tasks_tree = ttk.Treeview(tasks_box, columns=cols, show="headings", height=6)
        self.tasks_tree.heading("name", text="Nome")
        self.tasks_tree.heading("type", text="Tipo")
        self.tasks_tree.column("name", width=220)
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
        display_box.columnconfigure(0, weight=1)
        display_box.columnconfigure(1, weight=1)

        ttk.Label(display_box, text="name").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.display_name_var = tk.StringVar(value=self.quest.display_name)
        ttk.Entry(display_box, textvariable=self.display_name_var).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        ttk.Label(display_box, text="type (materiale Minecraft)").grid(row=0, column=1, sticky="w", padx=8, pady=(8, 2))
        self.display_type_var = tk.StringVar(value=self.quest.display_type)
        ttk.Entry(display_box, textvariable=self.display_type_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))

        auto_frame = ttk.Frame(display_box)
        auto_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self.display_auto_var = tk.BooleanVar(value=self.quest.display_auto)
        ttk.Checkbutton(
            auto_frame,
            text="Display name automatico (numero romano)",
            variable=self.display_auto_var,
            command=self._on_display_auto_toggle,
        ).pack(side="left")

        # ===== Lore
        lore_box = ttk.LabelFrame(self.body, text="Lore")
        lore_box.pack(fill="x", padx=10, pady=10)

        lore_btns = ttk.Frame(lore_box)
        lore_btns.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Button(lore_btns, text="Modifica lore-normal...", command=self._edit_lore_normal).pack(side="left")
        ttk.Button(lore_btns, text="Modifica lore-started...", command=self._edit_lore_started).pack(side="left", padx=8)
        ttk.Button(lore_btns, text="Modifica premi (lore)...", command=self._edit_lore_rewards).pack(side="left", padx=8)
        ttk.Button(lore_btns, text="Reset lore (auto)", command=self._reset_lore_auto).pack(side="right")

        lore_frame = ttk.Frame(lore_box)
        lore_frame.pack(fill="x", padx=8, pady=8)
        lore_frame.columnconfigure(0, weight=1)
        lore_frame.columnconfigure(1, weight=1)

        ttk.Label(lore_frame, text="lore-normal").grid(row=0, column=0, sticky="w")
        ttk.Label(lore_frame, text="lore-started").grid(row=0, column=1, sticky="w")

        self.lore_normal_view = tk.Text(lore_frame, height=12, wrap="none")
        self.lore_started_view = tk.Text(lore_frame, height=12, wrap="none")
        self.lore_normal_view.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(4, 0))
        self.lore_started_view.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(4, 0))
        self.lore_normal_view.configure(state="disabled")
        self.lore_started_view.configure(state="disabled")

        # ===== Rewards (comandi)
        rewards_box = ttk.LabelFrame(self.body, text="Rewards (comandi Minecraft)")
        rewards_box.pack(fill="x", padx=10, pady=10)
        self.rewards_editor = ListEditor(rewards_box, "Lista rewards", self.quest.rewards)
        self.rewards_editor.pack(fill="both", expand=True)

        # ===== Placeholders
        ph_box = ttk.LabelFrame(self.body, text="Placeholders (auto + modificabili)")
        ph_box.pack(fill="x", padx=10, pady=10)

        ph_btns = ttk.Frame(ph_box)
        ph_btns.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Button(ph_btns, text="Modifica placeholders...", command=self._edit_placeholders).pack(side="left", padx=(0, 8))
        ttk.Button(ph_btns, text="Modifica progress-placeholders...", command=self._edit_progress_placeholders).pack(side="left")
        ttk.Button(ph_btns, text="Reset override", command=self._reset_placeholders_override).pack(side="right")

        self.ph_preview = tk.Text(ph_box, height=9, wrap="none")
        self.ph_preview.pack(fill="x", padx=8, pady=8)
        self.ph_preview.configure(state="disabled")

        ttk.Button(ph_box, text="Aggiorna anteprima placeholders", command=self._update_placeholders_preview).pack(
            anchor="e", padx=8, pady=(0, 8)
        )

        # ===== Options
        opt_box = ttk.LabelFrame(self.body, text="Options")
        opt_box.pack(fill="x", padx=10, pady=10)
        opt_box.columnconfigure(1, weight=1)

        ttk.Label(opt_box, text="category").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.category_var = tk.StringVar(value=self.quest.category)
        ttk.Entry(opt_box, textvariable=self.category_var, state="disabled").grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 2))

        ttk.Label(opt_box, text="sort-order").grid(row=1, column=0, sticky="w", padx=8, pady=2)
        self.sort_order_var = tk.IntVar(value=self.quest.sort_order)
        ttk.Spinbox(opt_box, from_=1, to=999999, textvariable=self.sort_order_var, width=10).grid(
            row=1, column=1, sticky="w", padx=8, pady=2
        )
        self.sort_order_var.trace_add("write", self._on_sort_order_change)

        self.repeatable_var = tk.BooleanVar(value=self.quest.repeatable)
        ttk.Checkbutton(opt_box, text="repeatable", variable=self.repeatable_var).grid(row=2, column=1, sticky="w", padx=8, pady=2)

        cooldown_frame = ttk.Frame(opt_box)
        cooldown_frame.grid(row=3, column=1, sticky="w", padx=8, pady=2)

        self.cooldown_enabled_var = tk.BooleanVar(value=self.quest.cooldown_enabled)
        ttk.Checkbutton(cooldown_frame, text="cooldown.enabled", variable=self.cooldown_enabled_var).grid(row=0, column=0, padx=(0, 10))

        ttk.Label(cooldown_frame, text="cooldown.time (minuti)").grid(row=0, column=1, padx=(0, 6))
        self.cooldown_time_var = tk.IntVar(value=self.quest.cooldown_time)
        ttk.Spinbox(cooldown_frame, from_=0, to=10_000_000, textvariable=self.cooldown_time_var, width=10).grid(row=0, column=2)

        self.requires_editor = ListEditor(opt_box, "requires (quest richieste)", self.quest.requires)
        self.requires_editor.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)

        # stato iniziale
        if self.display_auto_var.get():
            self.display_name_var.set(self._default_display_name())
        self._rebuild_lore()
        self._update_placeholders_preview()

    # ----- Tasks management -----
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
        for key, (ftype, _default) in schema["required"].items():
            if ftype == "int":
                params[key] = random.randint(1, 64)
            else:
                params[key] = ""

        for key, (ftype, default) in schema["optional"].items():
            if ftype == "list[str]":
                params[key] = []
            elif ftype == "opt_int":
                params[key] = None
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
        # se le lore sono in auto, si aggiornano; se sono manuali, rimangono come sono
        self._rebuild_lore()
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
        self._rebuild_lore()
        self._update_placeholders_preview()

    def _remove_task(self):
        name = self._selected_task_name()
        if not name:
            return
        if messagebox.askyesno("Conferma", f"Rimuovere la task '{name}'?", parent=self):
            self.quest.tasks.pop(name, None)
            self._refresh_tasks_tree()
            self._rebuild_lore()
            self._update_placeholders_preview()

    # ----- Placeholders -----
    def _reset_placeholders_override(self):
        if not messagebox.askyesno("Conferma", "Vuoi resettare tutte le modifiche ai placeholders per questa quest?", parent=self):
            return
        self.quest.placeholders_override.clear()
        self.quest.progress_placeholders_override.clear()
        self._update_placeholders_preview()

    def _edit_placeholders(self):
        effective_placeholders, _ = self.generate_placeholders()
        edited = DictTextDialog.ask_dict(self, "Modifica placeholders", effective_placeholders)
        if edited is None:
            return
        self.quest.placeholders_override = edited
        self._update_placeholders_preview()

    def _edit_progress_placeholders(self):
        _, effective_progress = self.generate_placeholders()
        edited = DictTextDialog.ask_dict(self, "Modifica progress-placeholders", effective_progress)
        if edited is None:
            return
        self.quest.progress_placeholders_override = edited
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

    def _generate_placeholders_base(self) -> tuple[dict, dict]:
        cfg = self.placeholder_cfg_getter()
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

    def generate_placeholders(self) -> tuple[dict, dict]:
        base_placeholders, base_progress = self._generate_placeholders_base()
        placeholders = dict(self.quest.placeholders_override) if self.quest.placeholders_override else base_placeholders
        progress = dict(self.quest.progress_placeholders_override) if self.quest.progress_placeholders_override else base_progress
        return placeholders, progress

    def apply_ui_to_model(self):
        self.quest.display_auto = bool(self.display_auto_var.get())
        self.quest.display_name = self.display_name_var.get()
        self.quest.display_type = self.display_type_var.get()

        self.quest.rewards = self.rewards_editor.get_list()

        self.quest.sort_order = int(self.sort_order_var.get())
        self.quest.repeatable = bool(self.repeatable_var.get())
        self.quest.cooldown_enabled = bool(self.cooldown_enabled_var.get())
        self.quest.cooldown_time = int(self.cooldown_time_var.get())
        self.quest.requires = self.requires_editor.get_list()

        # assicurati che il model contenga l'ultima versione visualizzata
        self._rebuild_lore()


# =========================
# Main app
# =========================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SkyBlock Quests Creator")
        self.geometry("980x780")

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
        if not category_display:
            messagebox.showerror("Errore", "Il nome visualizzato non può essere vuoto.", parent=self)
            return
        if count <= 0:
            messagebox.showerror("Errore", "Il range deve essere >= 1.", parent=self)
            return

        self.quests.clear()
        base = 0 if last_sort <= 0 else last_sort

        for i in range(1, count + 1):
            sort_order = base + i if base > 0 else i
            quest_id = f"{category}{sort_order}"

            q = Quest(
                quest_id=quest_id,
                sort_order=sort_order,
                category=category,
                category_display=category_display,
                display_name=f"&e{category_display} {int_to_roman(sort_order)}",
                display_type="STONE",
                lore_normal=[],
                lore_started=[""],
                rewards=[],
                repeatable=False,
                cooldown_enabled=True,
                cooldown_time=1440,
                requires=[],
                lore_reward_lines=[],
                lore_normal_manual=False,
                lore_started_manual=False,
                display_auto=True,
            )

            if sort_order > 1 and (last_sort > 0 or i > 1):
                prev_id = f"{category}{sort_order - 1}"
                q.requires = [prev_id]

            self.quests.append(q)

        self.setup_frame.destroy()
        self._build_editor_ui()

    def _build_editor_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Configura le quest e poi premi 'Salva' per generare i file .yml").pack(anchor="w")

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
        for tab in self.quest_tabs:
            tab.apply_ui_to_model()

        try:
            for q in self.quests:
                self._save_quest_yaml(q)
        except Exception as e:
            messagebox.showerror("Errore", f"Salvataggio fallito: {e}", parent=self)
            return

        messagebox.showinfo("OK", "File YAML salvati correttamente nella cartella 'quests/'.", parent=self)

    def _save_quest_yaml(self, q: Quest):
        tasks_out = {}
        for tname, task in q.tasks.items():
            tdict = {"type": task.type}
            tdict.update(task.params)
            tasks_out[tname] = tdict

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
                "requires": q.requires if q.requires else None,
                "cooldown": {
                    "enabled": q.cooldown_enabled,
                    "time": q.cooldown_time,
                },
                "sort-order": q.sort_order,
            },
        }

        if out["options"].get("requires") is None:
            out["options"].pop("requires", None)

        base_dir = Path("quests") / q.category
        base_dir.mkdir(parents=True, exist_ok=True)

        file_path = base_dir / f"{q.quest_id}.yml"
        content = yaml_dump(out) + "\n"
        file_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    App().mainloop()