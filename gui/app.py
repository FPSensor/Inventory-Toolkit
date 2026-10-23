"""Dark Alpha Pre-Beta desktop shell with shared engines and guided setup."""

import os
from core.build import BUILD
from core.module_preferences import enabled_modules, set_enabled_modules
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
    _btn, _lbl, _entry, _pack_btn, apply_dark_theme, set_text_scale, COLORS)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from core.business_schema import ARTICLE_COLUMN, DATABASE_ORIGIN_COLUMN, DEFAULT_FAMILY, FAMILY_COLUMN, PRICE_COLUMN, RAW_DATA_SHEET, VARIANT_COLUMN
from core.configuration_manager import ConfigurationManager
from core.workflow_contracts import stock_input, stock_price_columns, cross_article_column
from core.input_columns import choose_input_columns
from core.profile_config import DEFAULTS
from core.logger import log
from core import paths as app_paths
from core.system_utils import InvalidExcelOutputPathError, normalize_xlsx_output_path
from core.profile_config import ensure_profile_config as initialize_profile_files
from core.profile_store import save_json, load_json, load_last_paths, save_last_paths
from engine.inventory_cross_check.generator import run_cross_check
from engine.stock_processing.generator import run_stock_processing
from engine.yoy_reports.generator import generate_sales_report
from engine.yoy_reports.metrics import select_run_metrics
from core.setup_service import SetupSession, SetupState
from core.setup_catalog import MODULE_LABELS
from core.profile_overview import inspect_profile
from core.input_doctor import inspect_workflow_inputs
from core.workflow_errors import WorkflowError
from gui.setup_wizard import SetupWizard


from gui.config_hub import ConfigurationWorkspace
from gui.profile_dialog import NewProfilePanel

