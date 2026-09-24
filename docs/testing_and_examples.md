# 🧪 Testing Suite & Demo Datasets

## Automated Tests (`/tests`)
We use `pytest` to guarantee mathematical and structural integrity. 
* `test_inventory_cross_check.py`: Validates sorting algorithms for prefix priority and difference calculations (handling negative system stocks correctly).
* `test_stock_processing.py`: Validates margin formulas and fallback zero-handling.

## Demo Dataset (`/examples/demo`)
Sanitized, structure-preserving mock spreadsheets designed to let users test all three core modules out of the box without real corporate data exposure.

## Reproducible release gate

Run the lightweight verification used before packaging changes:

```bash
python tools/ReleaseCheck.py
```

It compiles the source tree, runs pytest, executes `IntegrityCheck.py`, audits legacy-compatibility retirement readiness while that layer still exists, and validates every checked-in profile through the typed configuration API.

For an end-to-end demo smoke test of Cross Check, Stock Processing, and YoY Reports:

```bash
python tools/ReleaseCheck.py --demo
```

The demo mode writes only to a temporary directory. The legacy `.xls` Cross Check fixture requires the `xlrd` dependency from `requirements.txt`; `--cross-system PATH` can point to an equivalent `.xlsx` fixture during development.

## Golden-master pre-release certification

The strict release gate executes the complete repository checks plus all three demo workflows and compares their generated workbooks against approved references in `tests/release_reference/`:

```bash
python tools/ReleaseCheck.py --release
```

The comparison is semantic rather than a raw XLSX-file hash. It covers workbook/sheet structure, values and formulas, styles, merges, filters, frozen panes, dimensions, and other meaningful worksheet XML while ignoring ZIP-container timestamps. On a mismatch, the fast semantic digest falls back to human-readable workbook diagnostics including worksheet/cell coordinates and expected/actual values.

The reference manifest fingerprints the complete demo fixture: all demo inputs, `profile.json`, and every JSON configuration file in the demo profile. If those inputs change, certification stops and explains that the golden masters are stale instead of silently blessing a new result. Generated candidate files live in a temporary directory and are removed automatically.

### Deliberately updating approved references

When a business-rule change, demo dataset change, new database/store mapping, or approved output-layout change intentionally changes the expected result, regenerate the references only after reviewing that change:

```bash
python tools/ReleaseCheck.py --update-reference
```

This is intentionally guarded by an `UPDATE REFERENCES` confirmation. All three candidate workbooks must generate successfully and the repository gate must pass before any committed reference is replaced. The installation is rollback-protected so a partial copy failure cannot leave a mixed reference set. Review the resulting XLSX/manifest Git diff before committing it.

Updating references merely because `--release` failed defeats the protection provided by golden-master testing.

### Debug-level 3 CLI

When Inventory Toolkit is started with debug level 3, the main menu exposes **Developer / Release Tools**. It provides the quick gate, demo smoke test, strict golden-master certification, and the explicitly confirmed reference-update operation without requiring the user to remember the standalone commands.
