# Data Processing Engine

This directory contains Inventory Toolkit's analytical modules. Responsibilities are split when that boundary improves testing or readability; files are not fragmented merely to enforce a fixed pattern.

## Structure

- **`inventory_cross_check/`** — physical vs. system stock reconciliation.
- **`stock_processing/`** — inventory valuation and dynamic summaries.
- **`yoy_reports/`** — Year-over-Year sales comparisons. Worksheet construction is isolated in `sheet_renderer.py` because formula/layout logic is substantial.
- **`shared/`** — common business rules such as family classification.

## Typical responsibilities

- **`data_processor.py`** — dataframe transformations and calculations.
- **`excel_renderer.py`** — workbook orchestration and/or OpenPyXL output concerns.
- **`sheet_renderer.py`** — used by YoY for per-sheet layout and formula generation.
- **`generator.py`** — orchestration and module-level workflow.
