# `core/` — Shared Infrastructure

Cross-cutting services used by CLI, GUI, and engines.

## Current modules

- `business_schema.py` — centralized external workbook/business labels.
- `config_schemas.py` — strict Pydantic schema-v3 models.
- `configuration_manager.py` — profile loading/caching/typed accessors.
- `profile_config.py` — schema-v3 defaults, paths, initialization, readiness.
- `data_sanitizer.py` — shared value normalization.
- `logger.py` — runtime debug levels + forensic `logs/session.log`.
- `telemetry.py` — execution-stage timing helper.
- `system_utils.py` — safe saving/system helpers and locked-output handling.
- `compatibility.py`, `legacy_config.py`, `legacy_profile_migration.py` — temporary compatibility boundary while legacy support remains.

Core should provide infrastructure, not duplicate workflow-specific calculations.

See [`../docs/core.md`](../docs/core.md) and [`../docs/architecture.md`](../docs/architecture.md).
