# Inventory Toolkit

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.4.0-orange)

Inventory Toolkit is a profile-driven Python application for retail inventory reconciliation, stock valuation, and Year-over-Year sales reporting from Excel workbooks.

It was built around real operational constraints: legacy `.xls` exports, inconsistent scanner output, variable-length article codes, multiple stores and regional groups, price lists from different sources, Excel files left open by users, and business rules that must change without forking the processing engine.

The project currently exposes a mature CLI, an experimental desktop GUI, a typed configuration system, forensic logging, migration support for older profiles, and a reproducible pre-release gate backed by golden-master workbooks.

> **Current release line:** `1.4.x`
> **Primary interface:** CLI
> **GUI status:** experimental / active testing
> **Configuration schema:** v3

---

# What Inventory Toolkit Does

Inventory Toolkit contains three production-oriented workflows:

| Workflow | Purpose | Main inputs | Output |
| --- | --- | --- | --- |
| **Inventory Cross Check** | Reconcile physical scanner counts against system stock and value the differences | system stock, physical count, cost list, sales list | discrepancy workbook |
| **Stock Processing** | Clean and consolidate multi-store stock, assign families, attach cost/sales prices, value inventory, and create summaries | raw stock, cost list, sales list | detail + summary workbook |
| **YoY Sales Reports** | Compare current and previous periods by family/store/group, with optional monthly segmentation and size breakdown | historical sales workbook | multi-sheet comparative report |

The same engines can be used from the CLI, the experimental GUI, or directly from Python.

---

# Key Design Principles

## Business rules live outside the engines

Profiles under `profiles/<name>/configs/` own store mappings, family prefixes, column mappings, exclusions, report groups, pricing fields, and output layout. The built-in engines consume typed configuration instead of hard-coding one company or dataset.

## Ambiguous scanner data is preserved, not guessed

`normalize_article()` does **not** assume fixed article-code length. It uses the system-stock article master as the source of truth, accepts exact matches, otherwise selects the **longest valid article prefix**, and preserves unresolved input as `REVISAR | <original value>` for human review.

Example:

```text
scanner value:      11111-261XXLH1
known article:      11111-261
size/color suffix:  XXL / H1
normalized result:  11111-261
```

If no known article matches, the scanner value is not discarded or silently truncated.

## Business vocabulary is separated from implementation vocabulary

Implementation identifiers are English. External workbook labels such as `Artículo`, `Familias`, `Costo`, `Venta`, `Talle`, and the `REVISAR |` marker remain part of the business contract and are centralized in `core/business_schema.py`.

## Releases are certified against approved output

The strict pre-release gate executes all three demo workflows and compares their generated workbooks against committed golden masters in `tests/release_reference/`. Comparison is semantic, not a raw `.xlsx` ZIP hash.

---

# Features

- Three independent Excel-processing engines: Cross Check, Stock Processing, and YoY Reports.
- Profile-based configuration with schema-v3 validation through Pydantic.
- Module-oriented Guided Setup with per-workflow sample-file detection.
- Interactive Configuration Hub for catalog/families, network, Stock Processing, Cross Check, and YoY settings.
- Shared longest-prefix family classifier backed by a trie implementation.
- Variable-length article normalization against the system master.
- Per-profile last-path persistence for frequently used files.
- Native file picker support from the CLI.
- Safe Excel saving with retry/copy behavior in interactive CLI mode and non-blocking errors for GUI callers.
- Runtime-selectable debug levels and a hidden level-3 Developer Console.
- Forensic session logging to `logs/session.log`.
- Pytest, IntegrityCheck, stress/diagnostic tooling, demo smoke tests, and semantic golden-master certification.
- Guarded legacy-configuration migration and a one-shot compatibility-retirement tool.
- Experimental Tkinter/CustomTkinter desktop GUI.
- Windows launcher/setup helpers plus Linux/macOS shell launcher.

---

# Installation

## Windows — assisted setup

1. Clone or extract the repository.
2. Run `Setup Environment.bat` once.
3. Run `Inventory Toolkit.bat` for normal CLI use.

`Setup Environment.bat` installs Python 3.11.9 when `python` is not available, upgrades `pip`, and installs `requirements.txt`.

## Manual setup — Windows, Linux, or macOS

```bash
python -m venv .venv
```

