"""Console rendering for the shared, module-specific setup catalog."""
from pathlib import Path
from cli.utils import ask_file, clear_screen
from core.profile_config import ensure_profile_config
from core.configuration_errors import ConfigurationError

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def initialize_profile_files(configs_path: str) -> None:
    """Compatibility entry point used by profile creation."""
    ensure_profile_config(Path(configs_path))


def _load_columns(path: str) -> tuple[list[str], object | None]:
    if not path or not PANDAS_AVAILABLE:
        return [], None
    try:
        df = pd.read_excel(path, nrows=20)
        return [str(c) for c in df.columns], df
    except Exception as exc:
        print(f"  ❌ Could not read '{path}': {exc}")
        return [], None


def _pick(label: str, columns: list[str], current: str = "", hints=(), *, optional=False) -> str:
    default = current or ""
    print(f"\n  {label}")
    if columns:
        for idx, col in enumerate(columns, 1):
            marker = " ← current" if col == current else ""
            print(f"    [{idx:02d}] {col}{marker}")
        raw = input(f"  Choose number or type a column name [Enter={default or 'keep'}]: ").strip()
        if raw == "-" and optional:
            return ""
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(columns):
            return columns[int(raw) - 1]
        return raw
    raw = input(f"  {label} [Enter={default or 'unchanged'}]: ").strip()
    return "" if raw == "-" and optional else (raw or default)


def _sample_file(label: str) -> tuple[str, list[str], object | None]:
    print(f"\n  {label}")
    path = ask_file("Sample Excel", "")
    if not path:
        return "", [], None
    columns, df = _load_columns(path)
    if columns:
        print(f"  ✅ {len(columns)} columns detected.")
    return path, columns, df


def run_setup_wizard(profile_dir: str, profile_name: str = "") -> None:
    from cli.config_menu import configuration_menu
    configuration_menu(profile_name or Path(profile_dir).name)


