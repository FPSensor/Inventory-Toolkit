# Profile diagnostics

`core.profile_diagnostics.inspect_configuration(profile)` checks current configuration without initializing missing documents, reading workbooks or reviewing setup pages. It validates shared documents and enabled workflows; malformed disabled workflow files do not block another module.

The report contains stable issue codes, severity, source document and, when available, a module/setup-page destination. `healthy` means there are no errors. Competing identical category prefixes are warnings; different-length overlapping prefixes remain valid longest-prefix rules.

Checks include source-column collisions, required cleanup removals, stock location/group/summary references, physical-count column mappings, YoY comparison groups and Excel sheet names. The result does not certify an input file or replace ReleaseCheck. It never fixes mappings automatically.

## Headless commands

```bash
python -m inventory_toolkit doctor --profile demo
python -m inventory_toolkit doctor --profile demo --json
```

Exit status is 0 for no errors (warnings may remain), 1 for profile errors and 2 for command/dependency failures. Commands are available in CLI-only and GUI-only builds and do not import either frontend. Run module commands from the application directory, or make it available on Python's module path.
