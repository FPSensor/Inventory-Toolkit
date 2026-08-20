# Changelog

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