def run_module_setup(profile: str, module: str, step_id: str | None = None, *, include_advanced=False, single_page=False) -> None:
    """Configure one workflow through the shared page contract, saving each page."""
    from core.setup_service import SetupSession
    from core.setup_catalog import get_value, MODULE_LABELS
    from core.column_assist import advise_columns

    session = SetupSession(profile, module, include_advanced=include_advanced)
    pending = step_id or session.first_pending()
    index = next((i for i, step in enumerate(session.steps) if step.id == pending), 0)
    samples = {}
    try:
        while index < len(session.steps):
            step = session.steps[index]
            clear_screen()
            print(f'\n  {MODULE_LABELS[module]} setup | {index + 1}/{len(session.steps)}: {step.title}\n')
            if step.shared:
                print('  Shared settings: edits affect other modules in this profile.')
            print('  Saved pages are retained. Ctrl+C leaves setup without saving this page.')
            action = input('  Enter to edit, B to go back, Q to pause: ').strip().lower()
            if action == 'q':
                return
            if action == 'b':
                index = max(0, index - 1)
                continue
            scope = step.sample or step.id
            if any(f.kind == 'column' for f in step.fields):
                if scope not in samples or input('  Reuse the previous sample for this input? [Y/n]: ').strip().lower() == 'n':
                    samples[scope] = _sample_file('Optional: select the actual workbook to see its headers.')
                _, columns, _ = samples[scope]
            else:
                columns = []
            values = {}
            data = session.data(step)
            if columns:
                current = {'.'.join(field.path): get_value(data, field.path) for field in step.fields if field.kind == 'column'}
                for advice in advise_columns(step.fields, current, columns):
                    if advice.present:
                        continue
                    field = next(field for field in step.fields if '.'.join(field.path) == advice.field)
                    if advice.suggestion:
                        print(f'  {field.label}: configured {advice.configured!r} is absent; possible {advice.suggestion!r}.')
                    elif advice.ambiguous:
                        print(f'  {field.label}: multiple possible headers ({", ".join(advice.ambiguous)}). Choose manually.')
                    elif field.sample_required:
                        print(f'  {field.label}: configured {advice.configured!r} is absent from this sample.')
            for field in step.fields:
                key = '.'.join(field.path)
                current = get_value(data, field.path)
                print(f'\n  {field.label}\n  {field.help}')
                if field.kind == 'column':
                    values[key] = _pick(field.label, columns, current, optional=field.optional)
                elif field.kind == 'bool':
                    while True:
                        answer = input(f'  Enabled? [Y/N, Enter keeps {current}]: ').strip().lower()
                        if answer in ('', 'y', 'n'):
                            values[key] = current if not answer else answer == 'y'
                            break
                elif field.kind == 'choice':
                    for number, (label, stored) in enumerate(field.choices, 1):
                        print(f'    {number}. {label}' + (' (current)' if stored == current else ''))
                    while True:
                        raw = input('  Choose a number [Enter keeps current]: ').strip()
                        if not raw:
                            values[key] = current
                            break
                        if raw.isdigit() and 1 <= int(raw) <= len(field.choices):
                            values[key] = field.choices[int(raw) - 1][1]
                            break
                        print('  Choose one of the numbered options.')
                elif field.kind == 'number':
                    while True:
                        raw = input(f'  Number [Enter={current}]: ').strip()
                        try:
                            values[key] = float(raw) if raw else current
                            break
                        except ValueError:
                            print('  Enter a numeric value.')
                elif field.kind in {'list', 'metrics'}:
                    raw = input(f'  Comma-separated values [Enter keeps {current}; - clears]: ').strip()
                    values[key] = current if not raw else ([] if raw == '-' else list(dict.fromkeys(x.strip() for x in raw.split(',') if x.strip())))
                elif field.kind in {'mapping', 'rules', 'groups', 'summaries'}:
                    values[key] = _setup_table(field.kind, current)
                else:
                    raw = input(f'  Value [Enter keeps {current}]: ').strip()
                    values[key] = '' if raw == '-' and field.optional else (raw or current)
            try:
                session.save_step(step.id, values)
            except ValueError as exc:
                print(f'  Not saved: {exc}')
                input('  Press Enter to review this page...')
                continue
            if single_page:
                print('  Settings saved. Return to this module to finish any remaining setup.')
                input('  Press Enter...')
                return
            index += 1
        session.validate_required()
        print('\n  Review your setup:\n')
        for line in session.review_summary():
            print('  ' + line)
        print('\n  Setup complete. Return to the menu and run when ready.')
        input('  Press Enter...')
    except KeyboardInterrupt:
        print('\n  Setup paused. Previously saved pages are retained.')
    except ConfigurationError as exc:
        print(f'  Setup remains partial: {exc}')
        input('  Press Enter...')


def _setup_table(kind, current):
    """Edit typed rows one at a time without asking operators to write JSON."""
    from copy import deepcopy
    result = deepcopy(current)
    print(f'  Existing rows: {len(result)}')
    for name, value in ([(item['sheet_name'], ', '.join(item['entities'])) for item in result] if kind == 'summaries' else result.items()):
        print(f'    {name}: {value}')
    print('  Enter a name to add/replace, -name to remove, or Enter to finish.')
    while True:
        name = input('  Name: ').strip()
        if not name:
            return result
        if name.startswith('-'):
            if kind == 'summaries':
                result = [item for item in result if item['sheet_name'] != name[1:]]
            else:
                result.pop(name[1:], None)
            continue
        if kind == 'summaries':
            entities = input('  Stores (comma-separated): ')
            titles = input('  Display titles (comma-separated): ')
            result = [item for item in result if item['sheet_name'] != name]
            result.append({'sheet_name': name, 'entities': [x.strip() for x in entities.split(',') if x.strip()], 'titles': [x.strip() for x in titles.split(',') if x.strip()]})
        else:
            raw = input('  Members/prefixes (comma-separated): ' if kind in {'rules', 'groups'} else '  Target value: ').strip()
            if not raw:
                print('  Empty row ignored. Use -name to remove it.')
                continue
            result[name] = list(dict.fromkeys(x.strip() for x in raw.split(',') if x.strip())) if kind in {'rules', 'groups'} else raw
