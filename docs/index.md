# Inventory Toolkit Documentation

This directory is the technical and operational reference for the current Inventory Toolkit codebase.

The documentation is organized by **responsibility**, not by project history. If a document conflicts with the code, treat that as a documentation bug and fix both the text and the relevant test/contract where appropriate.

## Start here

### I want to install or run Inventory Toolkit

1. [Installation and launchers](installation.md)
2. [CLI reference](cli.md)
3. [Profiles and configuration](profiles.md)
4. [Troubleshooting](troubleshooting.md)

### I want to understand the codebase

1. [Architecture](architecture.md)
2. [Core infrastructure](core.md)
3. [Engine subsystems](engine.md)
4. [CLI layer](cli.md)
5. [Experimental GUI](gui.md)
6. [Developer notes](dev_notes.md)

### I want to prepare a release

1. [Testing and demo fixtures](testing_and_examples.md)
2. [Release process](release_process.md)
3. [Legacy compatibility lifecycle](legacy_compatibility.md), while that layer still exists

## Document map

| Document | Primary audience | Purpose |
| --- | --- | --- |
| [installation.md](installation.md) | users / maintainers | Python dependencies, Windows helpers, manual setup, launch commands |
| [architecture.md](architecture.md) | maintainers | layers, data flow, boundaries, business invariants |
| [cli.md](cli.md) | users / maintainers | main menu, module launchers, configuration, hidden debug console |
| [gui.md](gui.md) | testers / maintainers | experimental GUI scope, fallback UI, thread/error constraints |
| [core.md](core.md) | maintainers | configuration manager, schemas, logging, telemetry, sanitization, safe savers |
| [engine.md](engine.md) | maintainers / analysts | Cross Check, Stock Processing, YoY, shared family classification |
| [profiles.md](profiles.md) | users / maintainers | schema-v3 tree, ownership, Guided Setup, Configuration Hub |
| [testing_and_examples.md](testing_and_examples.md) | maintainers | pytest, IntegrityCheck, demo dataset, golden-master mechanics |
| [release_process.md](release_process.md) | maintainers | repeatable release gate and reference-update discipline |
| [legacy_compatibility.md](legacy_compatibility.md) | maintainers | migration diagnostics and guarded retirement |
| [troubleshooting.md](troubleshooting.md) | users / maintainers | common failures and recovery paths |
| [dev_notes.md](dev_notes.md) | contributors | engineering conventions and safe extension rules |

## Nearby README files

Some directories keep a short local README for context when browsing the repository directly:

- [`../cli/README.md`](../cli/README.md)
- [`../core/README.md`](../core/README.md)
- [`../engine/README.md`](../engine/README.md)
- [`../profiles/demo/README.md`](../profiles/demo/README.md)
- [`../examples/demo/README.md`](../examples/demo/README.md)
- [`../tests/release_reference/README.md`](../tests/release_reference/README.md)

Those local files intentionally stay shorter than the documents here.
