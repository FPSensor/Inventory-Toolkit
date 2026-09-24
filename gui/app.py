"""
app.py — Inventory Toolkit Desktop GUI

Fully cross-platform (Linux / macOS / Windows) — no Windows-only APIs.
Built on tkinter + customtkinter (falls back to plain ttk when CTk is absent).

Layout:
  Top bar   — profile selector, [New Profile], [Setup Wizard], [Config Hub], [Exit]
  Tab row   — Cross Check | Stock Processing | YoY Sales Reports
  Status bar — async task progress

Config Hub window:
  Left sidebar  — config file list
  Right panel   — dynamic editor:
    dict_list   → category list + item list with Add / Import / Delete
    key_value   → field grid with Save button
    stores      → active stores + regional groups, fully interactive
    yoy_reports → structured editor (data_source, output, sizes, resumenes, structures)
    pricing     → structured editor (expected columns + aliases)
"""

import os
import sys
import json
import queue
import threading
import time
from argparse import Namespace

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    USE_CTK = True
    BaseWindow   = ctk.CTk
    BaseToplevel = ctk.CTkToplevel
    BaseFrame    = ctk.CTkFrame
    BaseButton   = ctk.CTkButton
    BaseLabel    = ctk.CTkLabel
    BaseEntry    = ctk.CTkEntry
    BaseTextbox  = ctk.CTkTextbox
    BaseScrollable = ctk.CTkScrollableFrame
except ImportError:
    import tkinter.ttk as ttk
    USE_CTK = False
    BaseWindow   = tk.Tk
    BaseToplevel = tk.Toplevel
    BaseFrame    = ttk.Frame
    BaseButton   = ttk.Button
    BaseLabel    = ttk.Label
    BaseEntry    = ttk.Entry
    BaseTextbox  = tk.Text
    BaseScrollable = ttk.Frame   # fallback — no scroll

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from core.configuration_manager import ConfigurationManager
from core.logger import log
from cli.wizard import initialize_profile_files, run_setup_wizard
from cli.utils import save_json, load_json
from engine.inventory_cross_check.generator import run_cross_check
from engine.stock_processing.generator import run_stock_processing
from engine.yoy_reports.generator import generate_sales_report

PROFILES_DIR = "profiles"

# ── Widget helpers ────────────────────────────────────────────────────────────

def _btn(parent, text, command, **kw):
    """Create a button with consistent styling."""
    if USE_CTK:
        return ctk.CTkButton(parent, text=text, command=command, **kw)
    else:
        b = ttk.Button(parent, text=text, command=command)
        return b


def _lbl(parent, text, **kw):
    if USE_CTK:
        return ctk.CTkLabel(parent, text=text, **kw)
    return ttk.Label(parent, text=text)


def _entry(parent, textvariable=None, **kw):
    if USE_CTK:
        return ctk.CTkEntry(parent, textvariable=textvariable, **kw)
    return ttk.Entry(parent, textvariable=textvariable)


def _pack_btn(btn, **kw):
    btn.pack(**kw)
    return btn


# ═════════════════════════════════════════════════════════════════════════════
# 1. CONFIG HUB WINDOW
# ═════════════════════════════════════════════════════════════════════════════

