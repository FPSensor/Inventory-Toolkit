# CLI Reference

The CLI is Inventory Toolkit's primary interface and the most complete surface for configuration, workflows, diagnostics, and release tooling.

Entry point:

```bash
python cli.py
```

Windows and Linux/macOS launchers ultimately call the same entry point.

## Startup

At startup Inventory Toolkit:

1. configures logging/debug behavior;
2. checks critical import availability;
3. asks for the active profile;
4. opens the main menu.

The selected profile remains active until changed from the menu.

## Main menu

```text
C  Inventory Cross Check
S  Stock Processing
R  YoY Sales Report
K  Configuration
P  Change Profile
D  Developer / Release Tools   # visible only at debug level 3
E  Exit
```

Two intentionally undisplayed commands also exist:

- `debug` — runtime debug-level selector;
- `42` — harmless easter egg.

## Workflow launchers

### Cross Check

`cli/cross_check_launcher.py` collects:

- system-stock workbook;
- physical-count workbook;
- cost list;
- sales list;
- output path;
- consolidation/partial-count options.

It then calls the Cross Check engine. Article normalization/business reconciliation stays inside `engine/inventory_cross_check/`.

### Stock Processing

`cli/stock_processing_launcher.py` collects raw stock, price lists, and output path, then calls `engine/stock_processing/`.

Store mappings, family rules, cleaning rules, pricing mappings, and summary layout come from the active profile.

### YoY Reports

`cli/yoy_reports_launcher.py` collects the historical sales workbook, date range, segmentation/options, and output path, then calls `engine/yoy_reports/`. Enabled unit/sales metrics, annual-comparison behavior, and the default size-breakdown choice come from the active profile; the CLI may override size breakdown for a single run.

## Configuration Hub

Open `K` from the main menu.

The hub is organized by domain instead of by JSON filename:

1. Catalog & families
2. Stores & network
3. Stock Processing
4. Cross Check
5. YoY Reports

Additional actions:

- Guided Setup;
- profile validation;
- legacy migration/archive while compatibility support exists.

The intent is that a normal user chooses **what concept to configure**, not **which internal JSON file to edit**.

## Guided Setup

The Guided Setup is module-oriented. It does not assume a single sample workbook describes every workflow.

Each module can inspect the sample that actually belongs to it:

- Stock Processing: raw stock + price-list sample;
- Cross Check: cost/sales-list samples;
- YoY: historical sales sample;
- catalog/families and network: independent configuration.

The dashboard shows readiness and saves each section independently.

## Runtime debug levels

Type `debug` in the main menu.

### Level 1 — Operator

Errors only. Intended for normal usage.

### Level 2 — Diagnostics

Adds operational events, timings, warnings, and compatibility notices.

### Level 3 — Forensic

Adds structured, high-detail execution events and exposes the Developer Console.

The level can be changed while Inventory Toolkit is running. Existing log handlers are reused; changing level does not intentionally truncate the active session log.

Automation can still start directly in a specific level:

```bash
python cli.py --debug-level 3
```

The historical `-debug_level 3` spelling remains supported.

## Developer Console

Visible as `D` only at debug level 3.

Current tools:

1. Run pytest
2. Quick repository verification
3. Demo workflow smoke test
4. Full release certification against golden masters
5. Update golden-master references
6. Show current session log tail
7. Legacy compatibility lifecycle, while the retirement tool still exists

Developer tools run in subprocesses anchored to the application root so their failures and return codes remain isolated from the menu loop. Normal runtime profile/config resolution is independently CWD-safe and does not depend on this subprocess working directory.

### Updating golden masters

The CLI asks for an explicit `UPDATE REFERENCES` confirmation before invoking reference regeneration. This should only be used after intentionally changing expected business/demo output and reviewing the result.

### Retiring compatibility

Compatibility retirement requires an explicit `RETIRE COMPATIBILITY` confirmation and delegates to `tools/RetireLegacyCompatibility.py`. The tool performs its own readiness checks and validation. If retirement succeeds, it removes its own script and menu blocks.

## Native file picker

CLI file selection may use Tkinter's native file dialog. Tkinter availability therefore matters even when the full desktop GUI is not being used.

## Keyboard interruption

`Ctrl+C` at the main loop is treated as a safe interruption and exits cleanly.

## Source map

| File | Responsibility |
| --- | --- |
| `cli.py` | top-level entry point |
| `cli/menu.py` | main menu, profile routing, runtime debug selector, easter egg |
| `cli/profiles.py` | profile discovery/selection |
| `cli/config_menu.py` | domain-oriented Configuration Hub |
| `cli/wizard.py` | Guided Setup and column autodetection |
| `cli/debug_menu.py` | level-3 Developer Console |
| `cli/*_launcher.py` | workflow-specific prompts and engine invocation |
| `cli/utils.py` | presentation helpers/file dialog utilities |
