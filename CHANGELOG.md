# Changelog

All notable changes to Inventory Toolkit are documented in this file.

## [1.4.1] - Unreleased

### Changed

- Standardized the workbook output contract across Stock Processing, Cross Check, and YoY: legacy `.xls` remains supported as input where needed, while generated workbooks are validated and written only as `.xlsx`; extensionless output names are normalized before processing.
- Refactored Stock Processing from one legacy-heavy orchestration function into explicit profile-contract, cleanup/classification, pricing, valuation, and rendering stages while preserving the approved demo workbook contract.
- Made Stock Processing normalize profile-owned article/family labels at the engine boundary and use private internal keys during business processing, so non-default catalog column names work end to end without leaking implementation columns to Excel.
- Made profile configuration fail closed: existing JSON files must parse and the complete current schema must validate before a workflow can use the profile; missing current-schema files may still be initialized from documented defaults.
- Made all schema-v3 Pydantic models reject unknown keys, including nested Stock, Cross Check, and YoY structures, so misspelled settings cannot silently disappear behind defaults.
- Made the catalog `default_family` a real profile-owned business setting across Stock Processing, Cross Check, and dynamically classified YoY data instead of leaving the historical `Other` fallback hardcoded inside the shared classifier.
- Promoted YoY `metrics` from stored metadata to an enforced output contract: `units` uses the configured quantity column and `sales` uses a new configurable sales-amount column (`Monto` in the demo profile), with metric-specific workbook formatting.
- Made YoY `annual_comparison` control whether previous-year comparison blocks are rendered, and made `include_sizes` act as the runtime default in CLI/GUI unless explicitly overridden for the current run.
- Tightened YoY profile readiness and runtime validation so at least one supported metric and one concrete report-group branch are required before workbook generation.

### Fixed

- Fixed Stock Processing paths that validated a configured article column but later still read/merged the hardcoded `Artículo`/`Familias` labels.
- Fixed Cross Check system-stock/article-family handling to honor `general/catalog.json`, and fixed the GUI preflight that incorrectly checked the cost-list article mapping against the system-stock workbook.
- Prevented empty system-stock articles from becoming zero-length prefix candidates during Cross Check scanner normalization, preserving the `REVISAR | <original>` invariant for unknown readings even when the master contains blank/NaN article cells.
- Unified scalar and batch family-classification normalization so numeric/empty inputs and unmatched values share the same configurable fallback semantics.
- Prevented YoY configurations with no usable report groups from producing invalid total formulas such as a bare `=`.
- Wired the GUI YoY output path and size-breakdown defaults to the active profile instead of silently starting from hardcoded values.

## [1.4.0] - 2026-09-24

`1.4.0` is a broad evolution of the `1.3.1` architecture rather than a narrowly scoped feature release. Across the full development line, Inventory Toolkit gained a first desktop GUI, a redesigned profile/configuration system, stronger Cross Check and YoY behavior, substantially deeper diagnostics, guarded migration tooling, reproducible release certification, and a complete documentation overhaul while preserving the established business-output contracts of the three core workflows.

### Configuration & Profiles

- Added initial Pydantic configuration models in `core/config_schemas.py`, then hardened them so validated configuration preserves the real persisted shapes used by families, regional groups, pricing aliases, Cross Check settings, Stock summaries, and YoY reports.
- Reworked `ConfigurationManager` from the earlier hand-written `schema.json` / `ConfigNode` approach into typed configuration loading and validation.
- Replaced filename-stem lookup with module-oriented logical paths so Stock Processing, Cross Check, and YoY can each own an independent `settings.json` without collisions.
- Reorganized profile storage around cohesive ownership: shared catalog/family/network data under `general/`, plus one settings document per processing workflow.
- Introduced schema v2 and then schema v3, with automatic migration of supported older profiles and explicit rejection of stale versions after migration.
- Standardized current configuration vocabulary in English while preserving Spanish only where it belongs to workbook/business contracts or historical compatibility data.
- Centralized external workbook labels and business-facing constants in `core/business_schema.py`.
- Isolated legacy serialized keys and old configuration projections behind dedicated compatibility modules instead of mixing them with current configuration APIs.
- Redesigned Guided Setup from the original eight-step shared-file flow into a module-oriented setup dashboard where each workflow can use its own representative sample workbook for column discovery.
- Redesigned the Configuration Hub around business domains rather than JSON filenames, with dedicated editors for catalog/families, stores/network, Stock Processing, Cross Check, and YoY.
- Added profile-readiness summaries, current-schema validation, safe defaults for new profiles, and explicit migration/archive flows for older layouts.
- Added per-profile last-path persistence in `profiles/<profile>/last_paths.json`, allowing Cross Check, Stock Processing, and YoY launchers to pre-fill recently used files.