class InventoryToolkitGUI(BaseWindow):

    def __init__(self):
        super().__init__()
        self.title(f"Inventory Toolkit v{BUILD.version} | GUI {BUILD.gui_stage}")
        apply_dark_theme(self)
        self.geometry("1240x900")
        self.minsize(900, 680)

        self._setup_panel = None
        self._selected_module = None
        self._partial_permission = None
        self._busy = False
        self._running_profile = None
        self._locked_controls = []
        self._result_path = None
        self.active_profile = tk.StringVar(value="demo")
        self._refresh_profiles()
        self._build_top_bar()
        self._build_tabs()
        self._apply_yoy_profile_defaults()
        self.active_profile.trace_add("write", self._on_profile_changed)
        self._build_status_bar()
        self.after(50, lambda: self._split.sashpos(0, round(self.winfo_height() * 0.73)) if len(self._split.panes()) == 2 else None)
        self._show_module("overview")
        self.bind("<Control-Shift-I>", self._show_easter_egg)
        self.bind('<Control-comma>', lambda _event: self._open_config_hub())
        self.bind('<Control-n>', lambda _event: self._open_new_profile())
        self.bind('<Escape>', lambda _event: self._setup_panel._leave() if self._setup_panel is not None else None)
        self.protocol("WM_DELETE_WINDOW", self._request_close)

    def _show_easter_egg(self, _event=None):
        """Hidden nod for people who read source code and press suspicious shortcuts."""
        self._notify("info",
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
        self._split = ttk.Panedwindow(self, orient="vertical")
        self._split.pack(fill="both", expand=True, padx=12, pady=12)
        self._body = BaseFrame(self._split)
        self._split.add(self._body, weight=3)
        bar = BaseScrollable(self._body, width=228)
        self._top_bar = bar
        bar.pack(side="left", fill="y", padx=(0, 12))
        _lbl(bar, text="INVENTORY\nTOOLKIT", font=("Arial", 20, "bold")).pack(anchor="w", padx=16, pady=(20, 4))
        _lbl(bar, text=f"v{BUILD.version} · {BUILD.gui_stage}", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 20))
        _lbl(bar, text="Active profile").pack(anchor="w", padx=16)
        if USE_CTK:
            self._profile_menu = ctk.CTkOptionMenu(bar, values=self._profiles or [""], variable=self.active_profile, width=175)
        else:
            self._profile_menu = ttk.Combobox(bar, values=self._profiles, textvariable=self.active_profile, state="readonly", width=17)
        self._profile_menu.pack(fill="x", padx=12, pady=8)
        self._nav_buttons = {}
        for module, label in [('overview', 'Overview'), ('cross_check', 'Cross Check'), ('stock_processing', 'Stock'), ('yoy_reports', 'YoY Reports')]:
            button = _btn(bar, label, lambda name=module: self._show_module(name), variant='ghost', anchor='w')
            button.pack(fill='x', padx=12, pady=4)
            self._nav_buttons[module] = button
        _btn(bar, "Set up this module", self._open_wizard).pack(fill="x", padx=12, pady=(24, 5))
        _btn(bar, "New profile", self._open_new_profile, variant="primary").pack(fill="x", padx=12, pady=5)
        _btn(bar, "Configuration", self._open_config_hub).pack(fill="x", padx=12, pady=5)
        _lbl(bar, text="Text size").pack(anchor="w", padx=16, pady=(20, 2))
        self._scale_choice = tk.StringVar(value="100%")
        if USE_CTK:
            scale = ctk.CTkOptionMenu(bar, values=["100%", "115%", "130%"], variable=self._scale_choice, command=self._change_scale)
        else:
            scale = ttk.Combobox(bar, values=["100%", "115%", "130%"], textvariable=self._scale_choice, state="readonly")
            scale.bind("<<ComboboxSelected>>", lambda _event: self._change_scale(self._scale_choice.get()))
        scale.pack(fill="x", padx=12, pady=6)
        _btn(bar, "Exit", self._request_close, variant="ghost").pack(side="bottom", fill="x", padx=12, pady=12)
        self._workspace_root = BaseFrame(self._body)
        self._workspace_root.pack(side="left", fill="both", expand=True)
        self._workspace_root.grid_columnconfigure(0, weight=1)
        self._workspace_root.grid_rowconfigure(2, weight=1)
        self._page_title = _lbl(self._workspace_root, text="Cross Check", font=("Arial", 26, "bold"))
        self._page_title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        self._feedback = BaseFrame(self._workspace_root)
        self._feedback.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        self._feedback_text = _lbl(self._feedback, text="Choose files, review options and run. Results stay below.", wraplength=650, justify="left")
        self._feedback_text.pack(fill="x", padx=10, pady=8)
        self._feedback.bind("<Configure>", lambda event: self._feedback_text.configure(wraplength=max(180, event.width - 30)))
        self._feedback_actions = BaseFrame(self._feedback)
        self._feedback_actions.pack(fill="x", padx=8, pady=(0, 4))
        self._page_host = BaseFrame(self._workspace_root)
        self._page_host.grid(row=2, column=0, sticky="nsew")
        self._page_host.grid_columnconfigure(0, weight=1)
        self._page_host.grid_rowconfigure(0, weight=1)

    def _change_scale(self, value):
        fraction = int(value.rstrip("%")) / 100
        if USE_CTK:
            ctk.set_widget_scaling(fraction)
        else:
            set_text_scale(self, fraction)

    def _set_results_visible(self, visible):
        if not hasattr(self, '_results'):
            return
        included = str(self._results) in {str(pane) for pane in self._split.panes()}
        if visible and not included:
            self._split.add(self._results, weight=1)
            self.after_idle(lambda: self._split.sashpos(0, round(self.winfo_height() * .73)) if len(self._split.panes()) == 2 else None)
        elif not visible and included:
            self._split.forget(self._results)

    def _manage_workflows(self):
        self._module_selector_open = True
        self._show_module('overview')

    def _notify(self, kind, title, message, actions=(), **_kwargs):
        tone = COLORS.get({'error': 'error', 'warning': 'warning', 'success': 'positive'}.get(kind, 'muted'))
        self._feedback_text.configure(text=f"{title}: {message}", **({'text_color': tone} if USE_CTK else {'foreground': tone}))
        for widget in self._feedback_actions.winfo_children():
            widget.destroy()
        if actions:
            self._feedback_actions.pack(fill="x", padx=8, pady=(0, 4))
        else:
            self._feedback_actions.pack_forget()
        for label, callback in actions:
            _btn(self._feedback_actions, label, callback).pack(side="left", padx=4, pady=4)
        if hasattr(self, "_activity") and kind in {"warning", "error"}:
            self._append_activity(f"{title}: {message}\n")

    def _show_module(self, module):
        if self._setup_panel is not None:
            self._notify("info", "Setup in progress", "Leave or finish the current setup before switching modules.")
            return
        if module in MODULE_LABELS and module not in enabled_modules(self.active_profile.get()):
            self._notify("info", "Workflow disabled", "Enable this workflow in Profile overview before opening it.")
            return
        self._selected_module = module
        self._set_results_visible(module in MODULE_LABELS)
        for name, button in getattr(self, '_nav_buttons', {}).items():
            selected = name == module
            enabled = name not in MODULE_LABELS or name in enabled_modules(self.active_profile.get())
            if USE_CTK:
                button.configure(fg_color=COLORS['border'] if selected else 'transparent', text_color=COLORS['text'] if selected else COLORS['muted'], state='normal' if enabled else 'disabled')
            else:
                button.configure(style='NavActive.TButton' if selected else 'Nav.TButton', state='normal' if enabled else 'disabled')
        if hasattr(self, "_pages"):
            if module == "settings":
                self._render_settings()
                self._pages[module].tkraise()
                self._page_title.configure(text="Configuration")
                self._notify("info", "Configuration", "Search by what you want to change. Settings use the same guided forms as setup.")
                return
            if module == "overview":
                self._render_overview()
                self._pages[module].tkraise()
                self._page_title.configure(text="Profile overview")
                self._notify("info", "Profile overview", "Choose a workflow to inspect or configure.")
                return
            self._pages[module].tkraise()
            self._page_title.configure(text=MODULE_LABELS[module])
            try:
                state = SetupSession(self.active_profile.get(), module).state()
                label = {0: "Not configured", 1: "Partially configured", 2: "Configured"}[state]
                self._notify("info", "Module setup", label, [("Configure", lambda: self._open_wizard(module))])
            except Exception as exc:
                self._notify("error", "Profile configuration", str(exc))

    def _open_new_profile(self):
        if not self._require_idle():
            return
        def close_panel():
            panel = self._setup_panel
            self._setup_panel = None
            panel.destroy()
            self._profile_menu.configure(state='normal' if USE_CTK else 'readonly')
        def on_done(new_id):
            close_panel()
            self._refresh_profiles()
            self._profile_menu.configure(values=self._profiles)
            self.active_profile.set(new_id)
            self._show_module('overview')
            self._notify('success', 'Profile created', 'Choose an enabled workflow to set it up with your files.')
        def cancel():
            close_panel()
            self._show_module('overview')
        self._set_results_visible(False)
        self._page_title.configure(text="New profile")
        self._notify("info", "Create a workspace", "Choose only the workflows you need. Other settings come later.")
        self._setup_panel = NewProfilePanel(self._page_host, self.active_profile.get(), on_done, cancel)
        self._setup_panel.grid(row=0, column=0, sticky='nsew')
        self._setup_panel.tkraise()
        self._profile_menu.configure(state='disabled')

    def _open_wizard(self, module=None, step=None, *, edit_mode=False, single_page=False, return_to_settings=False):
        if not self._require_idle():
            return
        if any(isinstance(child, tk.Toplevel) for child in self.winfo_children()):
            self._notify("info", "Configuration window open", "Close other profile/configuration windows before opening guided setup.")
            return
        module = module or self._selected_module
        if module not in MODULE_LABELS:
            self._notify("info", "Select a workflow", "Choose a workflow before opening its setup assistant.")
            return
        profile = self.active_profile.get()
        self._set_results_visible(False)
        self._page_title.configure(text=f"{MODULE_LABELS[module]} settings" if edit_mode else f"Set up {MODULE_LABELS[module]}")
        def finish(message):
            panel = self._setup_panel
            self._setup_panel = None
            panel.destroy()
            self._profile_menu.configure(state="normal" if USE_CTK else "readonly")
            self._render_overview()
            self._show_module("settings" if return_to_settings else module)
            self._notify("info", "Configuration" if edit_mode else "Guided setup", message)
        try:
            self._setup_panel = SetupWizard(self._page_host, profile, module, finish, step, edit_mode=edit_mode, single_page=single_page)
            self._setup_panel.grid(row=0, column=0, sticky="nsew")
            self._setup_panel.tkraise()
            self._profile_menu.configure(state="disabled")
        except Exception as exc:
            self._setup_panel = None
            self._notify("error", "Could not open setup", str(exc))

    def _gate_setup(self, module):
        profile = self.active_profile.get()
        try:
            session = SetupSession(profile, module)
            state = session.state()
            if state == SetupState.NOT_CONFIGURED:
                self._open_wizard(module)
                return False
            if state == SetupState.PARTIAL and self._partial_permission != (profile, module):
                def proceed():
                    self._partial_permission = (profile, module)
                    {"cross_check": self._exec_cc, "stock_processing": self._exec_stock, "yoy_reports": self._exec_yoy}[module]()
                self._notify("warning", "Partial setup", "Some settings have not been reviewed. Continue with current settings or complete setup.",
                    [("Continue anyway", proceed), ("Complete setup", lambda: self._open_wizard(module))])
                return False
            self._partial_permission = None
            session.validate_required(include_sales=self.yoy_sales_amounts.get() if module == "yoy_reports" else False,
                include_variants=self.yoy_variants.get() if module == "yoy_reports" else False)
            return True
        except Exception as exc:
            self._handle_error(exc)
            return False

    def _handle_error(self, exc):
        actions = []
        if isinstance(exc, WorkflowError) and exc.can_configure:
            actions = [("Configure missing setting", lambda: self._open_wizard(exc.module, exc.step))]
        code = f" [{exc.code.value}]" if isinstance(exc, WorkflowError) else ""
        self._notify("error", f"Operation stopped{code}", str(exc), actions)

    def _open_config_hub(self):
        if self._require_idle():
            self._show_module("settings")

    def _render_settings(self):
        page = self._pages['settings']
        for child in page.winfo_children():
            child.destroy()
        workspace = ConfigurationWorkspace(page, self.active_profile.get(),
            lambda module, step: self._open_wizard(module, step, edit_mode=True, single_page=True, return_to_settings=True),
            self._manage_workflows)
        workspace.pack(fill='both', expand=True)

    def _select_columns(self, file_path, configured, defaults):
        def confirm(field, wanted, default):
            return messagebox.askyesno(
                "Missing configured column",
                f"{file_path}\n\nColumn '{wanted}' for {field} is absent.\n"
                f"Try default '{default}' for this run?",
                parent=self,
            )
        return choose_input_columns(file_path, configured, defaults, confirm)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._pages = {module: (BaseFrame(self._page_host) if module == "settings" else BaseScrollable(self._page_host)) for module in ("overview", "settings", *MODULE_LABELS)}
        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self.tab_overview = self._pages["overview"]
        self.tab_cc = self._pages["cross_check"]
        self.tab_stock = self._pages["stock_processing"]
        self.tab_yoy = self._pages["yoy_reports"]
        self._setup_cc_tab()
        self._setup_stock_tab()
        self._setup_yoy_tab()
        self.tab_overview.tkraise()

    def _render_overview(self):
        page = self.tab_overview
        for child in page.winfo_children():
            child.destroy()
        entries = inspect_profile(self.active_profile.get())
        selected = enabled_modules(self.active_profile.get())
        if getattr(self, "_module_selector_open", False):
            chooser = BaseFrame(page)
            chooser.pack(fill="x", padx=18, pady=12)
            _lbl(chooser, text="Use only the workflows you need", font=("Arial", 15, "bold")).pack(anchor="w", padx=12, pady=8)
            choices = {}
            for name, label in MODULE_LABELS.items():
                choices[name] = tk.BooleanVar(value=name in selected)
                cls = ctk.CTkCheckBox if USE_CTK else ttk.Checkbutton
                cls(chooser, text=label, variable=choices[name]).pack(anchor="w", padx=12, pady=4)
            def apply_modules():
                if not self._require_idle():
                    return
                try:
                    set_enabled_modules(self.active_profile.get(), [name for name, variable in choices.items() if variable.get()])
                    self._module_selector_open = False
                    self._render_overview()
                    self._notify("info", "Workflows updated", "Disabled workflows keep their settings for later.")
                except ValueError as exc:
                    self._notify("error", "Choose workflows", str(exc))
            _btn(chooser, "Apply workflow selection", apply_modules).pack(anchor="w", padx=12, pady=10)
        else:
            _btn(page, "Choose workflows", self._manage_workflows, variant="ghost").pack(anchor="w", padx=20, pady=12)
        ready = sum(entry.state == SetupState.COMPLETE for entry in entries)
        _lbl(page, text=f"{ready} of {len(selected)} enabled workflows ready", font=("Arial", 17, "bold")
            ).pack(anchor="w", padx=20, pady=(12, 5))
        _lbl(page, text="Review setup pages by workflow. 'Ready' reflects configuration review; input headers are checked when you select a file.",
            wraplength=650, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        for entry in entries:
            if not entry.enabled:
                continue
            card = BaseFrame(page)
            card.pack(fill="x", padx=18, pady=7)
            _lbl(card, text=f"{entry.label}   |   {entry.status}", font=("Arial", 16, "bold")
                ).pack(anchor="w", padx=12, pady=(10, 4))
            count = f"{entry.reviewed}/{entry.total} pages reviewed" if entry.reviewed is not None else "Existing profile"
            detail = (entry.issue or (f"Next: {entry.pending_titles[0]}"
                + (f" · {len(entry.pending_titles) - 1} more" if len(entry.pending_titles) > 1 else "")
                if entry.pending_titles else "Configuration reviewed. Select a workflow to choose files and run."))
            _lbl(card, text=f"{count}   |   {detail}", wraplength=620, justify="left"
                ).pack(anchor="w", padx=12, pady=(0, 6))
            buttons = BaseFrame(card)
            buttons.pack(anchor="w", padx=10, pady=(0, 10))
            _btn(buttons, "Open workflow", lambda name=entry.module: self._show_module(name)
                ).pack(side="left", padx=3)
            if entry.enabled and not entry.issue:
                _btn(buttons, "Review setup", lambda name=entry.module, step=entry.pending_step: self._open_wizard(name, step)
                    ).pack(side="left", padx=3)

    def _on_profile_changed(self, *_args):
        if getattr(self, "_setup_panel", None) is not None:
            guarded_profile = getattr(self._setup_panel, "profile", None) or self._setup_panel.session.profile
            if self.active_profile.get() != guarded_profile:
                self.active_profile.set(guarded_profile)
            return
        if self._busy:
            if self.active_profile.get() != self._running_profile:
                self.active_profile.set(self._running_profile)
            return
        if hasattr(self, "yoy_variants"):
            self._apply_yoy_profile_defaults()
        if getattr(self, "_selected_module", None) == "overview" and hasattr(self, "tab_overview"):
            self._render_overview()
        elif getattr(self, "_selected_module", None) == "settings":
            self._render_settings()

    def _apply_yoy_profile_defaults(self):
        """Restore YoY file paths and profile-owned defaults for the active profile."""
        try:
            profile = self.active_profile.get()
            output = ConfigurationManager(profile).get_yoy_reports_config()["output"]
            saved = load_last_paths(profile).get("yoy_reports", {})
        except Exception:
            return
        self.yoy_variants.set(bool(output.get("include_variants", False)))
        self.yoy_compare.set(False)
        self.yoy_sales_amounts.set(False)
        self.yoy_file.set(saved.get("file", ""))
        self.yoy_out.set(saved.get("out") or str(output.get("default_path", "yoy_analysis.xlsx")))

    def _resolve_xlsx_output(self, value: str, default: str):
        try:
            return normalize_xlsx_output_path(
                value.strip() or default,
                notify=lambda message: self._notify("warning", "Output File", message, parent=self),
            )
        except InvalidExcelOutputPathError as exc:
            self._notify("error", "Invalid Output File", str(exc), parent=self)
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
        _lbl(self.tab_cc, text="Compare recorded stock with your physical count and value the differences.", wraplength=700, justify="left", style="Muted.TLabel").pack(anchor="w", padx=20, pady=(12, 4))
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
        _btn(self.tab_cc, "Inspect selected files", lambda: self._inspect_inputs("cross_check")
            ).pack(pady=(0, 14))

    def _exec_cc(self):
        if not self._require_idle():
            return
        if not self._gate_setup("cross_check"):
            return
        if not PANDAS_AVAILABLE:
            self._notify("error", "Missing Dependency", "pandas is required.", parent=self)
            return
        files = [self.cc_sys.get(), self.cc_count.get(), self.cc_cost.get(), self.cc_sales.get()]
        for f in files:
            if not f or not os.path.exists(f):
                self._notify("error", "Missing File",
                                     f"Required file not found:\n'{f}'", parent=self)
                return

        if PANDAS_AVAILABLE:
            try:
                cm = ConfigurationManager(self.active_profile.get(), module="cross_check")
                cross_config = cm.get_cross_check_config()
                mappings = cross_config["price_lists"]
                defaults = DEFAULTS["cross_check/settings"]["price_lists"]
                overrides = {
                    "system": self._select_columns(self.cc_sys.get(),
                        { "article": cross_article_column(cm),
                          "quantity": cross_config["input"]["quantity_column"]},
                        {"article": DEFAULTS["general/catalog"]["columns"]["article"],
                         "quantity": DEFAULTS["cross_check/settings"]["input"]["quantity_column"]}),
                    "cost": self._select_columns(self.cc_cost.get(), mappings["cost"], defaults["cost"]),
                    "sales": self._select_columns(self.cc_sales.get(), mappings["sales"], defaults["sales"]),
                }
                if cross_config["input"]["count_mode"] == "quantities":
                    overrides["count"] = self._select_columns(self.cc_count.get(),
                        {"article": cross_config["input"]["count_article_column"], "quantity": cross_config["input"]["count_quantity_column"]},
                        {"article": DEFAULTS["general/catalog"]["columns"]["article"], "quantity": cross_config["input"]["quantity_column"]})
            except Exception as exc:
                self._notify("error",
                    "Cross Check Preflight Error",
                    str(exc),
                    parent=self,
                )
                return


        out = self._resolve_xlsx_output(self.cc_out.get(), "Cross_Check_Output.xlsx")
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
            column_overrides=overrides,
        )
        self._run_async(lambda progress, stats: run_cross_check(args), "Cross Check completed!", progress_target=args)

    # ── Tab 2: Stock Processing ───────────────────────────────────────────────

    def _setup_stock_tab(self):
        _lbl(self.tab_stock, text="Prepare quantities, classify products and value inventory by location.", wraplength=700, justify="left", style="Muted.TLabel").pack(anchor="w", padx=20, pady=(12, 4))
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
        _btn(self.tab_stock, "Inspect selected files", lambda: self._inspect_inputs("stock_processing")
            ).pack(pady=(0, 14))

    def _exec_stock(self):
        if not self._require_idle():
            return
        if not self._gate_setup("stock_processing"):
            return
        files = [self.sp_raw.get(), self.sp_cost.get(), self.sp_sales.get()]
        for f in files:
            if not f or not os.path.exists(f):
                self._notify("error", "Missing File",
                                     f"Required file not found:\n'{f}'", parent=self)
                return
        out = self._resolve_xlsx_output(self.sp_out.get(), "Stock_Valuation_Report.xlsx")
        if not out:
            return
        try:
            cm = ConfigurationManager(self.active_profile.get(), module="stock_processing")
            pricing = cm.get_stock_pricing()["columns"]
            defaults = DEFAULTS["stock_processing/settings"]["pricing"]["columns"]
            overrides = {
                "stock": self._select_columns(self.sp_raw.get(),
                    {"article": stock_input(cm)["article_column"]},
                    {"article": DEFAULTS["general/catalog"]["columns"]["article"]}),
                "cost": self._select_columns(self.sp_cost.get(), stock_price_columns(cm, "cost", required_only=True), defaults),
                "sales": self._select_columns(self.sp_sales.get(), stock_price_columns(cm, "sales", required_only=True), defaults),
            }
        except Exception as exc:
            self._handle_error(exc)
            return
        warnings = []
        args = Namespace(
            stock_processing_raw=self.sp_raw.get(),
            shared_cost=self.sp_cost.get(),
            shared_sales=self.sp_sales.get(),
            stock_processing_out=out,
            stock_processing_profile=self.active_profile.get(),
            non_interactive=True,
            column_overrides=overrides,
            warnings=warnings,
        )
        self._run_async(lambda progress, stats: run_stock_processing(args), "Stock Processing completed!", warnings=warnings, progress_target=args)

    # ── Tab 3: YoY Reports ────────────────────────────────────────────────────

    def _setup_yoy_tab(self):
        self.yoy_file    = tk.StringVar()
        self.yoy_start   = tk.StringVar(value="2026-01-01")
        self.yoy_end     = tk.StringVar(value="2026-12-31")
        self.yoy_group   = tk.StringVar(value="Family")
        self.yoy_has_fam = tk.BooleanVar(value=True)
        self.yoy_seg     = tk.BooleanVar(value=False)
        self.yoy_compare = tk.BooleanVar(value=False)
        self.yoy_sales_amounts = tk.BooleanVar(value=False)
        self.yoy_variants   = tk.BooleanVar(value=False)
        self.yoy_out     = tk.StringVar(value="yoy_analysis.xlsx")

        _lbl(self.tab_yoy, text="Sales Data File", font=("Arial", 11, "bold") if not USE_CTK else None
             ).pack(anchor="w", padx=15, pady=(12, 2))
        self._file_row(self.tab_yoy, "1. Sales history file:", self.yoy_file)

        # Date range
        date_frame = BaseFrame(self.tab_yoy)
        date_frame.pack(fill="x", padx=15, pady=8)
        _lbl(date_frame, text="Start date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        _entry(date_frame, textvariable=self.yoy_start, width=130 if USE_CTK else None
               ).grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        _lbl(date_frame, text="End date (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        _entry(date_frame, textvariable=self.yoy_end, width=130 if USE_CTK else None
               ).grid(row=1, column=1, sticky="ew", padx=5, pady=4)
        date_frame.columnconfigure(1, weight=1)

        # Options use two columns rather than a clipped horizontal strip.
        opts = BaseFrame(self.tab_yoy)
        opts.pack(fill="x", padx=15, pady=6)
        opts.columnconfigure(0, weight=1)
        opts.columnconfigure(1, weight=1)
        if USE_CTK:
            group_control = ctk.CTkSegmentedButton(opts, values=["Family", "Item"], variable=self.yoy_group)
            check_class = ctk.CTkCheckBox
        else:
            group_control = ttk.Combobox(opts, values=["Family", "Item"], textvariable=self.yoy_group, state="readonly", width=8)
            check_class = ttk.Checkbutton
        group_control.grid(row=0, column=0, sticky="w", padx=10, pady=8)
        for text, variable, row, column in [
            ("File has Family column", self.yoy_has_fam, 0, 1),
            ("Segment by Month", self.yoy_seg, 1, 0),
            ("Variant breakdown", self.yoy_variants, 1, 1),
        ]:
            check_class(opts, text=text, variable=variable).grid(row=row, column=column, sticky="w", padx=10, pady=8)

        if USE_CTK:
            compare_control = ctk.CTkCheckBox(
                self.tab_yoy, text="Annual comparison below full report",
                variable=self.yoy_compare,
            )
        else:
            compare_control = ttk.Checkbutton(
                self.tab_yoy, text="Annual comparison below full report",
                variable=self.yoy_compare,
            )
        compare_control.pack(anchor="w", padx=20, pady=4)

        if USE_CTK:
            sales_control = ctk.CTkCheckBox(
                self.tab_yoy, text="Include sales amounts (revenue), in addition to units",
                variable=self.yoy_sales_amounts,
            )
        else:
            sales_control = ttk.Checkbutton(
                self.tab_yoy, text="Include sales amounts (revenue), in addition to units",
                variable=self.yoy_sales_amounts,
            )
        sales_control.pack(anchor="w", padx=20, pady=4)

        def update_comparison_control(*_args):
            compare_control.configure(state="disabled" if self.yoy_seg.get() else "normal")

        self.yoy_seg.trace_add("write", update_comparison_control)
        update_comparison_control()

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
        _btn(self.tab_yoy, "Inspect selected file", lambda: self._inspect_inputs("yoy_reports")
            ).pack(pady=(0, 14))

    def _inspect_inputs(self, module):
        if not self._require_idle():
            return
        paths = {
            "cross_check": lambda: {"system": self.cc_sys.get(), "count": self.cc_count.get(),
                "cost": self.cc_cost.get(), "sales": self.cc_sales.get()},
            "stock_processing": lambda: {"stock": self.sp_raw.get(), "cost": self.sp_cost.get(),
                "sales": self.sp_sales.get()},
            "yoy_reports": lambda: {"file": self.yoy_file.get()},
        }[module]()
        options = ({"include_sales": self.yoy_sales_amounts.get(),
            "include_variants": self.yoy_variants.get(), "grouping": self.yoy_group.get().lower(),
            "has_families": self.yoy_has_fam.get()} if module == "yoy_reports" else {})
        profile = self.active_profile.get()
        result = queue.Queue(maxsize=1)
        self._set_busy(True)
        self._set_status("Inspecting selected workbook samples...")

        def worker():
            try:
                result.put((True, inspect_workflow_inputs(profile, module, paths, **options)))
            except Exception as exc:
                result.put((False, exc))

        def poll():
            try:
                ok, payload = result.get_nowait()
            except queue.Empty:
                self.after(100, poll)
                return
            self._set_busy(False)
            if ok:
                self._append_activity("\n" + payload.render() + "\n")
                self._set_status("Input inspection complete.")
                self._notify("info" if payload.ready else "warning", "Input inspection",
                    "Selected files look compatible." if payload.ready else
                    "Some files or configured headers need review. Details are in the activity area.")
            else:
                self._set_status("Input inspection failed.")
                self._notify("error", "Input inspection", str(payload))

        try:
            threading.Thread(target=worker, daemon=True).start()
        except RuntimeError as exc:
            self._set_busy(False)
            self._notify("error", "Input inspection", str(exc))
            return
        self.after(100, poll)

    def _exec_yoy(self):
        if not self._require_idle():
            return
        if not self._gate_setup("yoy_reports"):
            return
        f_path = self.yoy_file.get().strip()
        if not f_path or not os.path.exists(f_path):
            self._notify("error", "Missing File", "Sales data file not found.", parent=self)
            return

        if not PANDAS_AVAILABLE:
            self._notify("error", "Missing Dependency", "pandas is required.", parent=self)
            return

        try:
            s_dt = pd.to_datetime(self.yoy_start.get().strip(), format="%Y-%m-%d")
            e_dt = pd.to_datetime(self.yoy_end.get().strip(),   format="%Y-%m-%d")
            if s_dt > e_dt:
                self._notify("error", "Date Error", "Start date must be before end date.", parent=self)
                return
            e_dt = e_dt + pd.Timedelta(days=1, seconds=-1)
        except Exception as err:
            self._notify("error", "Invalid Date", f"Dates must be YYYY-MM-DD format:\n{err}", parent=self)
            return

        config_manager = ConfigurationManager(self.active_profile.get())
        yoy_config = deepcopy(config_manager.get_yoy_reports_config())
        if not yoy_config or "input" not in yoy_config:
            self._notify("error", "Config Error",
                                 f"YoY config missing for profile '{self.active_profile.get()}'.\n"
                                 "Run the Setup Wizard or edit YoY Reports in Config Hub.", parent=self)
            return

        try:
            yoy_config = select_run_metrics(yoy_config, self.yoy_sales_amounts.get())
        except ValueError as exc:
            self._handle_error(exc)
            return

        input_config = yoy_config["input"]
        grouping_column = (
            input_config["grouping_column"]
            if self.yoy_group.get() == "Family"
            else input_config["item_column"]
        )
        out = self._resolve_xlsx_output(
            self.yoy_out.get(), yoy_config["output"].get("default_path", "yoy_analysis.xlsx")
        )
        if not out:
            return

        # Capture every Tk variable on the UI thread before starting the worker.
        segmented = self.yoy_seg.get()
        if not segmented:
            yoy_config["output"]["annual_comparison"] = self.yoy_compare.get()
        has_families = self.yoy_has_fam.get()
        profile = self.active_profile.get()
        include_variants = self.yoy_variants.get()
        required_fields = ["date_column", "branch_column"]
        required_fields += ["quantity_column" if m == "units" else "sales_column" for m in yoy_config["output"]["metrics"]]
        required_fields.append("grouping_column" if self.yoy_group.get() == "Family" and has_families else "item_column")
        if include_variants:
            required_fields.append("variant_column")
        try:
            resolved = self._select_columns(f_path,
                {key: yoy_config["input"][key] for key in dict.fromkeys(required_fields)},
                DEFAULTS["yoy_reports/settings"]["input"])
            yoy_config["input"].update(resolved)
            grouping_column = yoy_config["input"]["grouping_column" if self.yoy_group.get() == "Family" else "item_column"]
        except Exception as exc:
            self._handle_error(exc)
            return

        try:
            save_last_paths(profile, {"yoy_reports": {"file": f_path, "out": out}})
        except Exception as exc:
            self._notify("error", "Path Persistence Error", str(exc), parent=self)
            return

        def task(progress, stats):
            return generate_sales_report(
                f_path, out, s_dt, e_dt, yoy_config, grouping_column,
                segmented, has_families, profile, include_variants,
                non_interactive=True,
                progress=progress,
                stats=stats,
            )
        self._run_async(task, "YoY Sales Report generated!")

    # ── Status bar & async runner ─────────────────────────────────────────────

    def _build_status_bar(self):
        self._results = BaseFrame(self._split)
        self._split.add(self._results, weight=1)
        self._result_frame = BaseFrame(self._results)
        self._result_frame.pack(side="bottom", fill="x", padx=12, pady=6)
        self._result_label = _lbl(self._result_frame, text="No report generated in this session.")
        self._result_label.pack(anchor="w", padx=6, pady=(4, 2))
        result_row = BaseFrame(self._result_frame)
        result_row.pack(fill="x", padx=6, pady=(0, 4))
        self._result_text = tk.StringVar(value="")
        result_entry = _entry(result_row, textvariable=self._result_text)
        result_entry.configure(state="readonly")
        result_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._open_report_button = _btn(result_row, "Open report", self._open_report)
        self._open_report_button.pack(side="left", padx=3)
        self._open_folder_button = _btn(result_row, "Open folder", self._open_result_folder)
        self._open_folder_button.pack(side="left", padx=3)
        self._open_report_button.configure(state="disabled")
        self._open_folder_button.configure(state="disabled")
        self._result_tabs = ttk.Notebook(self._results)
        self._result_tabs.pack(side='bottom', fill='both', expand=True, padx=12, pady=(0, 6))
        activity_page, stats_page = BaseFrame(self._result_tabs), BaseFrame(self._result_tabs)
        self._result_tabs.add(activity_page, text='Activity')
        self._result_tabs.add(stats_page, text='Statistics')
        self._stats_page = stats_page
        self._activity = BaseTextbox(activity_page, height=140 if USE_CTK else 7, wrap='word')
        self._statistics = BaseTextbox(stats_page, height=140 if USE_CTK else 7, wrap='word')
        for text in (self._activity, self._statistics):
            text.pack(fill='both', expand=True)
            text.configure(state='disabled')
        if USE_CTK:
            bar = ctk.CTkFrame(self._results, height=34, corner_radius=0)
            bar.pack(side="bottom", fill="x")
            self._status = ctk.CTkLabel(bar, text="⚡ Ready.", anchor="w")
            self._status.pack(side="left", padx=12, pady=6)
            self._progress = ctk.CTkProgressBar(bar, width=160)
            self._progress.pack(side="right", padx=12, pady=8)
            self._progress.set(0)
        else:
            bar = ttk.Frame(self._results)
            bar.pack(side="bottom", fill="x")
            self._status = ttk.Label(bar, text="⚡ Ready.", anchor="w")
            self._status.pack(side="left", padx=12, pady=4)
            self._progress = ttk.Progressbar(bar, orient="horizontal", mode="determinate", maximum=100, length=160)
            self._progress.pack(side="right", padx=12, pady=6)

    def _show_progress(self, event):
        """Display worker updates only after they reach the Tk event loop."""
        self._set_status(f"⏳ {event.fraction:.0%} | {event.message}")
        if USE_CTK:
            self._progress.set(event.fraction)
        else:
            self._progress["value"] = event.fraction * 100
        self._activity.configure(state="normal")
        self._activity.insert("end", f"[{event.completed}/{event.total}] {event.message}\n")
        self._activity.see("end")
        self._activity.configure(state="disabled")

    def _show_stats(self, event):
        """Keep final statistics separate from the stage event history."""
        rendered = event.render()
        target = getattr(self, '_statistics', self._activity)
        target.configure(state='normal')
        if hasattr(self, '_statistics'):
            target.delete('1.0', 'end')
        target.insert('end', f'\n{rendered}\n')
        target.see('end')
        target.configure(state='disabled')
        if hasattr(self, '_result_tabs'):
            self._result_tabs.select(self._stats_page)
        return rendered

    def _set_status(self, text: str):
        """Update the status bar from the Tk main thread."""
        self._status.configure(text=text)

    def _finish_progress(self, success: bool):
        if success:
            if USE_CTK:
                self._progress.set(1)
            else:
                self._progress["value"] = 100

    def _record_result(self, output_path, profile, elapsed):
        self._result_path = Path(output_path).resolve()
        self._result_text.set(str(self._result_path))
        self._result_label.configure(text=f"Last successful output | Profile: {profile} | {elapsed:.1f}s")
        self._open_report_button.configure(state="normal")
        self._open_folder_button.configure(state="normal")
        self._append_activity(f"Output: {self._result_path}\nCompleted in {elapsed:.1f}s.\n")

    def _append_activity(self, message):
        self._activity.configure(state="normal")
        self._activity.insert("end", message)
        self._activity.see("end")
        self._activity.configure(state="disabled")

    def _open_report(self):
        self._open_result(False)

    def _open_result_folder(self):
        self._open_result(True)

    def _open_result(self, folder):
        if not self._require_idle() or self._result_path is None:
            return
        target = self._result_path.parent if folder else self._result_path
        if not (target.is_dir() if folder else target.is_file()):
            self._notify("error", "Result unavailable", f"The {'folder' if folder else 'report'} no longer exists:\n{target}", parent=self)
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(target))
            else:
                command = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([command, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            self._notify("error", "Could not open result", str(exc), parent=self)

    def _require_idle(self):
        if getattr(self, "_setup_panel", None) is not None:
            self._notify("info", "Setup in progress", "Leave or finish setup before starting another action.")
            return False
        if self._busy:
            self._notify("info",
                "Task running", "Wait for the current task to finish before starting another action.",
                parent=self,
            )
            return False
        return True

    def _request_close(self):
        if self._require_idle():
            self.destroy()

    def _set_busy(self, busy):
        """Freeze run inputs and restore each control's original state on Tk's thread."""
        self._busy = busy
        if busy:
            self._running_profile = self.active_profile.get()
            self._locked_controls = []

            def disable_tree(widget):
                try:
                    state = widget.cget("state")
                except (tk.TclError, ValueError):
                    state = None
                if state is not None:
                    self._locked_controls.append((widget, state))
                    widget.configure(state="disabled")
                    # Composite CTk widgets propagate state to their internals.
                    return
                for child in widget.winfo_children():
                    disable_tree(child)

            for root in (self._top_bar, self.tab_overview, self.tab_cc, self.tab_stock, self.tab_yoy, self._result_frame):
                disable_tree(root)
        else:
            for widget, state in self._locked_controls:
                if widget.winfo_exists():
                    widget.configure(state=state)
            self._locked_controls = []
            self._running_profile = None

    def _run_async(self, func, success_msg: str, warnings=None, progress_target=None):
        """Run engine work off-thread while keeping every Tk call on the UI thread."""
        if not self._require_idle():
            return
        if any(isinstance(child, tk.Toplevel) for child in self.winfo_children()):
            self._notify("info",
                "Configuration window open",
                "Close profile and configuration windows before running a workflow.", parent=self,
            )
            return
        self._set_busy(True)
        run_profile = self._running_profile
        t_start = time.time()
        result_queue = queue.Queue(maxsize=1)
        progress_queue = queue.Queue()
        stats_queue = queue.Queue()
        summaries = []

        self._activity.configure(state="normal")
        self._activity.delete("1.0", "end")
        self._activity.configure(state="disabled")
        if USE_CTK:
            self._progress.set(0)
        else:
            self._progress["value"] = 0

        self._set_status("⏳ Running task in background... Please wait.")

        def worker():
            try:
                if progress_target is not None:
                    progress_target.progress = progress_queue.put
                    progress_target.stats = stats_queue.put
                out_path = func(progress_queue.put, stats_queue.put)
                if not out_path:
                    raise RuntimeError(
                        "The operation finished without producing an output file. "
                        "Check logs/session.log for the validation error."
                    )
                result_queue.put(("success", out_path, time.time() - t_start))
            except Exception as exc:
                log.error(f"Async error: {exc}")
                result_queue.put(("error", exc, time.time() - t_start))

        def drain_updates():
            while True:
                try:
                    self._show_progress(progress_queue.get_nowait())
                except queue.Empty:
                    break
            while True:
                try:
                    summaries.append(self._show_stats(stats_queue.get_nowait()))
                except queue.Empty:
                    break
        def poll_result():
            drain_updates()
            try:
                kind, payload, elapsed = result_queue.get_nowait()
            except queue.Empty:
                self.after(100, poll_result)
                return

            # Completion is queued after all updates; drain again to close the race.
            drain_updates()
            self._set_busy(False)
            if kind == "success":
                out_path = payload
                self._set_status(f"✅ Done in {elapsed:.1f}s  |  {out_path}")
                self._finish_progress(True)
                self._record_result(out_path, run_profile, elapsed)
                self._notify("info",
                    "Done",
                    f"{success_msg}\n\nTime: {elapsed:.1f}s\nOutput: {out_path}"
                    + ("\n\nWarnings:\n" + "\n".join(warnings) if warnings else ""),
                    parent=self,
                )
            else:
                exc = payload
                self._set_status(f"❌ Error: {exc}")
                self._finish_progress(False)
                self._append_activity(f"Error: {exc}\n")
                self._handle_error(exc)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as exc:
            self._set_busy(False)
            self._set_status(f"Error: {exc}")
            self._append_activity(f"Error: {exc}\n")
            self._notify("error", "Execution Error", str(exc), parent=self)
            return
        self.after(100, poll_result)


# ── Entry point ───────────────────────────────────────────────────────────────

def launch_gui():
    BUILD.require("gui")
    app = InventoryToolkitGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
