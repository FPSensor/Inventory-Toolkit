"""
profiles.py — Profile selection and creation for Inventory Toolkit.

Linear new-profile flow:
  1. Choose folder name
  2. Choose display name + description
  3. Create file structure
  4. Optionally run the Setup Wizard
"""

import os
import sys
from cli.utils import clear_screen, load_json, save_json, ask_yes_no
from cli.wizard import initialize_profile_files, run_setup_wizard

PROFILES_DIR = "profiles"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _profile_info(folder: str):
    """Return (display_name, description) for a profile folder."""
    info_path = os.path.join(PROFILES_DIR, folder, "profile.json")
    if os.path.exists(info_path):
        info = load_json(info_path) or {}
        return info.get("name", folder), info.get("description", "")
    return folder, ""


def _list_profiles():
    os.makedirs(PROFILES_DIR, exist_ok=True)
    return sorted(
        d for d in os.listdir(PROFILES_DIR)
        if os.path.isdir(os.path.join(PROFILES_DIR, d))
    )


# ── New profile ───────────────────────────────────────────────────────────────

def _create_new_profile() -> str | None:
    """
    Linear new-profile creation.
    Returns the folder name of the created profile, or None if cancelled.
    """
    print("\n" + "=" * 50)
    print("  ➕  CREATE NEW PROFILE")
    print("=" * 50)

    # 1. Folder name
    while True:
        folder = (
            input("  Folder name (e.g. my_company): ")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        if not folder:
            print("  ❌ Name cannot be empty.")
            continue
        profile_path = os.path.join(PROFILES_DIR, folder)
        if os.path.exists(profile_path):
            print(f"  ❌ A profile named '{folder}' already exists.")
            continue
        break

    # 2. Display name + description
    display_name = input(f"  Display name [{folder}]: ").strip() or folder
    description  = input("  Description (optional): ").strip()

    # 3. Create structure
    configs_path = os.path.join(profile_path, "configs")
    os.makedirs(configs_path, exist_ok=True)
    initialize_profile_files(configs_path)

    save_json(os.path.join(profile_path, "profile.json"), {
        "name":        display_name,
        "description": description,
        "version":     "1.3.1"
    })

    print(f"\n  ✅ Profile '{display_name}' created at: profiles/{folder}/\n")

    # 4. Wizard (optional but recommended)
    print("  The Setup Wizard reads a Stock file and configures")
    print("  columns and stores automatically in minutes.\n")
    if ask_yes_no("  Run the Setup Wizard now?"):
        run_setup_wizard(profile_path, display_name)
    else:
        print(
            "  ℹ️  You can run it later from:\n"
            "       Main menu → ⚙️  Configuration → [W] Quick Setup Wizard"
        )
        input("  Press Enter to continue...")

    return folder


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
