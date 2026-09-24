# `cli/` — Command-Line Interface

Inventory Toolkit's primary presentation layer.

The CLI gathers user intent and files, manages profiles/configuration, then delegates processing to `engine/`. Business calculations should not be implemented here.

## Files

- `menu.py` — main menu, active-profile routing, hidden `debug` selector and `42` easter egg.
- `profiles.py` — profile discovery/selection.
- `config_menu.py` — domain-oriented Configuration Hub and validation/migration entry points.
- `wizard.py` — module-oriented Guided Setup and Excel-column autodetection.
- `debug_menu.py` — level-3 Developer Console.
- `cross_check_launcher.py` — Cross Check prompts/pre-flight + engine invocation.
- `stock_processing_launcher.py` — Stock Processing prompts/pre-flight + engine invocation.
- `yoy_reports_launcher.py` — YoY prompts/pre-flight + engine invocation.
- `utils.py` — presentation/file-dialog helpers.

## Debug workflow

From the main menu, type the intentionally hidden command:

```text
debug
```

Level 3 exposes `D › Developer / Release Tools`, including pytest, repository gates, demo/golden-master certification, reference maintenance, log tail, and legacy retirement while available.

Startup flags remain supported for automation:

```bash
python cli.py --debug-level 3
```

See [`../docs/cli.md`](../docs/cli.md) for the full reference.
