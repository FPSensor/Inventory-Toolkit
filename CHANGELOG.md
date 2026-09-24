# Changelog

## [Unreleased]

### Refactored

- Isolated temporary legacy API/profile migration code behind explicit compatibility boundaries and added debug-level deprecation diagnostics for remaining users.
- Finished the internal English cleanup in the logging subsystem.
- Standardized non-business implementation vocabulary in English across core, CLI, GUI, tests, diagnostics, and engine internals. Spanish remains only at explicit business-data and legacy-compatibility boundaries.
- Upgraded the modular profile schema to v3, translating Stock summary keys and YoY metric identifiers to English with automatic v2-to-v3 migration.
- Centralized external workbook labels in `core/business_schema.py` and isolated pre-modular serialized keys in `core/legacy_config.py`.
- Split YoY worksheet/formula construction into `engine/yoy_reports/sheet_renderer.py`, leaving workbook segmentation and saving in `excel_renderer.py`.
- Split YoY worksheet rendering further into current-period, comparison, style, and orchestration modules without changing workbook formulas or output contracts.
- Added intentionally hidden CLI (`42`) and GUI (`Ctrl+Shift+I`) easter eggs; neither affects generated business output.


### Fixed

- Current Pydantic profile schemas now reject stale schema versions explicitly; compatibility migration still upgrades supported legacy profiles before validation.
- Finished the non-business English cleanup in the Windows launcher comments.
- Pydantic schemas now preserve the real profile JSON shapes, including family root mappings, regional groups, pricing aliases, Cross Check settings, and the shared Stock/YoY report configuration.
- Engines now consume validated configuration accessors consistently instead of mixing raw and typed configuration paths.
- Added the missing Pydantic runtime dependency and restored a green pytest suite.
- GUI background execution no longer calls Tk widgets from worker threads and no longer blocks on invisible terminal `input()` prompts when an output workbook is locked.
- Safe Saver keeps its existing interactive CLI retry/copy behavior while exposing a non-interactive error path for graphical callers.
- Diagnostic tools no longer claim a speedup or production guarantee when their own measurements do not support those conclusions.
- Family batch classification now uses a prefix trie, preserving longest-prefix semantics while avoiding repeated full-Series regex scans for every configured prefix.
- Cross Check and Stock output workbooks now freeze headers and expose filters; Stock column auto-sizing is capped to avoid pathological widths.
- Windows launchers now anchor execution to the repository directory.

### Testing

- Added a reproducible `tools/ReleaseCheck.py` gate for compilation, pytest, logical integrity, profile validation, compatibility readiness, and optional end-to-end demo workflows.
- Added pytest path configuration so both `pytest` and `python -m pytest` collect the repository consistently.
- Added `tools/RetireLegacyCompatibility.py`, a guarded read-only audit / optional removal-and-commit workflow for eventually deleting pre-v3 compatibility.
- Added regression coverage ensuring compatibility diagnostics remain silent normally, warn only in debug mode, and point legacy profiles toward migration.
- Added explicit regression coverage for variable-length scanned article normalization, longest-prefix matching, exact matches, and `REVISAR |` fallback behavior.
- Added Safe Saver tests for non-interactive locked-file handling and preserved CLI copy behavior.

## [1.4.0] - 2026-09-23

### Added

- Native desktop GUI (`gui/app.py`) built on Tkinter/CustomTkinter, providing Cross Check, Stock Processing, and YoY Sales Report tabs plus a full graphical Configuration Hub as an alternative to the CLI
- Linux/macOS shell launcher (`Inventory Toolkit.sh`)
- Pydantic-based configuration schemas (`core/config_schemas.py`) for families, stores, cleaning rules, pricing, cross-check settings, and YoY reports, with automatic fallback to safe defaults on validation errors
- Centralized SKU/article sanitization module (`core/data_sanitizer.py`) exposing `clean_sku_series()` and `sanitize_dataframe()`
- Vectorized, regex-based family classification (`vectorize_assign_families`) for large datasets, replacing row-by-row `apply()`/`lambda` matching
- Execution-timer utility (`core/telemetry.py`) for per-stage elapsed-time logging
- Repository diagnostic tool (`tools/IntegrityCheck.py`) validating family rules, margin logic, date-offset/leap-year math, and running an end-to-end simulation against the demo profile
- Performance benchmarking tool (`tools/StressTests.py`) comparing legacy vs. vectorized family classification on 50,000 synthetic SKUs, plus profile and environment audits
- Persistent "last used paths" per profile (`profiles/<profile>/last_paths.json`), pre-filling file prompts on subsequent runs of Cross Check, Stock Processing, and YoY Reports
- Optional "Include size breakdown" toggle for YoY Sales Reports
- Consolidated "Global" (all-branches) comparison column block per family group in YoY Sales Reports, shown whenever a group spans more than one store
- Expanded interactive Setup Wizard (`cli/wizard.py`), now covering active stores, columns to delete, YoY data-source columns, pricing columns, and Cross Check columns across 8 guided steps, each individually skippable
- Fully redesigned Configuration Hub (`cli/config_menu.py`) with in-app search/filter, sub-dictionary support, and structured in-app editors for `reports.json` and `pricing.json` (no external editor required anymore)
- Redesigned main menu with a boxed layout and ASCII-art logo (`cli/menu.py`)
- Linear, guided "Create new profile" flow, with profile descriptions shown in the profile selector

### Changed

- `ConfigurationManager` rewritten to recursively index every `*.json` file under a profile by filename stem and validate it against Pydantic models, replacing the previous hand-rolled `schema.json` validation and `ConfigNode` dual dot/dict-access wrapper
- `tkinter` is now an optional dependency across the CLI; file-browser prompts degrade gracefully when it is unavailable
- `open_in_editor()` is now genuinely cross-platform, adding a dedicated Linux (`xdg-open`) branch
- Inventory Cross Check and Stock Processing launchers now remember and pre-fill the last file paths used per profile
- `.gitignore` updated to exclude `profiles/*/last_paths.json`

