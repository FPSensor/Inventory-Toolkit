"""
utils.py — Shared helpers for the Inventory Toolkit CLI.

Provides:
  • clear_screen()
  • ask_yes_no(message)            → bool
  • ask_file(message, default, is_output) → str
"""

import os


try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

from core.runtime.logger import log_debug_event
from core.files.table_reader import FILE_PATTERNS
from core.runtime.paths import demo_root


# ── Screen ────────────────────────────────────────────────────────────────────

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


# ── Input helpers ─────────────────────────────────────────────────────────────

def ask_yes_no(message: str) -> bool:
    """Prompt the user for a yes/no answer. Accepts Y/y or N/n."""
    while True:
        resp = input(f"{message} [Y/N]: ").strip().upper()
        if resp in ("Y",):
            return True
        if resp == "N":
            return False
        print("  Invalid input — enter 'Y' for yes or 'N' for no.")


def confirm_default_column(field: str, configured: str, default: str) -> bool:
    return ask_yes_no(
        f"Configured {field} column '{configured}' is absent. "
        f"Try default '{default}' for this run?"
    )


def input_default(profile: str, saved_path: str | None, demo_filename: str, other_default: str | None = None) -> str:
    """Prefer a saved input; otherwise locate demo fixtures independent of CWD."""
    if saved_path:
        return saved_path
    if profile == "demo":
        return str(demo_root() / demo_filename)
    return demo_filename if other_default is None else other_default


def ask_file(message: str, default_val: str, is_output: bool = False) -> str:
    """
    Ask the user for a file path.
    - Press Enter to accept *default_val*.
    - Type 'B' to open a system file browser (requires tkinter).
    """
    hint = f"Enter='{default_val}'" if default_val else "Enter to skip"
    if TKINTER_AVAILABLE:
        hint += ", 'B' to browse"

    resp = input(f"  {message} ({hint}): ").strip()
    log_debug_event(
        "file_prompt_response",
        prompt=message,
        used_default=not bool(resp),
        requested_browser=resp.upper() == "B",
        is_output=is_output,
    )

    if resp.upper() == "B" and TKINTER_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        if is_output:
            path = filedialog.asksaveasfilename(
                title="Save result as...",
                initialfile=default_val,
                defaultextension=".xlsx",
                filetypes=[("Excel Workbook", "*.xlsx")],
            )
        else:
            path = filedialog.askopenfilename(
                title="Select file",
                filetypes=[("Tables", FILE_PATTERNS), ("All files", "*.*")],
            )
        root.destroy()

        if path:
            print(f"  File selected: {path}")
            log_debug_event("file_browser_selected", prompt=message, path=path, is_output=is_output)
            return path
        print("  Selection cancelled — using default value.")
        return default_val

    selected = resp if resp else default_val
    log_debug_event("file_prompt_resolved", prompt=message, path=selected, is_output=is_output)
    return selected


# ── Path persistence ──────────────────────────────────────────────────────────
