# `cli/` — Command-Line Interface

Inventory Toolkit's primary presentation layer.

The CLI gathers user intent and files, manages profiles/configuration, then delegates processing to `engine/`. Business calculations should not be implemented here.

## Files

- `menu.py` — main menu, active-profile routing, hidden `debug` selector and `42` easter egg.
- `profiles.py` — profile discovery/selection.
- `config_menu.py` — domain-oriented Configuration Hub and current-profile validation.
- `wizard.py` — module-oriented Guided Setup and Excel-column autodetection.
- `debug_menu.py` — source-compatibility wrapper for the optional `debug_tools.console` package.
- `cross_check_launcher.py` — Cross Check prompts/pre-flight + engine invocation.
- `stock_processing_launcher.py` — Stock Processing prompts/pre-flight + engine invocation.
- `yoy_reports_launcher.py` — YoY prompts/pre-flight + engine invocation.
- `utils.py` — presentation/file-dialog helpers, remembered paths and application-owned demo suggestions.
- `progress.py` — compact stage/percentage output and separate final statistics.

## Debug workflow

From the main menu, type the intentionally hidden command:

```text
debug
```

When `build.prop` selects a debug build and `debug_tools` is present, level 3 exposes `D › Developer / Release Tools`, including pytest, repository gates, demo/golden-master certification, reference maintenance, log tail.

Startup flags remain supported for automation:

```bash
python -m cli --debug-level 3
```

See [`../docs/cli.md`](../docs/cli.md) for the full reference.

The shared build launcher is `python -m inventory_toolkit --interface cli`. `config_menu.py` routes module selection, search and section editing through the same catalog and setup service used by the GUI. Shared persistence lives in `core/profile_store.py`; GUI operation does not require this package.