Activate the virtual environment, then:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python cli.py
```

Linux/macOS users can also run:

```bash
./Inventory\ Toolkit.sh
```

The CLI targets Python 3.10+. The current Windows bootstrap installs Python 3.11.9.

For platform-specific notes, GUI requirements, and troubleshooting, see [docs/installation.md](docs/installation.md).

---

# Quick Start

```text
1. Start Inventory Toolkit.
2. Select or create a profile.
3. Open Configuration if the profile is not ready.
4. Use Guided Setup or the module-specific Configuration Hub editors.
5. Choose Cross Check, Stock Processing, or YoY Reports.
6. Select the required Excel files.
7. Review the generated workbook and logs if needed.
```

The included `demo` profile and files under `examples/demo/` provide a complete reference workflow.

---

# CLI

The CLI is the primary supported interface.

Main menu:

```text
C  Inventory Cross Check
S  Stock Processing
R  YoY Sales Report
K  Configuration
P  Change Profile
E  Exit
```

### Hidden runtime debug selector

Type:

```text
debug
```

in the main menu. It is intentionally not displayed as a normal option.

Available levels:

- **Level 1 — Operator:** errors only.
- **Level 2 — Diagnostics:** operational milestones, timings, warnings, and compatibility notices.
- **Level 3 — Forensic:** detailed execution events plus the Developer Console.

The historical startup forms remain available for automation:

```bash
python cli.py -debug_level 3
python cli.py --debug-level 3
```

At level 3, the Developer Console can run pytest, quick verification, demo smoke workflows, full golden-master certification, reference regeneration, session-log inspection, and the guarded compatibility lifecycle while that layer still exists.

See [docs/cli.md](docs/cli.md).

---

# Experimental Desktop GUI

Launch from the repository root:

```bash
python -m gui.app
```

The GUI currently covers:

- profile selection and creation;
- Cross Check;
- Stock Processing;
- YoY Reports;
- graphical Configuration Hub.

It uses CustomTkinter when installed and falls back to Tkinter/ttk. The GUI remains **experimental** and is not yet considered a full replacement for the CLI. Engine code must therefore remain headless and must not assume that terminal input is available.

See [docs/gui.md](docs/gui.md).

---

# Profiles and Configuration

Current profiles use configuration schema v3:

```text
profiles/<profile>/
├── profile.json
└── configs/
    ├── general/
    │   ├── catalog.json
    │   ├── families.json
    │   └── network.json
    ├── stock_processing/
    │   └── settings.json
    ├── cross_check/
    │   └── settings.json
    └── yoy_reports/
        └── settings.json