class ConfigHubWindow(BaseToplevel):
    """
    Central configuration editor window.
    Left sidebar lists all config files; right panel renders the appropriate editor.
    """

    _REGISTRY = {
        "Product Families":         ("general/familias.json",              "dict_list"),
        "General Settings":          ("general/settings.json",              "key_value"),
        "Active Stores & Groups":    ("general/stores.json",               "stores"),
        "Database Aliases":          ("general/databases.json",             "key_value"),
        "Stock Cleaning Rules":      ("stock_processing/cleaning.json",     "dict_list"),
        "Pricing Rules":             ("stock_processing/pricing.json",      "pricing"),
        "Cross Check Exclusions":    ("cross_check/cross_check_settings.json", "dict_list"),
        "YoY Report Structure":      ("yoy_reports/reports.json",           "yoy_reports"),
    }

    def __init__(self, parent, active_profile: str):
        super().__init__(parent)
        self.profile = active_profile
        self.title(f"Configuration Hub — [{self.profile}]")
        self.geometry("1040x680")
        self.minsize(900, 560)
        self.current_data = {}
        self._active_key = list(self._REGISTRY.keys())[0]
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Outer split: sidebar (left) + workspace (right)
        outer = BaseFrame(self)
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Sidebar ──
        sidebar = BaseFrame(outer, width=210)
        sidebar.pack(side="left", fill="y", padx=(0, 8))
        sidebar.pack_propagate(False)

        _lbl(sidebar, text="Configuration Files", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=8, pady=(8, 4))

        self._sidebar_buttons = {}
        for name in self._REGISTRY:
            b = _btn(sidebar, text=name,
                     command=lambda n=name: self._select(n),
                     width=190 if USE_CTK else None,
                     fg_color="transparent" if USE_CTK else None,
                     anchor="w" if USE_CTK else None)
            b.pack(fill="x", padx=4, pady=2)
            self._sidebar_buttons[name] = b

        # ── Workspace ──
        self._workspace = BaseFrame(outer)
        self._workspace.pack(side="left", fill="both", expand=True)

        self._select(self._active_key)

    def _select(self, name: str):
        self._active_key = name
        # Highlight active button
        for n, b in self._sidebar_buttons.items():
            if USE_CTK:
                b.configure(fg_color=("#1f538d" if n == name else "transparent"))
        self._reload()

    def _filepath(self):
        rel, _ = self._REGISTRY[self._active_key]
        return os.path.join(PROFILES_DIR, self.profile, "configs", rel)

    def _reload(self):
        for w in self._workspace.winfo_children():
            w.destroy()
        self.current_data = load_json(self._filepath()) or {}
        _, kind = self._REGISTRY[self._active_key]
        dispatch = {
            "dict_list":  self._render_dict_list,
            "key_value":  self._render_key_value,
            "stores":     self._render_stores,
            "yoy_reports":self._render_yoy_reports,
            "pricing":    self._render_pricing,
        }
        dispatch.get(kind, self._render_key_value)()

    def _save(self, data=None):
        save_json(self._filepath(), data if data is not None else self.current_data)

    # ── A. Dict-list editor ───────────────────────────────────────────────────

    def _render_dict_list(self):
        ws = self._workspace
        # Title
        _lbl(ws, text=self._active_key, font=("Arial", 13, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=10, pady=(8, 4))

        # Search + listbox (left) / items (right)
        paned = BaseFrame(ws)
        paned.pack(fill="both", expand=True, padx=10, pady=4)

        left = BaseFrame(paned, width=260)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        right = BaseFrame(paned)
        right.pack(side="left", fill="both", expand=True)

        # Search
        search_var = tk.StringVar()
        _entry(left, textvariable=search_var,
               placeholder_text="Filter categories..." if USE_CTK else None
               ).pack(fill="x", padx=4, pady=4)

        cat_lb = tk.Listbox(left,
                            bg="#2b2b2b" if USE_CTK else "white",
                            fg="white" if USE_CTK else "black",
                            selectbackground="#1f538d",
                            relief="flat", borderwidth=0)
        cat_lb.pack(fill="both", expand=True, padx=4, pady=2)

        def refresh_cats(*_):
            q = search_var.get().lower()
            cat_lb.delete(0, tk.END)
            for k in sorted(self.current_data.keys()):
                if q in k.lower():
                    v = self.current_data[k]
                    tag = f"({len(v)})" if isinstance(v, list) else "{dict}"
                    cat_lb.insert(tk.END, f"{k} {tag}")

        search_var.trace_add("write", refresh_cats)
        refresh_cats()

        # Category buttons
        cat_btns = BaseFrame(left)
        cat_btns.pack(fill="x", padx=4, pady=4)

        def add_cat():
            name = simpledialog.askstring("Add Category", "New category name:", parent=self)
            if name and name.strip() and name.strip() not in self.current_data:
                self.current_data[name.strip()] = []
                self._save()
                refresh_cats()

        def del_cat():
            sel = cat_lb.curselection()
            if not sel:
                return
            cat = cat_lb.get(sel[0]).rsplit(" ", 1)[0]
            if messagebox.askyesno("Delete", f"Delete category '{cat}'?", parent=self):
                self.current_data.pop(cat, None)
                self._save()
                refresh_cats()
                for w in right.winfo_children():
                    w.destroy()

        _btn(cat_btns, "➕ Add", add_cat, width=90 if USE_CTK else None).pack(side="left", padx=2)
        _btn(cat_btns, "🗑️ Delete", del_cat, width=90 if USE_CTK else None).pack(side="left", padx=2)

        def on_cat_select(_evt=None):
            sel = cat_lb.curselection()
            if not sel:
                return
            cat = cat_lb.get(sel[0]).rsplit(" ", 1)[0]
            self._render_item_panel(right, cat, refresh_cats)

        cat_lb.bind("<<ListboxSelect>>", on_cat_select)

    def _render_item_panel(self, parent, cat_name: str, refresh_cb):
        for w in parent.winfo_children():
            w.destroy()
        if cat_name not in self.current_data:
            return

        val = self.current_data[cat_name]
        _lbl(parent, text=f"Category: {cat_name}",
             font=("Arial", 12, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=8, pady=(4, 2))

        if isinstance(val, list):
            item_lb = tk.Listbox(parent,
                                 bg="#2b2b2b" if USE_CTK else "white",
                                 fg="white" if USE_CTK else "black",
                                 selectbackground="#1f538d",
                                 relief="flat", borderwidth=0)
            item_lb.pack(fill="both", expand=True, padx=8, pady=4)
            for itm in val:
                item_lb.insert(tk.END, str(itm))

            btn_row = BaseFrame(parent)
            btn_row.pack(fill="x", padx=8, pady=6)

            def add_item():
                raw = simpledialog.askstring(
                    "Add Item", "Value(s) — comma-separated for bulk:", parent=self)
                if raw:
                    for entry in [x.strip() for x in raw.split(",") if x.strip()]:
                        if entry not in self.current_data[cat_name]:
                            self.current_data[cat_name].append(entry)
                    self._save()
                    self._render_item_panel(parent, cat_name, refresh_cb)
                    refresh_cb()

            def import_excel():
                path = filedialog.askopenfilename(
                    filetypes=[("Excel Files", "*.xlsx *.xls")], parent=self)
                if path and os.path.exists(path) and PANDAS_AVAILABLE:
                    try:
                        df = pd.read_excel(path, nrows=20)
                        added = 0
                        for c in df.columns:
                            if str(c) not in self.current_data[cat_name]:
                                self.current_data[cat_name].append(str(c))
                                added += 1
                        self._save()
                        self._render_item_panel(parent, cat_name, refresh_cb)
                        refresh_cb()
                        messagebox.showinfo("Import", f"Imported {added} column names.", parent=self)
                    except Exception as err:
                        messagebox.showerror("Error", str(err), parent=self)

            def del_item():
                sel = item_lb.curselection()
                if not sel:
                    return
                itm = item_lb.get(sel[0])
                try:
                    self.current_data[cat_name].remove(itm)
                except ValueError:
                    pass
                self._save()
                self._render_item_panel(parent, cat_name, refresh_cb)
                refresh_cb()

            _btn(btn_row, "➕ Add",             add_item).pack(side="left", padx=4)
            _btn(btn_row, "📊 From Excel",      import_excel).pack(side="left", padx=4)
            _btn(btn_row, "🗑️ Delete Selected", del_item).pack(side="left", padx=4)

        elif isinstance(val, dict):
            # Inline sub-dict editor
            entries = {}
            row_frame = BaseScrollable(parent) if USE_CTK else BaseFrame(parent)
            row_frame.pack(fill="both", expand=True, padx=8, pady=4)
            for i, (k, v) in enumerate(sorted(val.items())):
                _lbl(row_frame, text=f"{k}:").grid(row=i, column=0, sticky="w", padx=4, pady=3)
                var = tk.StringVar(value=str(v))
                _entry(row_frame, textvariable=var, width=260 if USE_CTK else None
                       ).grid(row=i, column=1, sticky="ew", padx=4, pady=3)
                entries[k] = var
            row_frame.columnconfigure(1, weight=1)

            def save_sub():
                for k, var in entries.items():
                    raw = var.get().strip()
                    if raw.lower() in ("true", "yes"):
                        self.current_data[cat_name][k] = True
                    elif raw.lower() in ("false", "no"):
                        self.current_data[cat_name][k] = False
                    elif raw.lstrip("-").isdigit():
                        self.current_data[cat_name][k] = int(raw)
                    else:
                        self.current_data[cat_name][k] = raw
                self._save()
                messagebox.showinfo("Saved", "Sub-dictionary saved.", parent=self)

            _btn(parent, "💾 Save", save_sub).pack(anchor="e", padx=8, pady=6)

    # ── B. Key-value editor ───────────────────────────────────────────────────

    def _render_key_value(self):
        ws = self._workspace
        _lbl(ws, text=self._active_key, font=("Arial", 13, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=10, pady=(8, 4))

        container = BaseScrollable(ws) if USE_CTK else BaseFrame(ws)
        container.pack(fill="both", expand=True, padx=10, pady=4)

        entries = {}
        for i, (k, v) in enumerate(sorted(self.current_data.items())):
            _lbl(container, text=f"{k}:", width=220 if USE_CTK else None, anchor="w"
                 ).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            var = tk.StringVar(value=str(v))
            _entry(container, textvariable=var, width=320 if USE_CTK else None
                   ).grid(row=i, column=1, sticky="ew", padx=6, pady=4)
            entries[k] = var

        try:
            container.columnconfigure(1, weight=1)
        except Exception:
            pass

        def save_kv():
            for k, var in entries.items():
                raw = var.get().strip()
                old = self.current_data.get(k)
                if isinstance(old, bool):
                    self.current_data[k] = raw.lower() in ("true", "yes", "1")
                elif isinstance(old, int) and raw.lstrip("-").isdigit():
                    self.current_data[k] = int(raw)
                else:
                    self.current_data[k] = raw
            self._save()
            messagebox.showinfo("Saved", "Settings saved successfully.", parent=self)

        _btn(ws, "💾 Save Configuration", save_kv).pack(anchor="e", padx=10, pady=8)

    # ── C. Stores editor ──────────────────────────────────────────────────────

    def _render_stores(self):
        ws = self._workspace
        _lbl(ws, text="Active Stores & Regional Groups",
             font=("Arial", 13, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=10, pady=(8, 4))

        def rebuild():
            for w in ws.winfo_children()[1:]:
                w.destroy()
            data = self.current_data
            activos = data.get("locales_activos", [])
            grupos  = data.get("grupos_regionales", {})

            # ── Active stores ─────────────────────────────────────────────────
            _lbl(ws, text="📍 Active Stores").pack(anchor="w", padx=10, pady=(6, 2))
            stores_lb = tk.Listbox(ws, height=6,
                                   bg="#2b2b2b" if USE_CTK else "white",
                                   fg="white" if USE_CTK else "black",
                                   selectbackground="#1f538d", relief="flat")
            stores_lb.pack(fill="x", padx=12, pady=2)
            for s in activos:
                stores_lb.insert(tk.END, s)

            st_row = BaseFrame(ws)
            st_row.pack(fill="x", padx=12, pady=4)

            def add_store():
                raw = simpledialog.askstring(
                    "Add Stores", "Store name(s) — comma-separated:", parent=self)
                if raw:
                    for s in [x.strip() for x in raw.split(",") if x.strip()]:
                        if s not in activos:
                            activos.append(s)
                    data["locales_activos"] = activos
                    self._save(data)
                    rebuild()

            def del_store():
                sel = stores_lb.curselection()
                if not sel:
                    return
                name = stores_lb.get(sel[0])
                activos.remove(name)
                data["locales_activos"] = activos
                self._save(data)
                rebuild()

            _btn(st_row, "➕ Add Store",    add_store).pack(side="left", padx=4)
            _btn(st_row, "🗑️ Delete Store", del_store).pack(side="left", padx=4)

            # ── Regional groups ───────────────────────────────────────────────
            _lbl(ws, text="🗂️ Regional Groups").pack(anchor="w", padx=10, pady=(10, 2))
            grp_lb = tk.Listbox(ws, height=6,
                                bg="#2b2b2b" if USE_CTK else "white",
                                fg="white" if USE_CTK else "black",
                                selectbackground="#1f538d", relief="flat")
            grp_lb.pack(fill="x", padx=12, pady=2)
            for grp, members in sorted(grupos.items()):
                grp_lb.insert(tk.END, f"{grp}  →  {', '.join(members)}")

            grp_row = BaseFrame(ws)
            grp_row.pack(fill="x", padx=12, pady=4)

            def add_group():
                gname = simpledialog.askstring("New Group", "Group name:", parent=self)
                if not gname:
                    return
                raw = simpledialog.askstring(
                    "Group Members", f"Stores for '{gname}' (comma-separated):", parent=self)
                grupos[gname] = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
                data["grupos_regionales"] = grupos
                self._save(data)
                rebuild()

            def del_group():
                sel = grp_lb.curselection()
                if not sel:
                    return
                gname = grp_lb.get(sel[0]).split("  →  ")[0]
                if messagebox.askyesno("Delete Group", f"Delete group '{gname}'?", parent=self):
                    grupos.pop(gname, None)
                    data["grupos_regionales"] = grupos
                    self._save(data)
                    rebuild()

            def edit_group():
                sel = grp_lb.curselection()
                if not sel:
                    return
                gname = grp_lb.get(sel[0]).split("  →  ")[0]
                curr = ", ".join(grupos.get(gname, []))
                raw = simpledialog.askstring(
                    "Edit Group", f"Stores for '{gname}':", initialvalue=curr, parent=self)
                if raw is not None:
                    grupos[gname] = [s.strip() for s in raw.split(",") if s.strip()]
                    data["grupos_regionales"] = grupos
                    self._save(data)
                    rebuild()

            _btn(grp_row, "➕ New Group",   add_group).pack(side="left", padx=4)
            _btn(grp_row, "✏️ Edit Group",  edit_group).pack(side="left", padx=4)
            _btn(grp_row, "🗑️ Delete Group",del_group).pack(side="left", padx=4)

        rebuild()

    # ── D. YoY reports editor ─────────────────────────────────────────────────

    def _render_yoy_reports(self):
        ws = self._workspace
        _lbl(ws, text="YoY Report Structure",
             font=("Arial", 13, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=10, pady=(8, 4))

        if USE_CTK:
            tabs = ctk.CTkTabview(ws)
        else:
            tabs = tk.ttk.Notebook(ws)
        tabs.pack(fill="both", expand=True, padx=8, pady=4)

        def _add_tab(label):
            if USE_CTK:
                return tabs.add(label)
            frame = ttk.Frame(tabs)
            tabs.add(frame, text=label)
            return frame

        tab_ds     = _add_tab("Data Source")
        tab_output = _add_tab("Output")
        tab_sizes  = _add_tab("Sizes")
        tab_sum    = _add_tab("Summaries")
        tab_struct = _add_tab("Structures")

        data = self.current_data
        ds   = data.get("data_source", {})

        # ── Data source tab ───────────────────────────────────────────────────
        ds_fields = [
            ("date_column",     "Date column"),
            ("quantity_column", "Quantity column"),
            ("item_column",     "Item / SKU column"),
            ("grouping_column", "Grouping column (Family)"),
            ("branch_column",   "Branch / Store column"),
        ]
        ds_vars = {}
        for i, (k, lbl) in enumerate(ds_fields):
            _lbl(tab_ds, text=lbl, anchor="w").grid(row=i, column=0, sticky="w", padx=8, pady=5)
            var = tk.StringVar(value=ds.get(k, ""))
            _entry(tab_ds, textvariable=var, width=280 if USE_CTK else None
                   ).grid(row=i, column=1, sticky="ew", padx=8, pady=5)
            ds_vars[k] = var
        tab_ds.columnconfigure(1, weight=1)

        def save_ds():
            data["data_source"] = {k: v.get().strip() for k, v in ds_vars.items()}
            self._save(data)
            messagebox.showinfo("Saved", "Data source saved.", parent=self)

        _btn(tab_ds, "💾 Save", save_ds).grid(row=len(ds_fields)+1, column=1, sticky="e", padx=8, pady=8)

        # ── Output tab ────────────────────────────────────────────────────────
        out_fields = [
            ("output_path",       "Output file path"),
            ("hoja_datos_crudos", "Raw data sheet name"),
        ]
        out_vars = {}
        for i, (k, lbl) in enumerate(out_fields):
            _lbl(tab_output, text=lbl).grid(row=i, column=0, sticky="w", padx=8, pady=5)
            var = tk.StringVar(value=str(data.get(k, "")))
            _entry(tab_output, textvariable=var, width=280 if USE_CTK else None
                   ).grid(row=i, column=1, sticky="ew", padx=8, pady=5)
            out_vars[k] = var

        _lbl(tab_output, text="Annual comparison (true/false)").grid(row=2, column=0, sticky="w", padx=8, pady=5)
        comp_var = tk.StringVar(value=str(data.get("comparacion_anual", True)).lower())
        _entry(tab_output, textvariable=comp_var, width=120 if USE_CTK else None
               ).grid(row=2, column=1, sticky="w", padx=8, pady=5)

        _lbl(tab_output, text="Output metrics (comma-sep)").grid(row=3, column=0, sticky="w", padx=8, pady=5)
        metrics_var = tk.StringVar(value=", ".join(data.get("metricas_salida", [])))
        _entry(tab_output, textvariable=metrics_var, width=280 if USE_CTK else None
               ).grid(row=3, column=1, sticky="ew", padx=8, pady=5)

        _lbl(tab_output, text="Base column order (comma-sep)").grid(row=4, column=0, sticky="w", padx=8, pady=5)
        order_var = tk.StringVar(value=", ".join(data.get("orden_columnas_base", [])))
        _entry(tab_output, textvariable=order_var, width=280 if USE_CTK else None
               ).grid(row=4, column=1, sticky="ew", padx=8, pady=5)
        tab_output.columnconfigure(1, weight=1)

        def save_output():
            for k, var in out_vars.items():
                data[k] = var.get().strip()
            data["comparacion_anual"] = comp_var.get().strip().lower() in ("true", "yes", "1")
            raw_m = metrics_var.get().strip()
            if raw_m:
                data["metricas_salida"] = [x.strip() for x in raw_m.split(",") if x.strip()]
            raw_o = order_var.get().strip()
            if raw_o:
                data["orden_columnas_base"] = [x.strip() for x in raw_o.split(",") if x.strip()]
            self._save(data)
            messagebox.showinfo("Saved", "Output settings saved.", parent=self)

        _btn(tab_output, "💾 Save", save_output).grid(row=5, column=1, sticky="e", padx=8, pady=8)

        # ── Sizes tab ─────────────────────────────────────────────────────────
        _lbl(tab_sizes, text="Include sizes (true/false)").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        incl_var = tk.StringVar(value=str(data.get("incluir_talles", False)).lower())
        _entry(tab_sizes, textvariable=incl_var, width=120 if USE_CTK else None
               ).grid(row=0, column=1, sticky="w", padx=8, pady=6)

        _lbl(tab_sizes, text="Size column name").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        size_col_var = tk.StringVar(value=data.get("columna_talle", "Talle"))
        _entry(tab_sizes, textvariable=size_col_var, width=200 if USE_CTK else None
               ).grid(row=1, column=1, sticky="w", padx=8, pady=6)

        def save_sizes():
            data["incluir_talles"] = incl_var.get().strip().lower() in ("true", "yes", "1")
            data["columna_talle"]  = size_col_var.get().strip()
            self._save(data)
            messagebox.showinfo("Saved", "Size settings saved.", parent=self)

        _btn(tab_sizes, "💾 Save", save_sizes).grid(row=2, column=1, sticky="e", padx=8, pady=8)
        tab_sizes.columnconfigure(1, weight=1)

        # ── Summaries tab ─────────────────────────────────────────────────────
        def rebuild_sum_tab():
            for w in tab_sum.winfo_children():
                w.destroy()
            resumenes = data.get("resumenes", [])
            sum_lb = tk.Listbox(tab_sum, height=8,
                                bg="#2b2b2b" if USE_CTK else "white",
                                fg="white" if USE_CTK else "black",
                                selectbackground="#1f538d", relief="flat")
            sum_lb.pack(fill="x", padx=8, pady=4)
            for r in resumenes:
                sum_lb.insert(tk.END, f"{r.get('nombre_hoja','?')}  ←  {r.get('locales_a_incluir','')}")

            row = BaseFrame(tab_sum)
            row.pack(fill="x", padx=8, pady=4)

            def add_sum():
                nombre = simpledialog.askstring("Add Summary", "Sheet name:", parent=self)
                if not nombre:
                    return
                raw = simpledialog.askstring(
                    "Stores", f"Stores for '{nombre}' (comma-sep):", parent=self)
                locales = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
                resumenes.append({"nombre_hoja": nombre, "locales_a_incluir": locales})
                data["resumenes"] = resumenes
                self._save(data)
                rebuild_sum_tab()

            def del_sum():
                sel = sum_lb.curselection()
                if not sel:
                    return
                del resumenes[sel[0]]
                data["resumenes"] = resumenes
                self._save(data)
                rebuild_sum_tab()

            _btn(row, "➕ Add",    add_sum).pack(side="left", padx=4)
            _btn(row, "🗑️ Delete", del_sum).pack(side="left", padx=4)

        rebuild_sum_tab()

        # ── Structures tab ────────────────────────────────────────────────────
        def rebuild_struct_tab():
            for w in tab_struct.winfo_children():
                w.destroy()
            structs = data.get("report_structures", {})
            struct_lb = tk.Listbox(tab_struct, height=8,
                                   bg="#2b2b2b" if USE_CTK else "white",
                                   fg="white" if USE_CTK else "black",
                                   selectbackground="#1f538d", relief="flat")
            struct_lb.pack(fill="x", padx=8, pady=4)
            for k, v in sorted(structs.items()):
                struct_lb.insert(tk.END, f"{k}  →  {', '.join(v)}")

            row = BaseFrame(tab_struct)
            row.pack(fill="x", padx=8, pady=4)

            def add_struct():
                key = simpledialog.askstring("Add Structure", "Group key name:", parent=self)
                if not key:
                    return
                raw = simpledialog.askstring(
                    "Stores", f"Stores for '{key}' (comma-sep):", parent=self)
                structs[key] = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
                data["report_structures"] = structs
                self._save(data)
                rebuild_struct_tab()

            def del_struct():
                sel = struct_lb.curselection()
                if not sel:
                    return
                key = struct_lb.get(sel[0]).split("  →  ")[0]
                structs.pop(key, None)
                data["report_structures"] = structs
                self._save(data)
                rebuild_struct_tab()

            def edit_struct():
                sel = struct_lb.curselection()
                if not sel:
                    return
                key = struct_lb.get(sel[0]).split("  →  ")[0]
                curr = ", ".join(structs.get(key, []))
                raw = simpledialog.askstring(
                    "Edit Structure", f"Stores for '{key}':", initialvalue=curr, parent=self)
                if raw is not None:
                    structs[key] = [s.strip() for s in raw.split(",") if s.strip()]
                    data["report_structures"] = structs
                    self._save(data)
                    rebuild_struct_tab()

            _btn(row, "➕ Add",   add_struct).pack(side="left", padx=4)
            _btn(row, "✏️ Edit",  edit_struct).pack(side="left", padx=4)
            _btn(row, "🗑️ Delete",del_struct).pack(side="left", padx=4)

        rebuild_struct_tab()

    # ── E. Pricing editor ─────────────────────────────────────────────────────

    def _render_pricing(self):
        ws = self._workspace
        _lbl(ws, text="Pricing Rules",
             font=("Arial", 13, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=10, pady=(8, 4))

        data = self.current_data

        # Expected columns
        _lbl(ws, text="Expected Columns (columnas_esperadas)").pack(anchor="w", padx=10, pady=(6, 2))
        col_lb = tk.Listbox(ws, height=6,
                            bg="#2b2b2b" if USE_CTK else "white",
                            fg="white" if USE_CTK else "black",
                            selectbackground="#1f538d", relief="flat")
        col_lb.pack(fill="x", padx=12, pady=2)

        def refresh_cols():
            col_lb.delete(0, tk.END)
            for c in data.get("columnas_esperadas", []):
                col_lb.insert(tk.END, c)

        refresh_cols()

        col_btn = BaseFrame(ws)
        col_btn.pack(fill="x", padx=12, pady=4)

        def add_col():
            raw = simpledialog.askstring(
                "Add Columns", "Column name(s) — comma-separated:", parent=self)
            if raw:
                cols = data.get("columnas_esperadas", [])
                for c in [x.strip() for x in raw.split(",") if x.strip()]:
                    if c not in cols:
                        cols.append(c)
                data["columnas_esperadas"] = cols
                self._save(data)
                refresh_cols()

        def del_col():
            sel = col_lb.curselection()
            if not sel:
                return
            c = col_lb.get(sel[0])
            cols = data.get("columnas_esperadas", [])
            if c in cols:
                cols.remove(c)
            data["columnas_esperadas"] = cols
            self._save(data)
            refresh_cols()

        _btn(col_btn, "➕ Add Column",    add_col).pack(side="left", padx=4)
        _btn(col_btn, "🗑️ Delete Column", del_col).pack(side="left", padx=4)

        # Aliases
        _lbl(ws, text="Column Aliases (mapeo_nombres)").pack(anchor="w", padx=10, pady=(10, 2))
        alias_lb = tk.Listbox(ws, height=5,
                              bg="#2b2b2b" if USE_CTK else "white",
                              fg="white" if USE_CTK else "black",
                              selectbackground="#1f538d", relief="flat")
        alias_lb.pack(fill="x", padx=12, pady=2)

        def refresh_aliases():
            alias_lb.delete(0, tk.END)
            for orig, short in (data.get("mapeo_nombres") or {}).items():
                alias_lb.insert(tk.END, f"'{orig}'  →  '{short}'")

        refresh_aliases()

        alias_btn = BaseFrame(ws)
        alias_btn.pack(fill="x", padx=12, pady=4)

        def add_alias():
            orig = simpledialog.askstring("Add Alias", "Original column name:", parent=self)
            if not orig:
                return
            short = simpledialog.askstring("Add Alias", f"Short alias for '{orig}':", parent=self)
            if short:
                mapeo = data.get("mapeo_nombres", {})
                mapeo[orig] = short
                data["mapeo_nombres"] = mapeo
                self._save(data)
                refresh_aliases()

        def del_alias():
            sel = alias_lb.curselection()
            if not sel:
                return
            raw = alias_lb.get(sel[0])
            orig = raw.split("'")[1]
            mapeo = data.get("mapeo_nombres", {})
            mapeo.pop(orig, None)
            data["mapeo_nombres"] = mapeo
            self._save(data)
            refresh_aliases()

        _btn(alias_btn, "➕ Add Alias",    add_alias).pack(side="left", padx=4)
        _btn(alias_btn, "🗑️ Delete Alias", del_alias).pack(side="left", padx=4)


# ═════════════════════════════════════════════════════════════════════════════
# 2. NEW PROFILE MODAL
# ═════════════════════════════════════════════════════════════════════════════

class NewProfileModal(BaseToplevel):
    def __init__(self, parent, on_created):
        super().__init__(parent)
        self.callback = on_created
        self.title("Create New Profile")
        self.geometry("520x300")
        self.attributes("-topmost", True)

        self.prof_id   = tk.StringVar()
        self.prof_name = tk.StringVar()
        self.prof_desc = tk.StringVar(value="Retail Business Profile")

        _lbl(self, text="Folder ID (lowercase, no spaces):").pack(anchor="w", padx=20, pady=(16, 2))
        _entry(self, textvariable=self.prof_id).pack(fill="x", padx=20, pady=2)

        _lbl(self, text="Display Name:").pack(anchor="w", padx=20, pady=(10, 2))
        _entry(self, textvariable=self.prof_name).pack(fill="x", padx=20, pady=2)

        _lbl(self, text="Description (optional):").pack(anchor="w", padx=20, pady=(10, 2))
        _entry(self, textvariable=self.prof_desc).pack(fill="x", padx=20, pady=2)

        btn_box = BaseFrame(self)
        btn_box.pack(fill="x", padx=20, pady=20)
        _btn(btn_box, "Cancel",         self.destroy).pack(side="right", padx=5)
        _btn(btn_box, "Create Profile", self._submit).pack(side="right", padx=5)

    def _submit(self):
        raw_id = self.prof_id.get().strip().lower().replace(" ", "_")
        if not raw_id:
            messagebox.showerror("Validation Error", "Profile ID is required.", parent=self)
            return
        target_dir = os.path.join(PROFILES_DIR, raw_id)
        if os.path.exists(target_dir):
            messagebox.showerror("Error", f"Profile '{raw_id}' already exists.", parent=self)
            return

        configs_path = os.path.join(target_dir, "configs")
        os.makedirs(configs_path, exist_ok=True)
        save_json(os.path.join(target_dir, "profile.json"), {
            "name":        self.prof_name.get().strip() or raw_id,
            "description": self.prof_desc.get().strip(),
            "version":     "1.4.0",
        })
        initialize_profile_files(configs_path)
        self.callback(raw_id)
        self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# 3. MAIN DESKTOP APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

class InventoryToolkitGUI(BaseWindow):

    def __init__(self):
        super().__init__()
        self.title("Inventory Toolkit v1.4.0")
        self.geometry("980x740")
        self.minsize(880, 620)

        self.active_profile = tk.StringVar(value="demo")
        self._refresh_profiles()
        self._build_top_bar()
        self._build_tabs()
        self._build_status_bar()

    # ── Profile helpers ───────────────────────────────────────────────────────

    def _refresh_profiles(self):
        if os.path.exists(PROFILES_DIR):
            self._profiles = sorted(
                d for d in os.listdir(PROFILES_DIR)
                if os.path.isdir(os.path.join(PROFILES_DIR, d))
            )
        else:
            self._profiles = ["demo"]
        if self._profiles and self.active_profile.get() not in self._profiles:
            self.active_profile.set(self._profiles[0])

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = BaseFrame(self)
        bar.pack(fill="x", padx=15, pady=10)

        _lbl(bar, text="Active Profile:").pack(side="left", padx=5)

        if USE_CTK:
            self._profile_menu = ctk.CTkOptionMenu(
                bar, values=self._profiles, variable=self.active_profile, width=140)
        else:
            self._profile_menu = tk.ttk.Combobox(
                bar, values=self._profiles,
                textvariable=self.active_profile, state="readonly", width=14)
        self._profile_menu.pack(side="left", padx=5)

        _btn(bar, "➕ New Profile",
             self._open_new_profile, width=120 if USE_CTK else None
             ).pack(side="left", padx=5)

        _btn(bar, "🧙 Setup Wizard",
             self._open_wizard, width=120 if USE_CTK else None
             ).pack(side="left", padx=5)

        _btn(bar, "⚙️ Config Hub",
             self._open_config_hub, width=110 if USE_CTK else None
             ).pack(side="left", padx=5)

        _btn(bar, "🚪 Exit",
             self.quit, width=80 if USE_CTK else None
             ).pack(side="right", padx=5)

    def _open_new_profile(self):
        def on_done(new_id):
            self._refresh_profiles()
            if USE_CTK:
                self._profile_menu.configure(values=self._profiles)
            else:
                self._profile_menu["values"] = self._profiles
            self.active_profile.set(new_id)
            messagebox.showinfo("Profile Ready", f"Active profile set to [{new_id}].", parent=self)
        NewProfileModal(self, on_done)

    def _open_wizard(self):
        profile = self.active_profile.get()
        profile_dir = os.path.join(PROFILES_DIR, profile)
        if not os.path.isdir(profile_dir):
            messagebox.showerror("Error", f"Profile '{profile}' not found.", parent=self)
            return
        # Run wizard in a thread so the GUI stays responsive; it's interactive
        # so we actually need to open a terminal-style sub-process or inform user.
        messagebox.showinfo(
            "Setup Wizard",
            "The Setup Wizard is a CLI process.\n\n"
            "Please run it from the CLI:\n"
            f"  Main menu → ⚙️  Configuration → [W] Quick Setup Wizard\n\n"
            "Or launch the CLI directly:\n"
            "  python cli.py",
            parent=self
        )

    def _open_config_hub(self):
        ConfigHubWindow(self, self.active_profile.get())

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        if USE_CTK:
            self._tabs = ctk.CTkTabview(self)
            self._tabs.pack(fill="both", expand=True, padx=15, pady=5)
            self.tab_cc    = self._tabs.add("🔄 Cross Check")
            self.tab_stock = self._tabs.add("📦 Stock Processing")
            self.tab_yoy   = self._tabs.add("📊 YoY Reports")
        else:
            self._tabs = tk.ttk.Notebook(self)
            self._tabs.pack(fill="both", expand=True, padx=15, pady=5)
            self.tab_cc    = ttk.Frame(self._tabs)
            self.tab_stock = ttk.Frame(self._tabs)
            self.tab_yoy   = ttk.Frame(self._tabs)
            self._tabs.add(self.tab_cc,    text="🔄 Cross Check")
            self._tabs.add(self.tab_stock, text="📦 Stock Processing")
            self._tabs.add(self.tab_yoy,   text="📊 YoY Reports")

        self._setup_cc_tab()
        self._setup_stock_tab()
        self._setup_yoy_tab()

    def _file_row(self, parent, label_text: str, var: tk.StringVar,
                  is_output: bool = False, row: int = 0):
        """Single file-input row: label + entry + Browse button."""
        frame = BaseFrame(parent)
        frame.pack(fill="x", padx=15, pady=5)
        _lbl(frame, text=label_text, width=230 if USE_CTK else None, anchor="w"
             ).pack(side="left", padx=5)
        _entry(frame, textvariable=var).pack(side="left", fill="x", expand=True, padx=5)

        def browse():
            if is_output:
                f = filedialog.asksaveasfilename(
                    title="Save as...", defaultextension=".xlsx",
                    filetypes=[("Excel Files", "*.xlsx *.xls")], parent=self)
            else:
                f = filedialog.askopenfilename(
                    title="Select file",
                    filetypes=[("Excel Files", "*.xlsx *.xls"), ("All files", "*.*")],
                    parent=self)
            if f:
                var.set(f)

        _btn(frame, "Browse", browse, width=80 if USE_CTK else None).pack(side="right", padx=5)

    # ── Tab 1: Cross Check ────────────────────────────────────────────────────

    def _setup_cc_tab(self):
        self.cc_sys    = tk.StringVar()
        self.cc_count  = tk.StringVar()
        self.cc_cost   = tk.StringVar()
        self.cc_sales  = tk.StringVar()
        self.cc_out    = tk.StringVar(value="Cross_Check_Output.xlsx")
        self.cc_consol = tk.BooleanVar(value=False)
        self.cc_partial= tk.BooleanVar(value=False)

        _lbl(self.tab_cc, text="Input Files", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(12, 2))
        self._file_row(self.tab_cc, "1. System Stock file:",     self.cc_sys)
        self._file_row(self.tab_cc, "2. Physical Count file:",   self.cc_count)
        self._file_row(self.tab_cc, "3. Cost Price List:",       self.cc_cost)
        self._file_row(self.tab_cc, "4. Sales Price List:",      self.cc_sales)

        _lbl(self.tab_cc, text="Output File", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(10, 2))
        self._file_row(self.tab_cc, "5. Output file:",           self.cc_out, is_output=True)

        opts = BaseFrame(self.tab_cc)
        opts.pack(fill="x", padx=15, pady=10)
        if USE_CTK:
            ctk.CTkCheckBox(opts, text="Consolidate multiple databases", variable=self.cc_consol
                            ).pack(side="left", padx=10)
            ctk.CTkCheckBox(opts, text="Partial count (scanned only)", variable=self.cc_partial
                            ).pack(side="left", padx=10)
            ctk.CTkButton(self.tab_cc, text="▶  Run Inventory Cross Check",
                          fg_color="#28a745", hover_color="#218838", height=40,
                          command=self._exec_cc).pack(pady=18)
        else:
            ttk.Checkbutton(opts, text="Consolidate databases", variable=self.cc_consol
                            ).pack(side="left", padx=10)
            ttk.Checkbutton(opts, text="Partial count filter", variable=self.cc_partial
                            ).pack(side="left", padx=10)
            ttk.Button(self.tab_cc, text="▶  Run Inventory Cross Check",
                       command=self._exec_cc).pack(pady=18)

    def _exec_cc(self):
        files = [self.cc_sys.get(), self.cc_count.get(), self.cc_cost.get(), self.cc_sales.get()]
        for f in files:
            if not f or not os.path.exists(f):
                messagebox.showerror("Missing File",
                                     f"Required file not found:\n'{f}'", parent=self)
                return

        if PANDAS_AVAILABLE:
            try:
                df_head = pd.read_excel(self.cc_sys.get(), nrows=0)
                cm = ConfigurationManager(self.active_profile.get())
                cfg = cm.get_cross_check_settings()
                art_col = cfg.get("columnas_costo", {}).get("articulo", "Artículo")
                if art_col not in df_head.columns:
                    messagebox.showwarning(
                        "Column Warning",
                        f"Expected column '{art_col}' not found in system stock file.\n"
                        "Proceeding anyway — check your config if results look wrong.",
                        parent=self)
            except Exception:
                pass

        out = self.cc_out.get().strip()
        if not out.endswith((".xlsx", ".xls")):
            out += ".xlsx"

        args = Namespace(
            cross_check_system=self.cc_sys.get(),
            cross_check_count=self.cc_count.get(),
            shared_cost=self.cc_cost.get(),
            shared_sales=self.cc_sales.get(),
            cross_check_out=out,
            cross_check_profile=self.active_profile.get(),
            cross_check_consolidate=self.cc_consol.get(),
            cross_check_partial=self.cc_partial.get(),
            non_interactive=True,
        )
        self._run_async(lambda: run_cross_check(args), "Cross Check completed!")

    # ── Tab 2: Stock Processing ───────────────────────────────────────────────

    def _setup_stock_tab(self):
        self.sp_raw   = tk.StringVar()
        self.sp_cost  = tk.StringVar()
        self.sp_sales = tk.StringVar()
        self.sp_out   = tk.StringVar(value="Stock_Valuation_Report.xlsx")

        _lbl(self.tab_stock, text="Input Files", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(12, 2))
        self._file_row(self.tab_stock, "1. Raw Stock spreadsheet:", self.sp_raw)
        self._file_row(self.tab_stock, "2. Cost Price List:",       self.sp_cost)
        self._file_row(self.tab_stock, "3. Sales Price List:",      self.sp_sales)

        _lbl(self.tab_stock, text="Output File", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(10, 2))
        self._file_row(self.tab_stock, "4. Output report name:",    self.sp_out, is_output=True)

        if USE_CTK:
            ctk.CTkButton(self.tab_stock, text="▶  Run Stock Processing & Valuation",
                          fg_color="#007bff", hover_color="#0069d9", height=40,
                          command=self._exec_stock).pack(pady=25)
        else:
            ttk.Button(self.tab_stock, text="▶  Run Stock Processing",
                       command=self._exec_stock).pack(pady=25)

    def _exec_stock(self):
        files = [self.sp_raw.get(), self.sp_cost.get(), self.sp_sales.get()]
        for f in files:
            if not f or not os.path.exists(f):
                messagebox.showerror("Missing File",
                                     f"Required file not found:\n'{f}'", parent=self)
                return
        out = self.sp_out.get().strip()
        if not out.endswith((".xlsx", ".xls")):
            out += ".xlsx"
        args = Namespace(
            stock_processing_raw=self.sp_raw.get(),
            shared_cost=self.sp_cost.get(),
            shared_sales=self.sp_sales.get(),
            stock_processing_out=out,
            stock_processing_profile=self.active_profile.get(),
            non_interactive=True,
        )
        self._run_async(lambda: run_stock_processing(args), "Stock Processing completed!")

    # ── Tab 3: YoY Reports ────────────────────────────────────────────────────

    def _setup_yoy_tab(self):
        self.yoy_file    = tk.StringVar()
        self.yoy_start   = tk.StringVar(value="2026-01-01")
        self.yoy_end     = tk.StringVar(value="2026-12-31")
        self.yoy_group   = tk.StringVar(value="Family")
        self.yoy_has_fam = tk.BooleanVar(value=True)
        self.yoy_seg     = tk.BooleanVar(value=False)
        self.yoy_sizes   = tk.BooleanVar(value=False)
        self.yoy_out     = tk.StringVar(value="yoy_analysis.xlsx")

        _lbl(self.tab_yoy, text="Sales Data File", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(12, 2))
        self._file_row(self.tab_yoy, "1. Sales history file:", self.yoy_file)

        # Date range
        date_frame = BaseFrame(self.tab_yoy)
        date_frame.pack(fill="x", padx=15, pady=8)
        _lbl(date_frame, text="Start date (YYYY-MM-DD):").pack(side="left", padx=5)
        _entry(date_frame, textvariable=self.yoy_start, width=130 if USE_CTK else None
               ).pack(side="left", padx=5)
        _lbl(date_frame, text="End date (YYYY-MM-DD):").pack(side="left", padx=10)
        _entry(date_frame, textvariable=self.yoy_end, width=130 if USE_CTK else None
               ).pack(side="left", padx=5)

        # Options
        opts = BaseFrame(self.tab_yoy)
        opts.pack(fill="x", padx=15, pady=6)

        if USE_CTK:
            ctk.CTkSegmentedButton(
                opts, values=["Family", "Item"], variable=self.yoy_group
            ).pack(side="left", padx=10)
            ctk.CTkCheckBox(opts, text="File has Family column", variable=self.yoy_has_fam
                            ).pack(side="left", padx=10)
            ctk.CTkCheckBox(opts, text="Segment by Month", variable=self.yoy_seg
                            ).pack(side="left", padx=10)
            ctk.CTkCheckBox(opts, text="Size breakdown", variable=self.yoy_sizes
                            ).pack(side="left", padx=10)
        else:
            tk.ttk.Combobox(
                opts, values=["Family", "Item"], textvariable=self.yoy_group,
                state="readonly", width=8
            ).pack(side="left", padx=10)
            ttk.Checkbutton(opts, text="Has Family col",  variable=self.yoy_has_fam
                            ).pack(side="left", padx=6)
            ttk.Checkbutton(opts, text="By month",        variable=self.yoy_seg
                            ).pack(side="left", padx=6)
            ttk.Checkbutton(opts, text="Size breakdown",  variable=self.yoy_sizes
                            ).pack(side="left", padx=6)

        _lbl(self.tab_yoy, text="Output File", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(8, 2))
        self._file_row(self.tab_yoy, "2. Output report name:", self.yoy_out, is_output=True)

        if USE_CTK:
            ctk.CTkButton(self.tab_yoy, text="▶  Generate YoY Sales Report",
                          fg_color="#6f42c1", hover_color="#5a32a3", height=40,
                          command=self._exec_yoy).pack(pady=20)
        else:
            ttk.Button(self.tab_yoy, text="▶  Generate YoY Sales Report",
                       command=self._exec_yoy).pack(pady=20)

    def _exec_yoy(self):
        f_path = self.yoy_file.get().strip()
        if not f_path or not os.path.exists(f_path):
            messagebox.showerror("Missing File", "Sales data file not found.", parent=self)
            return

        if not PANDAS_AVAILABLE:
            messagebox.showerror("Missing Dependency", "pandas is required.", parent=self)
            return

        try:
            s_dt = pd.to_datetime(self.yoy_start.get().strip(), format="%Y-%m-%d")
            e_dt = pd.to_datetime(self.yoy_end.get().strip(),   format="%Y-%m-%d")
            if s_dt > e_dt:
                messagebox.showerror("Date Error", "Start date must be before end date.", parent=self)
                return
            e_dt = e_dt + pd.Timedelta(days=1, seconds=-1)
        except Exception as err:
            messagebox.showerror("Invalid Date", f"Dates must be YYYY-MM-DD format:\n{err}", parent=self)
            return

        cm  = ConfigurationManager(self.active_profile.get())
        cfg = cm.get_yoy_settings()
        if not cfg or "data_source" not in cfg:
            messagebox.showerror("Config Error",
                                 f"YoY config missing for profile '{self.active_profile.get()}'.\n"
                                 "Run the Setup Wizard or edit reports.json.", parent=self)
            return

        ds      = cfg["data_source"]
        grp_col = ds["grouping_column"] if self.yoy_group.get() == "Family" else ds["item_column"]
        out     = self.yoy_out.get().strip()
        if not out.endswith((".xlsx", ".xls")):
            out += ".xlsx"

        # Capture every Tk variable on the UI thread before starting the worker.
        segmented = self.yoy_seg.get()
        has_families = self.yoy_has_fam.get()
        profile = self.active_profile.get()
        include_sizes = self.yoy_sizes.get()

        def task():
            return generate_sales_report(
                f_path, out, s_dt, e_dt, cfg, grp_col,
                segmented, has_families, profile, include_sizes,
                non_interactive=True,
            )
        self._run_async(task, "YoY Sales Report generated!")

    # ── Status bar & async runner ─────────────────────────────────────────────

    def _build_status_bar(self):
        if USE_CTK:
            bar = ctk.CTkFrame(self, height=34, corner_radius=0)
            bar.pack(side="bottom", fill="x")
            self._status = ctk.CTkLabel(bar, text="⚡ Ready.", anchor="w")
            self._status.pack(side="left", padx=12, pady=6)
            self._progress = ctk.CTkProgressBar(bar, width=160)
            self._progress.pack(side="right", padx=12, pady=8)
            self._progress.set(0)
        else:
            bar = ttk.Frame(self)
            bar.pack(side="bottom", fill="x")
            self._status = ttk.Label(bar, text="⚡ Ready.", anchor="w")
            self._status.pack(side="left", padx=12, pady=4)
            self._progress = None

    def _set_status(self, text: str):
        """Update the status bar from the Tk main thread."""
        self._status.configure(text=text)

    def _finish_progress(self, success: bool):
        if self._progress and USE_CTK:
            self._progress.stop()
            self._progress.configure(mode="determinate")
            self._progress.set(1 if success else 0)

    def _run_async(self, func, success_msg: str):
        """Run engine work off-thread while keeping every Tk call on the UI thread."""
        t_start = time.time()
        result_queue = queue.Queue(maxsize=1)

        self._set_status("⏳ Running task in background... Please wait.")
        if self._progress and USE_CTK:
            self._progress.configure(mode="indeterminate")
            self._progress.start()

        def worker():
            try:
                out_path = func()
                if not out_path:
                    raise RuntimeError(
                        "The operation finished without producing an output file. "
                        "Check logs/session.log for the validation error."
                    )
                result_queue.put(("success", out_path, time.time() - t_start))
            except Exception as exc:
                log.error(f"Async error: {exc}")
                result_queue.put(("error", exc, time.time() - t_start))

        def poll_result():
            try:
                kind, payload, elapsed = result_queue.get_nowait()
            except queue.Empty:
                self.after(100, poll_result)
                return

            if kind == "success":
                out_path = payload
                self._set_status(f"✅ Done in {elapsed:.1f}s  |  {out_path}")
                self._finish_progress(True)
                messagebox.showinfo(
                    "Done",
                    f"{success_msg}\n\nTime: {elapsed:.1f}s\nOutput: {out_path}",
                    parent=self,
                )
            else:
                exc = payload
                self._set_status(f"❌ Error: {exc}")
                self._finish_progress(False)
                messagebox.showerror("Execution Error", str(exc), parent=self)

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, poll_result)


# ── Entry point ───────────────────────────────────────────────────────────────

def launch_gui():
    app = InventoryToolkitGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
