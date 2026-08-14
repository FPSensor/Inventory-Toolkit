# Changelog

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
