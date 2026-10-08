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
import subprocess
from pathlib import Path
import time
from copy import deepcopy
from argparse import Namespace

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from gui.widgets import (ctk, ttk, USE_CTK, BaseWindow, BaseToplevel, BaseFrame,
    BaseButton, BaseLabel, BaseEntry, BaseTextbox, BaseScrollable,
    _btn, _lbl, _entry, _pack_btn, apply_dark_theme)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from core.business_schema import ARTICLE_COLUMN, DATABASE_ORIGIN_COLUMN, DEFAULT_FAMILY, FAMILY_COLUMN, PRICE_COLUMN, RAW_DATA_SHEET, SIZE_COLUMN
from core.configuration_manager import ConfigurationManager
from core.input_columns import choose_input_columns
from core.profile_config import DEFAULTS
from core.logger import log
from core import paths as app_paths
from core.system_utils import InvalidExcelOutputPathError, normalize_xlsx_output_path
from cli.wizard import initialize_profile_files, run_setup_wizard
from core.setup_service import initialize_setup
from cli.utils import save_json, load_json, load_last_paths, save_last_paths
from engine.inventory_cross_check.generator import run_cross_check
from engine.stock_processing.generator import run_stock_processing
from engine.yoy_reports.generator import generate_sales_report
from engine.yoy_reports.metrics import select_run_metrics


class NewProfileModal(BaseToplevel):
    def __init__(self, parent, on_created):
        super().__init__(parent)
        self.callback = on_created
        self.title("Create New Profile")
        self.geometry("520x300")
        self.attributes("-topmost", True)

        self.prof_id   = tk.StringVar()
        self.prof_name = tk.StringVar()
        self.prof_desc = tk.StringVar(value="")

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
        if not raw_id or raw_id in {".", ".."} or "/" in raw_id or "\\" in raw_id:
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
            "version":     "1.4.1",
        })
        initialize_profile_files(str(configs_path))
        initialize_setup(raw_id)
        self.callback(raw_id)
        self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# 3. MAIN DESKTOP APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

