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
