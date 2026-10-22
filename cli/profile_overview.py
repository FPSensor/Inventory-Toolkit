"""Console profile overview and direct module setup access."""

from cli.utils import clear_screen
from cli.wizard import run_module_setup
from core.profile_overview import inspect_profile


def show_profile_overview(profile):
    while True:
        clear_screen()
        print(f"\n  PROFILE OVERVIEW — {profile}\n")
        entries = inspect_profile(profile)
        for index, entry in enumerate(entries, 1):
            progress = (f"{entry.reviewed}/{entry.total} pages reviewed"
                if entry.reviewed is not None else "existing profile")
            print(f"  [{index}] {entry.label}: {entry.status} | {progress}")
            if entry.issue:
                print(f"      {entry.issue}")
            elif entry.pending_titles:
                print(f"      Next: {entry.pending_titles[0]}")
                if len(entry.pending_titles) > 1:
                    print(f"      {len(entry.pending_titles) - 1} more pages to review")
        print("\n  Choose a number to review its setup, or press Enter to return.")
        choice = input("  Selection: ").strip()
        if not choice:
            return
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            entry = entries[int(choice) - 1]
            if entry.issue:
                print("  Fix the profile configuration before opening guided setup.")
                input("  Press Enter to return...")
            else:
                run_module_setup(profile, entry.module, entry.pending_step)
