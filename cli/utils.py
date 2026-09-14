"""
utils.py — Shared helpers for the Inventory Toolkit CLI.

Provides:
  • clear_screen()
  • ask_yes_no(message)            → bool
  • ask_file(message, default, is_output) → str
  • load_last_paths / save_last_paths   — per-profile path persistence
  • validate_files_exist(file_list) → bool
  • open_in_editor(path)           — cross-platform (Linux / macOS / Windows)
  • load_json / save_json
"""

import os
import sys
import json
import subprocess

try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

from core.logger import log

PROFILES_DIR = "profiles"
_LAST_PATHS_FILE = "last_paths.json"


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

    if resp.upper() == "B" and TKINTER_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        if is_output:
            path = filedialog.asksaveasfilename(
                title="Save result as...",
                initialfile=default_val,
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx *.xls")],
            )
        else:
            path = filedialog.askopenfilename(
                title="Select file",
                filetypes=[("Excel", "*.xlsx *.xls"), ("All files", "*.*")],
            )
        root.destroy()

        if path:
            print(f"  File selected: {path}")
            return path
        print("  Selection cancelled — using default value.")
        return default_val

    return resp if resp else default_val


# ── Path persistence ──────────────────────────────────────────────────────────

def load_last_paths(profile: str) -> dict:
    """Load the saved file paths for *profile*. Returns {} if none saved yet."""
    path = os.path.join(PROFILES_DIR, profile, _LAST_PATHS_FILE)
    return load_json(path) or {}


def save_last_paths(profile: str, paths: dict) -> None:
    """Persist file paths for *profile* so the next run can pre-fill them."""
    path = os.path.join(PROFILES_DIR, profile, _LAST_PATHS_FILE)
    existing = load_last_paths(profile)
    existing.update(paths)
    save_json(path, existing)


# ── File validation ───────────────────────────────────────────────────────────

def validate_files_exist(file_list: list) -> bool:
    all_ok = True
    for fp in file_list:
        if fp and not os.path.isfile(fp):
            log.error(f"File not found: '{fp}'")
            all_ok = False
    return all_ok


# ── Editor — cross-platform ───────────────────────────────────────────────────

def open_in_editor(path: str) -> None:
    """Open *path* in the system's default text editor (Linux / macOS / Windows)."""
    print(f"  Opening {os.path.basename(path)} in the default editor...")
    try:
        if sys.platform.startswith("darwin"):
            subprocess.call(("open", path))
        elif sys.platform.startswith("linux"):
            subprocess.call(("xdg-open", path))
        elif os.name == "nt":
            # os.startfile is Windows-only; subprocess keeps cross-platform parity
            subprocess.call(("cmd", "/c", "start", "", path))
        else:
            subprocess.call(("xdg-open", path))
    except Exception as e:
        log.error(f"Could not open file automatically: {e}")
    input("\n  Press Enter when you have saved the file...")


# ── JSON I/O ──────────────────────────────────────────────────────────────────

def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        log.error(f"File {path} is corrupted or contains invalid JSON.")
        return None


def save_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"Error saving file: {e}")


# ── Output helpers ────────────────────────────────────────────────────────────

def print_success(msg: str) -> None:
    """Print a success message with a checkmark prefix."""
    print(f"  ✓  {msg}")


def print_error(msg: str) -> None:
    """Print an error message with a cross prefix."""
    print(f"  ✗  {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message with a warning-sign prefix."""
    print(f"  ⚠  {msg}")


def print_info(msg: str) -> None:
    """Print an informational message with an info prefix."""
    print(f"  ℹ  {msg}")


def print_section(title: str, width: int = 50) -> None:
    """Print a section header padded with a horizontal rule."""
    print(f"\n  ── {title} {'─' * max(0, width - len(title) - 5)}")