```

Application-owned resources are CWD-independent. `profiles/`, built-in examples, logs, developer tools, and release references are resolved from the Inventory Toolkit application root even when the CLI is invoked from another directory. User-provided relative workbook paths intentionally keep normal caller-CWD semantics.

Configuration ownership is deliberate:

- `general/` contains cross-workflow catalog and network concepts;
- Stock Processing owns its cleaning, pricing, and output settings;
- Cross Check owns exclusions and price-list mappings;
- YoY owns historical input mapping, output options, and report groups.

Use the Configuration Hub or Guided Setup for normal editing. Direct JSON editing remains supported for maintainers and version-controlled deployments.

See [docs/profiles.md](docs/profiles.md).

---

# Testing and Release Certification

### Unit/integration tests

```bash
pytest -q
```

### Quick repository gate

```bash
python tools/ReleaseCheck.py
```

### Demo smoke test

```bash
python tools/ReleaseCheck.py --demo
```

### Strict pre-release certification

```bash
python tools/ReleaseCheck.py --release
```

The release gate executes the three demo workflows in isolated subprocesses, writes outputs only to temporary storage, compares them against approved golden masters, runs repository checks, and removes generated temporary workbooks afterward.

### Deliberately approve new reference output

```bash
python tools/ReleaseCheck.py --update-reference
```

Only update references after intentionally changing business behavior, demo fixtures, or approved report layout and reviewing the new outputs. Updating a golden master merely to make a failing test green defeats the certification system.

See [docs/testing_and_examples.md](docs/testing_and_examples.md) and [docs/release_process.md](docs/release_process.md).

---

# Logging and Diagnostics

Every CLI session writes `logs/session.log`.

At forensic level, Inventory Toolkit records structured context such as:

- active profile and configuration files;
- workbook paths, dimensions, and detected columns;
- number of family rules and normalization review cases;
- filters and row counts before/after transformation stages;
- merge/valuation/report-generation decisions;
- generated sheets and output sizes;
- stage timings;
- exceptions and tracebacks.

Raw datasets are intentionally not dumped wholesale into the log.

See [docs/core.md](docs/core.md).

---

# Project Structure

```text
Inventory-Toolkit/
├── cli.py                         # CLI entry point
├── cli/                           # interactive presentation layer
│   ├── menu.py
│   ├── debug_menu.py
│   ├── config_menu.py
│   ├── wizard.py
│   ├── profiles.py
│   └── *_launcher.py
├── core/                          # shared infrastructure
│   ├── business_schema.py
│   ├── config_schemas.py
│   ├── configuration_manager.py
│   ├── profile_config.py
│   ├── paths.py
│   ├── logger.py
│   ├── telemetry.py
│   ├── data_sanitizer.py
│   ├── system_utils.py
│   └── legacy_*                  # temporary compatibility boundary
├── engine/                        # business processing
│   ├── inventory_cross_check/
│   ├── stock_processing/
│   ├── yoy_reports/
│   └── shared/
├── gui/
│   └── app.py                     # experimental desktop UI
├── profiles/
│   └── demo/
├── examples/
│   └── demo/
├── tests/
│   ├── release_reference/         # committed golden-master outputs
│   └── test_*.py
├── tools/
│   ├── IntegrityCheck.py
│   ├── StressTests.py
│   ├── ReleaseCheck.py
│   ├── release_reference.py
│   └── RetireLegacyCompatibility.py
├── docs/
├── requirements.txt
├── pytest.ini
├── Inventory Toolkit.bat
├── Inventory Toolkit.sh
├── Setup Environment.bat
├── CHANGELOG.md
└── LICENSE
```

For architecture and module responsibilities, see [docs/architecture.md](docs/architecture.md).

---

# Documentation

Start at **[docs/index.md](docs/index.md)**.

| Document | Covers |
| --- | --- |
| [Installation](docs/installation.md) | dependencies, launchers, platform notes |
| [Architecture](docs/architecture.md) | layers, boundaries, design invariants |
| [CLI](docs/cli.md) | menus, launchers, debug levels, Developer Console |
| [GUI](docs/gui.md) | current experimental GUI scope and limitations |
| [Core](docs/core.md) | configuration, logging, sanitization, safe savers |
| [Engine](docs/engine.md) | all three processing pipelines and shared rules |
| [Profiles](docs/profiles.md) | schema-v3 configuration and Guided Setup |
| [Testing & Examples](docs/testing_and_examples.md) | pytest, demo fixture, golden masters |
| [Release Process](docs/release_process.md) | repeatable pre-release procedure |
| [Legacy Compatibility](docs/legacy_compatibility.md) | migration warnings and retirement lifecycle |
| [Troubleshooting](docs/troubleshooting.md) | common installation/runtime/test failures |
| [Developer Notes](docs/dev_notes.md) | extension rules and engineering conventions |

---

# Contributing and Safe Changes

Before changing business logic:

1. Identify the affected business invariant.
2. Add or update a focused pytest where possible.
3. Run the quick repository gate.
4. Run strict golden-master certification.
5. If expected output intentionally changed, inspect it manually before updating references.

Do not simplify variable-length article normalization into a fixed-length slice, silently discard unresolved scanner input, or update golden masters only because a release test failed.

---

# Roadmap

The roadmap is directional rather than a release-date promise. Business correctness takes priority over shipping a version number.

## v1.4.1 — Stabilization and documentation

Target: make the current 1.4 architecture boringly reliable before adding major surface area.

- Finish the documentation/reference overhaul and keep docs synchronized with CLI/config schema v3.
- Expand tests around Guided Setup, Configuration Hub persistence, profile validation, and migration boundaries.
- Exercise the golden-master release gate on Windows and Linux with the official legacy `.xls` fixture and `xlrd` installed.
- Harden packaging/release hygiene so distributed archives exclude caches, logs, Git internals, and operational leftovers.
- Resolve remaining low-risk CLI/GUI rough edges without changing business calculations.

## v1.5.0 — GUI beta and interface parity

Target: make the desktop GUI a credible beta instead of an experimental companion.

- Bring profile setup and configuration workflows closer to CLI parity.
- Finish GUI-safe error/retry handling so no engine path assumes terminal input.
- Add automated smoke coverage for the GUI's critical paths.
- Improve progress/status reporting for long-running workbook operations.
- Define the supported CustomTkinter/Tkinter experience and installation story.

## v1.6.0 — Distribution and legacy retirement

Target: reduce historical/deployment complexity after the migration window has proved clean.

- Retire the legacy configuration compatibility layer **only if** the retirement audit remains clean for active profiles and external consumers.
- Move toward standard Python packaging (`pyproject.toml`, stable entry points, reproducible release artifacts).
- Produce a clean portable release bundle with explicit version metadata.
- Document supported Python/platform combinations from tested release environments rather than assumptions.

## v1.7.0 — Profile portability and diagnostics

Target: make profiles easier to move, inspect, validate, and maintain across installations.

- Add explicit profile export/import or portable-profile tooling.
- Improve configuration diff/diagnostic output for schema and mapping changes.
- Consider profile-specific validation fixtures where one global demo no longer covers important deployments.
- Keep migration/version behavior explicit and testable as schema evolution continues.

## v2.0.0 — Stable application boundary

A 2.0 release should be earned, not used as a cosmetic version bump. Candidate criteria:

- stable, documented CLI and GUI responsibilities;
- no temporary legacy compatibility layer;
- standard installation/distribution path;
- mature profile lifecycle;
- release certification covering all supported business workflows;
- documented internal API boundaries so future frontends do not require engine rewrites.

# License

Inventory Toolkit is released under the [MIT License](LICENSE).
