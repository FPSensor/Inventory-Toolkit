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
import tempfile
from pathlib import Path

from core.configuration_errors import ConfigurationFileError

try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

from core.logger import log, log_debug_event, log_exception
from core.paths import demo_root, profile_root
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
                filetypes=[("Excel", "*.xlsx *.xls"), ("All files", "*.*")],
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

def load_last_paths(profile: str) -> dict:
    """Load the saved file paths for *profile*. Returns {} if none saved yet."""
    path = profile_root(profile) / _LAST_PATHS_FILE
    payload = load_json(str(path)) or {}
    log_debug_event("last_paths_loaded", profile=profile, path=path, sections=sorted(payload.keys()))
    return payload


def save_last_paths(profile: str, paths: dict) -> None:
    """Persist file paths for *profile* so the next run can pre-fill them."""
    path = profile_root(profile) / _LAST_PATHS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_last_paths(profile)
    existing.update(paths)
    save_json(str(path), existing)
    log_debug_event("last_paths_saved", profile=profile, path=path, sections=sorted(paths.keys()))


# ── File validation ───────────────────────────────────────────────────────────

def validate_files_exist(file_list: list) -> bool:
    all_ok = True
    missing = []
    for fp in file_list:
        if fp and not os.path.isfile(fp):
            log.error(f"File not found: '{fp}'")
            missing.append(fp)
            all_ok = False
    log_debug_event(
        "file_validation",
        requested=len(file_list),
        missing=missing,
        ok=all_ok,
    )
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
        log_exception("Could not open file automatically: %s", e)
    input("\n  Press Enter when you have saved the file...")


# ── JSON I/O ──────────────────────────────────────────────────────────────────

def _validate_profile_document(path: Path, payload) -> None:
    """Validate editor documents before they can be read or replace a profile file."""
    if "configs" not in path.parts:
        return
    logical = Path(*path.parts[path.parts.index("configs") + 1:]).with_suffix("").as_posix()
    from core.configuration_manager import _CONFIG_MODELS

    model = _CONFIG_MODELS.get(logical)
    if model is None:
        return
    try:
        model.model_validate(payload)
    except Exception as exc:
        raise ConfigurationFileError(path, f"invalid profile configuration: {exc}") from exc

def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        _validate_profile_document(Path(path), payload)
        log_debug_event("json_loaded", path=path, payload_type=type(payload).__name__)
        return payload
    except FileNotFoundError:
        log_debug_event("json_missing", path=path)
        return None
    except json.JSONDecodeError as exc:
        raise ConfigurationFileError(
            Path(path), f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise ConfigurationFileError(Path(path), f"could not be read: {exc}") from exc


def save_json(path: str, data) -> None:
    target = Path(path)
    if target.exists() and "configs" in target.parts:
        load_json(str(target))  # Never replace a corrupt or future-version profile.
    _validate_profile_document(target, data)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.write("\n")
        temporary.replace(target)
        log_debug_event("json_saved", path=path, payload_type=type(data).__name__)
    except (OSError, TypeError, ValueError) as exc:
        raise ConfigurationFileError(target, f"could not be saved: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