### Fixed

- Inefficient row-by-row family assignment replaced with vectorized matching, reducing processing time on large datasets
- Duplicate `safe_pandas_to_excel` import removed from `engine/inventory_cross_check/generator.py`

### Notes

This release focuses on usability, cross-platform reach, and performance: it introduces a full graphical interface as an alternative to the CLI, adds native Linux/macOS launcher support, and replaces ad-hoc JSON validation with a proper Pydantic schema layer. Family classification is now vectorized for large inventories, and both the Setup Wizard and the Configuration Hub have been substantially expanded.

---

## [1.3.1] - 2026-08-20

### Added

- Modular engine architecture splitting processing domains into `data_processor.py`, `excel_renderer.py`, and `generator.py`
- Shared business logic module (`engine/shared/families.py`) for centralized SKU family classification
- Full English internationalization across CLI menus, prompts, variables, and error messages
- APB (A Prueba de Boludos) safety protocol for pre-execution header verification and strict `YYYY-MM-DD` date validation
- Safe Saver file handlers (`safe_pandas_to_excel`, `safe_openpyxl_save`) preventing crashes on locked/open Excel files
- Dual-channel logging engine with file persistence (`logs/session.log`) and hidden `-debug_level` CLI arguments
- Automated unit test suite using `pytest` for family rules, margin logic, and inventory differences
- Extensive documentation directory (`docs/`) including architecture, module codex, and operational guides
- Subdirectory structure for profile configurations (`general/`, `cross_check/`, `stock_processing/`, `yoy_reports/`)
- Dynamic family generation support inside the YoY Sales Reports engine
- Execution timers displaying elapsed processing duration upon task completion

### Changed

- Renamed `Cruces.py` to `engine/inventory_cross_check/`
- Renamed `Stocks.py` to `engine/stock_processing/`
- Renamed CLI launchers to `cross_check_launcher.py`, `stock_processing_launcher.py`, and `yoy_reports_launcher.py`
- Renamed demo sample datasets to English descriptive names matching their target modules
- Updated `ConfigurationManager` to resolve schemas and configuration JSON files from categorized subdirectories
- Standardized namespace parameters passed from CLI to engines using module prefixes
- Updated all module-level `README.md` files to reflect the v1.3.1 decoupled design

### Removed

- Removed obsolete root and legacy engine scripts (`engine/Cruces.py`, `engine/Stocks.py`, `cli/cruces.py`, `cli/stocks.py`, `cli/reports.py`)
- Removed obsolete sample spreadsheets in Spanish from `examples/demo/`
- Removed flat configuration file layout in profile folders

### Fixed

- Fixed runtime crashes caused by `PermissionError` when saving spreadsheets open in external viewers
- Fixed silent failures and false positives during scanned barcode normalization via longest-prefix priority sorting
- Fixed division-by-zero errors in margin calculations when sales values are zero
- Fixed test assertion mismatches in prefix ordering and dictionary unpacking

---

## [1.3.0] - 2026-08-14

### Added

- Year-over-Year (YoY) Sales Report generation
- Interactive sales report workflow through the CLI
- Sales comparison between current and previous-year periods
- Report grouping by product family or individual item
- Branch-level sales breakdowns
- Automatic year-over-year percentage calculations
- Monthly segmented sales reports
- Configurable report structures through JSON
- Configurable report output path
- Excel report generation with formatted tables, totals, and YoY comparisons
- Optional file browser for selecting sales data files

### Changed

- Added a dedicated Sales Reports workflow to the CLI
- Separated report data processing, report generation, and Excel rendering into independent modules
- Moved report configuration into the profile-based configuration system
- Improved date-range handling for sales analysis
- Added validation for interactive report options and date input
- Improved handling of items with no previous-year sales

### Notes

This release introduces Sales Reports as a new major capability of Inventory Toolkit, extending the application beyond inventory processing and reconciliation into sales analysis and reporting.

---

## [1.2.0] - 2026-07-24

### Added

- Interactive Command Line Interface (CLI)
- Profile selection menu
- Profile creation wizard
- Interactive JSON configuration editor
- Automatic Excel column mapping assistant
- Native file picker support
- Windows launcher (`Inventory Toolkit.bat`)
- Environment setup script (`Setup Environment.bat`)

### Changed

- Stock processor integrated into the CLI
- Inventory Reconciliation (Cruces) integrated into the CLI
- Complete project modularization
- CLI split into reusable modules
- Improved startup workflow
- Improved configuration management
- Better error handling during execution

### Fixed

- Restored original reconciliation workflow while maintaining compatibility with the profile system
- Fixed multiple reconciliation regressions introduced during the configuration system migration
- Improved processing stability

### Notes

This release transforms Inventory Toolkit from standalone Python scripts into a complete command-line application.

Profiles are now managed directly from the CLI, allowing independent configurations without modifying the processing engine.

The included example profile demonstrates a real-world configuration used during development and serves as a reference for creating new profiles.

---

## [1.1.0] - 2026-07-22

### Added

- Configuration Manager
- External JSON configuration system
- Configuration validation
- Example profile structure
- Core module

### Changed

- Refactored Stock Processor to use external configuration
- Refactored Reconciliation Processor to use external configuration
- Business rules moved from source code to JSON files
- Improved project maintainability

### Notes

This release introduces the foundation for profile-based configurations.

Although only a single example profile is currently provided, the project architecture now supports multiple independent profiles without modifying the processing engine.