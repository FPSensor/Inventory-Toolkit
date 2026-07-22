# Changelog

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