# Legacy configuration compatibility

Inventory Toolkit currently carries a temporary compatibility layer for two historical contracts:

1. **Legacy storage** — pre-v2/v3 profile files and serialized Spanish keys.
2. **Legacy API projections** — short `ConfigurationManager.get_config(...)` names such as `familias`, `reports`, or `cross_check_settings`.

Current built-in modules do not depend on either contract. They exist only so older profiles and external callers can transition without changing business behavior.

## Debug diagnostics

Run the CLI with:

```bash
python cli.py -debug_level 2
```

or `-debug_level 3`. Compatibility warnings are hidden at the normal level and appear only in debug modes. Each distinct event is reported once per process.

A storage warning means the profile should be opened in **Configuration → Migrate/archive legacy config**. An API warning identifies a caller that still needs to move to the module-oriented English accessors.

## Retirement readiness

Audit the repository without changing anything:

```bash
python tools/RetireLegacyCompatibility.py
```

The audit refuses retirement while it finds active legacy files, pre-v3 modular profiles, unexpected legacy imports, or deprecated `get_config(...)` calls.

When the audit is clean:

```bash
python tools/RetireLegacyCompatibility.py --apply
```

removes the compatibility code and validates the resulting tree. To create the retirement commit immediately after successful validation:

```bash
python tools/RetireLegacyCompatibility.py --apply --commit
```

The commit author is `FPSensor <gkartyt@gmail.com>`. The script requires a clean Git worktree and restores its own changes if validation fails.
After a successful retirement the one-shot retirement tool deletes itself as part of the same commit; Git history remains the recovery path.

Archived files under `_legacy_v1_backup/` are historical data and are not deleted automatically.
