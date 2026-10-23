# Operating and maintaining Inventory Toolkit independently

This guide covers normal operation, configuration recovery and the shortest useful route through the source. Keep it with your checkout; it does not require an online service.

## Start the application

From the repository root:

```bash
python -m inventory_toolkit
python -m inventory_toolkit --interface gui
python -m inventory_toolkit --interface cli
python -m inventory_toolkit --version
```

The platform launchers use the same application entry point. `build.prop` selects the default interface and the interfaces included in a distribution. `python -m cli` explicitly starts the console when it is included.

For a new Python environment:

```bash
python -m pip install -r requirements.txt
```

Tkinter is supplied by the platform/Python installation. CustomTkinter is optional. A display is required to open the GUI; headless profile maintenance does not need one.

## Configure only what you use

Create a profile and choose the required workflows. Configure each module with a sample from its own input file. The sample assists mapping; review suggestions before saving.

- Output product/category headings do not determine every input file's headers.
- Location names are stable identifiers; Stock maps them to quantity headers separately.
- Stock and Cross Check choose source categories, prefix rules or one default category.
- Use row-based stock when quantities are recorded per product/location row.
- Choose measured physical counts when a file contains product codes and explicit quantities; scanner mode means one headerless reading per unit.
- A variant identifies a dimension such as flavor or presentation. Quantity is the measured amount. Leave variants disabled when they do not apply.
- YoY revenue means the line total. If quantity is 3 and the unit price is 100, the line-revenue field must contain 300. Inventory Toolkit does not multiply a supplied line total again.
- Keep quantities and money comparable. Formatting `kg` does not convert units; currency/tax conversion is not automatic.

## Check a profile before investigating code

In the GUI, open **Overview → Check profile / restore configuration**. In the CLI, open **K → H → D**. Without either interface:

```bash
python -m inventory_toolkit doctor --profile demo
```

Replace `demo` with the profile folder ID. The check does not create defaults, inspect workbooks or review setup pages. It explains contradictions in enabled configurations and supplies a setup destination where possible. Disabled workflow files do not block another workflow's diagnostic.

| Code | Check |
| --- | --- |
| `PROFILE_METADATA` | The profile exists and metadata is an object with valid workflow selection. |
| `CONFIG_DOCUMENT` | The named JSON exists, parses and uses the supported schema. |
| `COLUMN_REQUIRED` | A required mapping has a nonempty header. |
| `COLUMN_COLLISION` | Distinct source roles have not accidentally selected the same column. |
| `DROP_REQUIRED` | Stock cleanup does not remove required processed columns. |
| `STOCK_LOCATION` / `PRICE_LOCATION` | A single-location input/list names a usable stock location. |
| `GROUP_LOCATIONS` / `SUMMARY_LOCATIONS` | Stock groups and summaries refer to available entities. |
| `SHEET_NAME` / `SHEET_COLLISION` | Excel sheet names are valid and unique, ignoring case. |
| `REPORT_GROUPS` / `REPORT_GROUP_MEMBERS` | YoY comparison groups have usable location members. |
| `PREFIX_CONFLICT` | An identical prefix appears in multiple categories; this is a warning. |

Different-length overlapping prefixes are valid: the longest matching prefix wins. Configuration checks cannot establish whether a future workbook contains the configured headers. Use **Inspect selected files** for that separate check.

## Return to a saved configuration

Setup saves a checkpoint before an accepted changed page, and workflow selection changes also checkpoint existing profiles. Only the last ten points are retained. For a separate backup, copy the profile folder elsewhere before extended work.

In the GUI, use the checks/recovery panel; restore requires an explicit confirmation. In the CLI, use **K → H → R** and select a list number.

Headless commands:

```bash
python -m inventory_toolkit history list --profile demo
python -m inventory_toolkit history create --profile demo --label "Before manual JSON edits"
python -m inventory_toolkit history restore --profile demo --checkpoint IDENTIFIER
```

Restore validates the saved documents first and creates a safety copy of the current state. It replaces configuration and review metadata, preserving original bytes. Workbooks, remembered paths and archived legacy data are outside restoration. Close other application instances before editing/restoring the same profile. See [profile_history.md](profile_history.md) for damaged/incomplete-state limitations.

## Follow an error to the right area

| Symptom | First place to inspect |
| --- | --- |
| Configured header missing | Module setup mapping and selected workbook headers. Explicit per-run fallback does not rewrite the profile. |
| Input file not found | Saved path, current machine and current working directory for relative paths. |
| Workbook cannot be saved | Excel/open-file lock and output-directory permissions. |
| Unexpected quantities | Source rows, quantity mappings, duplicate records, consolidation options and excluded products. |
| Unexpected category | Source-category mode or longest-prefix rules and configured default category. |
| Unexpected YoY amount | Line-revenue column, selected date range, report group membership and enabled metric blocks. |
| Development action unavailable | `build.prop` type and whether the optional `debug_tools` package is present. |

When sharing a problem, include the toolkit version, profile ID, module/options, exact error and a small anonymized input example. Review logs and sample data before sharing them; they may contain local paths or business identifiers.

## Verify changes before distributing them

A development checkout needs pytest in addition to the normal dependencies:

```bash
python -m pip install pytest
python -m pytest -q
python -m debug_tools release --release
```

ReleaseCheck generates all three demo outputs, compares them to approved golden masters and executes repository/integrity checks. Never regenerate expected workbooks solely to silence a failure. Inspect an intentional output change before approving references.

Real-widget tests require a display:

```bash
python -m pytest -q tests/test_gui_desktop.py
```

A headless run skips these checks. Linux display tests do not certify native Windows/macOS behavior.

## A practical source reading order

| Read | Purpose |
| --- | --- |
| `build.prop`, `inventory_toolkit/__main__.py` | Understand startup and interface capabilities. |
| `core/resources/new_profile_defaults.json`, one profile's `configs/` | See data-owned defaults and actual business choices. |
| `core/setup_catalog.py` | See friendly fields, help, conditional pages and their stored paths. |
| `core/setup_service.py` | Follow saving, review state, shared fingerprints and required settings. |
| `core/config_schemas.py`, `core/workflow_contracts.py` | Understand typed settings and effective input mappings. |
| A module's `engine/*/generator.py` | Follow the processing stages and report dispatch. |
| Its processor, pricing and renderer files | Inspect transformations, calculations and Excel layout separately. |
| `core/profile_diagnostics.py`, `core/profile_history.py` | Follow checks and configuration recovery. |
| `gui/app.py`, `cli/*_launcher.py` | See how interfaces gather options and dispatch the shared engine. |
| `tests/test_business_scenarios.py`, `examples/businesses/` | See complete neutral business examples and independently expected totals. |

Changes to processing should preserve report arithmetic unless the intended behavior is explicitly changing. Keep each focused change documented in `CHANGELOG.md`, with the relevant guide updated alongside it.
