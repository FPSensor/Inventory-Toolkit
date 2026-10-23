# `core/` — Shared Infrastructure

Cross-cutting services used by CLI, GUI, and engines.

## Current modules

- `business_schema.py` — centralized external workbook/business labels.
- `config_schemas.py` — strict Pydantic schema-v3 models.
- `configuration_manager.py` — profile loading/caching/typed accessors.
- `profile_config.py` — JSON-backed defaults, strict schema headers, paths, initialization, readiness.
- `resource_config.py` / `resources/` — bundled UTF-8 JSON defaults, report labels and column hints.
- `progress.py` — optional engine progress events and separate final statistics.
- `data_sanitizer.py` — shared value normalization.
- `logger.py` — runtime debug levels + forensic `logs/session.log`.
- `telemetry.py` — execution-stage timing helper.
- `system_utils.py` — safe saving/system helpers and locked-output handling.

Core should provide infrastructure, not duplicate workflow-specific calculations.

See [`../docs/core.md`](../docs/core.md) and [`../docs/architecture.md`](../docs/architecture.md).

## Application boundaries

- `build.py` reads the validated root `build.prop` manifest.
- `optional_debug.py` discovers developer capabilities only in debug builds.
- `profile_creation.py` creates neutral module-selected profiles from JSON resources.
- `profile_store.py` shares persistence without importing CLI or GUI.
- `json_documents.py` rejects ambiguous JSON and stages related setup writes with rollback.
- `workflow_contracts.py` resolves per-module input mappings independently of output labels.
- `module_preferences.py` owns enabled workflows; `setup_catalog.py` and `setup_service.py` own conditional forms, review state and recovery destinations.

`resources/new_profile_defaults.json` defines neutral defaults for newly created profiles. `profile_defaults.json` retains inherited schema-v3 defaults for existing profiles. Product catalogs, prefixes and location mappings belong to profile/example data, never to these services.
