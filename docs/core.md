# Core Infrastructure Reference

`core/` contains services shared by presentation and engine layers. It should remain business-workflow agnostic except for centralized external vocabulary/contracts.

## `business_schema.py`

Exposes external workbook vocabulary loaded from `core/resources/workbook_labels.json`, including labels such as `Artículo`, `Familias`, `Cantidad`, `Costo`, `Venta`, `Talle`, the raw-data sheet name, default family, and `REVISAR` marker.

The purpose is to keep implementation identifiers English while acknowledging that external workbooks and approved outputs may use Spanish business labels.

## `config_schemas.py`

Pydantic models for configuration schema v3.

The current schema requires version `3`, not merely an arbitrary integer. All current models, including nested structures, reject unknown keys. A misspelled setting is therefore a configuration error rather than an ignored field that silently falls back to another value.

Obsolete profiles must fail clearly rather than being interpreted as current.

## `paths.py`

Defines the canonical application root and application-owned resource roots. Internal resources such as `profiles/`, `examples/`, `logs/`, `tools/`, and release references are resolved from the Inventory Toolkit source/application tree, never from `Path.cwd()`.

This does **not** redefine user paths: a user-supplied relative workbook path still resolves relative to the caller's current working directory. The boundary is ownership: application resources are application-rooted; user file arguments remain caller-rooted.

## `configuration_manager.py`

Main typed configuration access layer.

Responsibilities:

- resolve `profiles/<profile>/configs/` from the canonical application root;
- ensure the profile can be consumed through the current schema;
- load/cache configuration documents by logical path;
- fail closed when an existing configuration file is malformed or unreadable;
- validate the complete current profile through Pydantic before workflows can use it;
- expose current English accessors such as:
  - `get_catalog()`;
  - `get_family_config()` / `get_family_rules()`;
  - `get_network_config()`;
  - `get_stock_processing_config()`;
  - `get_cross_check_config()`;
  - `get_yoy_reports_config()`.

<!-- BEGIN LEGACY_COMPATIBILITY -->
Old short-name projections are compatibility-only and should not be used by new built-in code.
<!-- END LEGACY_COMPATIBILITY -->

## `profile_config.py`

Defines:

- `CONFIG_VERSION = 3`;
- bundled default configuration structure loaded from `core/resources/profile_defaults.json`;
- explicit object/integer/current-version checks that remain after compatibility retirement;
- logical config paths;
- missing-file initialization;
- profile readiness summaries used by Setup/Configuration Hub.

Configuration ownership is described in [profiles.md](profiles.md).

<!-- BEGIN LEGACY_COMPATIBILITY -->
## `compatibility.py`, `legacy_config.py`, `legacy_profile_migration.py`

Temporary transition boundary for older Inventory Toolkit profiles/callers. Supported legacy names are converted explicitly before current-schema validation.

- `compatibility.py` emits deduplicated deprecation diagnostics when debug level 2/3 is enabled.
- `legacy_profile_migration.py` recognizes/migrates pre-v3 storage.
- `legacy_config.py` isolates old serialized key projections.

Built-in current modules should not depend on these contracts.

See [legacy_compatibility.md](legacy_compatibility.md) before modifying or removing them.
<!-- END LEGACY_COMPATIBILITY -->

## `resource_config.py` and `resources/`

`load_resource()` resolves UTF-8 JSON objects relative to the core package and raises a configuration error for unreadable or non-object resources. It does not depend on the caller's working directory.

- `profile_defaults.json`: bootstrap settings and defaults used by models, engines and editors.
- `workbook_labels.json`: shared external report vocabulary.
- `column_hints.json`: Guided Setup discovery hints; hints do not override explicit profile mappings.

These bundled files are application resources, not replacements for per-profile family/store rules. Runtime configuration remains in `profiles/<name>/configs/`.

## `progress.py`

`ProgressEvent` carries `completed`, `total`, `message` and optional `stage_fraction`. Its fraction is `(completed + stage_fraction) / total`. Engines emit useful stage boundaries and YoY sheet-level rendering updates; consumers should not interpret the fraction as a wall-clock estimate.

`StatsEvent` carries final human-readable lines and renders a separate `Stats:` block. Engines send statistics after a successful save. Optional callbacks keep headless engine calls independent of CLI/Tk widgets; CLI consumers print events and GUI consumers deliver them through queues to the main thread.

## `logger.py`

Runtime-configurable dual-channel logging.

### Level 1 — Operator

Errors only.

### Level 2 — Diagnostics

Operational milestones, stage timings, and warnings.

### Level 3 — Forensic

Detailed structured events, including where available:

- profile/config resolution;
- input workbook paths, shapes, and columns;
- configuration/rule counts;
- cleaning/filter row counts;
- scanner normalization review counts;
- merge/valuation/report-generation details;
- output sheet names/sizes;
- save attempts;
- Developer Console commands;
- exception tracebacks.

The logger intentionally avoids dumping entire raw datasets into `session.log`.

### Persistent log

`logs/session.log` includes timestamp, severity, process ID, thread, logger/source location, and message/context. The session log is initialized once and subsequent processes append, allowing developer subprocesses such as pytest to share the same session without truncating one another.

The level-3 Developer Console can display the current log tail.

## `telemetry.py`

Provides the `execution_timer()` context manager. It emits structured stage start/finish events and logs elapsed wall-clock time.

This is diagnostic timing, not production telemetry collection or remote analytics.

## `data_sanitizer.py`

Shared normalization helpers for values coming from Excel/scanners. Keep sanitization semantics covered by tests because seemingly harmless string/number conversions can affect article matching.

## `system_utils.py`

Cross-platform/system helpers and safe workbook saving.

### Safe savers

`safe_pandas_to_excel()` and `safe_openpyxl_save()` handle output files that are locked/open elsewhere.

- Interactive CLI callers can retry or save a numbered copy.
- Non-interactive callers receive `OutputFileLockedError` and decide how to present recovery in their own interface.

Infrastructure must not assume a terminal exists merely because the CLI was the first frontend.