### CLI & Developer Experience

- Redesigned profile creation/selection and the main CLI presentation, including profile descriptions, a boxed menu layout, and more guided configuration flows.
- Added an intentionally hidden runtime `debug` command so debug verbosity can be changed without restarting Inventory Toolkit.
- Added operator, diagnostics, and forensic debug levels while retaining startup debug flags for automation.
- Added a level-3 Developer Console with direct pytest execution, quick repository verification, demo smoke tests, strict release certification, golden-master maintenance, session-log inspection, and compatibility-lifecycle tooling.
- Rebuilt runtime logging so level 2 records operational diagnostics and level 3 records structured forensic events including profile/config resolution, workbook metadata, detected columns, transformation counts, merge/filter decisions, generated output structure, save operations, timings, subprocess activity, and tracebacks without dumping complete business datasets.
- Made `logs/session.log` safe for parent/child processes by truncating once at session start and using append-mode handlers afterward.
- Propagated the runtime debug level through Developer Console → `ReleaseCheck` → workflow subprocesses, allowing the parent process and concurrent Cross Check, Stock Processing, and YoY workers to contribute to one forensic session log with distinct PIDs.
- Added intentionally hidden CLI (`42`) and GUI (`Ctrl+Shift+I`) easter eggs; neither affects business output.

### GUI & Runtime Safety

- Added the first experimental desktop GUI in `gui/app.py`, using Tkinter with optional CustomTkinter support and exposing Cross Check, Stock Processing, YoY Reports, profile selection/creation, and a graphical Configuration Hub.
- Kept the GUI explicitly experimental and adapted it as the profile/configuration schema evolved.
- Moved GUI completion/error updates back onto Tk's main thread instead of updating widgets directly from worker threads.
- Added a non-interactive Safe Saver path so graphical callers receive an explicit locked-output error instead of blocking on an invisible terminal `input()` prompt.
- Preserved the interactive CLI retry/save-copy flow for locked output workbooks.
- Made Tkinter optional for CLI file-browser functionality so terminal workflows can degrade gracefully when graphical dialogs are unavailable.

### Cross-Platform Support & Launchers

- Added the Linux/macOS `Inventory Toolkit.sh` launcher.
- Added a dedicated Linux `xdg-open` branch to `open_in_editor()`.
- Anchored Windows launchers to the repository directory so startup no longer depends on the caller's current working directory.
- Added `.gitignore` coverage for per-profile `last_paths.json` state.

### Engine, Reporting & Data Handling

- Added centralized SKU/article sanitization through `core/data_sanitizer.py`, including `clean_sku_series()` and `sanitize_dataframe()`.
- Fixed missing values before string conversion so absent SKUs do not become literal `"nan"` identifiers.
- Added per-stage execution timing through `core/telemetry.py` and expanded processing-stage diagnostics.
- Introduced a batch regex family classifier as the first attempt to replace repeated row-by-row classification, then replaced repeated full-Series regex scans with a prefix trie after benchmarking exposed the regex approach's limitations.
- The trie preserves stable longest-prefix family semantics while improving the classifier's scaling behavior.
- Added explicit regression protection for variable-length `normalize_article()` behavior: exact master matches, longest valid article-prefix selection, and unresolved `REVISAR | <original>` preservation.
- Added frozen headers and filters to Cross Check and Stock outputs.
- Capped Stock auto-sized column widths to avoid pathological layouts caused by unusually long cell values.
- Added optional size breakdowns to YoY reports.
- Added a consolidated `Global` comparison block for YoY groups spanning multiple stores.
- Fixed YoY variation/global comparison behavior while integrating the size-breakdown path.
- Further modularized YoY rendering into workbook/period orchestration, worksheet orchestration, current-period blocks, comparison blocks, and shared styles without changing approved formulas or workbook contracts.
- Continued explicit memory cleanup in large Cross Check and YoY processing paths.

### Compatibility & Migration

- Added debug-level deprecation warnings whenever the deprecated configuration API, legacy profile storage, or pre-v3 migration path is actually used.
- Isolated compatibility behavior behind removable boundaries so current engines and configuration surfaces consume the modern API directly.
- Added `tools/RetireLegacyCompatibility.py` as a guarded audit and optional retirement workflow for eventually removing pre-v3 compatibility.
- Retirement refuses destructive changes when active legacy profiles, stale schemas, unexpected compatibility consumers, missing markers, or a dirty Git worktree are detected.
- Optional retirement validates the resulting repository, can create an authored Git commit, removes the legacy tooling itself, and strips its own Developer Console launcher/menu blocks.
- Legacy profile backups remain preserved when compatibility is retired.

