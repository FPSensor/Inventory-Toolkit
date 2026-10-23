"""One module-oriented configuration menu using the same guided editors."""
from cli.utils import clear_screen
from cli.wizard import run_module_setup
from core.configuration_manager import ConfigurationManager
from core.module_preferences import enabled_modules, set_enabled_modules
from core.profile_overview import inspect_profile
from core.setup_catalog import MODULE_LABELS
from core.setup_service import SetupSession


def select_workflows(profile):
    names = list(MODULE_LABELS)
    selected = enabled_modules(profile)
    print("\n  Choose workflows to enable. Disabled workflows keep their settings.")
    for index, name in enumerate(names, 1):
        print(f"  {index}. {MODULE_LABELS[name]}" + (" (enabled)" if name in selected else ""))
    raw = input("  Numbers separated by commas, or Enter to keep: ").strip()
    if not raw:
        return
    parts = [part.strip() for part in raw.split(',')]
    if not all(part in {'1', '2', '3'} for part in parts):
        raise ValueError("Choose workflow numbers 1, 2 or 3.")
    set_enabled_modules(profile, [names[int(part) - 1] for part in parts])


def _module_settings(profile, module):
    while True:
        clear_screen()
        session = SetupSession(profile, module, include_advanced=True)
        print(f"\n  {MODULE_LABELS[module]} — setup and settings\n")
        print("  G. Guided setup (essential questions only)")
        print("  V. Validate this workflow")
        print("  0. Back\n")
        query = input("  Search a setting, Enter to list all, or G/V/0: ").strip()
        if query == '0':
            return
        if query.upper() == 'G':
            run_module_setup(profile, module)
            continue
        if query.upper() == 'V':
            ConfigurationManager(profile, module=module)
            session.validate_required()
            print("  Configuration validates. Selected files are checked separately.")
            input("  Press Enter...")
            continue
        steps = [step for step in session.steps if not query or query.lower() in
            ' '.join([step.title, *(field.label + ' ' + field.help for field in step.fields)]).lower()]
        if not steps:
            print("  No matching settings. Try a product, price, location or report term.")
            input("  Press Enter...")
            continue
        for index, step in enumerate(steps, 1):
            labels = ', '.join(field.label for field in step.fields)
            print(f"  {index}. {step.title} — {labels}")
        choice = input("  Choose a section number, or Enter to search again: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(steps):
            run_module_setup(profile, module, steps[int(choice) - 1].id, include_advanced=True, single_page=True)


def configuration_menu(current_profile):
    while True:
        clear_screen()
        print(f"\n  CONFIGURATION — {current_profile}\n")
        entries = inspect_profile(current_profile)
        enabled = [entry for entry in entries if entry.enabled]
        for index, entry in enumerate(enabled, 1):
            print(f"  {index}. {entry.label} — {entry.status}")
            if entry.pending_titles:
                print(f"     Next: {entry.pending_titles[0]}")
            if entry.issue:
                print(f"     {entry.issue}")
        print("\n  M. Choose enabled workflows")
        print("  0. Back")
        choice = input("\n  Choose a workflow: ").strip().upper()
        if choice == '0':
            return
        try:
            if choice == 'M':
                select_workflows(current_profile)
            elif choice.isdigit() and 1 <= int(choice) <= len(enabled):
                _module_settings(current_profile, enabled[int(choice) - 1].module)
        except (ValueError, OSError) as exc:
            print(f"  Could not update configuration: {exc}")
            input("  Press Enter...")
