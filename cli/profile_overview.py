"""Console profile overview and direct module setup access."""

from cli.utils import clear_screen, input_default, load_last_paths
from cli.wizard import run_module_setup
from core.configuration_manager import ConfigurationManager
from core.input_doctor import inspect_workflow_inputs
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
        print("\n  Choose a number for setup, I1/I2/I3 to inspect remembered files, or Enter to return.")
        choice = input("  Selection: ").strip()
        if not choice:
            return
        if choice.upper() in {"I1", "I2", "I3"}:
            entry = entries[int(choice[1]) - 1]
            try:
                saved = load_last_paths(profile).get(entry.module, {})
                if entry.module == "cross_check":
                    examples = {"system": "cross_check_system_stock.xls", "count": "cross_check_physical_count.xlsx",
                        "cost": "shared_cost_list.xlsx", "sales": "shared_sales_price_list.xlsx"}
                elif entry.module == "stock_processing":
                    examples = {"stock": "stock_processing_raw_stock.xlsx",
                        "cost": "shared_cost_list.xlsx", "sales": "shared_sales_price_list.xlsx"}
                else:
                    examples = {"file": "yoy_sales_history.xlsx"}
                files = {name: input_default(profile, saved.get(name), example)
                    for name, example in examples.items()}
                options = {}
                if entry.module == "yoy_reports":
                    size_default = bool(ConfigurationManager(profile)
                        .get_yoy_reports_config()["output"]["include_sizes"])
                    group = input("  Inspect Family (F) or Item (I) grouping? [I]: ").strip().lower()
                    options["grouping"] = "family" if group == "f" else "item"
                    options["has_families"] = (input("  Does the file contain a Family column? [y/N]: ")
                        .strip().lower() == "y") if group == "f" else False
                    options["include_sales"] = input("  Include revenue columns? [y/N]: ").strip().lower() == "y"
                    answer = input(f"  Include size breakdown? [{'Y/n' if size_default else 'y/N'}]: ").strip().lower()
                    options["include_sizes"] = size_default if not answer else answer == "y"
                print("\n" + inspect_workflow_inputs(profile, entry.module, files, **options).render())
            except (OSError, ValueError) as exc:
                print(f"\n  Could not inspect inputs: {exc}")
            input("\n  Press Enter to return...")
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            entry = entries[int(choice) - 1]
            if entry.issue:
                print("  Fix the profile configuration before opening guided setup.")
                input("  Press Enter to return...")
            else:
                run_module_setup(profile, entry.module, entry.pending_step)
