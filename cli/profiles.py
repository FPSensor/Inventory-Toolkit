"""
profiles.py — Profile selection and creation for Inventory Toolkit.

Linear new-profile flow:
  1. Choose folder name
  2. Choose display name + description
  3. Create file structure
  4. Optionally run the Setup Wizard
"""

import os
from core.build import BUILD
from core.module_preferences import set_enabled_modules
from core.setup_catalog import MODULE_LABELS
import sys
from cli.utils import clear_screen, load_json, save_json, ask_yes_no
from cli.wizard import initialize_profile_files, run_setup_wizard
from core import paths as app_paths
from core.setup_service import initialize_setup


# ── Internal helpers ──────────────────────────────────────────────────────────

def _profile_info(folder: str):
    """Return (display_name, description) for a profile folder."""
    info_path = app_paths.profile_root(folder) / "profile.json"
    if os.path.exists(info_path):
        info = load_json(info_path) or {}
        return info.get("name", folder), info.get("description", "")
    return folder, ""


def _list_profiles():
    app_paths.PROFILES_ROOT.mkdir(parents=True, exist_ok=True)
    return sorted(
        path.name for path in app_paths.PROFILES_ROOT.iterdir()
        if path.is_dir()
    )


# ── New profile ───────────────────────────────────────────────────────────────

def _create_new_profile() -> str | None:
    from core.profile_creation import create_profile
    print("\n  CREATE A PROFILE — choose only what you use\n")
    name = input("  Profile name (Enter cancels): ").strip()
    if not name:
        return None
    description = input("  Description (optional): ").strip()
    choices = list(MODULE_LABELS)
    for index, module in enumerate(choices, 1):
        print(f"  {index}. {MODULE_LABELS[module]}")
    while True:
        raw = input("  Workflows, comma-separated [Enter=all]: ").strip()
        parts = [part.strip() for part in raw.split(',')] if raw else ['1', '2', '3']
        if all(part in {'1', '2', '3'} for part in parts):
            break
        print("  Choose workflow numbers 1, 2 or 3.")
    try:
        profile = create_profile(name, description, [choices[int(part) - 1] for part in parts])
    except (ValueError, OSError) as exc:
        print(f"  Could not create profile: {exc}")
        input("  Press Enter...")
        return None
    print("  Profile created. Choose a workflow to configure it with your own files.")
    input("  Press Enter...")
    return profile


# ── Profile selector ──────────────────────────────────────────────────────────

def select_profile(current_profile: str | None, is_startup: bool = False) -> str:
    while True:
        clear_screen()
        print("=" * 50)
        print("  👤  PROFILE SELECTION")
        print("=" * 50)

        if current_profile:
            print(f"  Active profile: [{current_profile}]\n")
        else:
            print("  👋 Welcome. Select or create a profile.\n")

        profiles = _list_profiles()

        if not profiles:
            print("  ⚠️  No profiles found. Create a new one.\n")
        else:
            print("  Available profiles:")
            for i, folder in enumerate(profiles, 1):
                name, desc = _profile_info(folder)
                active = " 🟢" if folder == current_profile else ""
                desc_str = f"  —  {desc}" if desc else ""
                print(f"    [{i}] {name}{desc_str}{active}  (folder: {folder})")

        print()
        print("  [N] Create new profile")
        if not is_startup or current_profile:
            print("  [0] Return to main menu")
        if is_startup and not profiles:
            print("  [E] Exit")

        opt = input("\n  Choose an option: ").strip().upper()

        # ── Actions ──────────────────────────────────────────────────────────

        if opt == "0" and (not is_startup or current_profile):
            return current_profile

        elif opt == "E" and is_startup and not profiles:
            sys.exit(0)

        elif opt == "N":
            new_folder = _create_new_profile()
            if new_folder:
                current_profile = new_folder
                if is_startup:
                    return current_profile

        elif opt.isdigit() and 1 <= int(opt) <= len(profiles):
            selected = profiles[int(opt) - 1]
            name, _ = _profile_info(selected)
            current_profile = selected
            print(f"\n  ✅ Profile switched to '{name}'.")
            input("  Press Enter to continue...")
            if is_startup:
                return current_profile

        else:
            print("  ❌ Invalid option.")
            input("  Press Enter to continue...")
