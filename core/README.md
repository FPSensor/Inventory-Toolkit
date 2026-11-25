# `core/` — Shared Infrastructure

Cross-cutting services used by CLI, GUI, and engines.

## Packages

- `config/` — strict schema-v3 models, profile loading and typed access, bundled defaults, JSON documents and configuration errors.
- `profiles/` — neutral profile creation, enabled workflows, remembered selections, diagnostics and restore points.
- `setup/` — guided steps, review state, sample-header advice and input inspection.
- `files/` — the single input reader, header selection, value cleanup, report saving and workbook packages.
- `runtime/` — build capabilities, application paths, logging, timing, progress events and optional developer tools.
- `resources/` — bundled UTF-8 JSON defaults, report labels and column hints.
- `business_schema.py`, `workflow_contracts.py`, `workflow_errors.py` — external labels, resolved input headers and stable error codes.

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

`profile_metadata.py` validates profile selection metadata without initialization. `profile_diagnostics.py` reports cross-setting contradictions without writing defaults. `profile_history.py` manages bounded local restore points; `json_documents.py` provides strict decoding and rollback-safe byte replacement/deletion. These services are shared by console, desktop and headless maintenance commands.