### Testing, Diagnostics & Release Engineering

- Added `tools/IntegrityCheck.py` for logical invariants including family-prefix priority, inventory differences, margins, date offsets/leap years, and demo-profile configuration checks.
- Added `tools/StressTests.py` for profile/environment audits and synthetic family-classification benchmarking.
- Corrected diagnostic reporting so a slower benchmark is no longer described as a speedup and integrity checks no longer claim absolute production guarantees.
- Added `tools/ReleaseCheck.py` as a reproducible gate for compilation, pytest, logical integrity, profile validation, compatibility readiness, and optional end-to-end demo execution.
- Added `pytest.ini` so `pytest` and `python -m pytest` resolve the project consistently from the repository root.
- Expanded pytest coverage for configuration migration/schema versions, Safe Saver behavior, runtime debug tooling, forensic logging, compatibility diagnostics, and article-normalization invariants.
- Added committed golden-master workbooks for Cross Check, Stock Processing, and YoY under `tests/release_reference/`.
- Added strict pre-release certification that executes all three demo workflows in isolated subprocesses and compares generated outputs against approved references.
- Golden-master comparison is semantic rather than a raw XLSX/ZIP hash and can diagnose changed sheets, dimensions, values/formulas, merged ranges, filters, freeze panes, and relevant workbook structure.
- Added fingerprints for demo fixtures and demo configuration so approved references are rejected as stale when their inputs change.
- Added guarded golden-master regeneration for intentional business/demo changes: all candidates are generated and repository-validated before rollback-protected reference installation.
- Release-test outputs are written to temporary storage and automatically removed after certification.
- Made demo JSON fixture fingerprints canonical and cross-platform so harmless whitespace, key-order, and LF/CRLF differences do not invalidate approved references; legacy raw-hash manifests remain accepted during transition.
- Canonicalized OOXML comparison across OpenPyXL XML serializers so namespace prefixes, attribute ordering, self-closing syntax, and equivalent serializer output do not cause false golden-master failures.
- Refined workbook fallback comparison to inspect effective presentation (cell font/fill/border/alignment/protection/number format plus worksheet structure) instead of treating unused/reordered internal style registries as user-visible changes.
- Added regression coverage proving real semantic JSON changes, real workbook presentation changes, and applied-cell style changes still fail certification.

### Fixed

- Fixed initial Pydantic schemas that silently discarded valid persisted data because their models did not match the JSON structures shipped by the profile.
- Fixed mixed raw/typed configuration access by routing built-in engines through validated accessors consistently.
- Restored the configuration accessor expected by the test suite and returned pytest to a green baseline before extending coverage.
- Added the missing Pydantic runtime dependency to `requirements.txt`.
- Made current schema models explicitly reject stale version numbers after supported migrations have run.
- Fixed GUI/background paths that could update Tk widgets from worker threads or wait for terminal input.
- Removed a duplicate Safe Saver import from the Cross Check generator.
- Fixed benchmark/integrity messaging that overstated measured guarantees.
- Fixed Cross Check header formatting so the engine explicitly owns the approved header font, fill, alignment, borders, protection, and number format instead of inheriting Pandas-version-dependent styling.
- Fixed false release-reference drift caused by Windows CRLF JSON checkouts and by equivalent OpenPyXL OOXML serializers.
- Fixed golden-master false positives caused by unused or reordered workbook style-table entries while preserving detection of effective style changes.

### Documentation

- Rewrote the root README and maintained module READMEs/docs to describe the current CLI-first application, experimental GUI, schema-v3 profile model, compatibility lifecycle, forensic logging, release tooling, and evolved engine architecture.
- Added dedicated installation, GUI, release-process, troubleshooting, and legacy-compatibility documentation.
- Documented `normalize_article()` and longest-prefix matching as protected business invariants, including why fixed-length slicing is not equivalent.
- Replaced outdated or overstated language such as "bulletproof" or assumed production readiness with concrete, testable statements.
- Added a version-oriented roadmap to the README while explicitly treating it as direction rather than a release-date promise.

### Notes

`1.4.0` is the complete release line represented by the repository diff from `v1.3.1` through this state. Although development happened in multiple waves, those waves are intentionally consolidated here rather than split into a historical `Unreleased` block. The release materially expands configuration, usability, diagnostics, testing, migration, documentation, and release engineering while preserving the established business behavior of the three core processing workflows unless a change is explicitly listed above.

Final pre-release certification was completed on Windows 10 / Python 3.12.10 using the committed demo fixtures: all three workflows matched their approved golden masters, the pytest suite passed 37 tests, IntegrityCheck passed 30 checks with no failures or warnings, the demo profile validated, and the compatibility audit reported ready.

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