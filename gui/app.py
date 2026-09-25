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
    stock_output → structured editor (raw sheet, base columns, summaries)
    yoy_reports  → structured editor (input, output, groups)
    pricing      → structured editor (column mapping + aliases)
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

from core.business_schema import ARTICLE_COLUMN, DATABASE_ORIGIN_COLUMN, DEFAULT_FAMILY, FAMILY_COLUMN, PRICE_COLUMN, RAW_DATA_SHEET, SIZE_COLUMN
from core.configuration_manager import ConfigurationManager
from core.logger import log
from core import paths as app_paths
from core.system_utils import InvalidExcelOutputPathError, normalize_xlsx_output_path
from cli.wizard import initialize_profile_files, run_setup_wizard
from cli.utils import save_json, load_json
from engine.inventory_cross_check.generator import run_cross_check
from engine.stock_processing.generator import run_stock_processing
from engine.yoy_reports.generator import generate_sales_report


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
        "Product Families":         ("general/families.json",          "dict_list"),
        "General Settings":         ("general/catalog.json",           "key_value"),
        "Active Stores & Groups":   ("general/network.json",           "stores"),
        "Database Aliases":         ("general/network.json",           "key_value"),
        "Stock Cleaning Rules":     ("stock_processing/settings.json", "dict_list"),
        "Pricing Rules":            ("stock_processing/settings.json", "pricing"),
        "Stock Output":             ("stock_processing/settings.json", "stock_output"),
        "Cross Check":              ("cross_check/settings.json",      "cross_check"),
        "YoY Report Structure":     ("yoy_reports/settings.json",      "yoy_reports"),
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
        return str(app_paths.profile_configs_root(self.profile) / rel)

    def _reload(self):
        for w in self._workspace.winfo_children():
            w.destroy()
        self.current_data = self._load_editor_data()
        _, kind = self._REGISTRY[self._active_key]
        dispatch = {
            "dict_list":  self._render_dict_list,
            "key_value":  self._render_key_value,
            "stores":     self._render_stores,
            "yoy_reports": self._render_yoy_reports,
            "pricing": self._render_pricing,
            "stock_output": self._render_stock_output,
            "cross_check": self._render_cross_check,
        }
        dispatch.get(kind, self._render_key_value)()

    def _load_editor_data(self):
        """Load the current schema into small English editor-specific views."""
        raw = load_json(self._filepath()) or {}
        key = self._active_key

        if key == "Product Families":
            return raw.get("rules", {})
        if key == "General Settings":
            columns = raw.get("columns", {})
            return {
                "article_column": columns.get("article", ARTICLE_COLUMN),
                "family_column": columns.get("family", FAMILY_COLUMN),
                "default_family": raw.get("default_family", DEFAULT_FAMILY),
            }
        if key == "Active Stores & Groups":
            return {
                "active_stores": raw.get("active", []),
                "regional_groups": raw.get("regional_groups", {}),
            }
        if key == "Database Aliases":
            return raw.get("stock_database_columns", {})
        if key == "Stock Cleaning Rules":
            cleaning = raw.get("cleaning", {})
            return {
                "text_columns": cleaning.get("text_columns", []),
                "drop_columns": cleaning.get("drop_columns", []),
                "numeric_columns": cleaning.get("numeric_columns", []),
            }
        if key == "Pricing Rules":
            pricing = raw.get("pricing", {})
            columns = pricing.get("columns", {})
            return {
                "article_column": columns.get("article", ARTICLE_COLUMN),
                "database_column": columns.get("database", DATABASE_ORIGIN_COLUMN),
                "price_column": columns.get("price", PRICE_COLUMN),
                "aliases": pricing.get("aliases", {}),
            }
        if key == "Stock Output":
            return raw.get("output", {})
        if key == "Cross Check":
            return {
                "filters": raw.get("filters", {}),
                "price_lists": raw.get("price_lists", {}),
            }
        if key == "YoY Report Structure":
            return {
                "input": raw.get("input", {}),
                "output": raw.get("output", {}),
                "groups": raw.get("groups", {}),
            }
        return raw

    def _save(self, data=None):
        data = data if data is not None else self.current_data
        raw = load_json(self._filepath()) or {"version": 3}
        raw["version"] = 3
        key = self._active_key

        if key == "Product Families":
            raw["rules"] = data
        elif key == "General Settings":
            raw["columns"] = {
                "article": data.get("article_column", ARTICLE_COLUMN),
                "family": data.get("family_column", FAMILY_COLUMN),
            }
            raw["default_family"] = data.get("default_family", DEFAULT_FAMILY)
        elif key == "Active Stores & Groups":
            raw["active"] = data.get("active_stores", [])
            raw["regional_groups"] = data.get("regional_groups", {})
        elif key == "Database Aliases":
            raw["stock_database_columns"] = data
        elif key == "Stock Cleaning Rules":
            raw["cleaning"] = {
                "text_columns": data.get("text_columns", []),
                "drop_columns": data.get("drop_columns", []),
                "numeric_columns": data.get("numeric_columns", []),
            }
        elif key == "Pricing Rules":
            raw["pricing"] = {
                "columns": {
                    "article": data.get("article_column", ARTICLE_COLUMN),
                    "database": data.get("database_column", DATABASE_ORIGIN_COLUMN),
                    "price": data.get("price_column", PRICE_COLUMN),
                },
                "aliases": data.get("aliases", {}),
            }
        elif key == "Stock Output":
            raw["output"] = data
        elif key == "Cross Check":
            raw["filters"] = data.get("filters", {})
            raw["price_lists"] = data.get("price_lists", {})
        elif key == "YoY Report Structure":
            raw["input"] = data.get("input", {})
            raw["output"] = data.get("output", {})
            raw["groups"] = data.get("groups", {})
        else:
            raw = data
        save_json(self._filepath(), raw)

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
        workspace = self._workspace
        _lbl(
            workspace,
            text="Active Stores & Regional Groups",
            font=("Arial", 13, "bold") if not USE_CTK else None,
        ).pack(anchor="w", padx=10, pady=(8, 4))

        def rebuild():
            for widget in workspace.winfo_children()[1:]:
                widget.destroy()

            data = self.current_data
            active_stores = data.get("active_stores", [])
            regional_groups = data.get("regional_groups", {})

            _lbl(workspace, text="📍 Active Stores").pack(
                anchor="w", padx=10, pady=(6, 2)
            )
            stores_list = tk.Listbox(
                workspace,
                height=6,
                bg="#2b2b2b" if USE_CTK else "white",
                fg="white" if USE_CTK else "black",
                selectbackground="#1f538d",
                relief="flat",
            )
            stores_list.pack(fill="x", padx=12, pady=2)
            for store in active_stores:
                stores_list.insert(tk.END, store)

            store_buttons = BaseFrame(workspace)
            store_buttons.pack(fill="x", padx=12, pady=4)

            def add_store():
                raw = simpledialog.askstring(
                    "Add Stores",
                    "Store name(s) — comma-separated:",
                    parent=self,
                )
                if raw:
                    for store in [item.strip() for item in raw.split(",") if item.strip()]:
                        if store not in active_stores:
                            active_stores.append(store)
                    data["active_stores"] = active_stores
                    self._save(data)
                    rebuild()

            def delete_store():
                selection = stores_list.curselection()
                if not selection:
                    return
                store = stores_list.get(selection[0])
                active_stores.remove(store)
                data["active_stores"] = active_stores
                self._save(data)
                rebuild()

            _btn(store_buttons, "➕ Add Store", add_store).pack(side="left", padx=4)
            _btn(store_buttons, "🗑️ Delete Store", delete_store).pack(side="left", padx=4)

            _lbl(workspace, text="🗂️ Regional Groups").pack(
                anchor="w", padx=10, pady=(10, 2)
            )
            groups_list = tk.Listbox(
                workspace,
                height=6,
                bg="#2b2b2b" if USE_CTK else "white",
                fg="white" if USE_CTK else "black",
                selectbackground="#1f538d",
                relief="flat",
            )
            groups_list.pack(fill="x", padx=12, pady=2)
            for group_name, members in sorted(regional_groups.items()):
                groups_list.insert(tk.END, f"{group_name}  →  {', '.join(members)}")

            group_buttons = BaseFrame(workspace)
            group_buttons.pack(fill="x", padx=12, pady=4)

            def add_group():
                group_name = simpledialog.askstring(
                    "New Group", "Group name:", parent=self
                )
                if not group_name:
                    return
                raw = simpledialog.askstring(
                    "Group Members",
                    f"Stores for '{group_name}' (comma-separated):",
                    parent=self,
                )
                regional_groups[group_name] = (
                    [store.strip() for store in raw.split(",") if store.strip()]
                    if raw
                    else []
                )
                data["regional_groups"] = regional_groups
                self._save(data)
                rebuild()

            def delete_group():
                selection = groups_list.curselection()
                if not selection:
                    return
                group_name = groups_list.get(selection[0]).split("  →  ")[0]
                if messagebox.askyesno(
                    "Delete Group",
                    f"Delete group '{group_name}'?",
                    parent=self,
                ):
                    regional_groups.pop(group_name, None)
                    data["regional_groups"] = regional_groups
                    self._save(data)
                    rebuild()

            def edit_group():
                selection = groups_list.curselection()
                if not selection:
                    return
                group_name = groups_list.get(selection[0]).split("  →  ")[0]
                current_members = ", ".join(regional_groups.get(group_name, []))
                raw = simpledialog.askstring(
                    "Edit Group",
                    f"Stores for '{group_name}':",
                    initialvalue=current_members,
                    parent=self,
                )
                if raw is not None:
                    regional_groups[group_name] = [
                        store.strip() for store in raw.split(",") if store.strip()
                    ]
                    data["regional_groups"] = regional_groups
                    self._save(data)
                    rebuild()

            _btn(group_buttons, "➕ New Group", add_group).pack(side="left", padx=4)
            _btn(group_buttons, "✏️ Edit Group", edit_group).pack(side="left", padx=4)
            _btn(group_buttons, "🗑️ Delete Group", delete_group).pack(side="left", padx=4)

        rebuild()

    # ── D. Stock output editor ─────────────────────────────────────────────────

    def _render_stock_output(self):
        workspace = self._workspace
        data = self.current_data
        _lbl(
            workspace,
            text="Stock Output",
            font=("Arial", 13, "bold") if not USE_CTK else None,
        ).pack(anchor="w", padx=10, pady=(8, 4))

        settings_frame = BaseFrame(workspace)
        settings_frame.pack(fill="x", padx=10, pady=6)

        raw_sheet_var = tk.StringVar(value=data.get("raw_data_sheet", RAW_DATA_SHEET))
        base_columns_var = tk.StringVar(value=", ".join(data.get("base_columns", [])))

        _lbl(settings_frame, text="Raw data sheet name").grid(
            row=0, column=0, sticky="w", padx=6, pady=5
        )
        _entry(settings_frame, textvariable=raw_sheet_var).grid(
            row=0, column=1, sticky="ew", padx=6, pady=5
        )
        _lbl(settings_frame, text="Base output columns").grid(
            row=1, column=0, sticky="w", padx=6, pady=5
        )
        _entry(settings_frame, textvariable=base_columns_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=5
        )
        settings_frame.columnconfigure(1, weight=1)

        def save_output_settings():
            data["raw_data_sheet"] = raw_sheet_var.get().strip() or RAW_DATA_SHEET
            data["base_columns"] = [
                value.strip()
                for value in base_columns_var.get().split(",")
                if value.strip()
            ]
            self._save(data)
            messagebox.showinfo("Saved", "Stock output settings saved.", parent=self)

        _btn(settings_frame, "💾 Save Output", save_output_settings).grid(
            row=2, column=1, sticky="e", padx=6, pady=6
        )

        _lbl(workspace, text="Summary Sheets").pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        summary_list = tk.Listbox(
            workspace,
            height=9,
            bg="#2b2b2b" if USE_CTK else "white",
            fg="white" if USE_CTK else "black",
            selectbackground="#1f538d",
            relief="flat",
        )
        summary_list.pack(fill="both", expand=True, padx=12, pady=2)

        def refresh_summaries():
            summary_list.delete(0, tk.END)
            for summary in data.get("summaries", []):
                summary_list.insert(
                    tk.END,
                    f"{summary.get('sheet_name', '?')}  ←  {', '.join(summary.get('entities', []))}",
                )

        def add_summary():
            sheet_name = simpledialog.askstring(
                "Add Summary", "Sheet name:", parent=self
            )
            if not sheet_name:
                return
            entities_text = simpledialog.askstring(
                "Summary Entities",
                f"Stores/groups for '{sheet_name}' (comma-separated):",
                parent=self,
            )
            titles_text = simpledialog.askstring(
                "Summary Titles",
                "Optional exported titles (comma-separated; leave blank to keep generated names):",
                parent=self,
            )
            data.setdefault("summaries", []).append(
                {
                    "sheet_name": sheet_name,
                    "entities": [
                        item.strip()
                        for item in (entities_text or "").split(",")
                        if item.strip()
                    ],
                    "titles": [
                        item.strip()
                        for item in (titles_text or "").split(",")
                        if item.strip()
                    ],
                }
            )
            self._save(data)
            refresh_summaries()

        def edit_summary():
            selection = summary_list.curselection()
            if not selection:
                return
            summary = data.get("summaries", [])[selection[0]]
            sheet_name = simpledialog.askstring(
                "Edit Summary",
                "Sheet name:",
                initialvalue=summary.get("sheet_name", ""),
                parent=self,
            )
            if not sheet_name:
                return
            entities_text = simpledialog.askstring(
                "Summary Entities",
                "Stores/groups (comma-separated):",
                initialvalue=", ".join(summary.get("entities", [])),
                parent=self,
            )
            if entities_text is None:
                return
            titles_text = simpledialog.askstring(
                "Summary Titles",
                "Exported titles (comma-separated):",
                initialvalue=", ".join(summary.get("titles", [])),
                parent=self,
            )
            if titles_text is None:
                return
            summary.update(
                {
                    "sheet_name": sheet_name,
                    "entities": [
                        item.strip() for item in entities_text.split(",") if item.strip()
                    ],
                    "titles": [
                        item.strip() for item in titles_text.split(",") if item.strip()
                    ],
                }
            )
            self._save(data)
            refresh_summaries()

        def delete_summary():
            selection = summary_list.curselection()
            if not selection:
                return
            del data.get("summaries", [])[selection[0]]
            self._save(data)
            refresh_summaries()

        summary_buttons = BaseFrame(workspace)
        summary_buttons.pack(fill="x", padx=12, pady=4)
        _btn(summary_buttons, "➕ Add", add_summary).pack(side="left", padx=4)
        _btn(summary_buttons, "✏️ Edit", edit_summary).pack(side="left", padx=4)
        _btn(summary_buttons, "🗑️ Delete", delete_summary).pack(side="left", padx=4)
        refresh_summaries()

    # ── E. Cross Check editor ──────────────────────────────────────────────────

    def _render_cross_check(self):
        workspace = self._workspace
        data = self.current_data
        filters = data.setdefault("filters", {})
        price_lists = data.setdefault("price_lists", {})

        _lbl(
            workspace,
            text="Cross Check Configuration",
            font=("Arial", 13, "bold") if not USE_CTK else None,
        ).pack(anchor="w", padx=10, pady=(8, 4))

        form = BaseFrame(workspace)
        form.pack(fill="both", expand=True, padx=10, pady=6)

        ignored_articles_var = tk.StringVar(
            value=", ".join(filters.get("ignored_articles", []))
        )
        ignored_terms_var = tk.StringVar(
            value=", ".join(filters.get("ignored_terms", []))
        )
        fields = [
            ("Ignored articles", ignored_articles_var),
            ("Ignored text terms", ignored_terms_var),
        ]

        cost_mapping = price_lists.setdefault("cost", {})
        sales_mapping = price_lists.setdefault("sales", {})
        cost_article_var = tk.StringVar(
            value=cost_mapping.get("article_column", ARTICLE_COLUMN)
        )
        cost_price_var = tk.StringVar(
            value=cost_mapping.get("price_column", PRICE_COLUMN)
        )
        sales_article_var = tk.StringVar(
            value=sales_mapping.get("article_column", ARTICLE_COLUMN)
        )
        sales_price_var = tk.StringVar(
            value=sales_mapping.get("price_column", PRICE_COLUMN)
        )
        fields.extend(
            [
                ("Cost list — article column", cost_article_var),
                ("Cost list — price column", cost_price_var),
                ("Sales list — article column", sales_article_var),
                ("Sales list — price column", sales_price_var),
            ]
        )

        for row_index, (label, variable) in enumerate(fields):
            _lbl(form, text=label).grid(
                row=row_index, column=0, sticky="w", padx=6, pady=5
            )
            _entry(form, textvariable=variable).grid(
                row=row_index, column=1, sticky="ew", padx=6, pady=5
            )
        form.columnconfigure(1, weight=1)

        def save_cross_check():
            filters["ignored_articles"] = [
                value.strip()
                for value in ignored_articles_var.get().split(",")
                if value.strip()
            ]
            filters["ignored_terms"] = [
                value.strip()
                for value in ignored_terms_var.get().split(",")
                if value.strip()
            ]
            price_lists["cost"] = {
                "article_column": cost_article_var.get().strip() or ARTICLE_COLUMN,
                "price_column": cost_price_var.get().strip() or PRICE_COLUMN,
            }
            price_lists["sales"] = {
                "article_column": sales_article_var.get().strip() or ARTICLE_COLUMN,
                "price_column": sales_price_var.get().strip() or PRICE_COLUMN,
            }
            data["filters"] = filters
            data["price_lists"] = price_lists
            self._save(data)
            messagebox.showinfo("Saved", "Cross Check settings saved.", parent=self)

        _btn(form, "💾 Save Configuration", save_cross_check).grid(
            row=len(fields), column=1, sticky="e", padx=6, pady=8
        )

    # ── F. YoY reports editor ─────────────────────────────────────────────────

    def _render_yoy_reports(self):
        workspace = self._workspace
        _lbl(
            workspace,
            text="YoY Report Structure",
            font=("Arial", 13, "bold") if not USE_CTK else None,
        ).pack(anchor="w", padx=10, pady=(8, 4))

        tabs = ctk.CTkTabview(workspace) if USE_CTK else tk.ttk.Notebook(workspace)
        tabs.pack(fill="both", expand=True, padx=8, pady=4)

        def add_tab(label):
            if USE_CTK:
                return tabs.add(label)
            frame = ttk.Frame(tabs)
            tabs.add(frame, text=label)
            return frame

        input_tab = add_tab("Input")
        output_tab = add_tab("Output")
        groups_tab = add_tab("Groups")

        data = self.current_data
        input_config = data.setdefault("input", {})
        output_config = data.setdefault("output", {})
        groups = data.setdefault("groups", {})

        input_fields = [
            ("date_column", "Date column", "Fecha"),
            ("quantity_column", "Quantity column", "Cantidad"),
            ("sales_column", "Sales amount column", "Monto"),
            ("item_column", "Item / SKU column", "Articulo"),
            ("grouping_column", "Grouping / Family column", "Familias"),
            ("branch_column", "Branch / Store column", "Base"),
            ("size_column", "Size column", "Talle"),
        ]
        input_vars = {}
        for row_index, (key, label, default) in enumerate(input_fields):
            _lbl(input_tab, text=label).grid(
                row=row_index, column=0, sticky="w", padx=8, pady=5
            )
            variable = tk.StringVar(value=input_config.get(key, default))
            _entry(input_tab, textvariable=variable).grid(
                row=row_index, column=1, sticky="ew", padx=8, pady=5
            )
            input_vars[key] = variable
        input_tab.columnconfigure(1, weight=1)

        def save_input():
            data["input"] = {
                key: variable.get().strip() for key, variable in input_vars.items()
            }
            self._save(data)
            messagebox.showinfo("Saved", "YoY input mapping saved.", parent=self)

        _btn(input_tab, "💾 Save Input", save_input).grid(
            row=len(input_fields), column=1, sticky="e", padx=8, pady=8
        )

        output_path_var = tk.StringVar(
            value=output_config.get("default_path", "analysis_report.xlsx")
        )
        enabled_metrics = output_config.get("metrics", ["units", "sales"])
        units_var = tk.BooleanVar(value="units" in enabled_metrics)
        sales_var = tk.BooleanVar(value="sales" in enabled_metrics)
        annual_var = tk.BooleanVar(value=output_config.get("annual_comparison", True))
        sizes_var = tk.BooleanVar(value=output_config.get("include_sizes", False))

        _lbl(output_tab, text="Default output path").grid(
            row=0, column=0, sticky="w", padx=8, pady=5
        )
        _entry(output_tab, textvariable=output_path_var).grid(
            row=0, column=1, sticky="ew", padx=8, pady=5
        )
        output_tab.columnconfigure(1, weight=1)

        metric_frame = BaseFrame(output_tab)
        metric_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=5)
        _lbl(metric_frame, text="Enabled metrics:").pack(side="left", padx=(0, 8))
        if USE_CTK:
            ctk.CTkCheckBox(metric_frame, text="Units", variable=units_var).pack(side="left", padx=6)
            ctk.CTkCheckBox(metric_frame, text="Sales amount", variable=sales_var).pack(side="left", padx=6)
            ctk.CTkCheckBox(output_tab, text="Annual comparison", variable=annual_var).grid(
                row=2, column=0, columnspan=2, sticky="w", padx=8, pady=5
            )
            ctk.CTkCheckBox(output_tab, text="Include size breakdown", variable=sizes_var).grid(
                row=3, column=0, columnspan=2, sticky="w", padx=8, pady=5
            )
        else:
            ttk.Checkbutton(metric_frame, text="Units", variable=units_var).pack(side="left", padx=6)
            ttk.Checkbutton(metric_frame, text="Sales amount", variable=sales_var).pack(side="left", padx=6)
            ttk.Checkbutton(output_tab, text="Annual comparison", variable=annual_var).grid(
                row=2, column=0, columnspan=2, sticky="w", padx=8, pady=5
            )
            ttk.Checkbutton(output_tab, text="Include size breakdown", variable=sizes_var).grid(
                row=3, column=0, columnspan=2, sticky="w", padx=8, pady=5
            )

        def save_output():
            metrics = []
            if units_var.get():
                metrics.append("units")
            if sales_var.get():
                metrics.append("sales")
            if not metrics:
                messagebox.showerror(
                    "Validation Error",
                    "Enable at least one YoY metric (Units or Sales amount).",
                    parent=self,
                )
                return

            try:
                output_config["default_path"] = normalize_xlsx_output_path(
                    output_path_var.get().strip() or "analysis_report.xlsx"
                )
            except InvalidExcelOutputPathError as exc:
                messagebox.showerror("Validation Error", str(exc), parent=self)
                return
            output_config["metrics"] = metrics
            output_config["annual_comparison"] = bool(annual_var.get())
            output_config["include_sizes"] = bool(sizes_var.get())
            data["output"] = output_config
            self._save(data)
            messagebox.showinfo("Saved", "YoY output settings saved.", parent=self)

        _btn(output_tab, "💾 Save Output", save_output).grid(
            row=4, column=1, sticky="e", padx=8, pady=8
        )

        def rebuild_groups():
            for widget in groups_tab.winfo_children():
                widget.destroy()

            groups_list = tk.Listbox(
                groups_tab,
                height=9,
                bg="#2b2b2b" if USE_CTK else "white",
                fg="white" if USE_CTK else "black",
                selectbackground="#1f538d",
                relief="flat",
            )
            groups_list.pack(fill="both", expand=True, padx=8, pady=4)
            for group_name, branches in sorted(groups.items()):
                groups_list.insert(tk.END, f"{group_name}  →  {', '.join(branches)}")

            buttons = BaseFrame(groups_tab)
            buttons.pack(fill="x", padx=8, pady=4)

            def add_group():
                group_name = simpledialog.askstring(
                    "Add Group", "Group key name:", parent=self
                )
                if not group_name:
                    return
                raw = simpledialog.askstring(
                    "Branches",
                    f"Branches for '{group_name}' (comma-separated):",
                    parent=self,
                )
                groups[group_name] = [
                    value.strip() for value in (raw or "").split(",") if value.strip()
                ]
                data["groups"] = groups
                self._save(data)
                rebuild_groups()

            def edit_group():
                selection = groups_list.curselection()
                if not selection:
                    return
                group_name = groups_list.get(selection[0]).split("  →  ")[0]
                raw = simpledialog.askstring(
                    "Edit Group",
                    f"Branches for '{group_name}':",
                    initialvalue=", ".join(groups.get(group_name, [])),
                    parent=self,
                )
                if raw is not None:
                    groups[group_name] = [
                        value.strip() for value in raw.split(",") if value.strip()
                    ]
                    data["groups"] = groups
                    self._save(data)
                    rebuild_groups()

            def delete_group():
                selection = groups_list.curselection()
                if not selection:
                    return
                group_name = groups_list.get(selection[0]).split("  →  ")[0]
                groups.pop(group_name, None)
                data["groups"] = groups
                self._save(data)
                rebuild_groups()

            _btn(buttons, "➕ Add", add_group).pack(side="left", padx=4)
            _btn(buttons, "✏️ Edit", edit_group).pack(side="left", padx=4)
            _btn(buttons, "🗑️ Delete", delete_group).pack(side="left", padx=4)

        rebuild_groups()

    # ── G. Pricing editor ─────────────────────────────────────────────────────

    def _render_pricing(self):
        workspace = self._workspace
        data = self.current_data
        _lbl(
            workspace,
            text="Pricing Rules",
            font=("Arial", 13, "bold") if not USE_CTK else None,
        ).pack(anchor="w", padx=10, pady=(8, 4))

        form = BaseFrame(workspace)
        form.pack(fill="x", padx=10, pady=6)
        article_var = tk.StringVar(value=data.get("article_column", ARTICLE_COLUMN))
        database_var = tk.StringVar(
            value=data.get("database_column", DATABASE_ORIGIN_COLUMN)
        )
        price_var = tk.StringVar(value=data.get("price_column", PRICE_COLUMN))
        for row_index, (label, variable) in enumerate(
            [
                ("Article column", article_var),
                ("Database / origin column", database_var),
                ("Price column", price_var),
            ]
        ):
            _lbl(form, text=label).grid(
                row=row_index, column=0, sticky="w", padx=6, pady=5
            )
            _entry(form, textvariable=variable).grid(
                row=row_index, column=1, sticky="ew", padx=6, pady=5
            )
        form.columnconfigure(1, weight=1)

        def save_columns():
            data["article_column"] = article_var.get().strip() or ARTICLE_COLUMN
            data["database_column"] = (
                database_var.get().strip() or DATABASE_ORIGIN_COLUMN
            )
            data["price_column"] = price_var.get().strip() or PRICE_COLUMN
            self._save(data)
            messagebox.showinfo("Saved", "Pricing columns saved.", parent=self)

        _btn(form, "💾 Save Columns", save_columns).grid(
            row=3, column=1, sticky="e", padx=6, pady=6
        )

        _lbl(workspace, text="Column Aliases").pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        alias_list = tk.Listbox(
            workspace,
            height=6,
            bg="#2b2b2b" if USE_CTK else "white",
            fg="white" if USE_CTK else "black",
            selectbackground="#1f538d",
            relief="flat",
        )
        alias_list.pack(fill="x", padx=12, pady=2)

        def refresh_aliases():
            alias_list.delete(0, tk.END)
            for original, alias in data.get("aliases", {}).items():
                alias_list.insert(tk.END, f"'{original}'  →  '{alias}'")

        def add_alias():
            original = simpledialog.askstring(
                "Add Alias", "Original column name:", parent=self
            )
            if not original:
                return
            alias = simpledialog.askstring(
                "Add Alias", f"Short alias for '{original}':", parent=self
            )
            if alias:
                data.setdefault("aliases", {})[original] = alias
                self._save(data)
                refresh_aliases()

        def delete_alias():
            selection = alias_list.curselection()
            if not selection:
                return
            original = alias_list.get(selection[0]).split("'")[1]
            data.setdefault("aliases", {}).pop(original, None)
            self._save(data)
            refresh_aliases()

        alias_buttons = BaseFrame(workspace)
        alias_buttons.pack(fill="x", padx=12, pady=4)
        _btn(alias_buttons, "➕ Add Alias", add_alias).pack(side="left", padx=4)
        _btn(alias_buttons, "🗑️ Delete Alias", delete_alias).pack(side="left", padx=4)
        refresh_aliases()


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
        target_dir = app_paths.profile_root(raw_id)
        if os.path.exists(target_dir):
            messagebox.showerror("Error", f"Profile '{raw_id}' already exists.", parent=self)
            return

        configs_path = target_dir / "configs"
        configs_path.mkdir(parents=True, exist_ok=True)
        save_json(str(target_dir / "profile.json"), {
            "name":        self.prof_name.get().strip() or raw_id,
            "description": self.prof_desc.get().strip(),
            "version":     "1.4.0",
        })
        initialize_profile_files(str(configs_path))
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
        self._apply_yoy_profile_defaults()
        self.active_profile.trace_add("write", self._on_profile_changed)
        self._build_status_bar()
        self.bind("<Control-Shift-I>", self._show_easter_egg)

    def _show_easter_egg(self, _event=None):
        """Hidden nod for people who read source code and press suspicious shortcuts."""
        messagebox.showinfo(
            "Inventory Toolkit",
            "🥚 Longest prefix wins.\nThe scanner may improvise; the master stock does not.\n\n— FPSensor",
            parent=self,
        )

    # ── Profile helpers ───────────────────────────────────────────────────────

    def _refresh_profiles(self):
        if app_paths.PROFILES_ROOT.exists():
            self._profiles = sorted(
                path.name for path in app_paths.PROFILES_ROOT.iterdir()
                if path.is_dir()
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
        profile_dir = app_paths.profile_root(profile)
        if not profile_dir.is_dir():
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

    def _on_profile_changed(self, *_args):
        if hasattr(self, "yoy_sizes"):
            self._apply_yoy_profile_defaults()

    def _apply_yoy_profile_defaults(self):
        """Reflect profile-owned YoY defaults in the main GUI controls."""
        try:
            output = ConfigurationManager(self.active_profile.get()).get_yoy_reports_config()["output"]
        except Exception:
            return
        self.yoy_sizes.set(bool(output.get("include_sizes", False)))
        default_path = str(output.get("default_path", "")).strip()
        if default_path:
            self.yoy_out.set(default_path)

    def _resolve_xlsx_output(self, value: str):
        try:
            return normalize_xlsx_output_path(value)
        except InvalidExcelOutputPathError as exc:
            messagebox.showerror("Invalid Output File", str(exc), parent=self)
            return None

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
                    filetypes=[("Excel Workbook", "*.xlsx")], parent=self)
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
                art_col = cm.get_catalog_columns()["article"]
                if art_col not in df_head.columns:
                    messagebox.showerror(
                        "Invalid System Stock",
                        f"Configured article column '{art_col}' was not found in the system stock file.\n"
                        "Update the profile or choose the matching workbook before running Cross Check.",
                        parent=self,
                    )
                    return
            except Exception as exc:
                messagebox.showerror(
                    "Cross Check Preflight Error",
                    str(exc),
                    parent=self,
                )
                return


        out = self._resolve_xlsx_output(self.cc_out.get().strip())
        if not out:
            return

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
        out = self._resolve_xlsx_output(self.sp_out.get().strip())
        if not out:
            return
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

        config_manager = ConfigurationManager(self.active_profile.get())
        yoy_config = config_manager.get_yoy_reports_config()
        if not yoy_config or "input" not in yoy_config:
            messagebox.showerror("Config Error",
                                 f"YoY config missing for profile '{self.active_profile.get()}'.\n"
                                 "Run the Setup Wizard or edit YoY Reports in Config Hub.", parent=self)
            return

        input_config = yoy_config["input"]
        grouping_column = (
            input_config["grouping_column"]
            if self.yoy_group.get() == "Family"
            else input_config["item_column"]
        )
        out = self._resolve_xlsx_output(self.yoy_out.get().strip())
        if not out:
            return

        # Capture every Tk variable on the UI thread before starting the worker.
        segmented = self.yoy_seg.get()
        has_families = self.yoy_has_fam.get()
        profile = self.active_profile.get()
        include_sizes = self.yoy_sizes.get()

        def task():
            return generate_sales_report(
                f_path, out, s_dt, e_dt, yoy_config, grouping_column,
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
