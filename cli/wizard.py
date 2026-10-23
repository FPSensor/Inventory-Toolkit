"""Module-oriented setup wizard for the current Inventory Toolkit configuration schema.

Unlike the old linear wizard, every module can be configured independently and
with the Excel file that actually belongs to that workflow.  Progress is saved
immediately, so users can leave and return at any time.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from cli.utils import ask_file, clear_screen, load_json, save_json
from core.profile_config import DEFAULTS, config_path, ensure_profile_config, profile_readiness
from core.resource_config import load_resource
from core.configuration_errors import ConfigurationError
from core.system_utils import InvalidExcelOutputPathError, normalize_xlsx_output_path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

_COLUMN_HINTS = load_resource("column_hints.json")
_ARTICLE_HINTS = tuple(_COLUMN_HINTS["article_hints"])
_FAMILY_HINTS = tuple(_COLUMN_HINTS["family_hints"])
_DATE_HINTS = tuple(_COLUMN_HINTS["date_hints"])
_QTY_HINTS = tuple(_COLUMN_HINTS["qty_hints"])
_BRANCH_HINTS = tuple(_COLUMN_HINTS["branch_hints"])
_PRICE_HINTS = tuple(_COLUMN_HINTS["price_hints"])
_SALES_HINTS = tuple(_COLUMN_HINTS["sales_hints"])
_DB_HINTS = tuple(_COLUMN_HINTS["db_hints"])
_VARIANT_HINTS = tuple(_COLUMN_HINTS["variant_hints"])
_NON_STORE = tuple(_COLUMN_HINTS["non_store"])


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


def _auto(columns: Iterable[str], hints: Iterable[str]) -> Optional[str]:
    lowered = [(c, str(c).lower()) for c in columns]
    for hint in hints:
        for original, value in lowered:
            if hint in value:
                return original
    return None


def _pick(label: str, columns: list[str], current: str = "", hints=()) -> str:
    detected = _auto(columns, hints) if columns else None
    default = current or detected or ""
    print(f"\n  {label}")
    if detected and detected != current:
        print(f"    Auto-detected: {detected}")
    if columns:
        for idx, col in enumerate(columns, 1):
            marker = " ← current" if col == current else ""
            print(f"    [{idx:02d}] {col}{marker}")
        raw = input(f"  Choose number or type a column name [Enter={default or 'keep'}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(columns):
            return columns[int(raw) - 1]
        return raw
    raw = input(f"  {label} [Enter={default or 'unchanged'}]: ").strip()
    return raw or default


def _sample_file(label: str) -> tuple[str, list[str], object | None]:
    print(f"\n  {label}")
    path = ask_file("Sample Excel", "")
    if not path:
        return "", [], None
    columns, df = _load_columns(path)
    if columns:
        print(f"  ✅ {len(columns)} columns detected.")
    return path, columns, df


def _save(configs: Path, logical: str, data: dict) -> None:
    save_json(str(config_path(configs, logical)), data)


def _dashboard(configs: Path, profile_name: str) -> None:
    ready = profile_readiness(configs)
    print("=" * 72)
    print(f"  🧭 INVENTORY TOOLKIT SETUP — {profile_name or configs.parent.name}")
    print("=" * 72)
    labels = [
        ("catalog", "Catalog & families"), ("stores", "Stores & network"),
        ("stock", "Stock Processing"), ("cross_check", "Cross Check"),
        ("yoy", "YoY Reports"),
    ]
    for key, label in labels:
        ok, detail = ready[key]
        print(f"  {'✅' if ok else '⚠️ '} {label:<22} {detail}")
    print("\n  Configure only what you use. Every section saves immediately.")


def _setup_catalog(configs: Path) -> None:
    clear_screen(); print("=== CATALOG & FAMILIES ===")
    catalog = load_json(str(config_path(configs, "general/catalog"))) or {}
    columns_cfg = catalog.setdefault("columns", {})
    _, columns, _ = _sample_file("Optional: select a Stock/Inventory file to detect core columns.")
    columns_cfg["article"] = _pick("Article / SKU column", columns, columns_cfg.get("article", DEFAULTS["general/catalog"]["columns"]["article"]), _ARTICLE_HINTS)
    columns_cfg["family"] = _pick("Family column", columns, columns_cfg.get("family", DEFAULTS["general/catalog"]["columns"]["family"]), _FAMILY_HINTS)
    raw = input(f"  Default family when no rule matches [Enter={catalog.get('default_family', DEFAULTS['general/catalog']['default_family'])}]: ").strip()
    if raw:
        catalog["default_family"] = raw
    _save(configs, "general/catalog", catalog)
    families = load_json(str(config_path(configs, "general/families"))) or {"version": 3, "rules": {}}
    print(f"  ✅ Catalog saved. Family rules currently: {len(families.get('rules', {}))}")
    print("  Family rules are easier to maintain from Config Hub → Catalog & Families.")
    input("  Press Enter...")


def _setup_network(configs: Path) -> None:
    clear_screen(); print("=== STORES & NETWORK ===")
    network = load_json(str(config_path(configs, "general/network"))) or {"version": 3}
    _, columns, df = _sample_file("Optional: select a raw Stock file to detect numeric store columns.")
    active = list(network.get("active", []))
    candidates = []
    if df is not None:
        numeric = [str(c) for c in df.select_dtypes(include="number").columns]
        candidates = [c for c in numeric if not any(h in c.lower() for h in _NON_STORE)]
    if candidates:
        print(f"  Possible stores: {', '.join(candidates)}")
        use = input("  Use these? [Y/n]: ").strip().lower()
        if use in ("", "y", "yes"):
            active = candidates
    raw = input(f"  Active stores comma-separated [Enter keeps {len(active)}]: ").strip()
    if raw:
        active = [x.strip() for x in raw.split(",") if x.strip()]
    network["active"] = active

    print("\n  Stock database/deposit columns map a visible store to a raw stock column.")
    dbmap = dict(network.get("stock_database_columns", {}))
    for store in active:
        current = dbmap.get(store, "")
        raw = input(f"    {store} database column [Enter={current or 'none'}]: ").strip()
        if raw:
            dbmap[store] = raw
    network["stock_database_columns"] = {k: v for k, v in dbmap.items() if v}
    _save(configs, "general/network", network)
    print(f"  ✅ Network saved: {len(active)} stores, {len(network.get('regional_groups',{}))} groups.")
    input("  Press Enter...")


def _setup_stock(configs: Path) -> None:
    clear_screen(); print("=== STOCK PROCESSING ===")
    cfg = load_json(str(config_path(configs, "stock_processing/settings"))) or {"version": 3}
    cleaning = cfg.setdefault("cleaning", {})
    pricing = cfg.setdefault("pricing", {}).setdefault("columns", {})
    output = cfg.setdefault("output", {})

    _, stock_cols, _ = _sample_file("Select a raw Stock file (optional but recommended).")
    if stock_cols:
        print("\n  Cleaning: list columns to drop. You can paste names separated by commas.")
        current = cleaning.get("drop_columns", [])
        raw = input(f"  Drop columns [Enter keeps {len(current)}]: ").strip()
        if raw:
            cleaning["drop_columns"] = [x.strip() for x in raw.split(",") if x.strip()]
        text = cleaning.get("text_columns", [])
        raw = input(f"  Text columns to trim [Enter={', '.join(text)}]: ").strip()
        if raw:
            cleaning["text_columns"] = [x.strip() for x in raw.split(",") if x.strip()]
        nums = cleaning.get("numeric_columns", [])
        raw = input(f"  Numeric columns to normalize [Enter keeps {len(nums)}]: ").strip()
        if raw:
            cleaning["numeric_columns"] = [x.strip() for x in raw.split(",") if x.strip()]

    _, price_cols, _ = _sample_file("Select a Cost/Sales price-list sample (separate from Stock).")
    if price_cols:
        pricing["article"] = _pick("Price-list article column", price_cols, pricing.get("article", DEFAULTS["general/catalog"]["columns"]["article"]), _ARTICLE_HINTS)
        pricing["database"] = _pick("Database/origin column", price_cols, pricing.get("database", DEFAULTS["stock_processing/settings"]["pricing"]["columns"]["database"]), _DB_HINTS)
        pricing["price"] = _pick("Price column", price_cols, pricing.get("price", DEFAULTS["stock_processing/settings"]["pricing"]["columns"]["price"]), _PRICE_HINTS)

    raw = input(f"  Raw-data sheet name [Enter={output.get('raw_data_sheet', DEFAULTS['stock_processing/settings']['output']['raw_data_sheet'])}]: ").strip()
    if raw: output["raw_data_sheet"] = raw
    base = output.get("base_columns", [DEFAULTS["general/catalog"]["columns"]["article"], DEFAULTS["general/catalog"]["columns"]["family"]])
    raw = input(f"  Base output columns comma-separated [Enter={', '.join(base)}]: ").strip()
    if raw: output["base_columns"] = [x.strip() for x in raw.split(",") if x.strip()]
    _save(configs, "stock_processing/settings", cfg)
    print("  ✅ Stock Processing saved. Advanced summary sheets remain editable in Config Hub.")
    input("  Press Enter...")


def _setup_cross(configs: Path) -> None:
    clear_screen(); print("=== CROSS CHECK ===")
    cfg = load_json(str(config_path(configs, "cross_check/settings"))) or {"version": 3}
    lists = cfg.setdefault("price_lists", {})
    for side, title in (("cost", "Cost list"), ("sales", "Sales list")):
        side_cfg = lists.setdefault(side, {})
        _, columns, _ = _sample_file(f"Select a {title} sample.")
        if columns:
            side_cfg["article_column"] = _pick(f"{title} article column", columns, side_cfg.get("article_column", DEFAULTS["general/catalog"]["columns"]["article"]), _ARTICLE_HINTS)
            side_cfg["price_column"] = _pick(f"{title} price column", columns, side_cfg.get("price_column", DEFAULTS["stock_processing/settings"]["pricing"]["columns"]["price"]), _PRICE_HINTS)
    filters = cfg.setdefault("filters", {})
    terms = filters.get("ignored_terms", DEFAULTS["cross_check/settings"]["filters"]["ignored_terms"])
    raw = input(f"  Ignored text terms comma-separated [Enter={', '.join(terms)}]: ").strip()
    if raw: filters["ignored_terms"] = [x.strip() for x in raw.split(",") if x.strip()]
    _save(configs, "cross_check/settings", cfg)
    print("  ✅ Cross Check saved. normalize_article() behavior is not configurable and was not changed.")
    input("  Press Enter...")


def _setup_yoy(configs: Path) -> None:
    clear_screen(); print("=== YOY REPORTS ===")
    cfg = load_json(str(config_path(configs, "yoy_reports/settings"))) or {"version": 3}
    inp = cfg.setdefault("input", {})
    _, columns, _ = _sample_file("Select the historical Sales file used by YoY.")
    if columns:
        fields = [
            ("date_column", "Date column", _DATE_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["date_column"]),
            ("quantity_column", "Quantity column", _QTY_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["quantity_column"]),
            ("sales_column", "Sales amount column", _SALES_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["sales_column"]),
            ("item_column", "Item/SKU column", _ARTICLE_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["item_column"]),
            ("grouping_column", "Grouping/family column", _FAMILY_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["grouping_column"]),
            ("branch_column", "Branch/store column", _BRANCH_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["branch_column"]),
            ("variant_column", "Variant column (optional)", _VARIANT_HINTS, DEFAULTS["yoy_reports/settings"]["input"]["variant_column"]),
        ]
        for key, label, hints, default in fields:
            inp[key] = _pick(label, columns, inp.get(key, default), hints)
    out = cfg.setdefault("output", {})
    while True:
        raw = input(
            f"  Default output path [Enter={out.get('default_path','analysis_report.xlsx')}]: "
        ).strip()
        if not raw:
            break
        try:
            out["default_path"] = normalize_xlsx_output_path(raw)
            break
        except InvalidExcelOutputPathError as exc:
            print(f"  ❌ {exc}")

    current_metrics = out.get("metrics", ["units", "sales"])
    raw = input(
        f"  Enabled metrics (units,sales) [Enter={', '.join(current_metrics)}]: "
    ).strip().lower()
    if raw:
        metrics = [value.strip() for value in raw.split(",") if value.strip()]
        unsupported = [value for value in metrics if value not in {"units", "sales"}]
        if unsupported:
            print(f"  ⚠️ Unsupported metrics ignored: {', '.join(unsupported)}")
            metrics = [value for value in metrics if value in {"units", "sales"}]
        if metrics:
            out["metrics"] = list(dict.fromkeys(metrics))

    annual = input(
        f"  Include annual comparison? [y/n, current={out.get('annual_comparison',True)}]: "
    ).strip().lower()
    if annual in ("y", "yes"):
        out["annual_comparison"] = True
    elif annual in ("n", "no"):
        out["annual_comparison"] = False

    inc = input(f"  Include variant breakdown? [y/n, current={out.get('include_variants',False)}]: ").strip().lower()
    if inc in ("y", "yes"):
        out["include_variants"] = True
    elif inc in ("n", "no"):
        out["include_variants"] = False
    _save(configs, "yoy_reports/settings", cfg)
    print("  ✅ YoY settings saved. Report groups can be edited in Config Hub.")
    input("  Press Enter...")


def run_setup_wizard(profile_dir: str, profile_name: str = "") -> None:
    configs = Path(profile_dir) / "configs"
    ensure_profile_config(configs)
    while True:
        clear_screen(); _dashboard(configs, profile_name)
        print("\n  [A] Guided setup — all modules")
        print("  [1] Catalog & families")
        print("  [2] Stores & network")
        print("  [3] Stock Processing")
        print("  [4] Cross Check")
        print("  [5] YoY Reports")
        print("  [0] Back")
        choice = input("\n  What do you want to configure? ").strip().upper()
        actions = {"1": _setup_catalog, "2": _setup_network, "3": lambda _configs: run_module_setup(configs.parent.name, "stock_processing"),
                   "4": lambda _configs: run_module_setup(configs.parent.name, "cross_check"),
                   "5": lambda _configs: run_module_setup(configs.parent.name, "yoy_reports")}
        if choice == "0": return
        if choice == "A":
            for action in actions.values():
                try:
                    action(configs)
                except ConfigurationError as exc:
                    print(f"  ❌ Configuration was not changed: {exc}")
                    input("  Press Enter...")
                    break
        elif choice in actions:
            try:
                actions[choice](configs)
            except ConfigurationError as exc:
                print(f"  ❌ Configuration was not changed: {exc}")
                input("  Press Enter...")


def run_module_setup(profile: str, module: str, step_id: str | None = None) -> None:
    """Configure one workflow through the shared page contract, saving each page."""
    from core.setup_service import SetupSession
    from core.setup_catalog import get_value, MODULE_LABELS
    from core.column_assist import advise_columns

    session = SetupSession(profile, module)
    pending = step_id or session.first_pending()
    index = next((i for i, step in enumerate(session.steps) if step.id == pending), 0)
    try:
        while index < len(session.steps):
            step = session.steps[index]
            clear_screen()
            print(f'\n  {MODULE_LABELS[module]} setup | {index + 1}/{len(session.steps)}: {step.title}\n')
            if step.shared:
                print('  Shared settings: edits affect other modules in this profile.')
            print('  Saved pages are retained. Ctrl+C leaves setup without saving this page.')
            _, columns, _ = _sample_file('Optional sample workbook for headers.') if any(f.kind == 'column' for f in step.fields) else ('', [], None)
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
                    values[key] = _pick(field.label, columns, current)
                elif field.kind == 'bool':
                    while True:
                        answer = input(f'  Enabled? [Y/N, Enter keeps {current}]: ').strip().lower()
                        if answer in ('', 'y', 'n'):
                            values[key] = current if not answer else answer == 'y'
                            break
                elif field.kind == 'list':
                    raw = input(f'  Comma-separated values [Enter keeps {current}; - clears]: ').strip()
                    values[key] = current if not raw else ([] if raw == '-' else list(dict.fromkeys(x.strip() for x in raw.split(',') if x.strip())))
                elif field.kind in {'mapping', 'rules', 'groups', 'summaries'}:
                    values[key] = _setup_table(field.kind, current)
                else:
                    raw = input(f'  Value [Enter keeps {current}]: ').strip()
                    values[key] = raw or current
            try:
                session.save_step(step.id, values)
            except ValueError as exc:
                print(f'  Not saved: {exc}')
                input('  Press Enter to review this page...')
                continue
            index += 1
        session.validate_required()
        print('  Setup complete. Return to the menu and run when ready.')
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
