# Legacy Configuration Compatibility

> This document describes a **temporary transition layer**. Current built-in modules use schema-v3 configuration and the English internal API.

Inventory Toolkit currently preserves two historical contracts so older profiles/external callers can migrate without changing business calculations:

1. **legacy storage** — pre-v3 profile layouts / old serialized keys;
2. **legacy API projections** — deprecated short `ConfigurationManager.get_config(...)` names from older code.

## What current code should use

New code should use current logical configuration paths/accessors such as:

- catalog/family/network accessors;
- Stock Processing config accessors;
- Cross Check config accessor;
- YoY config accessor.

Do not add new dependencies on compatibility modules simply because they still exist.

## Diagnostics

Start the normal CLI, type:

```text
debug
```

and select level 2 or 3.

Compatibility events are deduplicated and identify the kind of fallback being used where possible.

A storage warning means a profile still requires migration/archive. An API warning means a caller still uses an old projection and should be updated.

Automation can still launch with:

```bash
python cli.py --debug-level 2
```

## Migration/archive

The CLI Configuration Hub exposes legacy migration/archive while the layer exists.

Migrated original files are preserved under:

```text
configs/_legacy_v1_backup/
```

The backup is historical data and is not automatically deleted by compatibility retirement.

## Read-only retirement audit

```bash
python tools/RetireLegacyCompatibility.py
```

The audit refuses readiness while it detects conditions such as:

- active legacy profile files;
- pre-v3 modular profiles;
- unexpected compatibility imports/consumers;
- deprecated `get_config(...)` calls;
- repository state that makes safe automated removal impossible.

## Retirement from the CLI

At debug level 3:

```text
Developer Console
→ Legacy compatibility lifecycle
```

Options include read-only audit, apply without commit, and apply + Git commit.

Destructive retirement requires the literal confirmation:

```text
RETIRE COMPATIBILITY
```

## Direct retirement commands

Apply and validate but leave changes uncommitted:

```bash
python tools/RetireLegacyCompatibility.py --apply
```

Apply, validate, and create the retirement commit:

```bash
python tools/RetireLegacyCompatibility.py --apply --commit
```

The generated commit author is `FPSensor <gkartyt@gmail.com>`.

## Self-removal behavior

After successful retirement, the tool is designed to remove:

- compatibility implementation files;
- compatibility-specific tests/docs blocks;
- its own `RetireLegacyCompatibility.py` launcher;
- its own Developer Console submenu/entry.

The already-running CLI checks whether the tool still exists and hides the option immediately after successful retirement.

## Safety model

The retirement script is intentionally conservative:

- requires a clean Git worktree;
- audits before changing files;
- validates the resulting repository;
- restores its own changes if validation fails;
- does not delete archived `_legacy_v1_backup` data.

Do not manually delete compatibility files first and then try to use the audit tool. Let the audit tell you whether removal is safe.
